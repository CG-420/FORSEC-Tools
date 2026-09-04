const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, AlignmentType, BorderStyle,
  ImageRun, Table, TableRow, TableCell, WidthType, convertInchesToTwip,
} = require("docx");

const GREEN = "338A57";      // FORSEC Green
const DARKGREEN = "3B6E4D";  // Dark Green
const MUTED = "5F6B62";
const LOGO = "/root/.claude/skills/synced/207078e9-4d33-4dad-99a8-2b791688b599_a0b28c24-3dcb-4ca8-9b5e-dd26fbc6e188/forsec-document-standards/assets/Forestry_Sector_Council_Full_Colour_Logo_RGB.png";

const NONE = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const noBorders = { top: NONE, bottom: NONE, left: NONE, right: NONE };
const RULE = { style: BorderStyle.SINGLE, size: 4, color: "999999" };
const BOX = { style: BorderStyle.SINGLE, size: 6, color: "555555" };

const t = (text, opts = {}) => new TextRun({ text, font: "Arial", size: 20, ...opts });

const p = (children, opts = {}) =>
  new Paragraph({
    children: Array.isArray(children) ? children : [t(children)],
    spacing: { line: 240, after: 80 },
    ...opts,
  });

// Section heading: Arial bold 11pt green with a green rule under it.
const section = (text) =>
  new Paragraph({
    children: [new TextRun({ text, font: "Arial", size: 22, bold: true, color: GREEN })],
    spacing: { before: 160, after: 80 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: GREEN, space: 2 } },
  });

// A write-in field: small grey label, then blank space, then the rule. The
// empty paragraph is what gives a pen somewhere to go; without it the label
// and the rule sit on top of each other.
function field(label, width) {
  return new TableCell({
    width: { size: convertInchesToTwip(width), type: WidthType.DXA },
    borders: { ...noBorders, bottom: RULE },
    margins: { top: 40, bottom: 20, left: 0, right: 120 },
    children: [
      new Paragraph({ children: [t(label, { size: 15, color: MUTED })], spacing: { after: 0 } }),
      new Paragraph({ children: [t("", { size: 22 })], spacing: { after: 0 } }),
    ],
  });
}

const fieldRow = (pairs) => new TableRow({ children: pairs.map(([l, w]) => field(l, w)) });

const fieldTable = (widths, rows) => new Table({
  columnWidths: widths.map(convertInchesToTwip),
  width: { size: convertInchesToTwip(widths.reduce((a, b) => a + b, 0)), type: WidthType.DXA },
  borders: { ...noBorders, insideHorizontal: NONE, insideVertical: NONE },
  rows,
});

// A tick box: a small square cell with real borders, then the item text.
// Drawn as a bordered cell rather than a glyph so it prints reliably on
// whatever is in the office printer that morning.
function tickRow(name, blurb, flag) {
  const text = [t(name, { bold: true }), t("  " + blurb, { color: MUTED })];
  if (flag) text.push(t("  " + flag, { color: DARKGREEN, bold: true }));
  return new TableRow({
    children: [
      new TableCell({
        width: { size: convertInchesToTwip(0.22), type: WidthType.DXA },
        borders: { top: BOX, bottom: BOX, left: BOX, right: BOX },
        margins: { top: 30, bottom: 30, left: 0, right: 0 },
        children: [new Paragraph({ children: [t("", { size: 18 })], spacing: { after: 0 } })],
      }),
      new TableCell({
        width: { size: convertInchesToTwip(6.6), type: WidthType.DXA },
        borders: noBorders,
        margins: { top: 30, bottom: 30, left: 110, right: 0 },
        children: [new Paragraph({ children: text, spacing: { after: 0 } })],
      }),
    ],
  });
}

const tickTable = (rows) => new Table({
  columnWidths: [convertInchesToTwip(0.22), convertInchesToTwip(6.6)],
  width: { size: convertInchesToTwip(6.82), type: WidthType.DXA },
  borders: { ...noBorders, insideHorizontal: NONE, insideVertical: NONE },
  rows,
});

// Names and order follow the Offering Catalogue board (18428276304) so a
// ticked box maps to one Offerings Requested label with no translation step.
// Where the catalogue name is internal jargon the plain-language name is used
// here and the mapping is recorded in the monday.com form spec.
const TOOLS = [
  ["Block Reconciliation Tool", "see whether a block actually made money"],
  ["Block Assessment Tool", "one standard assessment before you sign"],
  ["Rental Rate Calculator", "your real cost per hour, per machine", "coming in Phase 2"],
  ["ConnecTeam App", "scheduling, forms and comms on your crew's phones"],
  ["Team Fuel Incentive Program", "reward drivers for the fuel they save"],
  ["Onboarding and Recruiting", "a repeatable way to hire and keep good people"],
  ["Sales Brochure", "win work directly from private woodlot owners"],
  ["Website Help", "get found when woodlot owners go looking"],
  ["Job Board", "post operator and driver openings, free"],
];

const PROGRAMS = [
  ["GIS and Telematics", "mapping and machine tracking", "10 seats, apply on the second form"],
  ["Operator Training", "apprenticeship pathway into the seat"],
  ["Mentorship Training", "teach your experienced people how to train others", "cohort 1 starts 22 Sept"],
  ["HR Services", "free HR support for hiring, contracts and policies"],
  ["Lean Training", "white, yellow and green belt"],
];

const doc = new Document({
  creator: "Chris Garcelon",
  title: "Continuous Improvement Sign-Up",
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },           // US Letter
        margin: {
          top: convertInchesToTwip(0.5), bottom: convertInchesToTwip(0.4),
          left: convertInchesToTwip(0.75), right: convertInchesToTwip(0.75),
        },
      },
    },
    children: [
      new Paragraph({
        children: [new ImageRun({ type: "png", data: fs.readFileSync(LOGO),
          transformation: { width: 140, height: 53 } })],
        spacing: { after: 80 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "Continuous Improvement: Sign-Up",
          font: "Arial", size: 32, bold: true, color: GREEN })],
        spacing: { after: 30 },
      }),
      p([t("Tick anything you would like to hear more about. There is no cost, and nothing here commits you to anything.",
           { color: MUTED, size: 18 })], { spacing: { after: 120 } }),

      fieldTable([3.5, 3.5], [
        fieldRow([["Business name", 3.5], ["Your name", 3.5]]),
        fieldRow([["Email", 3.5], ["Phone", 3.5]]),
        fieldRow([["Town", 3.5], ["Best way to reach you (circle): phone / text / email", 3.5]]),
      ]),
      p([t("Which session are you at? (circle one)   ", { size: 18 }),
         t("Port Hawkesbury   /   Bridgewater   /   Truro", { size: 18, color: MUTED })],
        { spacing: { before: 120, after: 40 } }),

      section("TOOLS"),
      tickTable(TOOLS.map(([n, b, f]) => tickRow(n, b, f))),

      section("TRAINING AND PROGRAMS"),
      tickTable(PROGRAMS.map(([n, b, f]) => tickRow(n, b, f))),

      section("SOMETHING ELSE"),
      tickTable([tickRow("Something we have not listed",
        "a project you have wanted to get to but never had the time or the people for")]),
      new Paragraph({
        children: [t("", { size: 22 })],
        border: { bottom: RULE },
        spacing: { before: 60, after: 140 },
        indent: { left: convertInchesToTwip(0.32) },
      }),

      section("YOUR OPERATION"),
      p([t("Rough numbers are fine. This is so we bring the right thing to you, not a survey.",
           { size: 17, color: MUTED })], { spacing: { after: 40 } }),
      fieldTable([1.36, 1.36, 1.36, 1.36, 1.36], [
        fieldRow([["Harvesters", 1.36], ["Forwarders", 1.36], ["Trucks", 1.36],
                  ["Crew vehicles", 1.36], ["Employees", 1.36]]),
      ]),

      new Paragraph({ children: [t("", { size: 12 })], spacing: { after: 60 } }),
      tickTable([tickRow("Call me first for a few starting numbers",
        "how long things take now, fuel, and so on, so we can show what actually changed")]),

      new Paragraph({
        children: [t("If you ticked GIS and Telematics, there is a second short form for that one. There are 10 seats and selection happens after the last session on 17 September, so applying today does not use up a seat. Ask me for the form and we can start it now, or I will call you.",
                     { size: 17, color: DARKGREEN, italics: true })],
        spacing: { before: 140, after: 100 },
        indent: { left: convertInchesToTwip(0.12) },
        border: { left: { style: BorderStyle.SINGLE, size: 12, color: GREEN, space: 8 } },
      }),

      new Paragraph({
        children: [t("What happens next:  ", { size: 17, bold: true, color: MUTED }),
                   t("I will get in touch to set you up with whatever you have ticked. If you also fill in the telematics form, you do not need to repeat your contact details there.",
                     { size: 17, color: MUTED })],
        spacing: { after: 50 },
      }),
      new Paragraph({
        alignment: AlignmentType.LEFT,
        children: [t("Chris Garcelon  |  Continuous Improvement Specialist  |  FORSEC  |  chris@forsec.ca  |  902-893-9582",
                     { size: 16, color: MUTED })],
      }),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(process.argv[2], buf);
  console.log("wrote", process.argv[2], (buf.length / 1024).toFixed(0) + " KB");
});
