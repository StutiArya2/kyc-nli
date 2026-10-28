// docs/PRESENTER-GUIDE.md -> .docx. Called by scripts/build_presenter_docs.py.
//
//   cd scripts && npm install docx      (once)
//   node scripts/presenter_docx.js docs/PRESENTER-GUIDE.md out.docx
//
// Handles the markdown subset the guide uses: headings, paragraphs with
// bold/italic/code spans, bullet lists, blockquotes, fenced code and tables.

const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  LevelFormat, convertInchesToTwip,
} = require("docx");

const [, , SRC, OUT] = process.argv;
if (!SRC || !OUT) {
  console.error("usage: node presenter_docx.js <source.md> <out.docx>");
  process.exit(2);
}

const CONTENT_WIDTH = convertInchesToTwip(6.5); // US Letter, 1" margins
const BODY = "Calibri";
const MONO = "Consolas";

function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let last = 0;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ ...base, text: text.slice(last, m.index) }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ ...base, text: t.slice(2, -2), bold: true }));
    else if (t.startsWith("`")) out.push(new TextRun({ ...base, text: t.slice(1, -1), font: MONO, size: 20 }));
    else out.push(new TextRun({ ...base, text: t.slice(1, -1), italics: true }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ ...base, text: text.slice(last) }));
  return out.length ? out : [new TextRun({ ...base, text: "" })];
}

function table(rows) {
  const cols = rows[0].length;
  const w = Math.floor(CONTENT_WIDTH / cols);
  const widths = Array(cols).fill(w);
  widths[cols - 1] = CONTENT_WIDTH - w * (cols - 1); // column widths must sum exactly
  return new Table({
    columnWidths: widths,
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    rows: rows.map((r, i) => new TableRow({
      tableHeader: i === 0,
      children: r.map((c, j) => new TableCell({
        width: { size: widths[j], type: WidthType.DXA },
        shading: i === 0 ? { type: ShadingType.CLEAR, fill: "EEEEEE", color: "auto" } : undefined,
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        children: [new Paragraph({ spacing: { before: 0, after: 0 },
          children: runs(c, i === 0 ? { bold: true } : {}) })],
      })),
    })),
  });
}

const lines = fs.readFileSync(SRC, "utf8").split(/\r?\n/);
const children = [];
let i = 0;
while (i < lines.length) {
  const line = lines[i];
  if (!line.trim()) { i++; continue; }

  if (line.startsWith("```")) {
    i++;
    const body = [];
    while (i < lines.length && !lines[i].startsWith("```")) body.push(lines[i++]);
    i++;
    body.forEach((l, n) => children.push(new Paragraph({
      spacing: { before: n === 0 ? 120 : 0, after: n === body.length - 1 ? 160 : 0 },
      shading: { type: ShadingType.CLEAR, fill: "F4F4F4", color: "auto" },
      children: [new TextRun({ text: l || " ", font: MONO, size: 19 })],
    })));
    continue;
  }

  if (line.trim().startsWith("|")) {
    const rows = [];
    while (i < lines.length && lines[i].trim().startsWith("|")) {
      const cells = lines[i].trim().replace(/^\||\|$/g, "").split("|").map((s) => s.trim());
      if (!cells.every((c) => /^:?-{2,}:?$/.test(c))) rows.push(cells);
      i++;
    }
    children.push(table(rows));
    children.push(new Paragraph({ spacing: { after: 160 }, children: [] }));
    continue;
  }

  const h = line.match(/^(#{1,3})\s+(.*)$/);
  if (h) {
    const n = h[1].length;
    children.push(new Paragraph({
      heading: n === 1 ? HeadingLevel.TITLE : n === 2 ? HeadingLevel.HEADING_1 : HeadingLevel.HEADING_2,
      spacing: { before: n === 1 ? 0 : 320, after: 140 },
      children: runs(h[2]),
    }));
    i++;
    continue;
  }

  if (line.startsWith(">")) {
    const body = [];
    while (i < lines.length && lines[i].startsWith(">")) body.push(lines[i++].replace(/^>\s?/, ""));
    children.push(new Paragraph({
      spacing: { before: 120, after: 200 },
      indent: { left: convertInchesToTwip(0.25) },
      border: { left: { style: BorderStyle.SINGLE, size: 18, color: "999999", space: 12 } },
      children: runs(body.join(" ")),
    }));
    continue;
  }

  if (/^[-*]\s+/.test(line)) {
    while (i < lines.length && /^[-*]\s+/.test(lines[i])) {
      children.push(new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        spacing: { after: 100 },
        children: runs(lines[i].replace(/^[-*]\s+/, "")),
      }));
      i++;
    }
    children.push(new Paragraph({ spacing: { after: 80 }, children: [] }));
    continue;
  }

  children.push(new Paragraph({ spacing: { after: 180 }, children: runs(line) }));
  i++;
}

const doc = new Document({
  title: "KYC-NLI: Plain-English Walkthrough",
  styles: {
    default: {
      document: { run: { font: BODY, size: 22 }, paragraph: { spacing: { line: 300 } } },
      title: { run: { font: BODY, size: 40, bold: true, color: "1A1A1A" } },
      heading1: { run: { font: BODY, size: 30, bold: true, color: "1A1A1A" } },
      heading2: { run: { font: BODY, size: 24, bold: true, color: "333333" } },
    },
  },
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: convertInchesToTwip(0.3), hanging: convertInchesToTwip(0.2) } } },
      }],
    }],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 },
      },
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log(`wrote ${OUT} (${Math.round(buf.length / 1024)} KB)`);
});
