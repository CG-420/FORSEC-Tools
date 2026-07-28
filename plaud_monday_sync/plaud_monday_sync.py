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
      CI Activity Log, with every action item as a subitem there -
      contractor meetings stay together as one interaction record.
      (Task Tracking, also in the CI Folder, is CI-only and has no
      automatic trigger of its own right now - see PARENT_SUBITEM_ROUTES.)
    - Otherwise, each action item is routed individually: a safety
      concern or event/demo idea (by keyword) goes to Safety Feedback
      & Ideas; else an item owned by Kyle/Ariel/Kerri/Samantha (or
      anyone previously taught via the interactive prompt - see
      learned_routes.json) goes to their board (Communications /
      Office & Program Administration / Board of Directors / Training
      Projects & Programs); everything else is left UNROUTED. Items
      sharing a destination board are grouped under one parent item
      per meeting (or created as flat items on boards with no subitem
      structure).
    - Right before pushing, you're asked where each still-unrouted
      item (grouped by owner) should go, with the option to teach the
      script that owner's default going forward. Anything you skip -
      or run with --no-interactive - lands on the Needs Routing board
      instead of being dropped, for later manual triage.

Usage:
    python3 plaud_monday_sync.py --file meeting.md
    python3 plaud_monday_sync.py --dir ./summaries
    python3 plaud_monday_sync.py                     # paste, then Ctrl-D
    python3 plaud_monday_sync.py --file meeting.md --no-push
    python3 plaud_monday_sync.py --file meeting.md --no-interactive

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

# Task Tracking / CI Activity Log / Communications / Office & Program
# Administration all share this subitem schema (Name / Owner / Status / Date).
SUBITEM_COLUMNS = {
    "owner": "person",
    "status": "status",  # Working on it / Done / Stuck
    "date": "date0",
}

COMMUNICATIONS_BOARD_ID = 18336748732
COMMUNICATIONS_GROUPS = {"tasks": "topics"}
COMMUNICATIONS_COLUMNS = {
    "status": "status",  # Working on it / Done / Stuck / In Flight / DRAFTED
    "date": "date4",
}

OFFICE_ADMIN_BOARD_ID = 18381184971
OFFICE_ADMIN_GROUPS = {"team_requests": "group_mm0fxafz"}
OFFICE_ADMIN_COLUMNS = {
    "status": "status",  # Working on it / Done / Stuck / Started, Paused
    "date_due": "date_mm3rx92q",
    "notes": "text_mkxsfve0",
}

# No subitems column - action items land as flat items directly.
BOARD_OF_DIRECTORS_BOARD_ID = 18386660346
BOARD_OF_DIRECTORS_GROUPS = {"other_tasks": "group_mm067c1p"}
BOARD_OF_DIRECTORS_COLUMNS = {
    "person": "person",
    "status": "status",  # Working on it / Done / Stuck
    "date": "date4",
}

# A submission-form board, not a task list - flat items, different shape.
SAFETY_FEEDBACK_BOARD_ID = 18418568346
SAFETY_FEEDBACK_GROUPS = {"new_submissions": "topics"}
SAFETY_FEEDBACK_COLUMNS = {
    "status": "color_mm4fr3me",  # Under Review / Completed / Planned / New
    "description": "long_text_mm4fwrcz",
    "date_submitted": "date_mm4f887d",
    "submission_type": "dropdown_mm4fr66x",  # Safety Feedback / Event or Demo Idea
    "submitted_by": "multiple_person_mm4fay1w",
}

# Training Projects & Programs' own groups are all specific named programs
# (Pilot Placement Initiative, Mentorship Coaching, etc.) with no generic
# catch-all, so "Incoming from Meetings" was created (2026-07-28) as a
# holding group for freshly parsed items pending Samantha's triage - same
# pattern as CI Activity Log's "To Log" group. Its subitems use a Timeline
# (date range) column instead of a single date, unlike the other boards.
TRAINING_BOARD_ID = 18407621067
TRAINING_GROUPS = {"incoming": "group_mm5pb87v"}
TRAINING_COLUMNS = {
    "lead": "person",
    "status": "color_mm27eh5n",  # Working on it / Done / Stuck / Upcoming
    "timeline": "timerange_mm26mnv8",
    "comments": "text_mm2f14wz",
}
TRAINING_SUBITEM_DATE_COLUMN = "timerange_mm26mvs0"  # different id than the parent's Timeline column

# Holding board for items with no matching department board (created
# 2026-07-28). Anything still unrouted after the interactive prompt at push
# time lands here instead of being dropped, for weekly manual triage.
NEEDS_ROUTING_BOARD_ID = 18424076669
NEEDS_ROUTING_GROUPS = {"needs_review": "topics"}
NEEDS_ROUTING_COLUMNS = {
    "owner": "multiple_person_mm5ph3ak",
    "due": "date_mm5pv64e",
    "status": "color_mm5pbgmw",  # Needs Review / Resolved
    "notes": "long_text_mm5pbbhn",
}

# Additional owner -> board mappings taught interactively at push time,
# layered on top of OWNER_DEFAULT_ROUTE below. See load_learned_routes().
LEARNED_ROUTES_PATH = Path(__file__).resolve().parent / "learned_routes.json"

# Action items owned by these people default to their department board
# instead of falling through to "unrouted" (overridden by a safety/
# demo-idea keyword match, which always wins regardless of owner).
OWNER_DEFAULT_ROUTE = {
    "81506714": "communications",      # Kyle MacKay
    "82580584": "office_admin",        # Ariel Durning
    "80632035": "board_of_directors",  # Kerri Marshall
    "97947987": "training",            # Samantha Chu
}

# Routes that use a parent item (the meeting) with action items as subitems.
# Task Tracking is CI-only (it lives in the CI Folder) and currently has no
# automatic trigger of its own now that contractor meetings go entirely to
# CI Activity Log - it stays wired up here for whenever a "CI but no named
# contractor" signal gets defined, but the router never sends items there today.
PARENT_SUBITEM_ROUTES = {"task_tracking", "communications", "office_admin", "training"}

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

SAFETY_OR_DEMO_KEYWORDS = {
    "Safety Feedback": ["safety concern", "safety issue", "safety hazard", "unsafe", "near miss", "close call", "ppe issue"],
    "Event or Demo Idea": ["demo idea", "demonstration idea", "team demo", "host a demo", "event idea", "should demo"],
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
    route: str = "unrouted"
    route_reason: Optional[str] = None
    safety_submission_type: Optional[str] = None


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
    recorded_by_raw: Optional[str] = None
    recorded_by_user_id: Optional[str] = None
    recorded_by_user_name: Optional[str] = None
    recorded_by_warning: Optional[str] = None


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

HEADING_RE = re.compile(r"^(#{1,6})\s*(.+?)\s*$", re.MULTILINE)
# [*_]* right after the anchor tolerates a fully-bolded/underlined heading or
# label line (e.g. "## **Action Items**", "**Date:** ..."), since the label
# text otherwise has to be the very first thing on the line to match.
# Matches an optional markdown heading marker, then "Action Items" as the
# leading phrase of the line, then tolerates anything after it - covers
# "## Action Items", a bare "Action Items" line (what survives copy-pasting
# rendered text off a webpage, or a .docx paragraph, where "#" never existed
# as a literal character), and a heading whose trailing description runs
# into the same line/paragraph, e.g. "Action Items - format each one
# exactly as: Task: [x] | Owner: [x] | Due: [x]" (seen in a real template -
# the whole thing is one Word paragraph, so it's one line once extracted).
# Anchored so "action items" must lead the line, not appear mid-sentence in
# ordinary prose.
ACTION_ITEMS_HEADING_RE = re.compile(
    r"^(#{1,6})?\s*[*_]*\s*action\s*items?\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
META_DATE_RE = re.compile(r"^[*_]*\s*(?:meeting\s*date|date)\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
RECORDED_BY_RE = re.compile(r"^[*_]*\s*(?:recorded\s*by|logged\s*by)\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
FIELD_RE = re.compile(
    r"(Task|Owner|Due)\s*:\s*(.*?)\s*(?=\s*\|\s*[*_]*\s*(?:Task|Owner|Due)\s*:|$)",
    re.IGNORECASE,
)
BULLET_PREFIX_RE = re.compile(r"^\s*(?:[-*]\s*)?(?:\[[ xX]\]\s*)?")


def _clean_field_value(text: str) -> str:
    """Strips markdown emphasis (**bold**, __bold__, stray */_ ) so a
    formatted template (e.g. a bolded 'Task:' label or value) doesn't leak
    literal markdown characters into what gets pushed to monday.com."""
    return text.replace("**", "").replace("__", "").strip("* _\t")


def extract_title(text: str) -> str:
    m = HEADING_RE.search(text)
    if m:
        return _clean_field_value(m.group(2).strip())
    stripped = text.strip()
    if not stripped:
        return "Untitled Meeting"
    return _clean_field_value(stripped.splitlines()[0].strip())[:120]


def extract_action_items_section(text: str) -> str:
    m = ACTION_ITEMS_HEADING_RE.search(text)
    if not m:
        return ""
    rest = text[m.end():]
    if not m.group(1):
        # Bare "Action Items" line, no markdown heading level to bound a
        # "next heading" search against (this is what copy-pasting rendered
        # text off a webpage looks like). Take the rest of the document -
        # stray trailing content won't match the Task/Owner/Due row pattern
        # anyway, so including a bit extra is harmless.
        return rest
    heading_level = len(m.group(1))
    next_heading = re.search(rf"^#{{1,{heading_level}}}\s+\S", rest, re.MULTILINE)
    return rest[: next_heading.start()] if next_heading else rest


def parse_action_items(section_text: str) -> list:
    items = []
    for line in section_text.splitlines():
        line = BULLET_PREFIX_RE.sub("", line).strip()
        if not line or ":" not in line or "task" not in line.lower():
            continue
        fields = {k.lower(): _clean_field_value(v.strip()) for k, v in FIELD_RE.findall(line)}
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
    raw = _clean_field_value(m.group(1).strip())
    iso, warning = parse_date_loose(raw, fallback)
    if iso:
        return iso, None
    return fallback.isoformat(), f"meeting date {raw!r} unparsed, defaulted to {fallback.isoformat()}"


def extract_recorded_by(text: str) -> Optional[str]:
    head = "\n".join(text.splitlines()[:20])
    m = RECORDED_BY_RE.search(head)
    return _clean_field_value(m.group(1).strip()) if m else None


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
    if not owner_raw or not owner_raw.strip() or owner_raw.strip().lower() in ("unassigned", "n/a", "none", "tbd"):
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


def load_learned_routes() -> dict:
    """Owner-taught routes from a past interactive session (user_id -> route)."""
    if not LEARNED_ROUTES_PATH.exists():
        return {}
    try:
        return json.loads(LEARNED_ROUTES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: could not read {LEARNED_ROUTES_PATH.name} ({e}); ignoring learned routes.", file=sys.stderr)
        return {}


def save_learned_routes(learned_routes: dict) -> None:
    LEARNED_ROUTES_PATH.write_text(json.dumps(learned_routes, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def route_action_item(item: ActionItem, learned_routes: dict) -> None:
    """Decides which board a non-contractor-meeting action item goes to.

    A safety/demo-idea keyword match wins regardless of owner, since a
    safety concern shouldn't get buried on someone's department board.
    Otherwise, items owned by Kyle/Ariel/Kerri/Samantha default to their
    board, then anyone else previously taught via the interactive prompt
    (learned_routes). Everything else is left "unrouted" - at push time
    you're asked where it should go, and anything left unresolved lands
    on the Needs Routing board rather than guessed or dropped.
    """
    label, matched = infer_field(item.task, SAFETY_OR_DEMO_KEYWORDS)
    if matched:
        item.route = "safety"
        item.safety_submission_type = label
        item.route_reason = f"keyword match ({label.lower()})"
        return
    if item.owner_user_id and item.owner_user_id in OWNER_DEFAULT_ROUTE:
        item.route = OWNER_DEFAULT_ROUTE[item.owner_user_id]
        item.route_reason = f"owner: {item.owner_user_name}"
        return
    if item.owner_user_id and item.owner_user_id in learned_routes:
        item.route = learned_routes[item.owner_user_id]
        item.route_reason = f"learned: {item.owner_user_name}"
        return
    item.route = "unrouted"
    item.route_reason = "no matching department board"


def group_items_by_route(action_items: list) -> dict:
    groups: dict = {}
    for item in action_items:
        groups.setdefault(item.route, []).append(item)
    return groups


# --------------------------------------------------------------------------
# Build a MeetingSummary from raw text
# --------------------------------------------------------------------------

def build_summary(source: str, text: str, contractors: list, users: list, today: date, learned_routes: dict) -> MeetingSummary:
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

    recorded_by_raw = extract_recorded_by(text)
    if recorded_by_raw:
        summary.recorded_by_raw = recorded_by_raw
        summary.recorded_by_user_id, summary.recorded_by_user_name, summary.recorded_by_warning = match_owner(
            recorded_by_raw, users
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
        for item in action_items:
            route_action_item(item, learned_routes)

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

    def update_item_columns(self, board_id: int, item_id: str, column_values: dict) -> None:
        """Sets column values on an already-existing item, as a genuine
        change rather than baked into creation. monday.com's "when column
        changes to X" automations (confirmed live 2026-07-28) do not fire
        when a value is set as part of item creation - only on a real
        subsequent change to an existing item - so this is required for
        anything that needs to trigger one of those automations."""
        query = """
        mutation ($boardId: ID!, $itemId: ID!, $columnValues: JSON!) {
          change_multiple_column_values(board_id: $boardId, item_id: $itemId, column_values: $columnValues) { id }
        }
        """
        variables = {
            "boardId": board_id,
            "itemId": item_id,
            "columnValues": json.dumps(column_values),
        }
        self._request(query, variables)


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


def dropdown_value(*labels: str) -> dict:
    return {"labels": list(labels)}


def timeline_value(iso: str) -> dict:
    return {"from": iso, "to": iso}


def build_task_tracking_parent_columns(summary: MeetingSummary, items: list) -> dict:
    cols = {TASK_TRACKING_COLUMNS["status"]: status_value("Not Started")}
    due_dates = [i.due_iso for i in items if i.due_iso]
    if due_dates:
        cols[TASK_TRACKING_COLUMNS["deadline"]] = date_value(min(due_dates))
    notes_lines = [f"Source: {summary.source}", f"Meeting date: {summary.meeting_date_iso}"]
    if summary.recorded_by_user_name or summary.recorded_by_raw:
        notes_lines.append(f"Recorded by: {summary.recorded_by_user_name or summary.recorded_by_raw}")
    if summary.meeting_date_warning:
        notes_lines.append(f"Note: {summary.meeting_date_warning}")
    cols[TASK_TRACKING_COLUMNS["notes"]] = "\n".join(notes_lines)
    return cols


def build_communications_parent_columns(items: list) -> dict:
    cols = {COMMUNICATIONS_COLUMNS["status"]: status_value("Working on it")}
    due_dates = [i.due_iso for i in items if i.due_iso]
    if due_dates:
        cols[COMMUNICATIONS_COLUMNS["date"]] = date_value(min(due_dates))
    return cols


def build_office_admin_parent_columns(summary: MeetingSummary, items: list) -> dict:
    cols = {OFFICE_ADMIN_COLUMNS["status"]: status_value("Working on it")}
    due_dates = [i.due_iso for i in items if i.due_iso]
    if due_dates:
        cols[OFFICE_ADMIN_COLUMNS["date_due"]] = date_value(min(due_dates))
    notes_lines = [f"Source: {summary.source}", f"Meeting date: {summary.meeting_date_iso}"]
    cols[OFFICE_ADMIN_COLUMNS["notes"]] = "\n".join(notes_lines)
    return cols


def build_board_of_directors_item_columns(item: ActionItem) -> dict:
    cols = {BOARD_OF_DIRECTORS_COLUMNS["status"]: status_value("Working on it")}
    if item.due_iso:
        cols[BOARD_OF_DIRECTORS_COLUMNS["date"]] = date_value(item.due_iso)
    if item.owner_user_id:
        cols[BOARD_OF_DIRECTORS_COLUMNS["person"]] = people_value(item.owner_user_id)
    return cols


def build_training_parent_columns(summary: MeetingSummary, items: list) -> dict:
    cols = {
        TRAINING_COLUMNS["status"]: status_value("Working on it"),
        TRAINING_COLUMNS["lead"]: people_value("97947987"),  # Samantha Chu
    }
    due_dates = [i.due_iso for i in items if i.due_iso]
    if due_dates:
        cols[TRAINING_COLUMNS["timeline"]] = timeline_value(min(due_dates))
    comments_lines = [f"Source: {summary.source}", f"Meeting date: {summary.meeting_date_iso}"]
    cols[TRAINING_COLUMNS["comments"]] = "\n".join(comments_lines)
    return cols


def build_training_subitem_columns(item: ActionItem) -> dict:
    cols = {SUBITEM_COLUMNS["status"]: status_value("Working on it")}
    if item.owner_user_id:
        cols[SUBITEM_COLUMNS["owner"]] = people_value(item.owner_user_id)
    if item.due_iso:
        cols[TRAINING_SUBITEM_DATE_COLUMN] = timeline_value(item.due_iso)
    return cols


def build_safety_feedback_item_columns(item: ActionItem, summary: MeetingSummary) -> dict:
    cols = {
        SAFETY_FEEDBACK_COLUMNS["status"]: status_value("New"),
        SAFETY_FEEDBACK_COLUMNS["description"]: long_text_value(item.task),
        SAFETY_FEEDBACK_COLUMNS["date_submitted"]: date_value(summary.meeting_date_iso),
    }
    if item.safety_submission_type:
        cols[SAFETY_FEEDBACK_COLUMNS["submission_type"]] = dropdown_value(item.safety_submission_type)
    submitter_id = item.owner_user_id or summary.recorded_by_user_id
    if submitter_id:
        cols[SAFETY_FEEDBACK_COLUMNS["submitted_by"]] = people_value(submitter_id)
    return cols


def build_needs_routing_item_columns(item: ActionItem, summary: MeetingSummary) -> dict:
    cols = {NEEDS_ROUTING_COLUMNS["status"]: status_value("Needs Review")}
    if item.due_iso:
        cols[NEEDS_ROUTING_COLUMNS["due"]] = date_value(item.due_iso)
    if item.owner_user_id:
        cols[NEEDS_ROUTING_COLUMNS["owner"]] = people_value(item.owner_user_id)
    notes_lines = [
        f"Reason: {item.route_reason or 'no matching department board'}",
        f"Owner (as written): {item.owner_raw or '(none)'}",
        f"Source: {summary.source}",
        f"Meeting date: {summary.meeting_date_iso}",
    ]
    cols[NEEDS_ROUTING_COLUMNS["notes"]] = long_text_value("\n".join(notes_lines))
    return cols


def build_ci_activity_log_parent_columns(summary: MeetingSummary, default_logged_by_user_id: Optional[str]) -> dict:
    cols = {}
    logged_by_user_id = summary.recorded_by_user_id or default_logged_by_user_id
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

BOARD_LABELS = {
    "task_tracking": "Task Tracking",
    "ci_activity_log": "CI Activity Log",
    "communications": "Communications",
    "office_admin": "Office & Program Administration",
    "board_of_directors": "Board of Directors (ED)",
    "safety": "Safety Feedback & Ideas",
    "training": "Training Projects & Programs",
    "unrouted": "UNROUTED - you'll be asked, or it lands on Needs Routing",
}


def print_draft(summaries: list) -> None:
    print("=" * 78)
    print("DRAFT - nothing has been created on monday.com yet")
    print("=" * 78)

    for summary in summaries:
        print(f"\n--- {summary.source} " + "-" * max(0, 60 - len(summary.source)))
        print(f"Meeting date:   {summary.meeting_date_iso}", end="")
        if summary.meeting_date_warning:
            print(f"  ⚠ {summary.meeting_date_warning}")
        else:
            print()

        if summary.recorded_by_raw:
            recorded_by_str = summary.recorded_by_user_name or summary.recorded_by_raw
            print(f"Recorded by:    {recorded_by_str}", end="")
            if summary.recorded_by_warning:
                print(f"  ⚠ {summary.recorded_by_warning}")
            else:
                print()

        if not summary.action_items:
            print("Action items:   (none parsed - check the 'Action Items' heading in this summary)")
            continue

        if summary.target_board == "ci_activity_log":
            print(f"Board:          {BOARD_LABELS['ci_activity_log']}")
            print(f"Parent item:    {summary.title}")
            print(f"Contractor:     {summary.contractor_name} (matched item id {summary.contractor_id})")
            if summary.other_contractor_mentions:
                print(f"  also mentions: {', '.join(summary.other_contractor_mentions)}")
            print(f"Activity Type:  {_fmt_inferred(summary.activity_type, summary.activity_type_inferred)}")
            print(f"Outcome:        {_fmt_inferred(summary.outcome, summary.outcome_inferred)}")
            print(f"Adoption Signal:{_fmt_inferred(summary.adoption_signal, summary.adoption_signal_inferred)}")
            print(f"Impl. Stage:    {_fmt_inferred(summary.implementation_stage, summary.implementation_stage_inferred)}")
            print("Entry Source:   AI Pipeline")
            print(f"Action items ({len(summary.action_items)}), as subitems:")
            for item in summary.action_items:
                _print_action_item(item)
            continue

        groups = group_items_by_route(summary.action_items)
        print(f"Action items ({len(summary.action_items)}), routed across {len(groups)} board(s):")
        for route, items in groups.items():
            prefix = "⚠ " if route == "unrouted" else ""
            print(f"\n  Board: {prefix}{BOARD_LABELS[route]}")
            if route in PARENT_SUBITEM_ROUTES:
                print(f"  Parent item: {summary.title}")
            for item in items:
                _print_action_item(item, indent="  ")
                if item.route_reason:
                    print(f"      routed by: {item.route_reason}")

    print("\n" + "=" * 78)


def _print_action_item(item: ActionItem, indent: str = "") -> None:
    print(f"{indent}  - Task: {item.task}")
    owner_str = item.owner_user_name or item.owner_raw or "(none)"
    print(f"{indent}    Owner: {owner_str}", end="")
    if item.owner_warning:
        print(f"  ⚠ {item.owner_warning}")
    else:
        print()
    due_str = item.due_iso or item.due_raw or "(none)"
    print(f"{indent}    Due:   {due_str}", end="")
    if item.due_warning:
        print(f"  ⚠ {item.due_warning}")
    else:
        print()


def _fmt_inferred(value: Optional[str], inferred: bool) -> str:
    if value is None:
        return "(not set - no keyword match, leaving blank for manual triage)"
    return f"{value} (inferred)" if inferred else value


# --------------------------------------------------------------------------
# Push
# --------------------------------------------------------------------------

# route -> (board_id, group_id) for routes that use a parent item + subitems.
PARENT_SUBITEM_BOARDS = {
    "task_tracking": (TASK_TRACKING_BOARD_ID, TASK_TRACKING_GROUPS["this_week"]),
    "communications": (COMMUNICATIONS_BOARD_ID, COMMUNICATIONS_GROUPS["tasks"]),
    "office_admin": (OFFICE_ADMIN_BOARD_ID, OFFICE_ADMIN_GROUPS["team_requests"]),
    "training": (TRAINING_BOARD_ID, TRAINING_GROUPS["incoming"]),
}


def push(client: MondayClient, summaries: list, logged_by_user_id: str, report=print) -> None:
    """Creates everything on monday.com. `report(message)` is called for
    every progress/result line instead of printing directly, so callers
    other than the CLI (e.g. the web UI) can collect results as data
    instead of console output - same push logic either way."""
    for summary in summaries:
        try:
            if summary.target_board == "ci_activity_log":
                _push_ci_activity_log(client, summary, logged_by_user_id, report)
                continue

            for route, items in group_items_by_route(summary.action_items).items():
                if route == "unrouted":
                    _push_needs_routing(client, summary, items, report)
                elif route in PARENT_SUBITEM_BOARDS:
                    _push_parent_and_subitems(client, summary, route, items, report)
                elif route == "board_of_directors":
                    _push_board_of_directors(client, items, report)
                elif route == "safety":
                    _push_safety_feedback(client, summary, items, report)
        except RuntimeError as e:
            report(f"FAILED to push {summary.title!r}: {e}")


def _push_ci_activity_log(client: MondayClient, summary: MeetingSummary, logged_by_user_id: str, report=print) -> None:
    cols = build_ci_activity_log_parent_columns(summary, logged_by_user_id)
    # Adoption Signal is set as a separate follow-up change, not baked into
    # creation, so it fires as a genuine change - required for monday's
    # "Adoption Signal -> Interest" automation (auto-creates a linked
    # Contractor Participation item) to actually trigger.
    adoption_signal_col = cols.pop(CI_ACTIVITY_LOG_COLUMNS["adoption_signal"], None)

    parent_id = client.create_item(CI_ACTIVITY_LOG_BOARD_ID, CI_ACTIVITY_LOG_GROUPS["to_log"], summary.title, cols)
    report(f"Created parent item {parent_id} ({summary.title!r}) on {BOARD_LABELS['ci_activity_log']}")

    if adoption_signal_col:
        client.update_item_columns(CI_ACTIVITY_LOG_BOARD_ID, parent_id, {CI_ACTIVITY_LOG_COLUMNS["adoption_signal"]: adoption_signal_col})
        report(f"  Set Adoption Signal on {parent_id} ({summary.adoption_signal}) - triggers monday's Contractor Participation automation when 'Interest'")

    for item in summary.action_items:
        sub_id = client.create_subitem(parent_id, item.task, build_subitem_columns(item))
        report(f"  Created subitem {sub_id}: {item.task}")


def _push_parent_and_subitems(client: MondayClient, summary: MeetingSummary, route: str, items: list, report=print) -> None:
    board_id, group_id = PARENT_SUBITEM_BOARDS[route]
    if route == "task_tracking":
        cols = build_task_tracking_parent_columns(summary, items)
    elif route == "communications":
        cols = build_communications_parent_columns(items)
    elif route == "training":
        cols = build_training_parent_columns(summary, items)
    else:
        cols = build_office_admin_parent_columns(summary, items)

    parent_id = client.create_item(board_id, group_id, summary.title, cols)
    report(f"Created parent item {parent_id} ({summary.title!r}) on {BOARD_LABELS[route]}")
    for item in items:
        sub_cols = build_training_subitem_columns(item) if route == "training" else build_subitem_columns(item)
        sub_id = client.create_subitem(parent_id, item.task, sub_cols)
        report(f"  Created subitem {sub_id}: {item.task}")


def _push_board_of_directors(client: MondayClient, items: list, report=print) -> None:
    for item in items:
        cols = build_board_of_directors_item_columns(item)
        item_id = client.create_item(BOARD_OF_DIRECTORS_BOARD_ID, BOARD_OF_DIRECTORS_GROUPS["other_tasks"], item.task, cols)
        report(f"Created item {item_id} ({item.task!r}) on {BOARD_LABELS['board_of_directors']}")


def _push_safety_feedback(client: MondayClient, summary: MeetingSummary, items: list, report=print) -> None:
    for item in items:
        cols = build_safety_feedback_item_columns(item, summary)
        item_id = client.create_item(SAFETY_FEEDBACK_BOARD_ID, SAFETY_FEEDBACK_GROUPS["new_submissions"], item.task, cols)
        report(f"Created item {item_id} ({item.task!r}) on {BOARD_LABELS['safety']}")


def _push_needs_routing(client: MondayClient, summary: MeetingSummary, items: list, report=print) -> None:
    for item in items:
        cols = build_needs_routing_item_columns(item, summary)
        item_id = client.create_item(NEEDS_ROUTING_BOARD_ID, NEEDS_ROUTING_GROUPS["needs_review"], item.task, cols)
        report(f"Created item {item_id} ({item.task!r}) on Needs Routing")


# --------------------------------------------------------------------------
# Interactive resolution of unrouted items, right before push
# --------------------------------------------------------------------------

# (route_key, display_label) choices offered when resolving an unrouted item.
# Task Tracking deliberately excluded - it's CI-only, not a general catch-all.
INTERACTIVE_ROUTE_CHOICES = [
    ("communications", "Communications"),
    ("office_admin", "Office & Program Administration"),
    ("board_of_directors", "Board of Directors (ED)"),
    ("training", "Training Projects & Programs"),
    ("safety", "Safety Feedback & Ideas"),
]


def collect_unrouted_groups(summaries: list) -> dict:
    """Groups still-unrouted items by owner identity, across all summaries.

    Items sharing an owner are resolved together with one prompt. Owners
    that didn't match a monday.com user are grouped by their raw typed
    name instead, since there's no stable id to group (or later learn) by.
    """
    groups: dict = {}
    for summary in summaries:
        if summary.target_board == "ci_activity_log":
            continue
        for item in summary.action_items:
            if item.route != "unrouted":
                continue
            key = item.owner_user_id or f"raw:{(item.owner_raw or '').strip().lower()}"
            groups.setdefault(key, []).append((summary, item))
    return groups


def resolve_unrouted_interactively(summaries: list, learned_routes: dict) -> None:
    groups = collect_unrouted_groups(summaries)
    if not groups:
        return

    print("\nSome action items have no matching department board.")
    for pairs in groups.values():
        first_item = pairs[0][1]
        owner_label = first_item.owner_user_name or first_item.owner_raw or "(no owner)"
        print(f"\n{owner_label} - {len(pairs)} unrouted item(s):")
        for _, item in pairs:
            print(f"  - {item.task}")
        print("  Where should these go?")
        for i, (_, label) in enumerate(INTERACTIVE_ROUTE_CHOICES, start=1):
            print(f"    {i}) {label}")
        print("    0) Leave for the Needs Routing board (decide later)")
        answer = input("  > ").strip()

        valid_choices = {str(i): route for i, (route, _) in enumerate(INTERACTIVE_ROUTE_CHOICES, start=1)}
        if answer not in valid_choices:
            print("  Leaving these for Needs Routing.")
            continue

        chosen_route = valid_choices[answer]
        for _, item in pairs:
            item.route = chosen_route
            item.route_reason = f"placed interactively ({owner_label})"

        if first_item.owner_user_id:
            remember = input(
                f"  Remember that {owner_label}'s items go to {BOARD_LABELS[chosen_route]} from now on? [y/N] "
            ).strip().lower()
            if remember == "y":
                learned_routes[first_item.owner_user_id] = chosen_route
                save_learned_routes(learned_routes)
                print(f"  Remembered: {owner_label} -> {BOARD_LABELS[chosen_route]}")


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
                         help="monday.com user id for 'Logged By' on CI Activity Log entries when a summary has "
                              f"no 'Recorded by:' line of its own (default: {DEFAULT_LOGGED_BY_USER_ID})")
    parser.add_argument("--today", help="Override 'today' as YYYY-MM-DD (mainly for testing relative due dates)")
    parser.add_argument("--no-interactive", action="store_true",
                         help="Don't prompt about unrouted items before pushing; send them straight to Needs Routing")
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

    learned_routes = load_learned_routes()
    summaries = [build_summary(name, text, contractors, users, today, learned_routes) for name, text in sources]

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

    if not args.no_interactive:
        resolve_unrouted_interactively(summaries, learned_routes)

    print(f"\n{len(summaries)} summary(ies), {total_items} action item(s) - final routing above.")
    answer = input("Type CONFIRM to create these on monday.com, or anything else to cancel: ").strip()
    if answer != "CONFIRM":
        print("Cancelled - nothing was created.")
        return

    push(client, summaries, args.logged_by_user_id)


if __name__ == "__main__":
    main()
