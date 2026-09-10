const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3 x 7.5
pres.author = "Stuti Arya";
pres.title = "KYC-NLI Mid-Review";

// ---- Palette: passport indigo, document sand, saffron accent, E/C/N signals
const INK = "16233D";      // deep indigo, dominant
const INK_SOFT = "2C3E63";
const SAND = "F4EFE6";     // document paper
const CREAM = "FFFFFF";
const SAFFRON = "E0873A";  // accent
const MUTED = "6B7280";
const ENTAIL = "2E7D5B";
const CONTRA = "B23A48";
const NEUTRAL = "D99A3C";

const HEAD = "Cambria";
const BODY = "Calibri";

// ---------------------------------------------------------------- helpers
function darkSlide() {
  const s = pres.addSlide();
  s.background = { color: INK };
  return s;
}
function lightSlide(title, kicker) {
  const s = pres.addSlide();
  s.background = { color: CREAM };
  if (kicker) {
    s.addText(kicker.toUpperCase(), {
      x: 0.6, y: 0.36, w: 12.1, h: 0.26, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 11, bold: true, color: SAFFRON, charSpacing: 2,
    });
  }
  s.addText(title, {
    x: 0.6, y: kicker ? 0.62 : 0.5, w: 12.1, h: 0.7, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 32, bold: true, color: INK,
  });
  return s;
}
// The deck's repeated motif: the three-label chip row.
function labelChips(s, x, y, scale = 1.0) {
  const items = [["E", ENTAIL], ["C", CONTRA], ["N", NEUTRAL]];
  items.forEach(([ch, col], i) => {
    s.addShape(pres.ShapeType.ellipse, {
      x: x + i * 0.3 * scale, y, w: 0.24 * scale, h: 0.24 * scale, fill: { color: col },
    });
    s.addText(ch, {
      x: x + i * 0.3 * scale, y, w: 0.24 * scale, h: 0.24 * scale, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 10 * scale, bold: true, color: "FFFFFF", align: "center", valign: "middle",
    });
  });
}
function statCard(s, x, y, w, value, label, valueColor) {
  s.addShape(pres.ShapeType.roundRect, {
    x, y, w, h: 1.5, rectRadius: 0.08,
    fill: { color: SAND }, line: { color: SAND },
  });
  s.addText(value, {
    x: x + 0.15, y: y + 0.18, w: w - 0.3, h: 0.7, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 34, bold: true, color: valueColor || INK, align: "center",
  });
  s.addText(label, {
    x: x + 0.15, y: y + 0.92, w: w - 0.3, h: 0.45, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 11, color: MUTED, align: "center",
  });
}
function footer(s, text) {
  s.addText(text, {
    x: 0.6, y: 6.95, w: 12.1, h: 0.3, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 9, color: MUTED,
  });
}

// ================================================================ 1. TITLE
{
  const s = darkSlide();
  s.addText("KYC-NLI", {
    x: 0.9, y: 2.0, w: 9, h: 1.0, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 54, bold: true, color: CREAM,
  });
  s.addText("Document-Level Natural Language Inference\nfor Identity Verification", {
    x: 0.9, y: 3.0, w: 9, h: 1.1, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 22, color: SAND, lineSpacing: 30,
  });
  s.addShape(pres.ShapeType.rect, {
    x: 0.9, y: 4.35, w: 1.1, h: 0.035, fill: { color: SAFFRON }, line: { color: SAFFRON },
  });
  s.addText("Mid-Review  ·  Stuti Arya  ·  September 2026", {
    x: 0.9, y: 4.65, w: 9, h: 0.35, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 14, color: SAND,
  });
  s.addText("Five Indian scripts  ·  Working system  ·  First empirical results", {
    x: 0.9, y: 5.05, w: 9, h: 0.35, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 13, italic: true, color: SAFFRON,
  });
  labelChips(s, 10.75, 2.15, 1.9);
  s.addText("Entailment\nContradiction\nNeutral", {
    x: 9.9, y: 2.8, w: 2.5, h: 0.85, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 10, color: SAND, align: "center", lineSpacing: 13,
  });
  s.addNotes("Mid-review. Headline: a working system, a real empirical result with confidence intervals, and a reframed central claim.");
}

// =================================================== 2. SINCE REVIEW 1
{
  const s = lightSlide("What changed since Review 1", "Progress");
  s.addText("Review 1 delivered a proposal. This review delivers a running system and a result that changes what we claim.", {
    x: 0.6, y: 1.42, w: 12.1, h: 0.35, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 14, color: MUTED,
  });

  const rows = [
    ["Then — Review 1", "Now — Mid-Review"],
    ["Problem statement and objectives", "Formal task schema, in code"],
    ["12-paper literature review", "All 12 re-verified against source; 4 corrected"],
    ["Claimed 6 contributions", "2 tested against a strong baseline"],
    ["No methodology", "Reproducible protocol, frozen and documented"],
    ["No data", "7,000-instance benchmark, 5 scripts"],
    ["No code", "Running system, 91 passing tests"],
    ["No results", "4 measured noise levels × 2 baselines × 5 languages, with CIs"],
  ];
  const y0 = 2.0, rh = 0.52;
  rows.forEach((r, i) => {
    const isHead = i === 0;
    if (!isHead && i % 2 === 1) {
      s.addShape(pres.ShapeType.rect, {
        x: 0.6, y: y0 + i * rh, w: 12.1, h: rh, fill: { color: SAND }, line: { color: SAND },
      });
    }
    s.addText(r[0], {
      x: 0.75, y: y0 + i * rh, w: 5.6, h: rh, isTextBox: true, margin: 0, valign: "middle",
      fontFace: BODY, fontSize: isHead ? 12 : 13, bold: isHead,
      color: isHead ? SAFFRON : MUTED,
    });
    s.addText(r[1], {
      x: 6.7, y: y0 + i * rh, w: 5.9, h: rh, isTextBox: true, margin: 0, valign: "middle",
      fontFace: BODY, fontSize: isHead ? 12 : 13, bold: isHead || !isHead,
      color: isHead ? SAFFRON : INK,
    });
  });
  s.addNotes("Frame the pivot as progress, not retreat. We tested our own idea and found where it holds.");
}

// =================================================== 3. WHAT IS BUILT
{
  const s = lightSlide("What is built and running today", "The system");

  statCard(s, 0.6, 1.55, 2.85, "7,000", "labelled instances\nacross 5 scripts", INK);
  statCard(s, 3.65, 1.55, 2.85, "91", "tests passing\nlint clean", ENTAIL);
  statCard(s, 6.7, 1.55, 2.85, "5", "Indian languages\n5 distinct scripts", INK);
  statCard(s, 9.75, 1.55, 2.95, "0", "real identity records\nused, by construction", ENTAIL);

  const mods = [
    ["Task schema", "Premise = multi-zone field observations. Hypothesis = one claim. Label = E / C / N."],
    ["Transliteration engines", "Devanagari, Tamil, Bengali, Perso-Arabic. Each returns a variant SET, not one string."],
    ["OCR noise model", "Rates MEASURED from Tesseract across 5 scripts and 4 capture conditions (M1)."],
    ["Benchmark generator", "Minimal-pair contrast groups. Reproducible from a config plus a seed."],
    ["Rule baseline", "ICAO tables, MRZ check digits, cross-field temporal rules, tuned fuzzy match."],
    ["Evaluation harness", "Macro-F1 with bootstrap CIs, paired significance testing, per-language, per-phenomenon."],
  ];
  let y = 3.35;
  mods.forEach(([h, d]) => {
    s.addShape(pres.ShapeType.ellipse, {
      x: 0.63, y: y + 0.06, w: 0.16, h: 0.16, fill: { color: SAFFRON }, line: { color: SAFFRON },
    });
    s.addText(h, {
      x: 0.95, y, w: 2.9, h: 0.3, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12.5, bold: true, color: INK,
    });
    s.addText(d, {
      x: 3.9, y, w: 8.8, h: 0.3, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, color: MUTED,
    });
    y += 0.56;
  });
  footer(s, "The neural model's pipeline is built and its training is running; there is deliberately no model number yet — see slide 7 for why that ordering was the right one.");
  s.addNotes("This is the 'something that works' slide. Everything listed runs on a laptop CPU in seconds.");
}

// =================================================== 4. LANGUAGES
{
  const s = lightSlide("Five scripts, one document", "Scope");
  s.addText("Indian identity documents print the holder's name in English AND a regional script on the same card. The cross-script comparison is therefore in-document, not across two records.", {
    x: 0.6, y: 1.42, w: 12.1, h: 0.5, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 14, color: MUTED,
  });

  const langs = [
    ["en", "Latin", "full", "Control — the zone the others are compared against", MUTED],
    ["hi", "Devanagari", "none", "No authority fixes the answer; holders romanise their own name differently", INK],
    ["ta", "Tamil", "none", "Script does not mark voicing at all: க is K or G, ப is P or B, equally correct", CONTRA],
    ["bn", "Bengali", "none", "Inherent vowel nearer /o/; ya-phala shares a letter with /dʒ/", INK],
    ["ur", "Perso-Arabic", "partial", "Short vowels unwritten: script gives SDYQY, lexicon gives SIDDIQUI", INK],
  ];
  const y0 = 2.15, rh = 0.72;
  s.addText(["Code", "Script", "Normative", "Why it is in the set"].join("          "), {
    x: 0.75, y: y0 - 0.34, w: 12, h: 0.25, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 10.5, bold: true, color: SAFFRON, charSpacing: 1,
  });
  langs.forEach((r, i) => {
    if (i % 2 === 0) {
      s.addShape(pres.ShapeType.rect, {
        x: 0.6, y: y0 + i * rh, w: 12.1, h: rh, fill: { color: SAND }, line: { color: SAND },
      });
    }
    s.addText(r[0], {
      x: 0.78, y: y0 + i * rh, w: 0.8, h: rh, isTextBox: true, margin: 0, valign: "middle",
      fontFace: HEAD, fontSize: 17, bold: true, color: INK,
    });
    s.addText(r[1], {
      x: 1.6, y: y0 + i * rh, w: 1.75, h: rh, isTextBox: true, margin: 0, valign: "middle",
      fontFace: BODY, fontSize: 12.5, color: INK,
    });
    s.addText(r[2], {
      x: 3.4, y: y0 + i * rh, w: 1.2, h: rh, isTextBox: true, margin: 0, valign: "middle",
      fontFace: BODY, fontSize: 12, bold: r[2] === "none", color: r[2] === "none" ? CONTRA : MUTED,
    });
    s.addText(r[3], {
      x: 4.7, y: y0 + i * rh, w: 7.9, h: rh, isTextBox: true, margin: 0, valign: "middle",
      fontFace: BODY, fontSize: 12, color: MUTED,
    });
  });
  s.addText("Four of five have no normative romanisation — the regime where a lookup table cannot win even in principle.", {
    x: 0.6, y: 6.05, w: 12.1, h: 0.4, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 13, bold: true, italic: true, color: INK,
  });
  footer(s, "One Dakshina download (CC BY-SA 4.0) supplies real romanisation pairs for all four non-English languages.");
  s.addNotes("Tamil is the strongest case: the script genuinely underdetermines the romanisation.");
}

// =================================================== 5. THE THREE LABELS
{
  const s = lightSlide("The definition everything turns on", "Task design");
  s.addText("NEUTRAL is a property of the DOCUMENT, not of the model. If it meant \"the model isn't sure\", the three-way task would collapse into binary classification plus a confidence threshold — a solved problem, and not a contribution.", {
    x: 0.6, y: 1.42, w: 12.1, h: 0.6, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 14, color: MUTED,
  });

  const cards = [
    ["ENTAILMENT", ENTAIL, "The evidence, correctly read across scripts and formats, supports the claim.",
     "Regional zone கண்ணன்\nClaim: \"surname is GANNAN\"\n→ Tamil க is K or G. Same name."],
    ["CONTRADICTION", CONTRA, "The evidence refutes it — directly, or by joint impossibility across fields.",
     "Issue 1995 · Expiry 2035\nTemplate: 2020 series\n→ Each field valid. Jointly impossible."],
    ["NEUTRAL", NEUTRAL, "The premise LACKS the evidence to decide. Route to a human.",
     "Surname unreadable, conf. 0.05\nNo other zone carries it\n→ Not contradicted. Undecidable."],
  ];
  cards.forEach(([title, col, desc, ex], i) => {
    const x = 0.6 + i * 4.08;
    s.addShape(pres.ShapeType.roundRect, {
      x, y: 2.2, w: 3.85, h: 3.35, rectRadius: 0.06,
      fill: { color: SAND }, line: { color: SAND },
    });
    s.addShape(pres.ShapeType.ellipse, {
      x: x + 0.25, y: 2.45, w: 0.42, h: 0.42, fill: { color: col }, line: { color: col },
    });
    s.addText(title.charAt(0), {
      x: x + 0.25, y: 2.45, w: 0.42, h: 0.42, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 16, bold: true, color: "FFFFFF", align: "center", valign: "middle",
    });
    s.addText(title, {
      x: x + 0.8, y: 2.47, w: 2.9, h: 0.38, isTextBox: true, margin: 0, valign: "middle",
      fontFace: HEAD, fontSize: 15, bold: true, color: col,
    });
    s.addText(desc, {
      x: x + 0.25, y: 3.05, w: 3.35, h: 0.95, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, color: INK,
    });
    s.addText(ex, {
      x: x + 0.25, y: 4.1, w: 3.35, h: 1.2, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 11, italic: true, color: MUTED, lineSpacing: 15,
    });
  });
  s.addText("The boundary everyone gets wrong:  contradiction requires positive evidence AGAINST. Absence of evidence is never contradiction.", {
    x: 0.6, y: 5.75, w: 12.1, h: 0.4, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 13, bold: true, color: INK,
  });
  footer(s, "Enforced in code: a test fails the build if any NEUTRAL instance carries a legible observation of the claimed field.");
  s.addNotes("This is the answer to the reviewer question 'is Neutral just an abstention threshold?'");
}

// =================================================== 6. THE EXPERIMENT
{
  const s = lightSlide("We built the strongest baseline against our own idea", "Method");
  s.addText("Before training any model, we built what a reviewer would demand: a deterministic rule engine, given every advantage.", {
    x: 0.6, y: 1.42, w: 12.1, h: 0.35, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 14, color: MUTED,
  });

  s.addShape(pres.ShapeType.roundRect, {
    x: 0.6, y: 2.05, w: 5.95, h: 3.55, rectRadius: 0.06,
    fill: { color: SAND }, line: { color: SAND },
  });
  s.addText("The rule engine gets", {
    x: 0.95, y: 2.3, w: 5.3, h: 0.35, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 16, bold: true, color: INK,
  });
  const gets = [
    "ICAO Doc 9303 transliteration tables",
    "Per-script romanisation variant sets",
    "MRZ check-digit verification",
    "Date-format normalisation across zones",
    "Cross-field temporal consistency rules",
    "A tuned fuzzy-match threshold",
    "Its own abstention band",
  ];
  s.addText(gets.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i !== gets.length - 1 } })), {
    x: 0.95, y: 2.75, w: 5.3, h: 2.6, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 12.5, color: INK, paraSpaceAfter: 6,
  });

  s.addShape(pres.ShapeType.roundRect, {
    x: 6.75, y: 2.05, w: 5.95, h: 3.55, rectRadius: 0.06,
    fill: { color: INK }, line: { color: INK },
  });
  s.addText("Why this comes first", {
    x: 7.1, y: 2.3, w: 5.3, h: 0.35, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 16, bold: true, color: SAFFRON,
  });
  s.addText("Every reviewer of this proposal will ask whether the neural approach does anything a rule engine could not.\n\nIf a rule engine wins, the contribution collapses — and it is far better to find that out in week two from 300 lines of code than in month five from a training run.\n\nSo the baseline is built to WIN, and is never weakened to flatter the method.", {
    x: 7.1, y: 2.8, w: 5.3, h: 2.6, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 12.5, color: SAND, lineSpacing: 17,
  });
  footer(s, "The benchmark was then generated at four OCR-noise levels and both baselines run on every one.");
  s.addNotes("Emphasise the methodological maturity: we tried to kill our own idea first.");
}

// =================================================== 7. THE RESULT
{
  const s = lightSlide("The result that reframes the project", "Finding");

  s.addChart(pres.ChartType.line, [
    { name: "Rule engine", labels: ["clean", "light", "moderate", "heavy"], values: [0.981, 0.920, 0.597, 0.361] },
    { name: "Exact match (incumbent)", labels: ["clean", "light", "moderate", "heavy"], values: [0.368, 0.354, 0.252, 0.219] },
  ], {
    x: 0.6, y: 1.5, w: 7.4, h: 4.3,
    showTitle: true, title: "Macro-F1 vs OCR noise (rates MEASURED from Tesseract)", titleFontSize: 13,
    titleColor: INK, titleFontFace: BODY,
    chartColors: [INK, CONTRA],
    lineDataSymbol: "circle", lineDataSymbolSize: 7, lineSize: 3,
    showValue: true, dataLabelPosition: "t", dataLabelFontSize: 10,
    dataLabelColor: MUTED, dataLabelFormatCode: "0.00",
    valAxisMinVal: 0, valAxisMaxVal: 1.0,
    catAxisLabelColor: MUTED, valAxisLabelColor: MUTED,
    catAxisLabelFontSize: 11, valAxisLabelFontSize: 11,
    valGridLine: { color: "E5E5E5", size: 1 },
    catGridLine: { style: "none" },
    showLegend: true, legendPos: "b", legendColor: MUTED, legendFontSize: 11,
  });

  s.addShape(pres.ShapeType.roundRect, {
    x: 8.3, y: 1.5, w: 4.4, h: 1.75, rectRadius: 0.06,
    fill: { color: INK }, line: { color: INK },
  });
  s.addText("0.981", {
    x: 8.5, y: 1.68, w: 4.0, h: 0.75, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 44, bold: true, color: SAFFRON, align: "center",
  });
  s.addText("A deterministic rule engine, on\nnoise-free input. No model involved.", {
    x: 8.5, y: 2.45, w: 4.0, h: 0.6, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 11.5, color: SAND, align: "center", lineSpacing: 15,
  });

  s.addText("What this means", {
    x: 8.3, y: 3.45, w: 4.4, h: 0.32, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 15, bold: true, color: INK,
  });
  const pts = [
    ["There is no headroom on clean input.", CONTRA],
    ["Contrast consistency 0.956 — not gaming surface similarity.", MUTED],
    ["Collapses under real corruption: 0.981 → 0.361 [0.315, 0.404].", INK],
    ["Review load 29% → 85%. It abstains on 79% of decidable cases — the exact gap a learned model is for.", INK],
  ];
  let py = 3.9;
  pts.forEach(([t, c]) => {
    s.addShape(pres.ShapeType.rect, {
      x: 8.3, y: py + 0.07, w: 0.07, h: 0.07, fill: { color: SAFFRON }, line: { color: SAFFRON },
    });
    s.addText(t, {
      x: 8.55, y: py, w: 4.15, h: 0.62, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, color: c, lineSpacing: 15,
    });
    py += 0.72;
  });
  footer(s, "Noise rates MEASURED from Tesseract on shaped renders (M1) — a lower bound on real documents. The earlier hand-built model had deletion 10-17x too low and put moderate at 0.831. 5 languages × 120 identities, seed 20260906.");
  s.addNotes("Lead with the number. 0.980 clean. That kills the original framing and points at the real one.");
}

// =================================================== 8. REVISED CLAIM
{
  const s = darkSlide();
  s.addText("THE REVISED CLAIM", {
    x: 0.9, y: 0.85, w: 11.5, h: 0.3, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 11, bold: true, color: SAFFRON, charSpacing: 2,
  });
  s.addText("Not this", {
    x: 0.9, y: 1.4, w: 5.3, h: 0.32, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 12, bold: true, color: CONTRA,
  });
  s.addText("\"Three-way NLI beats exact string matching\nfor identity verification.\"", {
    x: 0.9, y: 1.78, w: 5.3, h: 0.9, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 15, italic: true, color: "8A93A6", strike: true, lineSpacing: 22,
  });
  s.addText("A rule engine already does that. 0.980.", {
    x: 0.9, y: 2.72, w: 5.3, h: 0.3, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 12, color: "8A93A6",
  });

  s.addShape(pres.ShapeType.roundRect, {
    x: 6.6, y: 1.32, w: 5.8, h: 2.05, rectRadius: 0.06,
    fill: { color: INK_SOFT }, line: { color: SAFFRON, width: 1.5 },
  });
  s.addText("This", {
    x: 6.9, y: 1.5, w: 5.2, h: 0.3, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 12, bold: true, color: ENTAIL,
  });
  s.addText("Under OCR corruption, a learned entailment model recovers decisions a transliteration-aware rule engine must abstain on — reducing human review load at equal or better error rate.", {
    x: 6.9, y: 1.85, w: 5.2, h: 1.35, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 14.5, color: CREAM, lineSpacing: 21,
  });

  const why = [
    ["Falsifiable", "Stands or falls on the risk–coverage curve, with the rule engine's CI as the bar to clear."],
    ["Strong baseline", "The thing to beat is already built, already published in the repo, and hard."],
    ["Untouched by prior work", "Selective prediction under input corruption is not what the ID-verification literature does."],
    ["Operationally meaningful", "Review load is what a KYC team actually pays for."],
  ];
  why.forEach(([h, d], i) => {
    const x = 0.9 + (i % 2) * 5.75;
    const y = 3.85 + Math.floor(i / 2) * 1.35;
    s.addShape(pres.ShapeType.ellipse, {
      x, y: y + 0.03, w: 0.2, h: 0.2, fill: { color: SAFFRON }, line: { color: SAFFRON },
    });
    s.addText(h, {
      x: x + 0.35, y, w: 5.1, h: 0.3, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 13, bold: true, color: SAFFRON,
    });
    s.addText(d, {
      x: x + 0.35, y: y + 0.34, w: 5.1, h: 0.75, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 11.5, color: SAND, lineSpacing: 15,
    });
  });
  s.addNotes("The pivot slide. Two contributions from Review 1 are retired; the surviving claim is sharper and testable.");
}

// =================================================== 9. LITERATURE AUDIT
{
  const s = lightSlide("Literature re-verified against primary sources", "Rigour");
  s.addText("All 12 references checked against the published record. Four needed substantive correction — two of them errors a reviewer would have found first.", {
    x: 0.6, y: 1.42, w: 12.1, h: 0.35, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 14, color: MUTED,
  });

  const corr = [
    ["FakeIDet2", "Year 2026 → 2025, and four wrong EER figures", "numbers"],
    ["Adam & Kliegr", "Cited as a 2024 preprint — it is an IPM 2025 journal paper", "venue"],
    ["Marchesin et al.", "Cited as a survey — it is a special-issue EDITORIAL", "type"],
    ["González & Tapia", "Wrong architecture: serial 2-stage MobileNetV2, not modality-decoupled CNN", "method"],
  ];
  s.addShape(pres.ShapeType.roundRect, {
    x: 0.6, y: 1.95, w: 12.1, h: 2.55, rectRadius: 0.06,
    fill: { color: "FBEEF0" }, line: { color: CONTRA, width: 1 },
  });
  s.addText("Corrected", {
    x: 0.9, y: 2.12, w: 11.5, h: 0.32, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 15, bold: true, color: CONTRA,
  });
  corr.forEach(([n, d, kind], i) => {
    const y = 2.55 + i * 0.46;
    s.addText(n, {
      x: 0.95, y, w: 2.7, h: 0.4, isTextBox: true, margin: 0, valign: "middle",
      fontFace: BODY, fontSize: 12.5, bold: true, color: INK,
    });
    s.addText(kind, {
      x: 3.65, y, w: 1.1, h: 0.4, isTextBox: true, margin: 0, valign: "middle",
      fontFace: BODY, fontSize: 10, bold: true, color: CONTRA,
    });
    s.addText(d, {
      x: 4.85, y, w: 7.7, h: 0.4, isTextBox: true, margin: 0, valign: "middle",
      fontFace: BODY, fontSize: 12, color: MUTED,
    });
  });

  s.addShape(pres.ShapeType.roundRect, {
    x: 0.6, y: 4.65, w: 5.95, h: 1.9, rectRadius: 0.06,
    fill: { color: SAND }, line: { color: SAND },
  });
  s.addText("Verified as cited", {
    x: 0.9, y: 4.82, w: 5.4, h: 0.3, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 14, bold: true, color: ENTAIL,
  });
  s.addText("SGER (ACL 2026 Industry Track) · CDCL-NLI (EMNLP 2025) · Entailed Between the Lines (ACL 2025) · MultiOCR-QA (CIKM '25) · Syauqi & Wibawa (NLP Journal 2025)\n\nOne outstanding: Toprak & Turan's figures remain CANNOT VERIFY.", {
    x: 0.9, y: 5.15, w: 5.4, h: 1.25, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 11, color: INK, lineSpacing: 14,
  });

  s.addShape(pres.ShapeType.roundRect, {
    x: 6.75, y: 4.65, w: 5.95, h: 1.9, rectRadius: 0.06,
    fill: { color: INK }, line: { color: INK },
  });
  s.addText("SGER is now the closest prior work", {
    x: 7.05, y: 4.82, w: 5.4, h: 0.3, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 14, bold: true, color: SAFFRON,
  });
  s.addText("Indian KYC name matching, deployed at 250M-user scale. Same domain as our five-language set. Its stated limits — binary labels, no insufficient-evidence class, names only — are exactly what this project extends.", {
    x: 7.05, y: 5.15, w: 5.4, h: 1.25, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 11.5, color: SAND, lineSpacing: 14,
  });
  s.addNotes("Catching four of your own citation errors before a reviewer does is a credibility gain, not a loss. Say so plainly.");
}

// =================================================== 10. ROADMAP
{
  const s = lightSlide("Roadmap and the single point of failure", "Plan");
  s.addText("The critical path runs through one task. Everything downstream is conditional on it.", {
    x: 0.6, y: 1.42, w: 12.1, h: 0.35, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 14, color: MUTED,
  });

  const ms = [
    ["M0", "Schema, generator, baselines, evaluation harness", "DONE", ENTAIL],
    ["M1", "OCR noise model calibrated against Tesseract", "DONE", ENTAIL],
    ["M2", "Dakshina — engines measured on human romanisations", "DONE", ENTAIL],
    ["M3", "Fine-tuned cross-encoder (Colab / Kaggle GPU)", "", MUTED],
    ["M4", "Selective-prediction analysis, risk–coverage", "", MUTED],
    ["M5", "Human-labelled validation subset, agreement", "", MUTED],
    ["M6", "Ablations and error analysis", "", MUTED],
    ["M7", "Write-up", "", MUTED],
  ];
  const y0 = 2.0, rh = 0.44;
  ms.forEach(([id, t, badge, col], i) => {
    const y = y0 + i * rh;
    s.addShape(pres.ShapeType.ellipse, {
      x: 0.62, y: y + 0.04, w: 0.32, h: 0.32,
      fill: { color: badge ? col : "D8DCE3" }, line: { color: badge ? col : "D8DCE3" },
    });
    s.addText(id, {
      x: 0.62, y: y + 0.04, w: 0.32, h: 0.32, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 9.5, bold: true, color: "FFFFFF", align: "center", valign: "middle",
    });
    s.addText(t, {
      x: 1.12, y, w: 5.5, h: 0.4, isTextBox: true, margin: 0, valign: "middle",
      fontFace: BODY, fontSize: 13, bold: !!badge, color: badge ? INK : MUTED,
    });
    if (badge) {
      s.addText(badge, {
        x: 6.7, y, w: 1.3, h: 0.4, isTextBox: true, margin: 0, valign: "middle",
        fontFace: BODY, fontSize: 10, bold: true, color: col,
      });
    }
  });

  s.addShape(pres.ShapeType.roundRect, {
    x: 8.35, y: 2.0, w: 4.35, h: 3.5, rectRadius: 0.06,
    fill: { color: INK }, line: { color: INK },
  });
  s.addText("What M1 found", {
    x: 8.65, y: 2.22, w: 3.8, h: 0.35, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 16, bold: true, color: SAFFRON,
  });
  s.addText("Our OCR noise model is hand-built from documented per-script failure modes — matra loss, Perso-Arabic dot loss, homoglyphs. It has NOT been calibrated against a real OCR engine.\n\nThe direction of the finding is robust: it follows from the rule engine's brittleness to unparsable strings.\n\nThe magnitude is not yet trustworthy. Calibration against Tesseract on MIDV-2020 comes before any model is trained.", {
    x: 8.65, y: 2.68, w: 3.8, h: 2.6, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 11.5, color: SAND, lineSpacing: 15,
  });
  s.addText("Remaining risk: rendered text has no paper grain, glare or perspective, so the measured rates are a stated LOWER BOUND on real documents. M1b adds a second engine and a real-document correction factor.", {
    x: 0.6, y: 5.75, w: 7.4, h: 0.6, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 12, italic: true, color: MUTED, lineSpacing: 15,
  });
  s.addNotes("Naming your own single point of failure before a reviewer does is the strongest position available.");
}

// =================================================== 11. DEMO / CLOSE
{
  const s = darkSlide();
  s.addText("It runs. Now.", {
    x: 0.9, y: 1.0, w: 8.0, h: 0.7, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 38, bold: true, color: CREAM,
  });
  s.addText("No GPU required. Clean checkout to results in under a minute.", {
    x: 0.9, y: 1.75, w: 11.5, h: 0.35, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 14, color: SAND,
  });

  s.addShape(pres.ShapeType.roundRect, {
    x: 0.9, y: 2.35, w: 11.5, h: 1.75, rectRadius: 0.06,
    fill: { color: "0D1729" }, line: { color: INK_SOFT },
  });
  s.addText("kyc-nli languages          # the five scripts and why each is in the set\nkyc-nli generate           # build the 7,000-instance benchmark\nkyc-nli compare            # score every baseline\nkyc-nli inspect --language ta   # read real instances before trusting a number", {
    x: 1.2, y: 2.6, w: 10.9, h: 1.3, isTextBox: true, margin: 0,
    fontFace: "Courier New", fontSize: 12.5, color: "9FE8C4", lineSpacing: 20,
  });

  const closing = [
    ["What we can defend today", "A working system, a 7,000-instance benchmark across five Indian scripts, a strong baseline, and a reproducible protocol."],
    ["What we learned", "The original framing does not survive contact with a good baseline. The revised one is sharper and falsifiable."],
    ["What comes next", "Calibrate the noise model, swap in Dakshina, then train."],
  ];
  let cy = 4.4;
  closing.forEach(([h, d]) => {
    s.addShape(pres.ShapeType.rect, {
      x: 0.9, y: cy + 0.08, w: 0.08, h: 0.08, fill: { color: SAFFRON }, line: { color: SAFFRON },
    });
    s.addText(h, {
      x: 1.2, y: cy, w: 3.5, h: 0.3, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12.5, bold: true, color: SAFFRON,
    });
    s.addText(d, {
      x: 4.8, y: cy, w: 7.6, h: 0.6, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, color: SAND, lineSpacing: 15,
    });
    cy += 0.72;
  });
  labelChips(s, 11.2, 1.08, 1.6);
  s.addNotes("Close on the demo. Offer to run it live — kyc-nli compare takes about ten seconds.");
}

pres.writeFile({ fileName: "KYC-NLI-Mid-Review.pptx" })
  .then(f => console.log("wrote", f));
