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
