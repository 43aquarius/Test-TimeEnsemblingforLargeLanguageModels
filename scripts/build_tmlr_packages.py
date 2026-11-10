#!/usr/bin/env python3
"""build_tmlr_packages.py -- build the two double-blind TMLR (OpenReview) packages.

Package 1: tmlr_submission_latex.zip
    LaTeX source + compiled PDF.  Whitelist-based: only the files OpenReview
    needs to render the submission.  Author-internal documents (CHANGELOG.md,
    DECISIONS.md, REVIEW.md, audit reports, experiment protocols) are excluded.

Package 2: anonymous_repository.zip
    The anonymized code+data repository referenced by the paper's
    Reproducibility Statement.  Built from the research repo by (a) including
    only the reproducibility-relevant directories, (b) excluding
    identity-bearing files (release/publishing scripts, the de-anonymized
    manuscript, Word builders), and (c) replacing README/LICENSE with
    anonymous versions.

Both packages are re-verified in-place: every text member is scanned for
identity strings and API-key patterns; the build fails loudly on any hit.
"""
import os, re, shutil, subprocess, sys, zipfile

ROOT = "/home/z/my-project"
SUB = f"{ROOT}/download/tmlr_submission"      # TMLR submission dir (LaTeX)
REPO = f"{ROOT}/repo"                          # research repository
SCRIPTS = f"{ROOT}/scripts"                    # audit script lives here
OUT = f"{ROOT}/download"

# ------------------------------------------------------------------ helpers --
# NOTE: sk- pattern requires 20+ chars so that "risk-coverage" and similar
# hyphenated words cannot match a real key shape (sk-xxxxxxxx...).
IDENTITY_PATTERNS = [
    r"Chang\s+Tan", r"Dalian", r"foxmail", r"43aquarius", r"aquars",
    r"zenodo", r"10\.5281", r"github\.com/4", r"github_pat_", r"ghp_",
    r"sk-[A-Za-z0-9]{20,}", r"csrftoken=", r"sessionid=",
]
KEY_RE = [re.compile(p, re.I) for p in IDENTITY_PATTERNS]

def scan_text(name, data):
    """Return list of pattern hits in a text member (empty = clean)."""
    try:
        txt = data.decode("utf-8", errors="ignore")
    except Exception:
        return []
    hits = []
    for rx in KEY_RE:
        m = rx.search(txt)
        if m:
            hits.append(f"{name}: /{rx.pattern}/ -> ...{txt[max(0,m.start()-30):m.end()+30]!r}...")
    return hits

def add_dir(zf, src, prefix, exclude=(), exclude_dirs=()):
    """Recursively add a directory under prefix, with exclusion filters."""
    n = 0
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs
                       and not d.startswith(".")
                       and d != "__pycache__"]
        for fn in sorted(filenames):
            if fn in exclude or fn.endswith((".pyc", ".DS_Store")):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, src)
            zf.write(full, os.path.join(prefix, rel))
            n += 1
    return n

def verify_zip(path):
    """Re-open the zip and scan every text member for identity strings."""
    hits = []
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            if info.file_size > 8_000_000:       # skip anything implausibly big
                continue
            data = zf.read(info.filename)
            if info.filename.endswith((".json", ".jsonl", ".py", ".md", ".tex",
                                       ".bib", ".sty", ".bst", ".txt", ".csv",
                                       ".example", ".sh", ".js", ".html", "")):
                hits += scan_text(info.filename, data)
    return hits

# --------------------------------------------------- package 1: LaTeX source --
def build_latex():
    path = f"{OUT}/tmlr_submission_latex.zip"
    if os.path.exists(path):
        os.remove(path)
    files = ["main.tex", "refs.bib", "tmlr.sty", "tmlr.bst",
             "math_commands.tex", "fancyhdr.sty", "main.pdf"]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in files:
            zf.write(f"{SUB}/{fn}", fn)
        for d in ("sections", "tables", "figures"):
            add_dir(zf, f"{SUB}/{d}", d)
    return path

# ------------------------------------------- package 2: anonymous repository --
ANON_README = """# Anonymous repository (double-blind review)

Code, data, and logs for *When Does Test-Time Ensembling Help Large Language
Models? A Budget-Matched Study of Answer-Space and Prompt-Space Diversity*.

## Layout

| Directory | Contents |
|---|---|
| `data/` | questions, paraphrase bank with per-item validation verdicts, NLI/equivalence checks, raw benchmark items (`data/raw/`, third-party datasets under their own licenses) |
| `results/` | per-call raw logs (JSONL, one file per model; every call with timestamp, token usage, raw output), follow-up condition logs (`cond_*`, `expand/`), and analysis outputs (`analysis/`) |
| `supplementary_data/` | off-mode greedy audit used by the paper's greedy-bias analysis |
| `scripts/` | the full pipeline: dataset building, paraphrase generation and validation, condition execution, analysis, and the main recomputation pass (`recompute_all.py`) |
| `experiments/` | protocols + scripts for the four pre-registered follow-up experiments (D1-D4) whose results are not yet in the paper |
| `audit/` | the number-consistency audit: recomputes every quantitative claim in the manuscript from the raw call logs and compares value by value |

## Reproduce every number in the paper

```bash
# 1. full recomputation pass (145 checks over all tables and statistics)
python3 scripts/recompute_all.py

# 2. number-consistency audit of the TMLR manuscript (102 claims,
#    MATCH/MISMATCH/UNVERIFIABLE per claim; reports land in audit/)
python3 audit/audit_paper_numbers.py --root . --out audit/audit_report
```

Both passes are deterministic (fixed seeds; sorted iteration order) and
require only Python 3.8+ with the standard library.

## Pipeline conventions

- OpenAI-compatible endpoints, temperature 0.7 (sampling) / 0 (greedy);
  answers parsed as `Answer:<letter/number>` with a fallback scan;
  majority vote with earliest-vote tie-breaking in canonical order.
- Keys are read from environment variables or `scripts/credentials.py`
  (see `scripts/credentials.example.py`); no key material is stored in the logs.

## License

MIT (copyright holder anonymized during double-blind review; the licensing
terms are identical to the version that will accompany the de-anonymized
release).
"""

ANON_LICENSE = """MIT License

Copyright (c) 2026, the submitting author(s) (anonymized for double-blind review)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

# identity-bearing or publication-only scripts excluded from the anonymous repo.
# apinex_*.py: exploratory relay probes with a hard-coded API key (the key is
#   already public in the v1.5.0+ releases and must be rotated by the author;
#   the probes are not needed to reproduce any number in the paper).
# final_crosscheck.py: asserts against the de-anonymized Neurocomputing
#   manuscript (zenodo DOI expectation, paper/ paths) -- wrong manuscript for
#   the TMLR package; audit/audit_paper_numbers.py is the TMLR verification.
EXCLUDE_SCRIPTS = {
    "create_release_v5.py", "create_release_v6.py", "create_release_v7.py",
    "build_release_assets_v4.py", "build_release_assets_v5.py",
    "build_release_assets_v6.py", "build_release_assets_v7.py",
    "build_word_v2.py", "build_word_v3.py", "build_word_v4.py",
    "make_submission_docs.py", "rebuild_latex_zip.py", "move_appendix.py",
    "patch_results_a.py", "patch_results_b.py", "patch_discussion.py",
    "backup_data.sh",
    "apinex_diversity.py", "apinex_freemap.py", "apinex_gapcheck.py",
    "apinex_probe2.py", "apinex_ratelimit.py", "apinex_test.py",
    "final_crosscheck.py",
}
EXCLUDE_SCRIPT_DIRS = {"word", "__pycache__"}

def build_anon_repo():
    path = f"{OUT}/anonymous_repository.zip"
    if os.path.exists(path):
        os.remove(path)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        # research repo: data, logs, analysis
        for d in ("data", "results", "supplementary_data"):
            add_dir(zf, f"{REPO}/{d}", d)
        # pipeline scripts (identity-bearing publication tooling excluded)
        add_dir(zf, f"{REPO}/scripts", "scripts",
                exclude=EXCLUDE_SCRIPTS, exclude_dirs=EXCLUDE_SCRIPT_DIRS)
        # D1-D4 experiment protocols + scripts
        add_dir(zf, f"{SUB}/experiments", "experiments")
        # number-consistency audit (portable defaults; sanitized report header)
        audit_py = open(f"{SCRIPTS}/audit_paper_numbers.py").read()
        zf.writestr("audit/audit_paper_numbers.py", audit_py)
        rep = open(f"{SUB}/audit_report.md").read()
        rep = rep.replace("Input logs: `/home/z/my-project/repo`",
                          "Input logs: this repository (`data/` and `results/`)")
        zf.writestr("audit/audit_report.md", rep)
        repj = open(f"{SUB}/audit_report.json").read()
        repj = repj.replace("/home/z/my-project/repo", ".")
        zf.writestr("audit/audit_report.json", repj)
        # anonymous front matter
        zf.writestr("README.md", ANON_README)
        zf.writestr("LICENSE", ANON_LICENSE)
    return path

# ---------------------------------------------------------------------- main --
if __name__ == "__main__":
    print("building packages ...")
    p1 = build_latex()
    p2 = build_anon_repo()
    all_hits = []
    for p in (p1, p2):
        hits = verify_zip(p)
        size = os.path.getsize(p) / 1e6
        with zipfile.ZipFile(p) as zf:
            n = len(zf.namelist())
        print(f"  {os.path.basename(p)}: {n} files, {size:.1f} MB, "
              f"identity scan: {'CLEAN' if not hits else str(len(hits)) + ' HITS'}")
        all_hits += hits
    if all_hits:
        print("\nIDENTITY LEAKS FOUND -- package rejected:")
        for h in all_hits:
            print(" ", h)
        sys.exit(1)
    # cross-check: forbidden internal docs must not be in the LaTeX package
    with zipfile.ZipFile(p1) as zf:
        names = set(zf.namelist())
    bad = names & {"CHANGELOG.md", "DECISIONS.md", "REVIEW.md",
                   "audit_report.md", "audit_report.json"}
    assert not bad, f"internal docs leaked into LaTeX package: {bad}"
    print("\nOK: both packages built and verified (no identity strings, "
          "no internal documents).")
