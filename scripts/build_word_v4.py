#!/usr/bin/env python3
"""Build the Word version (v4): v3 pipeline (flatten, numeric citations,
\\ref -> real numbers, PNG figures) PLUS:
  - Unicode tau (tau=0 -> tau=0) instead of the literal 'tau'
  - real Word caption numbering: 'Table N:' / 'Figure N:' prefixes with
    SEQ fields + bookmarks on every caption paragraph
  - in-text 'Table N' / 'Figure N' references converted to REF fields
    (live cross-references, clickable with \\h)
Then pandoc -> docx, append reference list, post-process, save."""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import re, subprocess, os, shutil, copy
import docx
from docx import Document
from docx.shared import Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

P = ROOT + "/paper"
OUT = ROOT + "/download/paper_word_version.docx"
REF_SNAPSHOT = ROOT + "/scripts/word_reference_v3.docx"

# 0. one-time stable reference snapshot (v3 chained output-doc-as-reference)
if not os.path.exists(REF_SNAPSHOT):
    shutil.copy(OUT, REF_SNAPSHOT)

src = open(f"{P}/main.tex").read()

# 1. flatten \input{...}
def flatten(s):
    def repl(m):
        path = os.path.join(P, m.group(1) + ".tex")
        return open(path).read()
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\\input\{([^}]+)\}", repl, s)
    return s

src = flatten(src)

# 2. citation numbers from .bbl
bbl_path = f"{P}/main.bbl"
num = {}
if os.path.exists(bbl_path):
    bbl = open(bbl_path).read()
    for i, m in enumerate(re.finditer(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}", bbl), 1):
        num[m.group(1)] = i
else:
    bib = open(f"{P}/refs.bib").read()
    for i, m in enumerate(re.finditer(r"@\w+\{([^,]+),", bib), 1):
        num[m.group(1)] = i

def cite_repl(m):
    keys = [k.strip() for k in m.group(1).split(",")]
    ns = [num.get(k, "?") for k in keys]
    return "[" + ",".join(str(n) for n in sorted(ns, key=lambda x: (isinstance(x, str), x))) + "]"

src = re.sub(r"\\citep\{([^}]+)\}", cite_repl, src)
src = re.sub(r"\\citet\{([^}]+)\}", cite_repl, src)

# 3. resolve \ref to REAL numbers
sec_n = 0
sub_n = 0
tab_n = 0
fig_n = 0
label2num = {}
token_re = re.compile(
    r"\\section\{|\\subsection\{|\\begin\{table\}|\\begin\{figure\}|\\label\{([^}]+)\}")
for m in token_re.finditer(src):
    tok = m.group(0)
    if tok.startswith("\\section{"):
        sec_n += 1
        sub_n = 0
    elif tok.startswith("\\subsection{"):
        sub_n += 1
    elif tok.startswith("\\begin{table}"):
        tab_n += 1
    elif tok.startswith("\\begin{figure}"):
        fig_n += 1
    elif tok.startswith("\\label{"):
        lab = m.group(1)
        if lab.startswith("sec:"):
            label2num[lab] = str(sec_n) if sub_n == 0 else f"{sec_n}.{sub_n}"
        elif lab.startswith("tab:"):
            label2num[lab] = str(tab_n)
        elif lab.startswith("fig:"):
            label2num[lab] = str(fig_n)

def ref_repl(m):
    lab = m.group(1)
    return label2num.get(lab, "??")

n_refs = len(re.findall(r"\\ref\{[^}]+\}", src))
src = re.sub(r"\\ref\{([^}]+)\}", ref_repl, src)
src = src.replace("Section~", "Section ").replace("Table~", "Table ")
src = src.replace("Figure~", "Figure ").replace("Section\\\\~", "Section ")
src = src.replace("Tables~", "Tables ").replace("Figures~", "Figures ")
src = re.sub(r"\\label\{[^}]*\}", "", src)
print(f"resolved {n_refs} refs; sample map:",
      {k: label2num[k] for k in ("sec:rq1", "sec:results", "tab:main", "fig:budget") if k in label2num})

# 4. strip elsarticle-specific structure
src = re.sub(r"\\begin\{frontmatter\}|\\end\{frontmatter\}", "", src)
def abstract_to_section(m):
    return "\\section*{Abstract}\n" + m.group(1).strip() + "\n"
src = re.sub(r"\\begin\{abstract\}\n([\s\S]*?)\\end\{abstract\}", abstract_to_section, src, count=1)
src = src.replace("\\journal{Neurocomputing}", "")
src = re.sub(r"\\corref\{[^}]*\}", "", src)
src = re.sub(r"\\cortext\[[^\]]*\]\{[^}]*\}", "", src)
src = re.sub(r"\\ead\{[^}]*\}", "", src)
src = re.sub(r"\\address\[[^\]]*\]\{([^}]*)\}", r"\\institution{" + r"\1" + "}", src)
src = re.sub(r"\\author\[inst1\]\{([^}]*)\}", r"\\author{\1}", src)
src = re.sub(r"\\begin\{keyword\}\n([\s\S]*?)\\end\{keyword\}", lambda m: "\\paragraph{Keywords: " + m.group(1).strip() + "}", src)
src = re.sub(r"\\widowpenalty=\d+|\\clubpenalty=\d+", "", src)
src = re.sub(r"\\setlength\{\\emergencystretch\}\{[^}]*\}", "", src)
src = re.sub(r"\\hypersetup\{[\s\S]*?\n\}", "", src)
src = re.sub(r"\\usepackage(\[[^\]]*\])?\{[^}]*\}", "", src)
src = src.replace("\\bibliographystyle{elsarticle-num}", "").replace("\\bibliography{refs}", "")
src = re.sub(r"\\begin\{thebibliography\}[\s\S]*?\\end\{thebibliography\}", "", src)
src = re.sub(r"\\begin\{keyword\}[\s\S]*?\\end\{keyword\}", "", src)

# 5. tabular* -> tabular
src = src.replace("\\begin{tabular*}{\\columnwidth}{@{\\extracolsep{\\fill}} ", "\\begin{tabular}{")
src = src.replace("\\end{tabular*}", "\\end{tabular}")
src = re.sub(r"\\cmidrule\(lr\)\{[^}]*\}", "", src)
src = re.sub(r"\\addlinespace", "", src)

# 6. figures: PNG renders
src = re.sub(r"\\includegraphics\[[^\]]*\]\{figures/([^}]+)\.pdf\}",
             r"\\includegraphics{" + P + r"/figures/\1.png}", src)
src = re.sub(r"\\includegraphics\{figures/([^}]+)\.pdf\}",
             r"\\includegraphics{" + P + r"/figures/\1.png}", src)

# 7. math cleanups (tau as proper Unicode)
src = src.replace("$\\mathrm{SC}\\text{-}6$", "SC-6").replace("$\\mathrm{PE}\\text{-}6$", "PE-6")
src = src.replace("$\\mathrm{HB}\\text{-}6$", "HB-6").replace("$\\mathrm{COMB}\\text{-}12$", "COMB-12")
src = src.replace("$\\mathrm{PE}^{g}\\text{-}6$", "PE-g-6")
src = src.replace("$k{=}1$", "k=1")
src = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", src)
src = re.sub(r"\\text\{([^}]*)\}", r"\1", src)
src = src.replace("$\\tau{=}0$", "τ=0").replace("$\\tau = 0$", "τ=0")
src = src.replace("$\\tau = 0.7$", "τ=0.7").replace("$\\tau{=}0.7$", "τ=0.7")
src = src.replace("$\\tau$", "τ").replace("$\\bar{k}$", "mean k")

open(f"{P}/main_flat.tex", "w").write(src)
print("flattened tex written,", len(src), "chars; citation numbers:", len(num))

# 8. pandoc
cmd = ["pandoc", "-f", "latex", "-t", "docx",
       "--reference-doc", REF_SNAPSHOT,
       "-o", OUT, f"{P}/main_flat.tex"]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
print("pandoc exit:", r.returncode)
if r.stderr:
    print(r.stderr[:1200])

# 9. append the reference list
bbl = open(bbl_path).read()
entries = []
for m in re.finditer(r"\\bibitem\{([^}]+)\}([\s\S]*?)(?=\\bibitem\{|\\end\{thebibliography\})", bbl):
    body = m.group(2)
    body = re.sub(r"\\newblock", " ", body)
    body = body.replace("~", " ").replace("--", "-")
    body = re.sub(r"\s+", " ", body).strip()
    body = re.sub(r"\\url\{([^}]+)\}", r"\1", body)
    body = re.sub(r"\\href\{([^}]+)\}\{([^}]+)\}", r"\2 (\1)", body)
    body = body.replace("\\newline", " ").replace("{", "").replace("}", "")
    body = re.sub(r"\s+", " ", body).strip()
    entries.append((m.group(1), body))

d = Document(OUT)
h = d.add_paragraph()
hrun = h.add_run("References")
hrun.bold = True
hrun.font.size = Pt(13)
for i, (key, body) in enumerate(entries, 1):
    p = d.add_paragraph()
    run = p.add_run(f"[{i}] {body}")
    run.font.size = Pt(9)
print(f"appended {len(entries)} references")

# ---------------------------------------------------------------------------
# 10. caption numbering with SEQ fields + bookmarks, and REF cross-references
# ---------------------------------------------------------------------------
def run_text(text, rpr=None):
    r = OxmlElement("w:r")
    if rpr is not None:
        r.append(copy.deepcopy(rpr))
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    return r

def bold_rpr():
    rpr = OxmlElement("w:rPr")
    b = OxmlElement("w:b")
    rpr.append(b)
    return rpr

def fld(instr, cached, rpr=None):
    f = OxmlElement("w:fldSimple")
    f.set(qn("w:instr"), instr)
    f.append(run_text(cached, rpr))
    return f

def bm_start(bid, name):
    b = OxmlElement("w:bookmarkStart")
    b.set(qn("w:id"), str(bid))
    b.set(qn("w:name"), name)
    return b

def bm_end(bid):
    b = OxmlElement("w:bookmarkEnd")
    b.set(qn("w:id"), str(bid))
    return b

from docx.table import Table as DxTable
from docx.text.paragraph import Paragraph as DxPara

body = d.element.body
children = list(body.iterchildren())

# identify caption paragraphs: table captions precede w:tbl, figure captions
# follow the paragraph that contains the image
tab_caps, fig_caps = [], []
pending_img_para = None
for i, child in enumerate(children):
    tag = child.tag.split("}")[1]
    if tag == "tbl":
        # walk back to nearest paragraph with text = caption
        for j in range(i - 1, -1, -1):
            pc = children[j]
            if pc.tag.split("}")[1] == "p":
                p = DxPara(pc, d)
                if p.text.strip():
                    tab_caps.append((pc, p))
                    break
    elif tag == "p":
        if child.findall(".//" + qn("w:drawing")) or child.findall(".//" + qn("w:pict")):
            # next paragraph with text = figure caption
            for j in range(i + 1, len(children)):
                nc = children[j]
                if nc.tag.split("}")[1] == "p":
                    p = DxPara(nc, d)
                    if p.text.strip():
                        fig_caps.append((nc, p))
                        break
                    break

print(f"caption paragraphs: {len(tab_caps)} tables, {len(fig_caps)} figures")

bid = 500
bookmark_names = set()
def add_caption_prefix(p_el, label, number, bold=True):
    """Prepend 'Label {SEQ Label}: ' with a bookmark around the SEQ number."""
    global bid
    ppr = p_el.find(qn("w:pPr"))
    anchor = ppr.getnext() if ppr is not None else (list(p_el)[0] if len(p_el) else None)
    name = f"{'Tab' if label == 'Table' else 'Fig'}{number}"
    rpr = bold_rpr() if bold else None
    elems = [
        bm_start(bid, name),
        run_text(f"{label} ", rpr),
        fld(f" SEQ {label} \\* ARABIC ", str(number), rpr),
        bm_end(bid),
        run_text(": ", rpr),
    ]
    for e in elems:
        anchor.addprevious(e)
    bookmark_names.add(name)
    bid += 1

for k, (pc, p) in enumerate(tab_caps, 1):
    add_caption_prefix(pc, "Table", k)
for k, (pc, p) in enumerate(fig_caps, 1):
    add_caption_prefix(pc, "Figure", k)

# in-text references -> REF fields
ref_pat = re.compile(r"\b(Table|Figure) (\d+)\b")
n_converted = 0
caption_els = {id(pc) for pc, _ in tab_caps} | {id(pc) for pc, _ in fig_caps}
for para in d.paragraphs:
    if id(para._p) in caption_els:
        continue
    for r in list(para.runs):
        txt = r.text
        if not txt or not ref_pat.search(txt):
            continue
        parts = re.split(r"(\b(?:Table|Figure) \d+\b)", txt)
        if len(parts) == 1:
            continue
        rpr = r._r.find(qn("w:rPr"))
        new_nodes = []
        for part in parts:
            m = re.fullmatch(r"(Table|Figure) (\d+)", part)
            if m:
                label, n = m.group(1), m.group(2)
                name = f"{'Tab' if label == 'Table' else 'Fig'}{n}"
                if name in bookmark_names:
                    new_nodes.append(run_text(f"{label} ", rpr))
                    new_nodes.append(fld(f" REF {name} \\h ", n, rpr))
                    n_converted += 1
                else:
                    new_nodes.append(run_text(part, rpr))
            elif part:
                new_nodes.append(run_text(part, rpr))
        for node in new_nodes:
            r._r.addprevious(node)
        r._r.getparent().remove(r._r)

print(f"converted {n_converted} in-text Table/Figure references to REF fields")

d.save(OUT)
print("output:", OUT, os.path.getsize(OUT) // 1024, "KB")
