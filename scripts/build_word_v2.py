#!/usr/bin/env python3
"""Build the revised Word version: flatten main.tex, numericize citations from the
.bbl order, strip elsarticle-specific commands, then pandoc -> docx using the
previous Word version as style reference."""

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
    # fallback: order of \bibliography keys via the PDF is unavailable; use refs.bib order
    bib = open(f"{P}/refs.bib").read()
    for i, m in enumerate(re.finditer(r"@\w+\{([^,]+),", bib), 1):
        num[m.group(1)] = i

def cite_repl(m):
    keys = [k.strip() for k in m.group(1).split(",")]
    ns = [num.get(k, "?") for k in keys]
    return "[" + ",".join(str(n) for n in sorted(ns, key=lambda x: (isinstance(x, str), x))) + "]"

src = re.sub(r"\\citep\{([^}]+)\}", cite_repl, src)
src = re.sub(r"\\citet\{([^}]+)\}", cite_repl, src)

# 3. strip elsarticle-specific structure
src = re.sub(r"\\begin\{frontmatter\}|\\end\{frontmatter\}", "", src)
src = src.replace("\\journal{Neurocomputing}", "")
src = re.sub(r"\\corref\{[^}]*\}", "", src)
src = re.sub(r"\\cortext\[[^\]]*\]\{[^}]*\}", "", src)
src = re.sub(r"\\ead\{[^}]*\}", "", src)
src = re.sub(r"\\address\[[^\]]*\]\{([^}]*)\}", r"\\institution{" + r"\1" + "}", src)
src = re.sub(r"\\author\[inst1\]\{([^}]*)\}", r"\\author{\1}", src)
src = src.replace("\\begin{keyword}", "\\begin{abstract}\nKeywords: ").replace("\\end{keyword}", "\\end{abstract}")
# remove the second abstract (keywords block became abstract); keep original abstract only
# pandoc: \begin{keyword} isn't known; the replacement above makes two abstracts — drop the fake one later if duplicated
src = re.sub(r"\\widowpenalty=\d+|\\clubpenalty=\d+", "", src)
src = re.sub(r"\\setlength\{\\emergencystretch\}\{[^}]*\}", "", src)
src = re.sub(r"\\hypersetup\{[\s\S]*?\n\}", "", src)
src = re.sub(r"\\usepackage(\[[^\]]*\])?\{[^}]*\}", "", src)
src = src.replace("\\bibliographystyle{elsarticle-num}", "").replace("\\bibliography{refs}", "")
src = re.sub(r"\\begin\{keyword\}[\s\S]*?\\end\{keyword\}", "", src)  # safety
# separate the real abstract and the keyword line: rebuild keyword as plain paragraph
src = re.sub(r"Keywords: ([\s\S]*?)\\end\{abstract\}", lambda m: "KEYWORDSPLACEHOLDER", src) if False else src

# 4. tabular* -> tabular for pandoc friendliness (strip stretch spec)
src = src.replace("\\begin{tabular*}{\\columnwidth}{@{\\extracolsep{\\fill}} ", "\\begin{tabular}{")
src = re.sub(r"\\end\{tabular\*\}", "\\\\end{tabular}", src)
src = src.replace("\\end{tabular*}", "\\end{tabular}")
src = re.sub(r"\\cmidrule\(lr\)\{[^}]*\}", "", src)
src = re.sub(r"\\addlinespace", "", src)

# 5. \label/\ref -> literal text markers
def ref_repl(m):
    return "Section~" + m.group(1)
src = re.sub(r"\\ref\{sec:[^}]*\}", "REF", src)  # placeholder, handled below
labels = {}
for m in re.finditer(r"\\label\{([^}]+)\}", src):
    labels[m.group(1)] = m
# simple approach: replace \ref{X} with ?? is bad. Use numbering-free wording:
src = re.sub(r"Section~\\ref\{[^}]*\}", "the relevant section", src)
src = re.sub(r"Table~\\ref\{[^}]*\}", "the table", src)
src = re.sub(r"Figure~\\ref\{[^}]*\}", "the figure", src)
src = re.sub(r"\\ref\{[^}]*\}", "the relevant part", src)
src = re.sub(r"\\label\{[^}]*\}", "", src)

# 6. math cleanups pandoc can't do: \mathrm, \operatorname etc are fine; \mathbb needs amssymb (ok)
src = src.replace("$\\mathrm{SC}\\text{-}6$", "SC-6").replace("$\\mathrm{PE}\\text{-}6$", "PE-6")
src = src.replace("$\\mathrm{HB}\\text{-}6$", "HB-6").replace("$\\mathrm{COMB}\\text{-}12$", "COMB-12")
src = src.replace("$\\mathrm{PE}^{g}\\text{-}6$", "PE-g-6")
src = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", src)
src = re.sub(r"\\text\{([^}]*)\}", r"\1", src)

open(f"{P}/main_flat.tex", "w").write(src)
print("flattened tex written,", len(src), "chars; citation numbers:", len(num))

# 7. pandoc
cmd = ["pandoc", "-f", "latex", "-t", "docx",
       "--reference-doc", ROOT + "/download/paper_word_version.docx",
       "--resource-path", P,
       "-o", OUT, f"{P}/main_flat.tex"]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
print("pandoc exit:", r.returncode)
if r.stderr:
    print(r.stderr[:1500])
print("output:", OUT, os.path.getsize(OUT) // 1024, "KB")
