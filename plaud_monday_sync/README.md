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

Routing decision: **if the summary text mentions a contractor by name from
the Contractor Directory board, it routes to CI Activity Log. Otherwise it
routes to Task Tracking.**

### Task Tracking (board `18403136567`)

One parent item per meeting summary, one subitem per action item.

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

Parent items land in the **This Week** group. Task Tracking has no top-level
Owner/People column — only its subitems do — so per-task ownership only
shows up at the subitem level, matching the board's existing structure.

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

Two worked examples are in `samples/`:

```bash
python3 plaud_monday_sync.py --file samples/internal_standup.md --no-push
python3 plaud_monday_sync.py --file samples/contractor_site_visit.md --no-push
```

The first has no contractor mention and routes to Task Tracking; the second
mentions "S&S Forestry" (a real Contractor Directory entry) and routes to CI
Activity Log. Both need `MONDAY_API_TOKEN` set to see contractor/owner
matching in the draft — without it you'll still see the parsed tasks/owners/
dates, just unmatched.

## If your boards change

Board and column IDs are hardcoded as constants at the top of
`plaud_monday_sync.py` (`TASK_TRACKING_*`, `CI_ACTIVITY_LOG_*`,
`CONTRACTOR_DIRECTORY_BOARD_ID`). If you rename/add columns in monday.com,
update the relevant column ID there — get the current IDs from monday's
board settings or the API's `boards { columns { id title } }` query.
