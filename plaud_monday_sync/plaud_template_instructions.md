# Plaud custom template formatting instructions

Copy/paste reference for updating FORSEC's Plaud custom templates, based on
feedback from the first real Planning Meeting template run (2026-07-28).
Paste the relevant blocks into each template's prompt text in Plaud's
template editor.

Test on one template first with `python3 plaud_monday_sync.py --no-push`
before rolling out to all 12 — the parser handles bold/underline formatting
correctly (fixed 2026-07-28), but it's still worth confirming on real output
before touching everything.

## Universal — apply to all 12 templates

**Location/attendees at the top:**
> Immediately after the title, add one line: "Location: [location] —
> Attendees: [names]". This should appear before any other section starts.

**No numbered headers:**
> Do not number section headers (no "1.", "2.", "3.").

**Bold headers, no reliable underline:**
> Format all section headers in bold, using a heading level appropriate to
> make them visually larger than body text.
>
> Note for you (Chris), not Plaud: plain markdown has no native underline
> syntax, and font size isn't independently controllable outside of heading
> level. Bold + a higher heading level (## instead of plain bold text) is
> what's reliably achievable — true underline may or may not render
> depending on how Plaud displays it. Worth checking the actual output
> before assuming underline worked.

**Bold labels in any "Label: value" bullet list** (e.g. Meeting Details —
Date, Event Name, Attendees):
> Format each detail line as **Label:** value (bold the label, not the
> value) — e.g. **Date:** [value], **Event Name:** [value], **Attendees:**
> [value].

**Action Items heading — remove the formatting instruction from the visible heading:**
> Add a heading that says exactly "Action Items" — do not include
> formatting instructions in the heading text itself. Below it, list each
> item as: Task: [text] | Owner: [name] | Due: [date].

**Bold Task/Owner labels in each Action Items row:**
> Bold the Task: and Owner: labels in each Action Items line, e.g. **Task:**
> [text] | **Owner:** [name] | Due: [date].

## Event-planning template specific

**Group brainstormed ideas into categories instead of one flat list:**
> Organize brainstormed ideas into general event-planning categories (e.g.
> Venue & Logistics, Marketing & Promotion, Activities & Programming,
> Budget) as sub-headings, with ideas listed as bullets under each relevant
> category.

**Combine multiple roles per person into one bullet:**
> If a person is assigned more than one role, list them in a single bullet
> separated by commas, not one bullet per role — e.g. "Chris: Setup Lead,
> Registration Coordinator" rather than two separate bullets for Chris.
