const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  BorderStyle, ImageRun, Footer, PageNumber, LevelFormat, convertInchesToTwip,
} = require("docx");

const GREEN = "338A57";      // FORSEC Green
const DARKGREEN = "3B6E4D";  // Dark Green
const BODY = 22;             // 11pt, half-points
const LOGO = "/root/.claude/skills/synced/forsec-document-standards/assets/Forestry_Sector_Council_Full_Colour_Logo_RGB.png";

const arial = (text, opts = {}) => new TextRun({ text, font: "Arial", size: BODY, ...opts });

// Body paragraph, 1.15 spacing per the FORSEC Word standard.
const p = (children, opts = {}) =>
  new Paragraph({
    children: Array.isArray(children) ? children : [arial(children)],
    spacing: { line: 276, after: 160 },
    ...opts,
  });

// H1: Arial Bold 14pt, green, with a bottom rule.
const h1 = (text) =>
  new Paragraph({
    children: [new TextRun({ text, font: "Arial", size: 28, bold: true, color: GREEN })],
    spacing: { before: 380, after: 180 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: GREEN, space: 4 } },
  });

// H2: Arial Bold 12pt, dark green.
const h2 = (text) =>
  new Paragraph({
    children: [new TextRun({ text, font: "Arial", size: 24, bold: true, color: DARKGREEN })],
    spacing: { before: 260, after: 100 },
  });

const bullet = (children) =>
  new Paragraph({
    children: Array.isArray(children) ? children : [arial(children)],
    numbering: { reference: "dot", level: 0 },
    spacing: { line: 276, after: 100 },
  });

// Suggested wording sits indented with a green left rule so Kyle can see at a
// glance which text is meant to be pasted onto the page.
const quote = (text) =>
  new Paragraph({
    children: [arial(text)],
    indent: { left: convertInchesToTwip(0.35) },
    spacing: { line: 276, after: 140 },
    border: { left: { style: BorderStyle.SINGLE, size: 12, color: GREEN, space: 12 } },
  });

const label = (text) => p([arial(text, { bold: true })], { spacing: { line: 276, after: 60 } });

const doc = new Document({
  creator: "Chris Garcelon",
  title: "Continuous Improvement Page: Suggested Edits",
  numbering: {
    config: [{
      reference: "dot",
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 360, hanging: 220 } } },
      }],
    }],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },          // US Letter
        margin: {
          top: convertInchesToTwip(1), bottom: convertInchesToTwip(1),
          left: convertInchesToTwip(1), right: convertInchesToTwip(1),
        },
      },
      titlePage: true,                                   // no page number on page 1
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 18, color: "5F6B62" })],
        })],
      }),
      first: new Footer({ children: [new Paragraph("")] }),
    },
    children: [
      // ---------------------------------------------------------- title block
      new Paragraph({
        children: [new ImageRun({
          type: "png",
          data: fs.readFileSync(LOGO),
          transformation: { width: 190, height: 72 },
        })],
        spacing: { after: 220 },
      }),
      new Paragraph({
        children: [new TextRun({
          text: "Continuous Improvement Page: Suggested Edits",
          font: "Arial", size: 40, bold: true, color: GREEN,
        })],
        spacing: { after: 80 },
      }),
      new Paragraph({
        children: [arial("Chris Garcelon, Continuous Improvement Specialist  |  For Kyle MacKay  |  August 4, 2026", { color: "5F6B62" })],
        spacing: { after: 60 },
      }),
      new Paragraph({
        children: [arial("forsec.ca/continuousimprovement", { color: "5F6B62" })],
        spacing: { after: 300 },
      }),

      p("Kyle, the page reads well and the session details section is genuinely good. Below are the changes I would like before we start sending contractors to it. The audience is harvesting and trucking contractors in Nova Scotia, so everything here is aimed at making it land with them."),

      // ------------------------------------------------------------- wording
      h1("Wording to change"),

      h2("1. A paragraph appears twice"),
      p("The last paragraph of the opening section and the first paragraph of the Phase Two section are the same sentence, with only the words \"pilot project\" and \"pilot\" different between them. Please delete it from the Phase Two section and keep the flow moving."),

      h2("2. Replace \"pilot\" with \"Phase One\""),
      p("We use Phase One, Phase Two, and Phase Three, not \"pilot\". It appears twice on the page, both times just above a section headed Phase Two, which reads as though they are two different things. They are not."),

      h2("3. The opening is written for a funder, not a contractor"),
      p("The first paragraph describes a \"structured, multi-phase initiative designed to enhance the efficiency, productivity, and long-term sustainability of Nova Scotia's forestry supply chain.\" That is the language we use in a grant application. A contractor reading this on their phone in a truck needs to know four things quickly: what it is, what they get, when it is happening, and what it costs. All four are on the page already, but they are at the bottom."),
      label("Suggested wording for the opening:"),
      quote("If you run a harvesting or trucking operation in Nova Scotia, this program is about making your business work better."),
      quote("We spent Phase One working alongside a group of contractors to find where time and money were leaking out of their operations, then built practical tools and training to fix it. Those are now ready for everyone else."),
      quote("This September we are running three sessions across the province. Come and see what is on offer, pick what is useful to you, and sign up on the spot. There is no cost to take part."),

      h2("4. The framing is bleaker than it needs to be"),
      p("The second paragraph talks about \"the struggles many contractors face\" and helping them stay \"viable and resilient until market conditions improve.\" These are business owners who are proud of what they have built. Telling them they are struggling and need help surviving is not the note to open on, even where it is true."),
      label("Suggested replacement:"),
      quote("Margins are tight across the sector right now. This program is about practical ways to hold on to more of what you earn, and to build the skills your crew needs."),

      h2("5. Take out the Contractors Association sentence"),
      p("The page says the project is being done in partnership with the Nova Scotia Forestry Contractors Association. That agreement is not signed yet, so please remove the sentence for now. I will let you know as soon as we can put it back."),

      // -------------------------------------------------------------- add
      h1("What to add"),

      h2("6. Say what people can actually sign up for"),
      p("The page says \"new tools, training, and resources\" and \"efficiency and improvement training\". Contractors decide based on specifics, so let us name them."),
      label("Suggested new section, headed \"What you can sign up for\":"),
      quote("Mentorship training. [Chris to write one line on what it is and who it suits.] The first group starts in late September in the Port Hawkesbury area."),
      quote("HR services. Help with hiring, contracts, policies, and the day to day people problems most operations handle on their own. We already have a page for this on the site, so please link to it."),
      quote("Phase One improvement tools. The tools we built and tested with contractors. [Chris to pick two or three to name.]"),
      p("We will also mention the GIS and telematics training at the sessions, but the spaces for it are already full, so please do not list it as something people can sign up for."),

      h2("7. Say trucking, more than once"),
      p("The word trucking does not appear anywhere on the page, and neither photo shows a truck. Half the contractors we are trying to reach run trucks. A trucking contractor reading this page would not see themselves in it. The suggested opening above names trucking in the first line, and it should show up again wherever we describe who the program is for."),

      h2("8. Add a short Phase One section"),
      p("The page has a section headed Phase Two but nothing about Phase One. If we name something Phase Two, people expect to know what came before. Phase One results are the strongest reason for anyone to trust this, so a short section with two or three real results would do a lot of work. I will send you the numbers."),

      // ------------------------------------------------------------- photos
      h1("Photos"),

      h2("9. Lead with the log landing photo"),
      p("The photo of the roadside log decks is the better of the two. It is real, it is clearly Nova Scotia, and any contractor will recognise it straight away. I would move it up so it is the first picture people see."),

      h2("10. The photo of the crew in hi-vis is the wrong kind of work"),
      p("The person in the helmet with the face screen and ear protection is doing silviculture or thinning work, not harvesting or trucking. It is a real FORSEC photo, which is much better than a stock image, but it points at a different group than the one we are recruiting. If the 2024 woodlot photo shoot has a shot with a truck, a processor, or a forwarder in it, one of those would fit better."),

      h2("11. Both photos need a line of description attached"),
      p("Every photo on a website can carry a short written description, called alt text. It is what gets read out loud to someone using a screen reader, and it is what Google reads to understand the picture. Both photos on the page currently have none. One short line each is plenty, for example \"Roadside log decks at a Nova Scotia harvest site.\""),

      // ------------------------------------------------------- page setup
      h1("Page setup"),

      h2("12. \"Phase Two\" and \"Session Details\" are not set as headings"),
      p("On screen they look like headings, because they are bold and green. In the page itself they are set up as ordinary paragraphs. That matters for two reasons. People using screen readers move through a page by jumping from heading to heading, so they will skip straight past these. And Google uses headings to work out what a page is about, so we lose some of that too. Setting them as proper headings should be a quick change in the page builder."),

      h2("13. The top of the page has a lot of empty space"),
      p("The large title sits on the left with a big blank area underneath it, while the text runs down the right hand side. On a wide screen that leaves a noticeable gap. Worth tightening up if it is easy."),

      h2("14. The Phase Two block sits unevenly"),
      p("The photo is up at the top right with empty space below it while the text keeps going down the left. Same idea as above, just a balance thing."),

      // ------------------------------------------------------------ sign-up
      h1("The sign-up link"),
      p([
        arial("This is the one that matters most. There is currently no way for anyone to act on the page. There is no form, no button, no email address, and no phone number. If a contractor reads this and wants in, they have nowhere to go, and if I send someone here from a session I lose them."),
      ]),
      p("We already do this elsewhere on the site. The Become a Member button goes to a monday.com form. If we set the sign-up form up the same way, the entries land in monday.com where I am already tracking contractors, which saves me re-typing them."),
      p([
        arial("The form needs to be live before "),
        arial("September 10", { bold: true }),
        arial(", not September 17. Port Hawkesbury is the first session and it sets the pattern for the other two."),
      ]),

      // -------------------------------------------------------- later items
      h1("Leave until later"),
      p("These are not oversights, they are things we do not have yet. No action needed for now."),
      bullet([arial("Venue addresses. "), arial("Truro is confirmed but the other two are not booked yet, so let us add all three at once rather than piecemeal.")]),
      bullet([arial("The sign-up link itself. "), arial("Cannot go on until the form exists.")]),
      bullet([arial("The Contractors Association partnership. "), arial("Goes back on once the agreement is signed.")]),
      bullet([arial("Phase One results. "), arial("I will send you the real numbers for the new section.")]),
      bullet([arial("Funding acknowledgment. "), arial("Everything public facing needs to acknowledge the Canada and Nova Scotia funding and use the approved branding. Can you confirm whether that is already on the page or in the footer?")]),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(process.argv[2], buf);
  console.log("wrote", process.argv[2], (buf.length / 1024).toFixed(0) + " KB");
});
