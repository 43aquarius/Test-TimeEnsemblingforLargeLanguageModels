// Word version of the paper - journal manuscript style (English, Times New Roman)
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  ImageRun, Header, Footer, PageNumber, NumberFormat,
  AlignmentType, HeadingLevel, WidthType, BorderStyle, ShadingType,
} = require("docx");
const fs = require("fs");
const ROOT = require("path").resolve(__dirname, "../..");

const R = JSON.parse(fs.readFileSync(ROOT + "/results/analysis/results.json", "utf8"));
const POOLED = JSON.parse(fs.readFileSync(ROOT + "/results/analysis/pooled.json", "utf8"));

const MODELS = ["qwen3.8-max", "qwen3.8-omni", "agnes-3.0-flash", "agnes-2.5-flash", "gpt-6-luna", "gemini-3.8-flash"];
const LABEL = { "qwen3.8-max": "Qwen3.8-Max", "qwen3.8-omni": "Qwen3.8-Omni", "agnes-3.0-flash": "Agnes3.0-Flash",
  "agnes-2.5-flash": "Agnes2.5-Flash", "gpt-6-luna": "GPT-6-Luna", "gemini-3.8-flash": "Gemini3.8-Flash" };
const FAM = { "qwen3.8-max": "Qwen", "qwen3.8-omni": "Qwen", "agnes-3.0-flash": "Agnes",
  "agnes-2.5-flash": "Agnes", "gpt-6-luna": "GPT", "gemini-3.8-flash": "Gemini" };
const TIER = { "qwen3.8-max": "flagship", "qwen3.8-omni": "multimodal", "agnes-3.0-flash": "fast",
  "agnes-2.5-flash": "reasoning", "gpt-6-luna": "reasoning", "gemini-3.8-flash": "fast" };
const DS_ORDER = ["gsm8k", "sat_math", "piqa", "truthfulqa", "lsat_lr", "logiqa"];
const DS_LABEL = { gsm8k: "GSM8K", logiqa: "LogiQA", lsat_lr: "LSAT-LR", sat_math: "SAT-Math", piqa: "PIQA", truthfulqa: "TruthfulQA" };

const pct = (x, d = 1) => (x === null || x === undefined) ? "--" : (100 * x).toFixed(d);
const f3 = (x) => (x === null || x === undefined) ? "--" : x.toFixed(3);

function runsFromMarkup(text, opts = {}) {
  const runs = [];
  const parts = text.split("*");
  parts.forEach((p, i) => {
    if (!p) return;
    runs.push(new TextRun({
      text: p, italics: i % 2 === 1, size: opts.size || 24,
      bold: opts.bold || false, color: "000000",
      font: { ascii: "Times New Roman", eastAsia: "SimSun" },
    }));
  });
  return runs.length ? runs : [new TextRun({ text: " ", size: opts.size || 24 })];
}
function body(text, opts = {}) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { line: 360, after: 120 },
    children: runsFromMarkup(text, opts),
  });
}
function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    alignment: AlignmentType.LEFT,
    spacing: { before: 360, after: 180, line: 360 },
    children: [new TextRun({ text, bold: true, size: 28, color: "000000",
      font: { ascii: "Times New Roman", eastAsia: "SimHei" } })],
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    alignment: AlignmentType.LEFT,
    spacing: { before: 280, after: 140, line: 360 },
    children: [new TextRun({ text, bold: true, size: 26, color: "000000",
      font: { ascii: "Times New Roman", eastAsia: "SimHei" } })],
  });
}
function caption(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 80, after: 240, line: 312 },
    children: runsFromMarkup(text, { size: 21 }),
  });
}
function tableTitle(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    keepNext: true,
    spacing: { before: 240, after: 80, line: 312 },
    children: runsFromMarkup(text, { size: 21 }),
  });
}
const sizeOf = require("image-size");
function figureImage(pngPath, widthPx) {
  const buf = fs.readFileSync(pngPath);
  const dim = sizeOf.imageSize ? sizeOf.imageSize(buf) : sizeOf(buf);
  const w = widthPx;
  const h = Math.round(w * dim.height / dim.width);
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    keepNext: true,
    spacing: { before: 200, after: 60 },
    children: [new ImageRun({ data: buf, transformation: { width: w, height: h }, type: "png" })],
  });
}
const CELL_MARGINS = { top: 50, bottom: 50, left: 90, right: 90 };
const NONE = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const TOPBOT = { style: BorderStyle.SINGLE, size: 8, color: "000000" };

function threeLineTable(headerCells, rows, colWidths, fontSize = 18) {
  const mkCell = (content, bold, align, w) => new TableCell({
    children: [new Paragraph({
      alignment: align || AlignmentType.CENTER,
      spacing: { line: 276 },
      children: [new TextRun({ text: String(content), bold: !!bold, size: fontSize, color: "000000",
        font: { ascii: "Times New Roman", eastAsia: "SimSun" } })],
    })],
    margins: CELL_MARGINS,
    width: { size: w, type: WidthType.PERCENTAGE },
  });
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: { top: TOPBOT, bottom: TOPBOT, left: NONE, right: NONE, insideHorizontal: NONE, insideVertical: NONE },
    rows: [
      new TableRow({
        tableHeader: true, cantSplit: true,
        children: headerCells.map((t, i) => mkCell(t, true, i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER, colWidths[i])),
      }),
      ...rows.map(r => new TableRow({
        cantSplit: true,
        children: r.map((t, i) => mkCell(t, false, i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER, colWidths[i])),
      })),
    ],
  });
}
function refPara(num, text) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { line: 312, after: 60 },
    indent: { left: 480, hanging: 480 },
    children: [new TextRun({ text: `[${num}] ${text}`, size: 21, color: "000000",
      font: { ascii: "Times New Roman", eastAsia: "SimSun" } })],
  });
}

module.exports = { Document, Packer, Paragraph, TextRun, Header, Footer, PageNumber, NumberFormat,
  AlignmentType, HeadingLevel, fs, R, POOLED, MODELS, LABEL, FAM, TIER, DS_ORDER, DS_LABEL,
  pct, f3, body, h1, h2, caption, tableTitle, figureImage, threeLineTable, refPara };
