# FORSEC-Tools

Staff tools and calculators for the Forestry Sector Council (FORSEC).

Chris Garcelon, Continuous Improvement Specialist, is the author and primary
user. FORSEC document/brand standards live in the `forsec-document-standards`
skill; load it before producing any FORSEC-branded output.

## What's in here

- `FORSEC_Rental_vs_Mileage_Calculator.html` - standalone travel expense
  calculator, opened directly in a browser.
- `plaud_monday_sync/` - the original Python parser/pusher. **Not currently
  in use** - see "The Python tool" below before touching it.

---

# Current approach: do it in-session with the MCP connectors (decided 2026-09-11)

Chris evaluated three routes and chose this one. Plaud summaries are pulled
with the Plaud connector, turned into monday items with the monday connector,
in a Claude session. No Python, no terminal, no API token.

Rejected, with reasons worth not re-litigating:

- **Email to board.** monday gives every board an email address, but one
  email creates exactly one item: subject becomes the name, body becomes an
  Update comment, and **no columns are populated**. A 29-item meeting would
  land as a single row with the tasks buried in a comment. monday's AI blocks
  cannot rescue it - they operate within a column on one item and cannot fan
  a text blob out into many items.
- **Plaud to Zapier.** Real and would work: Plaud has a "Transcript & Summary
  Ready" trigger and Zapier's monday integration can set column values. Costs
  a paid Zapier tier for the looping needed to create many items from one
  trigger, adds another system to maintain, and parses more crudely.
- **monday AI Notetaker.** A Pro add-on that writes meeting notes natively
  into monday. Costs extra and cannot record in-person site visits, which is
  a large share of CI work. Plaud is the only thing covering a truck cab.

## The procedure

1. `mcp__Plaud__list_files` to find the recording. `page_size` minimum is 10.
2. `mcp__Plaud__get_note` with the file id. **It returns more than one tab.**
   Use the custom template tab (e.g. "Monday Morning Team Meeting"), not the
   default "Summary" tab - see "Which tab" below.
3. Parse the Action Items section. Match owner names against monday users
   (`list_users_and_teams`), resolve dates, keep the raw owner string.
4. Create the meeting record on CI Activity Log (Phase 2).
5. Create one item per action item on Action Items, each linked back to the
   meeting via Source Meeting.
6. **Read every item back and verify.** Not optional - see "Silent failures".
7. Show Chris the result. Draft first and get approval before pushing unless
   he has already said to push.

## Which tab, and why it matters

`get_note` returns one entry per tab in the Plaud app. On the 09-08 test:

- **"Summary"** (Plaud's built-in) groups action items by person with
  checkboxes: `**@Speaker 1**` then `- [ ] task - [TBD]`. It uses speaker
  numbers rather than names and has no Task/Owner/Due structure.
- **"Monday Morning Team Meeting"** (Chris's custom template) uses
  `**Task:** ... | **Owner:** ... | Due: ...`, which is what to parse.

Chris has applied the Block A formatting from
`plaud_monday_sync/plaud_template_instructions.md` to at least this template.
Templates he has not updated yet may not carry the structure.

## Phase 2 board map

Workspace: Continuous Improvement (`16763083`), folder "Phase 2".

**CI Activity Log (Phase 2)** `18428276309`, group `topics` (Meetings and Visits)

| Column | id | Notes |
|---|---|---|
| Date | `date_mm6kf3xt` | |
| Activity Type | `color_mm6k8h29` | Site Visit 0, Phone Call 1, Meeting 2, Training 3, Email 4, Follow-up 5, Issue 6, Kickoff Session 7 |
| Outcome | `color_mm6k2msw` | Positive 0, Neutral 1, Concern 2 |
| Entry Source | `color_mm6kmyhc` | AI Pipeline 0, Manual 1 |
| AI Summary | `long_text_mm6kcpmp` | |
| Decisions | `long_text_mm6kd2t9` | |
| Open Questions | `long_text_mm6m78` | |
| Contractor | `board_relation_mm6ksnqf` | to Contractor Directory (Phase 2) |
| Related Signup | `board_relation_mm6knrtv` | |
| link to Action Items | `board_relation_mm6kkqbz` | auto-fills from the Action Items side |
| Source Recording | `link_mm6kfzs2` | see "Source Recording" below |

**Action Items** `18428276296`, group `topics` (Open Items)

| Column | id | Notes |
|---|---|---|
| Owner | `multiple_person_mm6ke9y3` | people |
| Due | `date_mm6kd6c7` | omit entirely when TBD |
| Status | `color_mm6k4z6c` | To do 0, Doing 1, Done 2, Blocked 3 |
| Source Meeting | `board_relation_mm6k41kp` | to `18428276309` |
| Contractor | `board_relation_mm6k9ar3` | |
| Entry Source | `color_mm6khq9w` | AI Pipeline 0, Manual 1 |
| Review State | `color_mm6kgnmv` | Needs Review 0, Confirmed 1 |
| Raw Owner Text | `text_mm6knbbe` | always populate with the name as written |
| Source Recording | `link_mm6ks8hq` | |

Other Phase 2 boards, not yet wired in: Contractor Directory (Phase 2)
`18428276306`, CI Work Plan `18428276313`, Signups `18428276319`, Site Visits
`18428276327`, Offering Catalogue `18428276304`.

Review State convention used so far: `Confirmed` when the owner matched and a
real due date was parsed, `Needs Review` when the date was TBD or the owner
was uncertain. Entry Source is always `AI Pipeline`.

## Silent failures - the reason step 6 exists

Found the hard way on 2026-09-11, pushing 29 items:

- **Status columns: use `{"index": N}`, never `{"label": "..."}`.** Sending
  `{"label":"Confirmed"}` wrote index 0 ("Needs Review") with no error at all.
  All 14 items meant to be Confirmed were silently wrong. Note that `To do`
  and `AI Pipeline` appeared to work by label, but both are index 0 - which is
  also what a failed write produces, so that proves nothing. Always use index.
- **Relation columns read back as `null` on `text` and `value`.** That is not
  a failure. Query `linked_item_ids` or `linked_items` instead. This nearly
  got reported as a broken link that was working correctly.
- **Newlines cannot be written through the connector.** `\n` inside a
  long_text value returns `DOWNSTREAM_SERVICE_ERROR`. Use inline numbering
  (`1. ... 2. ...`) instead.
- **Question marks and parentheses in long_text also failed.** Rephrase open
  questions as statements. The failure mode is the same opaque downstream
  error, so isolate fields when a write fails rather than guessing.
- **Passing `column_values` as a GraphQL variable fails.** Inline the JSON
  string into the mutation instead.
- Batching ~10 `create_item` calls per mutation with aliases works fine.

## Name aliases

Transcription produces variants. Confirmed by Chris:

- **Kerry = Kerri = Carrie = Kerri Marshall** (`80632035`).

Keep `Raw Owner Text` set to what the transcript actually said, so the
original wording survives even when the assignment is corrected.

Team user ids: Chris Garcelon `82580586`, Kerri Marshall `80632035`, Kyle
MacKay `81506714`, Ariel Durning `82580584`, Samantha Chu `97947987`, Emma
Church `105734480`, Zoe Croke `81506160`, Brock `99172273`.

## Source Recording

Left blank so far. Plaud's API only returns a presigned S3 URL that expires,
and no permanent app URL format has been confirmed. Do not invent one - find
the real format first.

## The Python tool

`plaud_monday_sync/` still works but targets the **Phase 1** boards and is
not in use. Deliberately not repointed at Phase 2: if the MCP route holds up
over a few real meetings it gets retired, and repointing would be wasted.

If it does need repointing, the job is much smaller than the Phase 1 mapping
was. Phase 2 has one central Action Items board rather than per-department
boards, so roughly 40% of the tool is already obsolete: `OWNER_DEFAULT_ROUTE`,
`learned_routes.json`, the Needs Routing board, the interactive routing
prompt, and the web UI's route dropdowns. `Review State: Needs Review` and
`Raw Owner Text` now do what those were built for.

Its `README.md` still documents the Phase 1 mapping and design rationale,
including why CI Activity Log needed a two-step Adoption Signal write.

---

# monday.com notifications muted (2026-09-11)

Chris was still getting daily overdue-item emails from the Phase 1 CI boards.
Root cause: **those boards were never actually archived.** Moving a board into
a folder named "Archive" does not archive it - the board stays active and its
automations keep firing. All seven were `state: active`.

The automations, all notifying Chris:
  - Improvement Steps `7918000318` "Overdue Step Alert", daily 8:30 Halifax
  - Improvements `7918000411` "Overdue Improvement Alert", daily 8:30
  - Contractor Participation `7918495988` "Overdue Contractor Target Alert",
    daily 8:30; plus `7918000807` High Adoption Risk and `7918495884`
    Contractor Blocked, both status-triggered
  - CI Project `502211326` "Original Target Date has passed", daily 12:30

Deactivating them was not possible: the monday connector returns
USER_UNAUTHORIZED on workflow writes, and `502211326` is an older-style
automation the API cannot modify. Instead every Phase 1 board was set to
`CURRENT_USER_MUTE_ALL` via `update_mute_board_settings` - per-user,
reversible, affects only Chris, leaves the automations intact, and covers
every notification source.

Muted: 18403119396, 18403117952, 18403125589, 18373208940, 18403136567,
18403818341, 18403133772. Reverse with the same mutation and `NOT_MUTED`.

# Still outstanding

- **Chris has not updated all 12 Plaud templates.** Paste-ready text is in
  `plaud_monday_sync/plaud_template_instructions.md`. At least the Monday
  Morning Team Meeting template has it applied. Templates without it may not
  produce a parseable Action Items section.
- **Kerri Marshall has no board.** Board of Directors (ED) was deleted in the
  reorg. Under the Phase 2 model this no longer matters much: her items go to
  the shared Action Items board like everyone else.
- **The old archived "Needs Routing" board** (`18424076669`) sits empty in the
  Strategic Work Plan workspace. Safe to delete in monday.com.
- **Samantha Chu plans to review her Training board.** Only affects the Python
  tool, which is not in use.
- **Source Recording link format** still unknown, see above.
