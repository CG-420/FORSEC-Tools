# Continuous Improvement page edits

Generates `../Continuous Improvement Page Edits.docx`, the feedback document for
Kyle MacKay on the Continuous Improvement program page at
`forsec.ca/continuousimprovement`.

Built to the FORSEC Word standard: Arial, FORSEC Green headings with a bottom
rule, Dark Green subheads, US Letter, 1 inch margins, logo top left of the
title page, page numbers from page 2.

## Rebuilding

```
npm install docx      # only if it is not already available
node build_edits_doc.js "../Continuous Improvement Page Edits.docx"
```

Suggested replacement copy sits in `quote()` paragraphs, which render indented
with a green left rule so Kyle can tell at a glance which text is meant to be
pasted onto the page. Square brackets mark the places where Chris still owes
content, for example the Phase One results and the mentorship training blurb.

The logo is read from the `forsec-document-standards` skill so the document
always carries the current official mark.
