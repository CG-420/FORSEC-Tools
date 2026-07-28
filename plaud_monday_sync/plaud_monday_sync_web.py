#!/usr/bin/env python3
"""
Local web UI for plaud_monday_sync.py.

Runs a small local server (stdlib only, no dependencies) that serves a
single browser page for pasting/dropping Plaud summaries, seeing the
draft, resolving unrouted items with dropdowns instead of terminal
prompts, and pushing to monday.com - all without a terminal once it's
running. All the parsing/routing/column-building logic is imported from
plaud_monday_sync.py, not reimplemented - this is just a thin web-facing
layer over the same code the CLI uses.

monday.com's API blocks direct browser calls (CORS), which is why this
needs a local server at all rather than being a plain static HTML file:
the browser talks to this server (same-origin, no CORS issue), and this
server talks to monday.com itself (server-to-server, not subject to
browser CORS).

Usage:
    export MONDAY_API_TOKEN="your monday.com API v2 token"
    python3 plaud_monday_sync_web.py
    # opens http://127.0.0.1:8765 in your browser automatically
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import threading
import webbrowser
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import plaud_monday_sync as pms

WEB_DIR = Path(__file__).resolve().parent / "web"
INDEX_HTML_PATH = WEB_DIR / "index.html"
ASSETS_DIR = WEB_DIR / "assets"

# Static artwork (logos, topographic background, treeline). These live as
# separate files rather than inline data URIs because the contour map is
# ~160KB of real path data - far too much to bury in the HTML.
ASSET_CONTENT_TYPES = {".svg": "image/svg+xml", ".png": "image/png"}

# Cached monday.com context (contractors/users), fetched once per server
# process rather than on every request - refreshed via /api/refresh-context.
_context_cache = {"contractors": [], "users": [], "loaded": False}


def _get_client() -> pms.MondayClient:
    return pms.MondayClient(os.environ.get("MONDAY_API_TOKEN"))


def _ensure_context(client: pms.MondayClient, force: bool = False):
    if not client.available:
        return [], []
    if force or not _context_cache["loaded"]:
        _context_cache["contractors"] = client.fetch_contractors()
        _context_cache["users"] = client.fetch_users()
        _context_cache["loaded"] = True
    return _context_cache["contractors"], _context_cache["users"]


# --------------------------------------------------------------------------
# Serialization: MeetingSummary/ActionItem -> plain JSON-able dicts
# --------------------------------------------------------------------------

def serialize_action_item(item: pms.ActionItem) -> dict:
    return {
        "task": item.task,
        "ownerRaw": item.owner_raw,
        "ownerUserId": item.owner_user_id,
        "ownerUserName": item.owner_user_name,
        "ownerWarning": item.owner_warning,
        "dueRaw": item.due_raw,
        "dueIso": item.due_iso,
        "dueWarning": item.due_warning,
        "route": item.route,
        "routeLabel": pms.BOARD_LABELS.get(item.route, item.route),
        "routeReason": item.route_reason,
        "safetySubmissionType": item.safety_submission_type,
        "ownerKey": item.owner_user_id or f"raw:{(item.owner_raw or '').strip().lower()}",
    }


def serialize_summary(summary: pms.MeetingSummary) -> dict:
    return {
        "source": summary.source,
        "title": summary.title,
        "meetingDateIso": summary.meeting_date_iso,
        "meetingDateWarning": summary.meeting_date_warning,
        "recordedByRaw": summary.recorded_by_raw,
        "recordedByUserName": summary.recorded_by_user_name,
        "recordedByWarning": summary.recorded_by_warning,
        "targetBoard": summary.target_board,
        "targetBoardLabel": pms.BOARD_LABELS.get(summary.target_board, summary.target_board),
        "contractorName": summary.contractor_name,
        "contractorId": summary.contractor_id,
        "otherContractorMentions": summary.other_contractor_mentions,
        "activityType": summary.activity_type,
        "activityTypeInferred": summary.activity_type_inferred,
        "outcome": summary.outcome,
        "outcomeInferred": summary.outcome_inferred,
        "adoptionSignal": summary.adoption_signal,
        "adoptionSignalInferred": summary.adoption_signal_inferred,
        "implementationStage": summary.implementation_stage,
        "implementationStageInferred": summary.implementation_stage_inferred,
        "actionItems": [serialize_action_item(i) for i in summary.action_items],
    }


# --------------------------------------------------------------------------
# Request handling
# --------------------------------------------------------------------------

def _build_summaries(body: dict):
    today_str = body.get("today")
    today = date.fromisoformat(today_str) if today_str else date.today()
    client = _get_client()
    contractors, users = _ensure_context(client)
    learned_routes = pms.load_learned_routes()
    summaries = [
        pms.build_summary(src["name"], src["text"], contractors, users, today, learned_routes)
        for src in body.get("sources", [])
        if src.get("text", "").strip()
    ]
    return summaries, client, learned_routes


def handle_draft(body: dict) -> dict:
    summaries, client, _ = _build_summaries(body)
    return {
        "ok": True,
        "tokenConfigured": client.available,
        "routeChoices": [{"key": k, "label": v} for k, v in pms.INTERACTIVE_ROUTE_CHOICES],
        "summaries": [serialize_summary(s) for s in summaries],
    }


def _apply_resolutions(summaries: list, resolutions: dict, learned_routes: dict) -> list:
    remembered = []
    for summary in summaries:
        if summary.target_board == "ci_activity_log":
            continue
        for item in summary.action_items:
            if item.route != "unrouted":
                continue
            key = item.owner_user_id or f"raw:{(item.owner_raw or '').strip().lower()}"
            res = resolutions.get(key)
            if not res or not res.get("route"):
                continue
            item.route = res["route"]
            item.route_reason = "placed via web UI"
            if res.get("remember") and item.owner_user_id:
                learned_routes[item.owner_user_id] = res["route"]
                remembered.append({"owner": item.owner_user_name, "route": pms.BOARD_LABELS[res["route"]]})
    if remembered:
        pms.save_learned_routes(learned_routes)
    return remembered


def handle_push(body: dict) -> dict:
    client = _get_client()
    if not client.available:
        return {"ok": False, "error": "MONDAY_API_TOKEN is not set on the machine running this server."}

    summaries, client, learned_routes = _build_summaries(body)
    if not summaries:
        return {"ok": False, "error": "No summaries with action items to push."}

    remembered = _apply_resolutions(summaries, body.get("resolutions", {}), learned_routes)
    logged_by_user_id = body.get("loggedByUserId") or pms.DEFAULT_LOGGED_BY_USER_ID

    log_lines = []
    pms.push(client, summaries, logged_by_user_id, report=log_lines.append)

    return {"ok": True, "log": log_lines, "remembered": remembered}


def handle_refresh_context(body: dict) -> dict:
    client = _get_client()
    contractors, users = _ensure_context(client, force=True)
    return {"ok": True, "tokenConfigured": client.available, "contractors": len(contractors), "users": len(users)}


ROUTES = {
    "/api/draft": handle_draft,
    "/api/push": handle_push,
    "/api/refresh-context": handle_refresh_context,
}


class Handler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, obj: dict, status: int = 200) -> None:
        payload = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_asset(self, name: str) -> None:
        # Resolve inside ASSETS_DIR and verify containment, so a crafted
        # path like /assets/../../secrets can't escape the artwork folder.
        candidate = (ASSETS_DIR / name).resolve()
        try:
            candidate.relative_to(ASSETS_DIR.resolve())
        except ValueError:
            self.send_error(404)
            return
        content_type = ASSET_CONTENT_TYPES.get(candidate.suffix.lower())
        if content_type is None or not candidate.is_file():
            self.send_error(404)
            return
        body = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=3600")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            body = INDEX_HTML_PATH.read_text(encoding="utf-8").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path.startswith("/assets/"):
            self._send_asset(path[len("/assets/"):])
        elif path == "/api/status":
            client = _get_client()
            self._send_json({"tokenConfigured": client.available})
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        handler = ROUTES.get(path)
        if handler is None:
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8")) if raw.strip() else {}
        except json.JSONDecodeError:
            self._send_json({"ok": False, "error": "invalid JSON body"}, status=400)
            return

        try:
            self._send_json(handler(body))
        except Exception as e:  # noqa: BLE001 - surface any failure to the browser, don't crash the server
            self._send_json({"ok": False, "error": str(e)}, status=500)

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - quiet the default request logging
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open a browser tab on startup")
    args = parser.parse_args()

    if not os.environ.get("MONDAY_API_TOKEN"):
        print(
            "Warning: MONDAY_API_TOKEN is not set. The page will load and draft summaries, "
            "but pushing to monday.com will fail until you set it and restart this server."
        )

    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Plaud -> monday.com web UI running at {url}")
    print("Press Ctrl-C to stop.")

    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
        server.shutdown()


if __name__ == "__main__":
    main()
