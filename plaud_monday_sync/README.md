# Plaud → monday.com Action Item Sync

Parses the "Action Items" section out of Plaud AI meeting summaries and drafts
what would be created on monday.com, then pushes it after you confirm.

## What it assumes about your Plaud summaries

- A markdown-style heading containing the words "Action Items" (any level,
  e.g. `## Action Items`).
- Under that heading, one bullet per action item, in the form:

  ```
  Task: <task text> | Owner: <name> | Due: <date>
  ```

  Leading `-`, `*`, or `- [ ]` checkboxes are stripped automatically. Field
  order doesn't matter and any of the three can be omitted, but the parser
  currently only recognizes `Task`, `Owner`, and `Due` — extra pipe-delimited
  fields (e.g. `Priority:`) aren't extracted (harmless, just ignored).
- Optionally, a `Date:` or `Meeting Date:` line near the top of the summary
  gives the meeting's own date (used as the reference date for relative due
  dates like "next Friday", and as the CI Activity Log interaction date).
  Falls back to today if absent or unparseable.
- Optionally, a `Recorded by:` or `Logged by:` line near the top identifies
  who ran that particular recording — relevant now that summaries may come
  from shared office devices or Desktop installs across several people, not
  just one person's device. Matched against monday.com users the same way
  Owner is. Used for CI Activity Log's Logged By column and noted in Task
  Tracking's Notes. Falls back to `--logged-by-user-id` (default: Chris)
  when absent.

This is deliberately template-agnostic — it doesn't care about the other 11
headings/sections in your 12 templates, only that this one heading and
row format are consistent.

## Where these boards live

FORSEC reorganised monday.com on 2026-07-29/30: the Main workspace was
renamed **Strategic Work Plan** and reserved for the strategic plan itself,
and each department got its own workspace. Board ids survive a move between
workspaces, so the mapping below is keyed on ids and was unaffected — but
for orientation:

| Board | Workspace |
|---|---|
| Task Tracking, CI Activity Log, Contractor Directory, Needs Routing | Continuous Improvement |
| Communications | Communications |
| Office & Program Administration | Administration |
| Training Projects & Programs | Training - Skills Development & Training |
| Safety Feedback & Ideas | Safety Committee |
| Strategic Work Plan | Strategic Work Plan |

Two other workspaces exist with no task board this tool targets yet:
**Outreach - Attraction & Retention** and **Labour - Human Resources &
Planning**. They're likely future routing destinations as those areas grow.

Before any push, `check_configured_boards()` verifies every configured
board in a single query and reports anything archived, deleted or
inaccessible — in the CLI before the confirm prompt, and as a banner on the
web draft. This exists because the reorg silently archived one target board
and deleted another; without it, that surfaces only as a confusing API
error partway through a push.

## Board / column mapping

Routing happens in two stages:

1. **Meeting-level**: if the summary text mentions a contractor by name from
   the Contractor Directory board, the *whole meeting* routes to CI Activity
   Log as one interaction record — all its action items stay together as
   subitems there, regardless of who owns them.
2. **Per-item** (everything else): each action item is routed individually,
   since one internal meeting can easily have items for several different
   people/departments. In order:
   1. A safety concern or event/demo-idea keyword match (see
      `SAFETY_OR_DEMO_KEYWORDS`) → **Safety Feedback & Ideas**, regardless of
      owner.
   2. An item owned by Kyle MacKay → **Communications**; Ariel Durning →
      **Office & Program Administration**; Samantha Chu → **Training
      Projects & Programs** (see `OWNER_DEFAULT_ROUTE`) — or anyone else
      previously taught via the interactive prompt (see
      `learned_routes.json` below). A mapping is only honoured if its board
      is still configured, so a deleted board or a stale learned entry can
      never aim items at something that no longer exists. Kerri Marshall
      has no mapping — see "Board of Directors" below.
   3. Everything else → **UNROUTED**. It is *not* defaulted to Task Tracking
      — Task Tracking lives in the CI Folder and Chris wants it CI-only, so
      an item with no matching department board isn't guessed onto a board
      it may not belong on. The draft flags these with a `⚠`. Unlike the
      other routes, unrouted items aren't dropped — see "Unrouted items and
      Needs Routing" below for what actually happens to them at push time.

   **Every department board gets one flat item per action item.** An
   earlier version grouped a meeting's items as subitems under a parent
   item named after the meeting, but that buried them behind a collapsed
   dropdown — a busy meeting's tasks effectively vanished from the board.
   CI Activity Log is the one exception and still uses parent + subitems,
   because there an item genuinely *is* the interaction rather than a task.

   Because there is no parent item naming the meeting any more, flat items
   carry a one-line provenance note ("From: *meeting* (*date*), recorded by
   *who*") in whichever text column the board has — Office Admin Notes,
   Training Comments, Task Tracking Notes. Communications has no such
   column, so its items rely on the owner and date alone.

### Task Tracking (board `18403136567`) — CI-only, no active trigger

Task Tracking sits in the CI Folder alongside CI Activity Log, and per Chris
it should only ever contain CI-related content. Since contractor meetings
already route entirely to CI Activity Log, there's currently no rule that
sends anything here automatically — it stays wired up
(`build_task_tracking_item_columns`, `FLAT_ITEM_BOARDS`) for whenever a
"CI work, but no named contractor" signal gets defined, but the router
doesn't reach it today. If/when that signal exists, items would land in the
**This Week** group as flat items: Task → item name, Status → `Not Started`,
Due → Deadline. This board has no people column at all, so the owner is
written into its Notes text alongside the provenance note.

### CI Activity Log (board `18403818341`)

This board logs one *interaction* (meeting/call/site visit) per item, not a
flat action-item list, so a whole Plaud summary becomes one parent
"Interaction" item, with its action items as subitems (same schema as Task
Tracking's subitems: Name / Owner / Status / Date).

| Plaud field | monday.com target |
|---|---|
| Meeting title | Parent item name |
| Matched contractor | Contractor (board relation → Contractor Directory) |
| Meeting date | Interaction Date |
| Keyword-inferred | Activity Type, Outcome, Adoption Signal, Implementation Stage |
| Meeting title | Short Notes |
| Full summary text | AI Summary (long text) |
| — | Entry Source → `AI Pipeline` |
| `--logged-by-user-id` (default: Chris) | Logged By |
| Task / Owner / Due | Subitem, same as Task Tracking |

Parent items land in the **To Log** group (pending your review), not
"In Progress" — they're freshly parsed, not yet triaged.

**Existing monday.com automations on this board** (confirmed live
2026-07-28 — see `list_automations` on board `18403818341`): two AI
auto-categorization recipes on Activity Type (harmless — one only fires
when Activity Type is empty, the other fires on name changes but didn't
alter an explicitly-set value in testing), status-change automations that
move items between groups based on Implementation Stage, and — the
important one — **when Adoption Signal changes to "Interest", monday
auto-creates a linked item on Contractor Participation**. Live-tested and
confirmed: none of these fire on values baked into item creation via the
API, only on a genuine subsequent change to an existing item. Since
"Interest" is one of the values our own keyword inference can produce, the
script sets Adoption Signal as a separate follow-up `change_multiple_column_values`
call after creating the item (see `_push_ci_activity_log`), specifically
so this automation actually fires for real pushes instead of silently not
triggering.

The four inferred status fields use simple keyword heuristics (see
`ACTIVITY_TYPE_KEYWORDS` etc. in the script) and are always marked
`(inferred)` in the draft. If no keyword matches, the field is left blank
rather than guessed, and the draft says so explicitly.

### Communications (board `18336748732`) and Office & Program Administration (board `18381184971`)

One flat item per action item. Both boards carry the owner on their own
**Person** column, Status → `Working on it`, and the due date (Communications
`Date`, Office Admin `Date Due`). Office & Program Administration also gets
the provenance note in its **Notes** column; Communications has no notes
column, so its items rely on owner and date alone. Items land in
Communications' **Tasks** group and Office Admin's **Team Requests** group.

Communications' **Spend** and **Link to Draft** columns are deliberately
left blank for manual entry — a meeting summary rarely states a budget, and
the draft an action item asks for doesn't exist yet when the item is created.

### Training Projects & Programs (board `18407621067`)

Same parent+subitems pattern, with two differences: its own groups are all
specific named programs (Pilot Placement Initiative, Mentorship Coaching,
C2C-GIS, ROOT, Recognition of Prior Learning Fund 2.0, Dendro Learning
Series) with no generic catch-all, so a new **"Incoming from Meetings"**
group was created (2026-07-28, mirroring CI Activity Log's "To Log" holding
group) as the landing spot for freshly parsed items pending Samantha's
triage into the right program. It also uses a **Timeline** (date range)
column instead of a single date — the parser sets `{"from": due, "to":
due}` since it only has one date to work with, on both the parent (earliest
due date) and each subitem. The parent's Lead column defaults to Samantha.

### Board of Directors (ED) — deleted

This board was deleted during FORSEC's 2026-07-29/30 monday.com reorg.
Kerri Marshall therefore has no entry in `OWNER_DEFAULT_ROUTE`, and her
action items fall through to Needs Routing for manual placement until she
has a board again. Its config and column builder were removed rather than
left pointing at a dead board id — a replacement would get new ids anyway.

### Safety Feedback & Ideas (board `18418568346`)

Also flat items, but a different shape entirely (it's a submission-intake
board, not a task list): Description (the task text), Date Submitted (the
meeting date), Submission Type (`Safety Feedback` or `Event or Demo Idea`,
whichever keyword matched), Submitted By (the item's owner, or the
recording person if the item has no owner), Status → `New`. Lands in the
**New Submissions** group.

### Unrouted items and Needs Routing (board `18424493577`)

An action item lands here when it isn't a contractor meeting, doesn't match
a safety/demo-idea keyword, and its owner isn't Kyle/Ariel/Kerri/Samantha or
anyone taught via the process below.

**At push time**, before anything is created, you're asked about each
unrouted item (grouped by owner, so one prompt covers everyone's items for
that person in this run): pick one of the department boards to place them
on right now, or leave them for later. If you place them and the owner
matched a monday.com user, you're also asked whether to remember that
owner's default board — say yes and it's written to `learned_routes.json`
(a simple `{"monday_user_id": "route_key"}` file next to the script,
committed to the repo) and checked automatically on every future run,
layered on top of (but never overriding) the hardcoded
`OWNER_DEFAULT_ROUTE` mapping. Owners that didn't resolve to a monday.com
user can still be placed for this run, just not remembered — there's no
stable id to key the learned route on.

Anything you skip — or the whole batch, if you run with `--no-interactive`
— gets created on the **Needs Routing** board instead of dropped: a small
holding board (Owner / Due / Status `Needs Review`/`Resolved` / Notes with
the reason and source meeting) in the **Needs Review** group, meant to be
reviewed and manually placed on a regular cadence rather than left to pile
up in terminal scrollback.

The original Needs Routing board sat in the Main workspace and was
archived during the reorg. monday's API has no unarchive mutation and the
board was empty, so it was recreated in the **Continuous Improvement**
workspace, where Chris's own boards live — the Strategic Work Plan
workspace is reserved for the strategic plan itself. The old archived
shell can be deleted from monday.com whenever convenient.

### Owner matching

Owner names in Plaud text are free-form ("Chris", "Kerri"). The script fetches
your monday.com users and matches by exact name, then first-name/token match,
then fuzzy match (`difflib`, cutoff 0.6). Ambiguous or unmatched owners are
never silently guessed — they're flagged with a `⚠` warning in the draft and
left off the People column on push (you assign them manually afterward).

### Due dates

Handles ISO dates, `MM/DD/YYYY`, month-name dates (with or without year),
weekday names, `next <weekday>`, and common relative terms (`ASAP`, `today`,
`tomorrow`, `EOD`, `EOW`, `TBD`). Anything it can't confidently parse is left
blank with a `⚠` warning rather than guessed — a wrong deadline pushed to
monday.com is worse than a missing one.

## Usage

```bash
export MONDAY_API_TOKEN="your monday.com API v2 token"   # Profile → Admin → API

# One file
python3 plaud_monday_sync.py --file meeting.md

# A whole folder of summaries (.md / .txt)
python3 plaud_monday_sync.py --dir ./summaries

# Paste directly
python3 plaud_monday_sync.py
# (paste, then Ctrl-D)

# Draft only, never prompt to push
python3 plaud_monday_sync.py --file meeting.md --no-push

# Push without being asked about unrouted items (send them all to Needs Routing)
python3 plaud_monday_sync.py --file meeting.md --no-interactive
```

### Or: the browser-based version (no terminal needed after setup)

```bash
export MONDAY_API_TOKEN="your monday.com API v2 token"
python3 plaud_monday_sync_web.py
# opens http://127.0.0.1:8765 in your browser automatically
```

This runs a small local server and opens a page where you can drag/drop or
paste in summaries, see the draft, resolve unrouted items with dropdowns
instead of terminal prompts, and push — all in the browser from then on.
It reuses the exact same parsing/routing/column-building code as the CLI
(`plaud_monday_sync.py` is imported, not duplicated), so anything true of
the CLI's behavior above is true here too.

**Why a local server and not just a plain HTML file:** monday.com's API
blocks direct browser-to-API calls (CORS) — there's no way around this on
monday's end, so a pure static page can't call monday.com itself. This
server sits in between: the browser talks to it (same machine, no CORS
issue), and it talks to monday.com server-side. You still need to run one
command to start it, but everything after that is point-and-click.

Options: `--port 8765` (default) and `--no-browser` (don't auto-open a tab).

Without `MONDAY_API_TOKEN` set, the script still parses and prints the draft
(contractor/owner matching just gets skipped, and pushing is disabled) — handy
for eyeballing the parser on a new template before wiring up credentials.

The script always prints the full draft first. If there's anything to push,
and there are unrouted items, it asks where each one (grouped by owner)
should go — see "Unrouted items and Needs Routing" above. After that, it
asks you to type `CONFIRM` before creating anything — nothing is created on
a stray Enter keypress or a typo.

## Try it

Three worked examples are in `samples/`:

```bash
python3 plaud_monday_sync.py --file samples/internal_standup.md --no-push
python3 plaud_monday_sync.py --file samples/contractor_site_visit.md --no-push
python3 plaud_monday_sync.py --file samples/team_meeting_mixed.md --no-push
```

The first has no contractor mention, has no owner mapped to a department
board, and routes entirely to UNROUTED; the second mentions "S&S Forestry"
(a real Contractor Directory entry) and routes to CI Activity Log; the
third has action items for Kyle, Ariel, Kerri, Samantha, a safety concern,
a demo idea, and one person with no department mapping, and shows the
per-item routing splitting across six boards plus one unrouted item. All
three need `MONDAY_API_TOKEN` set to see contractor/owner matching (and
therefore department routing) in the draft — without it, owned items fall
through to UNROUTED since there's no live user data to match against
(safety/demo-idea keyword routing still works without a token, since it
doesn't depend on owner matching).

## If your boards change

Board and column IDs are hardcoded as constants at the top of
`plaud_monday_sync.py` (`TASK_TRACKING_*`, `CI_ACTIVITY_LOG_*`,
`COMMUNICATIONS_*`, `OFFICE_ADMIN_*`, `BOARD_OF_DIRECTORS_*`,
`SAFETY_FEEDBACK_*`, `TRAINING_*`, `NEEDS_ROUTING_*`,
`CONTRACTOR_DIRECTORY_BOARD_ID`, `OWNER_DEFAULT_ROUTE`). If you rename/add
columns in monday.com, update the relevant column ID there — get the
current IDs from monday's board settings or the API's
`boards { columns { id title } }` query. If department leads change, update
`OWNER_DEFAULT_ROUTE` (monday user id → route key); if someone's learned
route needs correcting or removing, edit `learned_routes.json` directly.

**Chris expects most of these boards to get a proper cleanup/revision in
the next few weeks**, now that the note-taker devices make it realistic to
actually keep them current. When that happens, this whole mapping will
likely need a review pass — group IDs, column IDs, and possibly which
boards exist at all may change. Nothing here is designed to be precious;
re-run the same `get_board_info` discovery process against whatever the
boards look like afterward and update the constants accordingly.
