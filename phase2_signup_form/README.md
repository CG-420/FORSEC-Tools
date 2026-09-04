# Phase 2 Contractor Sign-Up

Two ways for a contractor to sign up at the September information sessions, both
landing in the same place: a paper sheet handed out in the room, and a
monday.com form behind a QR code.

There is a third form, the GIS and Telematics application, which Samantha owns.
It is deliberately not part of this. Telematics appears here as one tick box
among the others, and the application is the follow-up.

## The paper sheet

`signup_sheet.js` generates `CI Sign-Up Sheet.docx`. One page, one per person.

```bash
npm install
node signup_sheet.js "CI Sign-Up Sheet.docx"
```

Tick boxes are drawn as bordered table cells rather than Wingdings glyphs, so
they survive whatever printer is free that morning.

## Where submissions land

Both routes write **one row per contractor** to **Contractor Directory (Phase 2)**,
board `18428276306`, group `topics` ("Contractors"), in the Continuous
Improvement workspace.

They do *not* write to the Signups board. Signups is a junction table: one row is
one contractor wanting one offering, so a single form submission with six boxes
ticked becomes six Signups rows. A monday form creates one item per submission
and cannot fan out. The fan-out is a separate step, described at the bottom.

## Field mapping

Paper and online use identical wording so the two merge without translation.

| Question | Column | Column ID | Type |
|---|---|---|---|
| Business name | Name | `name` | name |
| Your name | **Contact Name** | *needs creating* | text |
| Email | Email | `email_mm6kpn6x` | email |
| Phone | Phone | `phone_mm6k2z1r` | phone |
| Town | Location | `text_mm6kwrbd` | text |
| Best way to reach you | **Preferred Contact** | *needs creating* | status |
| Which session are you at | Session | `color_mm6khndk` | status |
| Tick boxes (all of them) | Offerings Requested | `dropdown_mm6mswx6` | dropdown |
| Something we have not listed | Notes | `long_text_mm6k389k` | long text |
| Harvesters | Harvesters | `numeric_mm6merc9` | numbers |
| Forwarders | Forwarders | `numeric_mm6mzy2p` | numbers |
| Trucks | Transport Trucks | `numeric_mm6m9dhy` | numbers |
| Crew vehicles | Crew Vehicles | `numeric_mm6mjf8z` | numbers |
| Employees | Employees | `numeric_mm6mq37b` | numbers |
| Call me first for a few starting numbers | Baseline Consent | `color_mm6m16ar` | status |

Two columns do not exist yet and have to be created before the form is built:

- **Contact Name** (text). The board keys on company name, so the human being
  who filled the sheet in currently has nowhere to go.
- **Preferred Contact** (status: Phone, Text, Email).

Set by automation on submission rather than asked:

| Column | Value |
|---|---|
| Engagement Stage `color_mm6k7kyr` | Signed Up |
| Type `color_mm6ve85t` | Contractor |
| Last Contact `date_mm6ksjs` | submission date |
| Attended On `date_mm6mjgej` | submission date, session route only |

Leave **Lead Source** and **Outreach Round** alone. Most people in the room came
through an existing outreach round and already have a row, which is the merge
case below.

## Offering label mismatch

The paper sheet uses plain language. The `Offerings Requested` dropdown uses
internal names, and a monday form displays the column's own labels verbatim, so
online the contractor would read the internal ones.

| Sheet says | Dropdown says |
|---|---|
| Rental Rate Calculator | Performa Rental Rate Calculator |
| Website Help | FDAP - Digital Adoption |
| Operator Training | Operator Training - Enhanced Direct Entry |
| Onboarding and Recruiting | Onboarding & Recruiting |
| GIS and Telematics | GIS & Telematics |
| Something we have not listed | Custom Improvement Support |

Recommendation: rename the six dropdown labels to the sheet wording. Renaming a
label preserves existing values, and nothing is recorded against these yet.
"FDAP" in particular means nothing to a contractor.

Two labels stay on the dropdown but must be **hidden on the form**:

- **PM Whiteboards**, retired.
- **Site Visit**. The catalogue is explicit that contractors have to ask, and it
  is not assumed from a sign-up sheet. Priority goes to contractors who signed
  up for two or more offerings, so it cannot be self-served.

## Form settings

- Title: **Continuous Improvement: Sign-Up**
- Shortened intro from the sheet: "Tick anything you would like to hear more
  about. There is no cost, and nothing here commits you to anything."
- No login required, one submission per person, no monday branding.
- Question order matches the sheet exactly: contact, session, tools, training
  and programs, something else, your operation, baseline consent.
- Only Business name, Email and Phone required. Everything else optional, on the
  same reasoning as the paper sheet: signing up has to be easy.
- Conditional rule: when GIS and Telematics is ticked, show the note about ten
  seats and selection after 17 September.
- Confirmation message repeats the "what happens next" line from the sheet.
- Print the QR code on the sheet footer, the session slides, and a table card.

## After the sessions

Two steps, in this order.

**1. Merge against existing rows.** The Directory already holds 99 contractors
from the outreach rounds. Anyone who came through outreach already has a row, so
a form submission is an update, not a new contractor. Match on email first, then
phone, then business name. Merge into the existing row and keep its Outreach
Round and Lead Source. Only create a row for a genuinely new name.

**2. Fan out to Signups.** For each label in Offerings Requested, create one row
on Signups `18428276319` with:

| Signups column | Value |
|---|---|
| Contractor `board_relation_mm6k3cyg` | the Directory row |
| Offering `board_relation_mm6kvf4t` | the Offering Catalogue row |
| Status `color_mm6kwf1x` | Interested |
| Capture Source `color_mm6kjnc6` | Session form, or Online form |
| Session `color_mm6k63re` | as submitted |
| Signed Up Date `date_mm6kna5x` | submission date |
| Count `numeric_mm6kazpj` | 1 |
| Baseline Status `color_mm6m2bkz` | Pending if consent given, else Not needed |

`Count` must be set or the Directory's `# Signups` rollup stays at zero.

This fan-out is the obvious thing to script next, against the same monday API
the Plaud sync already uses. Doing it by hand for three sessions is the reason
to build it.

## Open decisions

- **Lean Training** is on the sheet, but the catalogue has it as *In development
  / Demo only* and flags the open question of whether belt training is on the
  sign-up sheet this round. Taking sign-ups for something with no delivery date
  is a promise. Decide before printing.
- **Rental Rate Calculator** is *In development*. The sheet says "coming in
  Phase 2" rather than dropping it, since it was named the top Phase 2 priority.
- **Mentorship Training** has a hard deadline: Port Hawkesbury sign-ups must
  reach Genevieve MacInnis by **15 September** for the pre-calls, and cohort 1
  starts 22 September. The Port Hawkesbury sheets need processing the same week,
  not after all three sessions.
- **Operations** (`dropdown_mm6kbtgz`: harvesting, trucking, silviculture,
  roadbuilding, firewood, tree service) is not asked on either form. One more
  line would fill it and it drives most useful filtering. Left off for now
  because the fleet counts imply most of it.
