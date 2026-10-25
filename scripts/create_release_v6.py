#!/usr/bin/env python3
"""Create GitHub Release v1.8.0 and upload assets (submission-ready revision)."""
import json, os, sys, time, urllib.request

TOKEN = os.environ["GH_TOKEN"]
OWNER_REPO = "43aquarius/Test-TimeEnsemblingforLargeLanguageModels"
API = f"https://api.github.com/repos/{OWNER_REPO}"
UPLOADS = f"https://uploads.github.com/repos/{OWNER_REPO}"
ASSETS = "/home/z/my-project/release_assets"
TAG = "v1.8.0"

BODY = """## When Does Test-Time Ensembling Help Large Language Models? (v1.8.0 — submission-ready)
**A Budget-Matched Study of Answer-Space and Prompt-Space Diversity**

Chang Tan · Dalian University of Technology

Preprint (fifth revision), prepared for submission to *Neurocomputing* (Elsevier). This revision is a submission-readiness pass against the journal's Guide for Authors: the abstract now meets the 250-word limit, the title page carries the full postal address, the declarations follow the journal's required formats and placement, and — most importantly — every one of the 42 cited references has been verified against publisher records.

### Compliance with the Guide for Authors
- **Abstract**: trimmed from 274 to **247 words** (journal limit: 250). All headline numbers retained (+2.4/+4.9/+4.1 over S1, the +1.9 difficulty offset decomposition, 79–87% budget transfer); the Holm *p*-value clause, per-model coverage detail, and redundant quantifiers were cut.
- **Title page**: affiliation completed to the full postal address (No. 2 Linggong Road, Ganjingzi District, Dalian 116024, Liaoning, China); corresponding-author email unchanged.
- **Declarations**: the block (CRediT, competing interests, funding, data availability, generative-AI statement) now appears **before the appendices**, matching Elsevier typeset order; the generative-AI statement follows the journal's required wording ("During the preparation of this work the author used ... After using these tools, the author reviewed and edited the content as needed and takes full responsibility for the content of the published article.").
- **Highlights**: re-issued as an editable **Highlights.docx** (5 bullets, each ≤85 characters including spaces) alongside highlights.txt.
- **Cover letter**: a submission-ready **cover_letter.docx** draft (article type, originality declaration, data availability, no-conflict and no-funding statements, GenAI disclosure).

### Reference audit (the substantive change)
All 42 cited works were verified against publisher records (ACL Anthology, PMLR, Nature, AAAI, IJCAI, OpenReview, arXiv). Per the guide ("Where a preprint has subsequently become available as a peer-reviewed publication, use the formal publication as your reference"), 6 preprint citations were upgraded to their formal publications, and 8 entries carried errors that are now fixed:

| Reference | Was | Now |
|---|---|---|
| PIQA (Bisk et al.) | ACL 2020, wrong title/authors/pages | **AAAI 2020**, pp. 7432–7439, correct authors + DOI |
| AGIEval (Zhong et al.) | arXiv preprint, wrong author list | **NAACL 2024 Findings**, pp. 2299–2314 + DOI |
| MMLU-Pro (Wang et al.) | arXiv preprint, wrong author list | **NeurIPS 2024 (D&B)**, correct 17-author list |
| Scaling test-time compute (Snell et al.) | arXiv preprint | **ICLR 2025** (oral) |
| Multiagent debate (Du et al.) | arXiv preprint | **ICML 2024**, PMLR 235:11733–11763 |
| Input clarification ensembling (Hou et al.) | arXiv preprint | **ICML 2024**, PMLR 235:19023–19042 |
| Diversity of thought (Naik et al.) | wrong author list | Correct authors (Naik, Chandrasekaran, Yuksekgonul, Palangi, Nushi) |
| Should we be going MAD? (Smit et al.) | wrong authors + wrong arXiv ID | Correct authors (A. Smit et al., InstaDeep), arXiv:2311.17371 |
| Uncertainty survey | arXiv ID did not resolve to the cited work | Replaced with the verified survey (Liu et al., arXiv:2503.15850) |
| Ask Me Anything (Arora et al.) | wrong arXiv ID | arXiv:2210.02441 (2022) |

In addition: 11 DOIs added (Nature, TACL, ACL, EMNLP, EACL, IJCAI, AAAI entries), the Leidinger et al. page range corrected (9210–9232), PromptBench retitled to its current arXiv name (PromptRobust), 2 unused bib entries removed, and the committed `main.bbl` regenerated (the DeepSeek documentation entry was missing from the previously committed bbl even though it rendered in the PDF).

### Verification (all green from a fresh checkout)
- `scripts/recompute_all.py`: **106/106 checks pass** — every number in the paper re-derived from the raw call logs. The script is now repo-relative (runs from any clone) and reads the greedy-bias audit from its tracked location.
- `scripts/final_crosscheck.py`: **38/38 in-text placements verified** against the rebuilt PDF (abstract checks updated to the 247-word wording).
- Word version regenerated from the same LaTeX source: 42 references, 11 table captions with appendix numbering (A.1/B.1/C.1), 18 live REF cross-references, and a complete title page (the previous Word build had lost the affiliation and email in conversion; the pipeline now preserves them).

### Assets
| File | Content |
|---|---|
| `paper_main.pdf` | Full manuscript (58 pages), submission layout |
| `paper_word_version.docx` | Word version with live caption fields and cross-references |
| `latex_source.zip` | Complete LaTeX source (main.tex, sections, tables, figures, refs.bib, main.bbl) |
| `highlights.txt` / `Highlights.docx` | 5 highlights, ≤85 characters each (editable docx for submission) |
| `cover_letter.docx` | Cover letter draft for the submission system |
| `supplementary_data.zip` | Questions, paraphrases, validation reports, audits, all raw predictions incl. the complete held-out matrices, analysis JSONs |

All numbers are regenerable from the released call matrices via `scripts/recompute_all.py`.
"""

def api(url, data=None, method=None, ctype="application/json"):
    req = urllib.request.Request(url, method=method or ("POST" if data else "GET"))
    req.add_header("Authorization", f"Bearer {TOKEN}")
    if data is not None:
        req.add_header("Content-Type", ctype)
        data = data if isinstance(data, bytes) else json.dumps(data).encode()
    with urllib.request.urlopen(req, data=data) as r:
        return r.status, json.loads(r.read() or b"{}")

# 1. verify default branch head
status, repo = api(f"{API}")
head = repo["default_branch"]
status, ref = api(f"{API}/git/ref/heads/{head}")
sha = ref["object"]["sha"]
print(f"default branch {head} @ {sha[:7]}")

# tag v1.8.0 was pushed with git; find or create the release
status, tags = api(f"{API}/tags?per_page=10")
tag_obj = next((t for t in tags if t["name"] == TAG), None)
if tag_obj is None:
    sys.exit(f"tag {TAG} not found on remote")
print(f"tag {TAG} -> {tag_obj['commit']['sha'][:7]}")

# 2. create release
status, rel = api(f"{API}/releases",
                  {"tag_name": TAG, "name": f"{TAG} — submission-ready revision",
                   "body": BODY, "draft": False, "prerelease": False})
print(f"release id={rel['id']} url={rel['html_url']}")
RID = rel["id"]

# 3. upload assets
for f in ["paper_main.pdf", "paper_word_version.docx", "latex_source.zip",
          "supplementary_data.zip", "highlights.txt", "Highlights.docx",
          "cover_letter.docx"]:
    path = os.path.join(ASSETS, f)
    ctype = "application/zip" if f.endswith(".zip") else (
        "application/pdf" if f.endswith(".pdf") else (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if f.endswith(".docx") else "text/plain"))
    with open(path, "rb") as fh:
        data = fh.read()
    req = urllib.request.Request(
        f"{UPLOADS}/releases/{RID}/assets?name={urllib.parse.quote(f)}",
        method="POST", data=data)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", ctype)
    with urllib.request.urlopen(req) as r:
        out = json.loads(r.read())
    print(f"uploaded {f} ({len(data)//1024} KB) -> {out['browser_download_url']}")
    time.sleep(1)

print("release complete")
