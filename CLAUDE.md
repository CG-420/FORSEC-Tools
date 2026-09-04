# FORSEC-Tools

Staff tools and calculators for the Forestry Sector Council (FORSEC).

Chris Garcelon, Continuous Improvement Specialist, is the author and primary
user. FORSEC document/brand standards live in the `forsec-document-standards`
skill; load it before producing any FORSEC-branded output.

## What's in here

- `FORSEC_Rental_vs_Mileage_Calculator.html` - standalone travel expense
  calculator, opened directly in a browser.
- `plaud_monday_sync/` - turns Plaud AI meeting summaries into monday.com
  action items. See `plaud_monday_sync/README.md` for the full board and
  column mapping, routing rules, and design rationale. Read that before
  changing anything in there.
- `phase2_signup_form/` - the contractor sign-up, paper and online. Read
  `phase2_signup_form/README.md` before touching either.

---

# Before building anything for Phase 2, read this

Most of Phase 2 already exists on monday.com. It was built across several
sessions and it is easy to miss, which has already cost real time once.

**Check monday.com before proposing to build anything there.** `get_board_info`
with `filters.columns.only` suppresses the `views` array, so a board that
already carries a form looks like a bare board. Query `views` explicitly:

```graphql
{ boards(ids: [BOARD_ID]) { views { id name type view_specific_data_str } } }
```

`view_specific_data_str` carries the form token, which `get_form`,
`update_form` and `update_form_question` all need.

**The Phase 2 boards**, all in the Continuous Improvement workspace
(`16763083`), folder `21217377`:

| Board | ID | What it is |
|---|---|---|
| Contractor Directory (Phase 2) | `18428276306` | One row per contractor. Carries the sign-up form. |
| Offering Catalogue | `18428276304` | The 17 offerings, with a baseline metric on each. |
| Signups | `18428276319` | Junction. One row = one contractor wanting one offering. |
| Site Visits | `18428276327` | |
| Action Items | `18428276296` | |
| CI Activity Log (Phase 2) | `18428276309` | |
| Phase 2 Kickoff Registration | `18426462650` | **Different thing.** See below. |

**Two forms exist and they are not the same form.** Confusing them is the
mistake that has already been made:

- **Phase 2 Kickoff Registration** (`18426462650`, form view `275339033`) is
  for registering to *attend* an information session. It asks which session
  you can attend. It had 38 registrations as of 4 September.
- **Sign-Up** (form view `277840698` on the Contractor Directory, short link
  `https://wkf.ms/3UIP6nj`) is what a contractor fills in *after* the session
  to ask for the offerings they want.

The Offering Catalogue is the source of truth for offering names, status and
delivery partner. Read it before writing any contractor-facing list of what
FORSEC provides. Do not write that list from memory.

---

# Where we left off (2026-07-30)

Everything described below is committed and pushed to `main`. Nothing is
half-finished in the working tree.

## The tool works end to end

`plaud_monday_sync/` parses the Action Items section out of a Plaud summary,
routes each item to the right monday.com board, shows a draft, and pushes
only after an explicit confirmation. Two ways to run it:

```bash
cd plaud_monday_sync
export MONDAY_API_TOKEN="..."        # PowerShell: $env:MONDAY_API_TOKEN = "..."
python3 plaud_monday_sync_web.py     # browser UI, opens automatically
python3 plaud_monday_sync.py --file meeting.md --no-push   # CLI, draft only
```

Chris has run a real push successfully. Three Communications items reached
Kyle's board.

## Next task: test the parser against the other templates

This is the open item. The parser has only ever been proven against **one**
real Plaud file (a Timber Queens planning summary, 22 action items, parsed
correctly) plus fixtures written by hand. Chris has **12 custom templates**.
If some of them format the Action Items section differently, the parser will
silently find nothing, which is exactly how two earlier bugs behaved.

The **Plaud MCP connector is now installed** on Chris's account, so a fresh
session can pull real summaries directly instead of him exporting files.
Tools: `list_files`, `get_file`, `get_note`, `get_transcript`,
`get_current_user`.

Suggested opening for the next session:

> Continuing the Plaud to monday.com sync work in FORSEC-Tools. The Plaud MCP
> connector is set up. Pull a few of my recent Plaud summaries covering
> different templates and run them through
> `plaud_monday_sync/plaud_monday_sync.py` in draft mode only, do not push
> anything, so we can see whether the parser handles all 12 templates.

If the Plaud tools are missing, the connector needs a fresh session to load;
starting a new one picks it up.

## Also outstanding

- **Chris has not yet updated his 12 Plaud templates.** Ready-to-paste text
  is in `plaud_monday_sync/plaud_template_instructions.md`. Block A is
  self-contained and goes at the end of any template unchanged. It fixes the
  numbered headers, over-long bullet lists, weak section separation, repeated
  per-person bullets, and the Action Items header that currently carries the
  format description inside it.
- **Kerri Marshall has no board.** Board of Directors (ED) was deleted in the
  monday.com reorg, so her action items deliberately fall through to the
  Needs Routing board for manual placement. Restore a mapping in
  `OWNER_DEFAULT_ROUTE` if she gets a new board.
- **The old archived "Needs Routing" board** (id `18424076669`) still sits in
  the Strategic Work Plan workspace. It is empty and replaced by
  `18424493577` in Continuous Improvement. Safe to delete in monday.com.
- **Samantha Chu plans to review her Training board.** If she changes groups
  or columns, re-check `TRAINING_*` in `plaud_monday_sync.py`. The preflight
  check will flag a deleted or archived board but not a renamed group.
- **Possible next build:** the Plaud CLI (`plaud recent`, `plaud summary
  <id>`) could replace the manual export-and-upload step in the web UI with a
  dropdown of real recordings, and would work for other staff without a
  Claude session. Confirmed commands are recorded at the end of
  `plaud_monday_sync/README.md`. Not started.

## Working notes

- monday.com board ids survive a workspace move, so the 2026-07-29/30 reorg
  did not break the mapping. Groups and columns can still change.
- monday's "when a column changes" automations do not fire on values set
  during item creation, only on a later change to an existing item. This is
  why `_push_ci_activity_log` sets Adoption Signal in a separate follow-up
  call, so the Contractor Participation automation actually triggers.
- Test items created on live boards during development have all been deleted.
- The web UI's artwork is generated, not hand-drawn: see
  `plaud_monday_sync/web/assets/generate_topo.py` and `generate_trees.py`.
