# Plaud custom template instructions

Copy-paste text for updating FORSEC's Plaud custom templates. Nothing here
needs to be inserted at a particular point in an existing prompt: Block A is
self-contained and goes at the end of any template, whatever that template
already says.

Two things to know before starting:

- **Underline is not achievable.** Plaud summaries are markdown, and markdown
  has no underline syntax. Bold plus a heading level is what actually renders.
  The instructions below use `##` headings, which display larger and bolder
  than body text, and that is the closest thing to what was asked for.
- **Test on one template first.** Apply Block A to a single template, record a
  short meeting, and run the result through `plaud_monday_sync.py --no-push`
  before rolling it out to all twelve. Two real parser bugs have already been
  found this way.

---

## Block A: standard formatting (paste into all 12 templates)

Paste this at the very end of each template's prompt, after whatever content
sections that template already defines. It does not reference any specific
section, so it works unchanged across every template.

```
FORMATTING RULES

Write every section header as a markdown heading using "## " followed by the
header text. Do not number the headers. Do not write "1.", "2.", "3." before
any header.

Put one blank line before and one blank line after every header, so sections
are clearly separated.

Immediately below the title, before any other section, add one line in this
exact form:
Location: [location] | Attendees: [names]
If the location was not stated, write "Location: Not stated".

Where a section lists short labelled facts, bold the label only, like this:
**Date:** 2026-07-28
**Event Name:** Timber Queen 2026

Keep bullet lists short. No section should exceed 8 bullets. If a section
would run longer than 8 bullets, group the bullets under "### " sub-headings
by theme, and keep each group to 5 bullets or fewer. Prefer a short sentence
over a bullet when only one or two points are being made.

Never repeat the same point in more than one bullet. Combine related points
into a single bullet instead.

If one person is assigned several things in a list of people, put all of them
in that person's single bullet separated by commas. Do not give a person more
than one bullet.

Write in plain, direct language. Use active voice. Use the Oxford comma. Do
not use em dashes; use a hyphen or rewrite the sentence. Do not use hype
words such as "excited", "thrilled", or "game-changer". Refer to project
stages as "Phase 1", "Phase 2", "Phase 3", never "pilot" or "replication
round".

Ignore small talk, greetings, personal check-ins, weather or weekend chat,
and other off-topic conversation at the start or end of the recording, and do
not include it in any section. Only ignore it when it is purely social and
contains no task, decision, deadline, or commitment. If a task, owner, or due
date is mentioned during otherwise casual conversation, still capture it in
Action Items. When unsure whether something is a real commitment or just
small talk, include it.

ACTION ITEMS SECTION

End the summary with a section whose header is exactly:

## Action Items

Do not add any other words to that header. Do not put the format description
in the header.

Under that header, write one line per action item, in exactly this form:

**Task:** [what needs doing] | **Owner:** [name] | Due: [date or TBD]

Use the person's first name as the Owner. If nobody was assigned, write
UNASSIGNED. If no date was given, write TBD. Do not add bullets, numbering,
or checkboxes before these lines. Do not add any other fields to the line.
```

### Why the Action Items wording is exact

`plaud_monday_sync.py` reads this section. It is tolerant of bold markers and
of a missing `##`, but it depends on the header line beginning with the words
"Action Items", and on each row using the `Task: ... | Owner: ... | Due: ...`
pattern. The current templates put the format description inside the header
("Action Items - format each one exactly as: ..."), which is what Block A
removes.

`UNASSIGNED` and `TBD` are both handled: `UNASSIGNED` is treated as no owner
rather than as a person's name, and `TBD` as no due date.

---

## Block B: complete Event Planning template

This is the whole prompt for the event planning template, rewritten. Replace
that template's entire prompt with everything between the lines.

```
You are producing a planning meeting summary for the Forestry Sector Council.

Write the title as a markdown heading using "# ", in the form:
# [MM-DD] Planning Meeting: [event name]

Immediately below the title, add one line:
Location: [location] | Attendees: [names]
If the location was not stated, write "Location: Not stated".

Then produce these sections, each as a "## " heading, in this order:

## Meeting Details
Short labelled lines with the label bolded:
**Date:** [date]
**Event Name:** [event name]
**Attendees:** [names]

## Event Concept
The theme, purpose, or angle discussed. Maximum 8 bullets.

## Logistics
Venue, date, budget, format, and vendors. Group these under "### " sub-headings
(### Venue, ### Date, ### Budget, ### Format, ### Vendors) with 5 bullets or
fewer under each.

## Brainstormed Ideas
Group every idea under "### " sub-headings by theme, choosing themes that fit
what was discussed, for example ### Venue & Logistics, ### Marketing &
Promotion, ### Activities & Programming, ### Budget & Sponsorship. Keep each
group to 5 bullets or fewer. Do not produce one long flat list.

## Roles Assigned
One bullet per person. If a person has several roles, list them all in that
person's single bullet separated by commas.

## Decisions Made
Decisions the group actually settled on. Maximum 8 bullets.

## Action Items
One line per action item, in exactly this form:

**Task:** [what needs doing] | **Owner:** [name] | Due: [date or TBD]

Use the person's first name as the Owner. If nobody was assigned, write
UNASSIGNED. If no date was given, write TBD. Do not add bullets, numbering,
or checkboxes before these lines. Do not add any other fields to the line.

FORMATTING RULES

Do not number section headers. Put one blank line before and after every
header. Keep bullet lists short and never exceed 8 bullets in a section.
Never repeat a point across bullets.

Write in plain, direct language. Use active voice. Use the Oxford comma. Do
not use em dashes; use a hyphen or rewrite the sentence. Do not use hype
words such as "excited", "thrilled", or "game-changer". Refer to project
stages as "Phase 1", "Phase 2", "Phase 3", never "pilot" or "replication
round".

Ignore small talk, greetings, personal check-ins, weather or weekend chat,
and other off-topic conversation, and do not include it in any section. Only
ignore it when it is purely social and contains no task, decision, deadline,
or commitment. If a task, owner, or due date is mentioned during otherwise
casual conversation, still capture it in Action Items.
```

---

## The other 11 templates

Block A is written to work as-is on all of them, so the fastest route is to
paste it at the end of each template's existing prompt and change nothing
else. That alone fixes the numbered headers, the over-long bullet lists, the
section separation, the repeated-person bullets, and the Action Items header.

If any template needs a full rewrite like Block B, paste its current prompt
into a Claude session and ask for the same treatment. Doing that needs the
template's existing content sections, which are not recorded here.
