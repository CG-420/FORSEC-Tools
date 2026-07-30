# Phase 2 Kickoff Tracker

A single-file project tracker for the CI Project Phase 2 kickoff: three regional
advertising sessions in September 2026. Built to keep Kerri Marshall and the
Wavez consultants current on where the project stands.

The deliverable is `../Phase 2 Kickoff Tracker.html`. It is fully self-contained
(logo, background artwork, styles, and script are all inlined), so it can be
emailed as an attachment or dropped on a shared drive and it will open correctly
with no supporting files.

## Using it

Open the HTML file in any browser.

- Click a workstream heading to expand or collapse it.
- Click a task's box to cycle its status: not started, in progress, complete,
  blocked. The colours follow the monday.com board convention.
- Click "Add a note" under any task to type a note.
- Tick contractors as they are re-contacted and set whether they are attending.
- Overwrite any budget figure and the totals and contingency recalculate.
- "Print or save as PDF" produces a clean report with all workstreams expanded
  and the interactive controls hidden.

Ticks, notes, and budget edits save to `localStorage` in whichever browser has
the file open. They do not travel with the file when it is emailed, and the
recipient sees the baseline state. Send the PDF when the current status needs to
travel with it.

## Editing the plan

All content lives in the data block at the top of the `<script>` in
`template.html`: `SESSIONS`, `MILESTONES`, `QUESTIONS`, `WORKSTREAMS`,
`CONTRACTORS`, `BUDGET`, `RISKS`, `DECISIONS`, and `OUT_OF_SCOPE`. Edit those
arrays rather than the markup, then rebuild.

Dates are ISO `YYYY-MM-DD`. Overdue, "due in 14 days", and the countdown are all
computed against the viewer's current date, so the tracker ages on its own.

## Rebuilding

```
python3 build.py
```

This inlines the official FORSEC logo from the `forsec-document-standards`
skill, regenerates the topographic contour background and the conifer treeline,
and writes `../Phase 2 Kickoff Tracker.html`.

The contours are a real marching-squares extraction from a periodic height
field, and the treeline is generated tier by tier per tree, so both tile
seamlessly. Neither needs regenerating unless the artwork should change.

## Sources

Content is drawn from the July 17, 2026 strategic planning meeting summary, the
Phase 2 CI kickoff meeting plan, and the April and May 2026 contractor outreach
report. Where those documents conflict, the July 17 meeting wins: it superseded
the two-session delivery model while leaving the contractor list valid.

Scope is Phase 2 kickoff planning and setup only. The "Deliberately out of
scope" section at the bottom of the tracker lists the live CI work that sits
outside it.
