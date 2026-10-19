#!/usr/bin/env python3
"""Build the Word version (v3): flatten main.tex, numericize citations from the
.bbl order, RESOLVE ALL \\ref TO REAL NUMBERS (fixes the 26x 'the relevant
section' / 13x 'the table' / 4x 'the figure' placeholders of v2), swap PDF
figures for PNG, strip elsarticle-specific commands, then pandoc -> docx."""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import re, subprocess, os

P = ROOT + "/paper"
OUT = ROOT + "/download/paper_word_version.docx"

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

# 3. resolve \ref to REAL numbers -------------------------------------------
# counters mirror LaTeX numbering: sections/subsections in order of appearance,
# tables and figures numbered by environment order (caption inside).
sec_n = 0
sub_n = 0
tab_n = 0
fig_n = 0
label2num = {}
token_re = re.compile(
    r"\\section\{|\\subsection\{|\\begin\{table\}|\\begin\{figure\}|\\label\{([^}]+)\}")
pos = 0
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
        elif lab.startswith("eq:"):
            pass  # equations not cross-referenced in text

def ref_repl(m):
    lab = m.group(1)
    return label2num.get(lab, "??")

n_refs = len(re.findall(r"\\ref\{[^}]+\}", src))
src = re.sub(r"\\ref\{([^}]+)\}", ref_repl, src)
# non-breaking ties around numbers -> plain space
src = src.replace("Section~", "Section ").replace("Table~", "Table ")
src = src.replace("Figure~", "Figure ").replace("Section\\\\~", "Section ")
src = src.replace("Tables~", "Tables ").replace("Figures~", "Figures ")
src = re.sub(r"\\label\{[^}]*\}", "", src)
print(f"resolved {n_refs} refs; sample map:",
      {k: label2num[k] for k in ("sec:rq1", "sec:results", "tab:main", "fig:budget") if k in label2num})

# 4. strip elsarticle-specific structure
src = re.sub(r"\\begin\{frontmatter\}|\\end\{frontmatter\}", "", src)
# elsarticle has no \maketitle: without it pandoc swallows the abstract into
# metadata and drops it in non-standalone mode. Render it explicitly.
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
src = re.sub(r"\\begin\{keyword\}[\s\S]*?\\end\{keyword\}", "", src)  # safety

# 5. tabular* -> tabular for pandoc friendliness
src = src.replace("\\begin{tabular*}{\\columnwidth}{@{\\extracolsep{\\fill}} ", "\\begin{tabular}{")
src = src.replace("\\end{tabular*}", "\\end{tabular}")
src = re.sub(r"\\cmidrule\(lr\)\{[^}]*\}", "", src)
src = re.sub(r"\\cmidrule\(lr\)\{\d+-\d+\}", "", src)
src = re.sub(r"\\addlinespace", "", src)

# 6. figures: use PNG renders (pandoc cannot embed PDF)
src = re.sub(r"\\includegraphics\[[^\]]*\]\{figures/([^}]+)\.pdf\}",
             r"\\includegraphics{" + P + r"/figures/\1.png}", src)
src = re.sub(r"\\includegraphics\{figures/([^}]+)\.pdf\}",
             r"\\includegraphics{" + P + r"/figures/\1.png}", src)

# 7. math cleanups
src = src.replace("$\\mathrm{SC}\\text{-}6$", "SC-6").replace("$\\mathrm{PE}\\text{-}6$", "PE-6")
src = src.replace("$\\mathrm{HB}\\text{-}6$", "HB-6").replace("$\\mathrm{COMB}\\text{-}12$", "COMB-12")
src = src.replace("$\\mathrm{PE}^{g}\\text{-}6$", "PE-g-6")
src = src.replace("$k{=}1$", "k=1")
src = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", src)
src = re.sub(r"\\text\{([^}]*)\}", r"\1", src)
src = src.replace("$\\tau{=}0$", "tau=0").replace("$\\tau = 0$", "tau=0")
src = src.replace("$\\tau = 0.7$", "tau=0.7").replace("$\\tau{=}0.7$", "tau=0.7")
src = src.replace("$\\bar{k}$", "mean k")

open(f"{P}/main_flat.tex", "w").write(src)
print("flattened tex written,", len(src), "chars; citation numbers:", len(num))

# 8. pandoc
cmd = ["pandoc", "-f", "latex", "-t", "docx",
       "--reference-doc", ROOT + "/download/paper_word_version.docx",
       "-o", OUT, f"{P}/main_flat.tex"]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
print("pandoc exit:", r.returncode)
if r.stderr:
    print(r.stderr[:1200])

# 9. append the reference list (pandoc mangles thebibliography)
import docx
from docx import Document
from docx.shared import Pt

bbl = open(f"{P}/main.bbl").read()
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
# drop any paragraph that pandoc produced from a stray thebibliography remnant
h = d.add_paragraph()
hrun = h.add_run("References")
hrun.bold = True
hrun.font.size = Pt(13)
for i, (key, body) in enumerate(entries, 1):
    p = d.add_paragraph()
    run = p.add_run(f"[{i}] {body}")
    run.font.size = Pt(9)
d.save(OUT)
print(f"appended {len(entries)} references")
print("output:", OUT, os.path.getsize(OUT) // 1024, "KB")
