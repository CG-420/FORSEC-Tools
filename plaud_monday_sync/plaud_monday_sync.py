#!/usr/bin/env python3
"""
Plaud AI meeting summary -> monday.com sync tool.

Parses the "Action Items" section out of a Plaud AI meeting summary
(pipe-delimited "Task: ... | Owner: ... | Due: ..." rows under a
markdown-style heading), drafts what would be created on the FORSEC
monday.com boards, and pushes to monday.com via the GraphQL API only
after you review the draft and type CONFIRM.

Routing:
    - If the summary text mentions a contractor from the Contractor
      Directory board, a parent "Interaction" item is drafted on
      CI Activity Log, with each action item as a subitem.
    - Otherwise a parent item is drafted on Task Tracking, with each
      action item as a subitem.

Usage:
    python3 plaud_monday_sync.py --file meeting.md
    python3 plaud_monday_sync.py --dir ./summaries
    python3 plaud_monday_sync.py                     # paste, then Ctrl-D
    python3 plaud_monday_sync.py --file meeting.md --no-push

Environment:
    MONDAY_API_TOKEN   monday.com API v2 token. Required to fetch live
                        contractor/user lists for matching and to push.
                        Without it, the script still parses and drafts,
                        with matching skipped.

See README.md in this directory for the board/column mapping this
script assumes, and how to update it if the boards change.
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

# --------------------------------------------------------------------------
# Board / column configuration
# --------------------------------------------------------------------------
# Pulled live from the FORSEC monday.com account on 2026-07-27.
# Edit here if boards or columns change.

MONDAY_API_URL = "https://api.monday.com/v2"
MONDAY_API_VERSION = "2024-10"

TASK_TRACKING_BOARD_ID = 18403136567
TASK_TRACKING_GROUPS = {
    "last_week": "topics",
    "this_week": "group_mm19m9vy",
    "next_week": "group_mm19krcm",
}
TASK_TRACKING_COLUMNS = {
    "status": "color_mm19qtk1",  # Not Started / In Progress / Blocked / Completed
    "deadline": "date_mm195pwe",
    "notes": "text_mm19s19h",
}

CI_ACTIVITY_LOG_BOARD_ID = 18403818341
CI_ACTIVITY_LOG_GROUPS = {
    "in_progress": "group_mm1dg7z6",
    "completed": "group_mm1dqa4p",
    "to_log": "topics",
}
CI_ACTIVITY_LOG_COLUMNS = {
    "contractor": "board_relation_mm1d2wmt",
    "interaction_date": "date_mm1dg0vn",
    "implementation_stage": "color_mm1dp35v",  # Not Started / In Progress / Implemented / Blocked
    "adoption_signal": "color_mm1dvgf",  # No Signal / Interest / Testing / Using
    "activity_type": "color_mm1dv4yw",  # Site Visit / Phone Call / Training / Issue / Follow-up / Email / Meeting
    "short_notes": "text_mm1d5pg5",
    "outcome": "color_mm1dapcq",  # Neutral / Positive / Concern
    "ai_summary": "long_text_mm33fwe7",
    "logged_by": "multiple_person_mm33v2c9",
    "entry_source": "color_mm33cqe6",  # AI Pipeline / Manual
}

# Both boards' subitem boards share this schema (Name / Owner / Status / Date).
SUBITEM_COLUMNS = {
    "owner": "person",
    "status": "status",  # Working on it / Done / Stuck
    "date": "date0",
}

CONTRACTOR_DIRECTORY_BOARD_ID = 18403133772

DEFAULT_LOGGED_BY_USER_ID = "82580586"  # Chris Garcelon

# --------------------------------------------------------------------------
# Keyword heuristics for CI Activity Log field inference
# --------------------------------------------------------------------------

ACTIVITY_TYPE_KEYWORDS = {
    "Site Visit": ["site visit", "on-site", "walked the site", "visited the yard", "visited site"],
    "Training": ["training session", "workshop", "trained the crew", "training day"],
    "Issue": ["complaint", "issue raised", "problem reported", "reported an issue"],
    "Follow-up": ["follow-up call", "follow up call", "checking in", "followed up"],
    "Email": ["via email", "emailed", "email exchange"],
    "Phone Call": ["phone call", "called them", "on the phone", "conference call"],
    "Meeting": ["met with", "in-person meeting", "sat down with"],
}
OUTCOME_KEYWORDS = {
    "Positive": ["went well", "positive feedback", "great progress", "happy with", "excited about"],
    "Concern": ["concerned", "pushback", "frustrated", "declined", "not happy", "raised concerns"],
}
ADOPTION_SIGNAL_KEYWORDS = {
    "Using": ["actively using", "fully adopted", "now using", "using the new"],
    "Testing": ["testing", "trialing", "piloting", "trial run"],
    "Interest": ["interested in", "would like to try", "keen to try", "open to trying"],
    "No Signal": ["not interested", "no interest", "declined to adopt", "not ready"],
}
IMPLEMENTATION_STAGE_KEYWORDS = {
    "Implemented": ["fully implemented", "rolled out", "now in place", "completed the rollout"],
    "Blocked": ["blocked", "stuck", "on hold", "put on hold"],
    "In Progress": ["in progress", "currently implementing", "working on it", "underway"],
    "Not Started": ["not started", "have not begun", "haven't started", "yet to begin"],
}

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclasses.dataclass
class ActionItem:
    task: str
    owner_raw: str
    due_raw: str
    due_iso: Optional[str] = None
    due_warning: Optional[str] = None
    owner_user_id: Optional[str] = None
    owner_user_name: Optional[str] = None
    owner_warning: Optional[str] = None


@dataclasses.dataclass
class MeetingSummary:
    source: str
    title: str
    meeting_date_iso: str
    meeting_date_warning: Optional[str]
    raw_text: str
    action_items: list = dataclasses.field(default_factory=list)
    target_board: str = "task_tracking"  # or "ci_activity_log"
    contractor_id: Optional[str] = None
    contractor_name: Optional[str] = None
    other_contractor_mentions: list = dataclasses.field(default_factory=list)
    activity_type: Optional[str] = None
    activity_type_inferred: bool = False
    outcome: Optional[str] = None
    outcome_inferred: bool = False
    adoption_signal: Optional[str] = None
    adoption_signal_inferred: bool = False
    implementation_stage: Optional[str] = None
    implementation_stage_inferred: bool = False


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

HEADING_RE = re.compile(r"^(#{1,6})\s*(.+?)\s*$", re.MULTILINE)
ACTION_ITEMS_HEADING_RE = re.compile(r"^(#{1,6})\s*action\s*items?\b.*$", re.IGNORECASE | re.MULTILINE)
META_DATE_RE = re.compile(r"^(?:meeting\s*date|date)\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
FIELD_RE = re.compile(
    r"(Task|Owner|Due)\s*:\s*(.*?)\s*(?=\s*\|\s*(?:Task|Owner|Due)\s*:|$)",
    re.IGNORECASE,
)
BULLET_PREFIX_RE = re.compile(r"^\s*(?:[-*]\s*)?(?:\[[ xX]\]\s*)?")


def extract_title(text: str) -> str:
    m = HEADING_RE.search(text)
    if m:
        return m.group(2).strip()
    stripped = text.strip()
    if not stripped:
        return "Untitled Meeting"
    return stripped.splitlines()[0].strip()[:120]


def extract_action_items_section(text: str) -> str:
    m = ACTION_ITEMS_HEADING_RE.search(text)
    if not m:
        return ""
    heading_level = len(m.group(1))
    rest = text[m.end():]
    next_heading = re.search(rf"^#{{1,{heading_level}}}\s+\S", rest, re.MULTILINE)
    return rest[: next_heading.start()] if next_heading else rest


def parse_action_items(section_text: str) -> list:
    items = []
    for line in section_text.splitlines():
        line = BULLET_PREFIX_RE.sub("", line).strip()
        if not line or ":" not in line or "task" not in line.lower():
            continue
        fields = {k.lower(): v.strip() for k, v in FIELD_RE.findall(line)}
        if not fields.get("task"):
            continue
        items.append(ActionItem(
            task=fields.get("task", ""),
            owner_raw=fields.get("owner", ""),
            due_raw=fields.get("due", ""),
        ))
    return items


def _next_weekday(reference: date, weekday_name: str, inclusive: bool, force_next_week: bool = False) -> date:
    target = WEEKDAYS.index(weekday_name)
    days_ahead = target - reference.weekday()
    if days_ahead < 0 or (days_ahead == 0 and not inclusive):
        days_ahead += 7
    if force_next_week and days_ahead <= 7:
        days_ahead += 7
    return reference + timedelta(days=days_ahead)


def parse_date_loose(raw: str, reference: date):
    """Best-effort parse of a free-text date into ISO (YYYY-MM-DD).

    Returns (iso_date_or_None, warning_or_None). Never guesses silently
    on genuinely ambiguous input - it leaves the date unset and returns
    a warning instead, since a wrong deadline pushed to monday.com is
    worse than a blank one.
    """
    if not raw or not raw.strip():
        return None, "no due date given"
    text = raw.strip()
    low = text.lower()

    if low in ("asap", "immediately", "today"):
        return reference.isoformat(), None
    if low == "tomorrow":
        return (reference + timedelta(days=1)).isoformat(), None
    if low in ("eod", "end of day"):
        return reference.isoformat(), None
    if low in ("eow", "end of week", "this friday"):
        return _next_weekday(reference, "friday", inclusive=True).isoformat(), None
    if low in ("tbd", "tba", "n/a", "none", "-"):
        return None, None
    if low in WEEKDAYS:
        return _next_weekday(reference, low, inclusive=False).isoformat(), None

    m = re.match(r"next\s+(\w+)", low)
    if m and m.group(1) in WEEKDAYS:
        return _next_weekday(reference, m.group(1), inclusive=False, force_next_week=True).isoformat(), None
    if low == "next week":
        return None, f"vague due date {raw!r} - needs manual entry"

    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat(), None
        except ValueError:
            continue

    for fmt in ("%B %d", "%b %d", "%m/%d"):
        try:
            parsed = datetime.strptime(text, fmt).date()
            candidate = parsed.replace(year=reference.year)
            if candidate < reference:
                candidate = candidate.replace(year=reference.year + 1)
            return candidate.isoformat(), None
        except ValueError:
            continue

    return None, f"could not parse due date {raw!r} - needs manual entry"


def extract_meeting_date(text: str, fallback: date):
    head = "\n".join(text.splitlines()[:20])
    m = META_DATE_RE.search(head)
    if not m:
        return fallback.isoformat(), None
    iso, warning = parse_date_loose(m.group(1).strip(), fallback)
    if iso:
        return iso, None
    return fallback.isoformat(), f"meeting date {m.group(1).strip()!r} unparsed, defaulted to {fallback.isoformat()}"


# --------------------------------------------------------------------------
# Matching: contractors and owners against live monday.com data
# --------------------------------------------------------------------------

def match_contractor(text: str, contractors: list):
    text_low = text.lower()
    matches = []
    for cid, name in contractors:
        if not name:
            continue
        if re.search(r"\b" + re.escape(name.lower()) + r"\b", text_low):
            matches.append((cid, name))
    if not matches:
        return None, None, []
    primary_id, primary_name = matches[0]
    return primary_id, primary_name, [n for _, n in matches[1:]]


def match_owner(owner_raw: str, users: list):
    """Returns (user_id, user_name, warning)."""
    if not owner_raw or not owner_raw.strip():
        return None, None, "no owner given"
    owner_low = owner_raw.strip().lower()

    for uid, name in users:
        if name.lower() == owner_low:
            return uid, name, None

    candidates = [
        (uid, name) for uid, name in users
        if owner_low == name.lower().split()[0] or owner_low in name.lower().split()
    ]
    if len(candidates) == 1:
        return candidates[0][0], candidates[0][1], None
    if len(candidates) > 1:
        names = ", ".join(n for _, n in candidates)
        return None, None, f"ambiguous owner {owner_raw!r} matches multiple users: {names}"

    names_only = [name for _, name in users]
    close = difflib.get_close_matches(owner_raw, names_only, n=1, cutoff=0.6)
    if close:
        uid = next(uid for uid, name in users if name == close[0])
        return uid, close[0], f"fuzzy-matched {owner_raw!r} -> {close[0]!r}, verify before pushing"

    return None, None, f"no monday.com user matches owner {owner_raw!r}"


def infer_field(text: str, keyword_map: dict):
    text_low = text.lower()
    scores = {label: sum(text_low.count(kw) for kw in kws) for label, kws in keyword_map.items()}
    best_label, best_score = max(scores.items(), key=lambda kv: kv[1])
    if best_score == 0:
        return None, False
    tied = [l for l, s in scores.items() if s == best_score]
    if len(tied) > 1:
        return None, False
    return best_label, True


# --------------------------------------------------------------------------
# Build a MeetingSummary from raw text
# --------------------------------------------------------------------------

def build_summary(source: str, text: str, contractors: list, users: list, today: date) -> MeetingSummary:
    title = extract_title(text)
    meeting_date_iso, date_warning = extract_meeting_date(text, today)
    ref_date = datetime.strptime(meeting_date_iso, "%Y-%m-%d").date()

    section = extract_action_items_section(text)
    action_items = parse_action_items(section)
    for item in action_items:
        item.due_iso, item.due_warning = parse_date_loose(item.due_raw, ref_date)
        item.owner_user_id, item.owner_user_name, item.owner_warning = match_owner(item.owner_raw, users)

    summary = MeetingSummary(
        source=source,
        title=title,
        meeting_date_iso=meeting_date_iso,
        meeting_date_warning=date_warning,
        raw_text=text,
        action_items=action_items,
    )

    contractor_id, contractor_name, others = match_contractor(text, contractors)
    if contractor_id:
        summary.target_board = "ci_activity_log"
        summary.contractor_id = contractor_id
        summary.contractor_name = contractor_name
        summary.other_contractor_mentions = others
        summary.activity_type, summary.activity_type_inferred = infer_field(text, ACTIVITY_TYPE_KEYWORDS)
        summary.outcome, summary.outcome_inferred = infer_field(text, OUTCOME_KEYWORDS)
        summary.adoption_signal, summary.adoption_signal_inferred = infer_field(text, ADOPTION_SIGNAL_KEYWORDS)
        summary.implementation_stage, summary.implementation_stage_inferred = infer_field(text, IMPLEMENTATION_STAGE_KEYWORDS)
    else:
        summary.target_board = "task_tracking"

    return summary


# --------------------------------------------------------------------------
# monday.com API client
# --------------------------------------------------------------------------

class MondayClient:
    def __init__(self, token: Optional[str]):
        self.token = token

    @property
    def available(self) -> bool:
        return bool(self.token)

    def _request(self, query: str, variables: dict) -> dict:
        if not self.token:
            raise RuntimeError("MONDAY_API_TOKEN is not set")
        payload = json.dumps({"query": query, "variables": variables}).encode()
        req = urllib.request.Request(
            MONDAY_API_URL,
            data=payload,
            headers={
                "Authorization": self.token,
                "Content-Type": "application/json",
                "API-Version": MONDAY_API_VERSION,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"monday.com API HTTP {e.code}: {e.read().decode(errors='replace')}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"could not reach monday.com API: {e}") from e
        if "errors" in body:
            raise RuntimeError(f"monday.com API error: {body['errors']}")
        return body["data"]

    def fetch_contractors(self) -> list:
        query = """
        query ($boardId: [ID!]) {
          boards(ids: $boardId) {
            items_page(limit: 200) { items { id name } }
          }
        }
        """
        data = self._request(query, {"boardId": [CONTRACTOR_DIRECTORY_BOARD_ID]})
        items = data["boards"][0]["items_page"]["items"]
        return [(i["id"], i["name"]) for i in items]

    def fetch_users(self) -> list:
        data = self._request("query { users { id name } }", {})
        return [(u["id"], u["name"]) for u in data["users"]]

    def create_item(self, board_id: int, group_id: str, name: str, column_values: dict) -> str:
        query = """
        mutation ($boardId: ID!, $groupId: String, $itemName: String!, $columnValues: JSON) {
          create_item(board_id: $boardId, group_id: $groupId, item_name: $itemName, column_values: $columnValues) { id }
        }
        """
        variables = {
            "boardId": board_id,
            "groupId": group_id,
            "itemName": name,
            "columnValues": json.dumps(column_values),
        }
        data = self._request(query, variables)
        return data["create_item"]["id"]

    def create_subitem(self, parent_item_id: str, name: str, column_values: dict) -> str:
        query = """
        mutation ($parentItemId: ID!, $itemName: String!, $columnValues: JSON) {
          create_subitem(parent_item_id: $parentItemId, item_name: $itemName, column_values: $columnValues) { id }
        }
        """
        variables = {
            "parentItemId": parent_item_id,
            "itemName": name,
            "columnValues": json.dumps(column_values),
        }
        data = self._request(query, variables)
        return data["create_subitem"]["id"]


# --------------------------------------------------------------------------
# column_values builders
# --------------------------------------------------------------------------

def status_value(label: str) -> dict:
    return {"label": label}


def date_value(iso: str) -> dict:
    return {"date": iso}


def people_value(user_id: str) -> dict:
    return {"personsAndTeams": [{"id": int(user_id), "kind": "person"}]}


def board_relation_value(item_id: str) -> dict:
    return {"item_ids": [int(item_id)]}


def long_text_value(text: str) -> dict:
    return {"text": text}


def build_task_tracking_parent_columns(summary: MeetingSummary) -> dict:
    cols = {TASK_TRACKING_COLUMNS["status"]: status_value("Not Started")}
    due_dates = [i.due_iso for i in summary.action_items if i.due_iso]
    if due_dates:
        cols[TASK_TRACKING_COLUMNS["deadline"]] = date_value(min(due_dates))
    notes_lines = [f"Source: {summary.source}", f"Meeting date: {summary.meeting_date_iso}"]
    if summary.meeting_date_warning:
        notes_lines.append(f"Note: {summary.meeting_date_warning}")
    cols[TASK_TRACKING_COLUMNS["notes"]] = "\n".join(notes_lines)
    return cols


def build_ci_activity_log_parent_columns(summary: MeetingSummary, logged_by_user_id: Optional[str]) -> dict:
    cols = {}
    if summary.contractor_id:
        cols[CI_ACTIVITY_LOG_COLUMNS["contractor"]] = board_relation_value(summary.contractor_id)
    cols[CI_ACTIVITY_LOG_COLUMNS["interaction_date"]] = date_value(summary.meeting_date_iso)
    if summary.activity_type:
        cols[CI_ACTIVITY_LOG_COLUMNS["activity_type"]] = status_value(summary.activity_type)
    if summary.outcome:
        cols[CI_ACTIVITY_LOG_COLUMNS["outcome"]] = status_value(summary.outcome)
    if summary.adoption_signal:
        cols[CI_ACTIVITY_LOG_COLUMNS["adoption_signal"]] = status_value(summary.adoption_signal)
    if summary.implementation_stage:
        cols[CI_ACTIVITY_LOG_COLUMNS["implementation_stage"]] = status_value(summary.implementation_stage)
    cols[CI_ACTIVITY_LOG_COLUMNS["short_notes"]] = summary.title
    cols[CI_ACTIVITY_LOG_COLUMNS["ai_summary"]] = long_text_value(summary.raw_text)
    cols[CI_ACTIVITY_LOG_COLUMNS["entry_source"]] = status_value("AI Pipeline")
    if logged_by_user_id:
        cols[CI_ACTIVITY_LOG_COLUMNS["logged_by"]] = people_value(logged_by_user_id)
    return cols


def build_subitem_columns(item: ActionItem) -> dict:
    cols = {SUBITEM_COLUMNS["status"]: status_value("Working on it")}
    if item.due_iso:
        cols[SUBITEM_COLUMNS["date"]] = date_value(item.due_iso)
    if item.owner_user_id:
        cols[SUBITEM_COLUMNS["owner"]] = people_value(item.owner_user_id)
    return cols


# --------------------------------------------------------------------------
# Draft report
# --------------------------------------------------------------------------

BOARD_LABELS = {"task_tracking": "Task Tracking", "ci_activity_log": "CI Activity Log"}


def print_draft(summaries: list) -> None:
    print("=" * 78)
    print("DRAFT - nothing has been created on monday.com yet")
    print("=" * 78)

    for summary in summaries:
        board_label = BOARD_LABELS[summary.target_board]
        print(f"\n--- {summary.source} " + "-" * max(0, 60 - len(summary.source)))
        print(f"Board:          {board_label}")
        print(f"Parent item:    {summary.title}")
        print(f"Meeting date:   {summary.meeting_date_iso}", end="")
        if summary.meeting_date_warning:
            print(f"  ⚠ {summary.meeting_date_warning}")
        else:
            print()

        if summary.target_board == "ci_activity_log":
            print(f"Contractor:     {summary.contractor_name} (matched item id {summary.contractor_id})")
            if summary.other_contractor_mentions:
                print(f"  also mentions: {', '.join(summary.other_contractor_mentions)}")
            print(f"Activity Type:  {_fmt_inferred(summary.activity_type, summary.activity_type_inferred)}")
            print(f"Outcome:        {_fmt_inferred(summary.outcome, summary.outcome_inferred)}")
            print(f"Adoption Signal:{_fmt_inferred(summary.adoption_signal, summary.adoption_signal_inferred)}")
            print(f"Impl. Stage:    {_fmt_inferred(summary.implementation_stage, summary.implementation_stage_inferred)}")
            print("Entry Source:   AI Pipeline")

        if not summary.action_items:
            print("Action items:   (none parsed - check the 'Action Items' heading in this summary)")
            continue

        print(f"Action items ({len(summary.action_items)}), as subitems:")
        for item in summary.action_items:
            print(f"  - Task: {item.task}")
            owner_str = item.owner_user_name or item.owner_raw or "(none)"
            print(f"    Owner: {owner_str}", end="")
            if item.owner_warning:
                print(f"  ⚠ {item.owner_warning}")
            else:
                print()
            due_str = item.due_iso or item.due_raw or "(none)"
            print(f"    Due:   {due_str}", end="")
            if item.due_warning:
                print(f"  ⚠ {item.due_warning}")
            else:
                print()

    print("\n" + "=" * 78)


def _fmt_inferred(value: Optional[str], inferred: bool) -> str:
    if value is None:
        return "(not set - no keyword match, leaving blank for manual triage)"
    return f"{value} (inferred)" if inferred else value


# --------------------------------------------------------------------------
# Push
# --------------------------------------------------------------------------

def push(client: MondayClient, summaries: list, logged_by_user_id: str) -> None:
    for summary in summaries:
        try:
            if summary.target_board == "ci_activity_log":
                board_id = CI_ACTIVITY_LOG_BOARD_ID
                group_id = CI_ACTIVITY_LOG_GROUPS["to_log"]
                cols = build_ci_activity_log_parent_columns(summary, logged_by_user_id)
            else:
                board_id = TASK_TRACKING_BOARD_ID
                group_id = TASK_TRACKING_GROUPS["this_week"]
                cols = build_task_tracking_parent_columns(summary)

            parent_id = client.create_item(board_id, group_id, summary.title, cols)
            print(f"Created parent item {parent_id} ({summary.title!r}) on {BOARD_LABELS[summary.target_board]}")

            for item in summary.action_items:
                sub_cols = build_subitem_columns(item)
                sub_id = client.create_subitem(parent_id, item.task, sub_cols)
                print(f"  Created subitem {sub_id}: {item.task}")
        except RuntimeError as e:
            print(f"FAILED to push {summary.title!r}: {e}", file=sys.stderr)


# --------------------------------------------------------------------------
# Input loading / CLI
# --------------------------------------------------------------------------

def load_sources(args) -> list:
    sources = []
    if args.file:
        for path in args.file:
            p = Path(path)
            sources.append((p.name, p.read_text(encoding="utf-8")))
    if args.dir:
        d = Path(args.dir)
        for p in sorted(list(d.glob("*.md")) + list(d.glob("*.txt"))):
            sources.append((p.name, p.read_text(encoding="utf-8")))
    if not sources:
        if sys.stdin.isatty():
            print("Paste your Plaud summary, then press Ctrl-D (Ctrl-Z on Windows) when done:", file=sys.stderr)
        text = sys.stdin.read()
        if text.strip():
            sources.append(("<pasted>", text))
    return sources


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", nargs="+", help="One or more Plaud summary files")
    parser.add_argument("--dir", help="Directory of .md/.txt Plaud summary files (non-recursive)")
    parser.add_argument("--no-push", action="store_true", help="Only print the draft; never prompt to push")
    parser.add_argument("--logged-by-user-id", default=DEFAULT_LOGGED_BY_USER_ID,
                         help=f"monday.com user id for 'Logged By' on CI Activity Log entries (default: {DEFAULT_LOGGED_BY_USER_ID})")
    parser.add_argument("--today", help="Override 'today' as YYYY-MM-DD (mainly for testing relative due dates)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    today = date.fromisoformat(args.today) if args.today else date.today()

    sources = load_sources(args)
    if not sources:
        print("No input provided.", file=sys.stderr)
        sys.exit(1)

    token = os.environ.get("MONDAY_API_TOKEN")
    client = MondayClient(token)

    contractors, users = [], []
    if client.available:
        try:
            contractors = client.fetch_contractors()
            users = client.fetch_users()
        except RuntimeError as e:
            print(f"Warning: could not fetch monday.com context ({e}). Matching will be skipped.", file=sys.stderr)
    else:
        print(
            "Warning: MONDAY_API_TOKEN not set. Contractor/owner matching and push are disabled; "
            "showing parse-only draft.",
            file=sys.stderr,
        )

    summaries = [build_summary(name, text, contractors, users, today) for name, text in sources]

    print_draft(summaries)

    if args.no_push:
        return

    total_items = sum(len(s.action_items) for s in summaries)
    if total_items == 0:
        print("\nNo action items parsed - nothing to push.")
        return

    if not client.available:
        print("\nMONDAY_API_TOKEN not set - cannot push. Set it and re-run to push these items.")
        return

    print(f"\n{len(summaries)} parent item(s), {total_items} action item(s) parsed above.")
    answer = input("Type CONFIRM to create these on monday.com, or anything else to cancel: ").strip()
    if answer != "CONFIRM":
        print("Cancelled - nothing was created.")
        return

    push(client, summaries, args.logged_by_user_id)


if __name__ == "__main__":
    main()
