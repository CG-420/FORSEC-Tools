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
      **Office & Program Administration**; Kerri Marshall → **Board of
      Directors (ED)**; Samantha Chu → **Training Projects & Programs** (see
      `OWNER_DEFAULT_ROUTE`).
   3. Everything else → **UNROUTED**. It is *not* defaulted to Task Tracking
      — Task Tracking lives in the CI Folder and Chris wants it CI-only, so
      an item with no matching department board is left for manual
      placement rather than guessed onto a board it may not belong on. The
      draft flags these clearly with a `⚠`, and the push step skips them
      entirely (prints what was skipped, creates nothing for them).

   Items that land on a board with a subitems column (Communications,
   Office & Program Administration, Training Projects & Programs) are
   grouped under one parent item per meeting. Boards without a subitems
   column (Board of Directors, Safety Feedback & Ideas) get flat items
   instead — one item per action item, no parent. Unrouted items are never
   pushed anywhere.

### Task Tracking (board `18403136567`) — CI-only, no active trigger

Task Tracking sits in the CI Folder alongside CI Activity Log, and per Chris
it should only ever contain CI-related content. Since contractor meetings
already route entirely to CI Activity Log, there's currently no rule that
sends anything to Task Tracking automatically — it's wired up in the script
(`build_task_tracking_parent_columns`, `PARENT_SUBITEM_BOARDS`) for whenever
a "CI work, but no named contractor" signal gets defined, but the router
doesn't reach it today. If/when that signal exists:

| Plaud field | monday.com target |
|---|---|
| Meeting title | Parent item name |
| — | Parent Status → `Not Started` |
| earliest action item Due date | Parent Deadline |
| source filename + meeting date | Parent Notes |
| Task | Subitem name |
| Owner | Subitem Owner (People column, matched to a monday user) |
| Due | Subitem Date |
| — | Subitem Status → `Working on it` |

Parent items would land in the **This Week** group.

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

The four inferred status fields use simple keyword heuristics (see
`ACTIVITY_TYPE_KEYWORDS` etc. in the script) and are always marked
`(inferred)` in the draft. If no keyword matches, the field is left blank
rather than guessed, and the draft says so explicitly.

### Communications (board `18336748732`) and Office & Program Administration (board `18381184971`)

Same parent-item-per-meeting + subitems-per-action-item pattern described
for Task Tracking above. Communications only has a Status/Date on the
parent (no notes column); Office & Program Administration also gets a
Notes column with the source/meeting date, and its parent Date Due is set
to the earliest action item due date. Parent items land in Communications'
**Tasks** group and Office Admin's **Team Requests** group.

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

### Board of Directors (ED) (board `18386660346`)

No subitems column, so each routed action item becomes its own flat item
(Person / Status / Date) directly in the **Other Tasks** group — no parent
meeting item.

### Safety Feedback & Ideas (board `18418568346`)

Also flat items, but a different shape entirely (it's a submission-intake
board, not a task list): Description (the task text), Date Submitted (the
meeting date), Submission Type (`Safety Feedback` or `Event or Demo Idea`,
whichever keyword matched), Submitted By (the item's owner, or the
recording person if the item has no owner), Status → `New`. Lands in the
**New Submissions** group.

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
```

Without `MONDAY_API_TOKEN` set, the script still parses and prints the draft
(contractor/owner matching just gets skipped, and pushing is disabled) — handy
for eyeballing the parser on a new template before wiring up credentials.

The script always prints the full draft first. If there's anything to push,
it then asks you to type `CONFIRM` before creating anything — nothing is
created on a stray Enter keypress or a typo.

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
`SAFETY_FEEDBACK_*`, `TRAINING_*`, `CONTRACTOR_DIRECTORY_BOARD_ID`,
`OWNER_DEFAULT_ROUTE`). If you rename/add columns in monday.com, update the
relevant column ID there — get the current IDs from monday's board settings
or the API's `boards { columns { id title } }` query. If department leads
change, update `OWNER_DEFAULT_ROUTE` (monday user id → route key).

**Chris expects most of these boards to get a proper cleanup/revision in
the next few weeks**, now that the note-taker devices make it realistic to
actually keep them current. When that happens, this whole mapping will
likely need a review pass — group IDs, column IDs, and possibly which
boards exist at all may change. Nothing here is designed to be precious;
re-run the same `get_board_info` discovery process against whatever the
boards look like afterward and update the constants accordingly.
