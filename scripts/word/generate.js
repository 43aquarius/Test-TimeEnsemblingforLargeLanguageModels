// Assemble the Word document
const H = require("./helpers");
const { Document, Packer, Paragraph, TextRun, Header, Footer, PageNumber, NumberFormat, AlignmentType, fs } = H;
const { part1 } = require("./part1");
const { part2 } = require("./part2");
const ROOT = require("path").resolve(__dirname, "../..");

const doc = new Document({
  creator: "Chang Tan",
  title: "When Does Test-Time Ensembling Help Large Language Models? A Budget-Matched Study of Answer-Space and Prompt-Space Diversity",
  description: "Journal manuscript",
  styles: {
    default: {
      document: {
        run: { font: { ascii: "Times New Roman", eastAsia: "SimSun" }, size: 24, color: "000000" },
        paragraph: { spacing: { line: 360 } },
      },
      heading1: {
        run: { font: { ascii: "Times New Roman", eastAsia: "SimHei" }, size: 28, bold: true, color: "000000" },
        paragraph: { spacing: { before: 360, after: 180, line: 360 } },
      },
      heading2: {
        run: { font: { ascii: "Times New Roman", eastAsia: "SimHei" }, size: 26, bold: true, color: "000000" },
        paragraph: { spacing: { before: 280, after: 140, line: 360 } },
      },
    },
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1440, bottom: 1440, left: 1701, right: 1417, header: 850, footer: 992 },
        pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "Test-Time Ensembling for Large Language Models", size: 18,
            color: "333333", font: { ascii: "Times New Roman", eastAsia: "SimSun" } })],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ children: [PageNumber.CURRENT], size: 20,
            font: { ascii: "Times New Roman" } })],
        })],
      }),
    },
    children: [...part1, ...part2],
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(ROOT + "/download/paper_word_version.docx", buf);
  console.log("Word document written:", buf.length, "bytes");
});
