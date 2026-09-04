# Phase 2 Contractor Sign-Up

Two ways for a contractor to sign up at the September information sessions, both
landing in the same place: a paper sheet handed out in the room, and a
monday.com form behind a QR code.

Do not confuse this with the **Phase 2 Kickoff Registration** board
(`18426462650`). That is a different form for a different job: registering to
attend an information session. It had 38 registrations as of 4 September and
nothing here touches it. This sign-up is what a contractor fills in *after*
seeing the deck, to ask for the things they want.

The GIS and Telematics application is a third form, owned by Samantha. It is
deliberately not part of this. Telematics appears here as one tick box among the
others, and the application is the follow-up.

## The paper sheet

`signup_sheet.js` generates the sheet. One page, one per person.

```bash
npm install
node signup_sheet.js "Sign-Up Sheet.docx"
```

Tick boxes are drawn as bordered table cells rather than Wingdings glyphs, so
they survive whatever printer is free that morning, with borderless spacer rows
between them so each box reads as a separate box.

## The online form

Live, on **Contractor Directory (Phase 2)** board `18428276306`.

| | |
|---|---|
| Short link | https://wkf.ms/3UIP6nj |
| Form view | `277840698` |
| Form token | `d793a7f13efb95b8b38dee9d089ea930` |
| Group | `topics` ("Contractors") |

It does *not* write to the Signups board. Signups is a junction table: one row is
one contractor wanting one offering, so a single submission with six boxes
ticked becomes six Signups rows. A monday form creates one item per submission
and cannot fan out. That step is manual, and is described at the bottom.

## Field mapping

Paper and online ask the same questions in the same order.

| Sheet | Form question | Column | Column ID |
|---|---|---|---|
| Business name | Business name *(required)* | Name | `name` |
| Your name | Your name *(required)* | Contact Name | `text_mm6wdey6` |
| Email | Email | Email | `email_mm6kpn6x` |
| Phone | Phone *(required)* | Phone | `phone_mm6k2z1r` |
| Location | Location *(required)* | Location | `text_mm6kwrbd` |
| Tick boxes | What are you interested in learning more about? | Offerings Requested | `dropdown_mm6mswx6` |
| write-in line | Anything else we should know? *(last)* | Notes | `long_text_mm6k389k` |

Hidden on the form, set by hand or by automation when processing:

| Column | Value |
|---|---|
| Session `color_mm6khndk` | which session they came from |
| Baseline Consent `color_mm6m16ar` | the starting-point call is assumed, not asked, so this is set when the call happens |
| Engagement Stage `color_mm6k7kyr` | Signed Up |
| Type `color_mm6ve85t` | Contractor |
| Last Contact `date_mm6ksjs` | submission date |
| Harvesters, Forwarders, Transport Trucks, Crew Vehicles, Employees | left for the follow-up call |

Leave **Lead Source** and **Outreach Round** alone. Most people in the room came
through an existing outreach round and already have a row, which is the merge
case below.

## Offerings

Two labels were renamed on 4 September so contractors read plain language,
on both the dropdown and the matching Offering Catalogue items:

- FDAP - Digital Adoption → **Website Creation / Help**
- Performa Rental Rate Calculator → **Rental Rate Calculator**

Two stay on the dropdown but are hidden on the form:

- **PM Whiteboards**, retired.
- **Site Visit**. The catalogue is explicit that contractors have to ask, and it
  is not assumed from a sign-up sheet. Priority goes to contractors signed up
  for two or more offerings, so it cannot be self-served.

The sheet carries a one-sentence explanation of each offering. The form cannot:
monday renders the dropdown's own label text and gives no per-label description,
so the sentences live only on paper. The nearest equivalent online would be
stacking all fifteen into the question description, which reads worse than
nothing.

## After the sessions

Both steps are manual by choice, because submissions arrive on paper and online
and both have to be reconciled by a person who knows the contractors.

**1. Merge against existing rows.** The Directory already holds 99 contractors
from the outreach rounds. Anyone who came through outreach already has a row, so
a submission is an update, not a new contractor. Match on email first, then
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

## Open items

- **Session on the online form.** Hidden, so a QR submission cannot say which
  session it came from. Three links carrying a prefill parameter would fix it,
  but prefilling a hidden question is unverified and testing it means putting a
  real row on a live board. Setting Session by hand while processing costs
  nothing extra, since the merge is manual anyway.
- **Email is the only optional contact field.** Business name, contact name,
  phone and location are all required; some contractors genuinely have no
  email, so that one is not.
- **Lean Training** is on both forms. The catalogue has it as *In development /
  Demo only*. It is there to gauge interest before it is confirmed.
- **Mentorship Training** cohort 1 starts 22 September and Port Hawkesbury
  sign-ups were meant to reach Genevieve MacInnis by 15 September for pre-calls.
  Registration dates will bend for anyone interested, so the sheet does not
  mention a deadline.
