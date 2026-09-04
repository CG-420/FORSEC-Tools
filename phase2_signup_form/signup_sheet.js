const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, BorderStyle,
  ImageRun, Table, TableRow, TableCell, WidthType, convertInchesToTwip,
} = require("docx");

const GREEN = "338A57";      // FORSEC Green
const DARKGREEN = "3B6E4D";  // Dark Green
const MUTED = "5F6B62";
const LOGO = "/root/.claude/skills/synced/207078e9-4d33-4dad-99a8-2b791688b599_a0b28c24-3dcb-4ca8-9b5e-dd26fbc6e188/forsec-document-standards/assets/Forestry_Sector_Council_Full_Colour_Logo_RGB.png";

const NONE = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const noBorders = { top: NONE, bottom: NONE, left: NONE, right: NONE };
const RULE = { style: BorderStyle.SINGLE, size: 4, color: "999999" };
const BOX = { style: BorderStyle.SINGLE, size: 8, color: "555555" };

const WIDTH = 7.5;  // usable width inside 0.5in margins on US Letter

const t = (text, opts = {}) => new TextRun({ text, font: "Arial", size: 22, ...opts });

const p = (children, opts = {}) =>
  new Paragraph({
    children: Array.isArray(children) ? children : [t(children)],
    spacing: { line: 240, after: 80 },
    ...opts,
  });

const section = (text) =>
  new Paragraph({
    children: [new TextRun({ text, font: "Arial", size: 24, bold: true, color: GREEN })],
    spacing: { before: 200, after: 100 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: GREEN, space: 2 } },
  });

// A write-in field: small grey label, then blank space, then the rule. The
// empty paragraph is what gives a pen somewhere to go; without it the label
// and the rule sit on top of each other.
function field(label, width) {
  return new TableCell({
    width: { size: convertInchesToTwip(width), type: WidthType.DXA },
    borders: { ...noBorders, bottom: RULE },
    margins: { top: 40, bottom: 20, left: 0, right: 140 },
    children: [
      new Paragraph({ children: [t(label, { size: 17, color: MUTED })], spacing: { after: 0 } }),
      new Paragraph({ children: [t("", { size: 26 })], spacing: { after: 0 } }),
    ],
  });
}

const fieldTable = (widths, rows) => new Table({
  columnWidths: widths.map(convertInchesToTwip),
  width: { size: convertInchesToTwip(widths.reduce((a, b) => a + b, 0)), type: WidthType.DXA },
  borders: { ...noBorders, insideHorizontal: NONE, insideVertical: NONE },
  rows,
});

const BOX_W = 0.26;
const TEXT_W = WIDTH - BOX_W;

// A tick box: a small square cell with real borders, then the item text.
// Drawn as a bordered cell rather than a Wingdings glyph so it prints
// reliably on whatever is free in the office that morning.
function tickRow(name, blurb, flag) {
  const text = [t(name, { bold: true }), t("  " + blurb, { color: MUTED, size: 20 })];
  if (flag) text.push(t("  " + flag, { color: DARKGREEN, bold: true, size: 20 }));
  return new TableRow({
    children: [
      new TableCell({
        width: { size: convertInchesToTwip(BOX_W), type: WidthType.DXA },
        borders: { top: BOX, bottom: BOX, left: BOX, right: BOX },
        margins: { top: 20, bottom: 20, left: 0, right: 0 },
        children: [new Paragraph({ children: [t("", { size: 20 })], spacing: { after: 0 } })],
      }),
      new TableCell({
        width: { size: convertInchesToTwip(TEXT_W), type: WidthType.DXA },
        borders: noBorders,
        margins: { top: 20, bottom: 20, left: 130, right: 0 },
        children: [new Paragraph({ children: text, spacing: { after: 0 } })],
      }),
    ],
  });
}

// Borderless row between two tick rows. Without it the bordered box cells
// stack edge to edge and read as one tall column divided by lines, rather
// than as separate boxes you can aim a pen at.
const spacerRow = () => new TableRow({
  children: [0, 1].map((i) => new TableCell({
    width: { size: convertInchesToTwip(i === 0 ? BOX_W : TEXT_W), type: WidthType.DXA },
    borders: noBorders,
    margins: { top: 0, bottom: 0, left: 0, right: 0 },
    children: [new Paragraph({ children: [t("", { size: 12 })], spacing: { after: 0 } })],
  })),
});

function tickTable(items) {
  const rows = [];
  items.forEach((item, i) => {
    if (i > 0) rows.push(spacerRow());
    rows.push(tickRow(...item));
  });
  return new Table({
    columnWidths: [convertInchesToTwip(BOX_W), convertInchesToTwip(TEXT_W)],
    width: { size: convertInchesToTwip(WIDTH), type: WidthType.DXA },
    borders: { ...noBorders, insideHorizontal: NONE, insideVertical: NONE },
    rows,
  });
}

// One sentence each, saying what the thing does rather than what it is called.
// Names stay as they are; the sentence carries the explaining.
const TOOLS = [
  ["Block Reconciliation Tool",
   "Check a finished block against the mill summary to see what each machine actually earned per hour."],
  ["Block Assessment Tool",
   "Walk every block with the same checklist before you sign, so you have real numbers to negotiate the rate."],
  ["Rental Rate Calculator",
   "Work out what it truly costs you to run each machine for an hour, before you agree to a price.",
   "coming in Phase 2"],
  ["ConnecTeam App",
   "Scheduling, field forms and crew messaging on everyone's phone. Free for up to 10 people."],
  ["Team Fuel Incentive Program",
   "Pay drivers a share of the fuel they save. One contractor cut fleet fuel use by 3.31 percent in a quarter."],
  ["Onboarding and Recruiting",
   "A written process for hiring, orienting and keeping new people, instead of starting over every time."],
  ["Sales Brochure",
   "A brochure you put your own logo and photos on, to win work straight from private woodlot owners."],
  ["Website Help",
   "Get a website built so woodlot owners can find you. 13 done for contractors so far."],
  ["Job Board",
   "Post operator and driver openings on a forestry-only board, free, with a social media post for each one."],
];

const PROGRAMS = [
  ["GIS and Telematics",
   "Mapping training, plus tracking on your machines so you can see how they are really being used.",
   "limited seats"],
  ["Operator Training",
   "A faster route to get someone into a seat as a paid apprentice, with the NS Apprenticeship Agency."],
  ["Mentorship Training",
   "Teach your experienced people how to train and coach, over seven weeks of short sessions."],
  ["HR Services",
   "Free HR help on call for hiring, contracts, policies, and any staff problem you would rather not handle alone."],
  ["Lean Training",
   "White, yellow and green belt training in finding and cutting out waste, cost and delay in your operation."],
];

const doc = new Document({
  creator: "Chris Garcelon",
  title: "Sign-Up",
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },           // US Letter
        margin: {
          top: convertInchesToTwip(0.5), bottom: convertInchesToTwip(0.5),
          left: convertInchesToTwip(0.5), right: convertInchesToTwip(0.5),
        },
      },
    },
    children: [
      new Paragraph({
        children: [new ImageRun({ type: "png", data: fs.readFileSync(LOGO),
          transformation: { width: 150, height: 57 } })],
        spacing: { after: 80 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "Sign-Up", font: "Arial", size: 40, bold: true, color: GREEN })],
        spacing: { after: 40 },
      }),
      p([t("Tick anything you would like to hear more about. There is no cost, and nothing here commits you to anything.",
           { color: MUTED, size: 21 })], { spacing: { after: 140 } }),

      fieldTable([3.75, 3.75], [
        new TableRow({ children: [field("Business name", 3.75), field("Your name", 3.75)] }),
      ]),
      fieldTable([2.9, 2.2, 2.4], [
        new TableRow({ children: [field("Email", 2.9), field("Phone", 2.2), field("Location", 2.4)] }),
      ]),

      section("TOOLS"),
      tickTable(TOOLS),

      section("TRAINING AND PROGRAMS"),
      tickTable(PROGRAMS),

      section("SOMETHING ELSE"),
      tickTable([["Something we have not listed",
        "A project you have wanted to get to but never had the time or the people for."]]),
      fieldTable([WIDTH], [
        new TableRow({ children: [field("", WIDTH)] }),
      ]),

      new Paragraph({
        children: [t("GIS and Telematics: limited seats.  ", { bold: true, color: DARKGREEN }),
                   t("This one needs more detail than fits on this sheet, so it works as an application rather than a sign-up. Tick the box and I will be in touch shortly to take those details.",
                     { color: DARKGREEN })],
        spacing: { before: 220, after: 140 },
        indent: { left: convertInchesToTwip(0.14) },
        border: { left: { style: BorderStyle.SINGLE, size: 14, color: GREEN, space: 9 } },
      }),

      new Paragraph({
        children: [t("What happens next:  ", { bold: true }),
                   t("I will get in touch to set you up with whatever you have ticked.")],
      }),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(process.argv[2], buf);
  console.log("wrote", process.argv[2], (buf.length / 1024).toFixed(0) + " KB");
});
