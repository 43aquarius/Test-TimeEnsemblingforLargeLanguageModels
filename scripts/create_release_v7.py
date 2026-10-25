#!/usr/bin/env python3
"""Create GitHub Release v1.8.1 and upload assets (post-review correction pass:
held-out RQ2/RQ3 recomputation, greedy-divergence count fix, instruction-variant
control, LaTeX residue cleanup, bibliography casing, Zenodo archival statement).

Usage: GH_TOKEN=<token> python3 scripts/create_release_v7.py
Requires the local tag v1.8.1 to have been pushed first (git push origin main --tags).
"""
import json, os, re, sys, time, urllib.request, urllib.error

TOKEN = os.environ["GH_TOKEN"]
OWNER_REPO = "43aquarius/Test-TimeEnsemblingforLargeLanguageModels"
API = f"https://api.github.com/repos/{OWNER_REPO}"
UPLOADS = f"https://uploads.github.com/repos/{OWNER_REPO}"
ASSETS = "/home/z/my-project/release_assets"
TAG = "v1.8.1"

# --- guard: the Zenodo DOI must be the real reserved one (record 23642990) ----
tex = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "paper", "main.tex")).read()
m = re.search(r"\\newcommand\{\\zenododoi\}\{([^}]*)\}", tex)
if not m or not re.fullmatch(r"10\.5281/zenodo\.\d+", m.group(1)):
    sys.exit(f"paper/main.tex Zenodo DOI is not a real reserved DOI: {m.group(1) if m else 'macro missing'}")
print(f"Zenodo DOI in paper: {m.group(1)}")

BODY = """## When Does Test-Time Ensembling Help Large Language Models? (v1.8.1 — submission-ready, corrected)
**A Budget-Matched Study of Answer-Space and Prompt-Space Diversity**

Chang Tan · Dalian University of Technology

Preprint (sixth revision), prepared for submission to *Neurocomputing* (Elsevier). This release is a correction pass that fixes every issue remaining from the final internal review of v1.8.0. No new data was collected: every correction is either a wording fix or a recomputation from the already-released call logs, carried out by the new `scripts/analyze_rq23_expand.py`.

### Corrections in this release

**1. LaTeX residue.** The seven duplicated "Appendix Appendix" / "Appendices Appendix A–Appendix C" cross-reference prefixes are gone (elsarticle's `\\appendix` already renders `\\ref{app:...}` as "Appendix A"; the Word pipeline now restores the prefix on its side), and a sentence duplicated in Section 5.7 ("All margins can be re-derived from the released call matrices.") is deduplicated.

**2. Greedy-divergence count.** The abstract, Section 6.3, and the conclusion said greedy and S1 differ by 4–11 points on *three* of ten model–endpoint configurations; the correct count is **four of ten** — three with greedy below the sampled expectation (Agnes3.0-Flash +10.6, Agnes2.5-Flash +4.2, DeepSeekV4.1-Flash +4.5) and one above (Gemini3.8-Flash −5.6) — now stated with the direction split.

**3. RQ2 and RQ3 recomputed on the held-out suite** (previously development-suite only, and Section 6.1's third finding rested on models with 1–3 ensemble errors, below the paper's own five-error rule):
- **Fragility** loses its clean locus split: pooled over the four fully covered held-out models, stem-locus flips run **17.4%** (41/236) and instruction-locus flips **9.6%** (23/240) — the development suite's 0/52 instruction-locus result was a property of its question draw, and the held-out instruction flips sit almost entirely on SAT-Math (40/0/15/20% per model), exactly where the instruction variants differ in elicitation quality.
- **Error signals** now carry 12–21 reference errors per model (new **Table 9**): pooled AUROC **0.75** sample agreement / **0.74** paraphrase agreement / **0.81** summed disagreement; the stronger single signal tracks the model's stronger diversity source (paraphrase on the Agnes models, sample on the DeepSeek tiers); coverage complementarity holds at scale (15/12 pooled errors flagged by only one side); and the regime caveat is made explicit (non-degenerate-stratum AUROC 0.49–0.86; 35.1% error rate where any vote dissents vs. 3.6% on unanimous questions). Section 6.1's third and fourth findings are restated on these numbers.

**4. SAT-Math instruction control** (was "left to future work"): scoring each of the six handcrafted instruction variants separately from the released logs, the best variant — selected post hoc, an optimistic ceiling — lifts pooled single-call accuracy from **76.2% to 95.0%**, while the six-variant paraphrase ensemble captures about **eighty percent** of that (91.2%) with no variant selection (reaching the ceiling exactly on Agnes3.0-Flash). On PIQA the best variant sits at the canonical level (86.2 vs 87.9), so the instruction effect is specific to quantitative items. The one condition these logs cannot decide — six resamples under the single best instruction — is flagged as the cell's one unrun control.

**5. PE description.** Section 3.3 no longer says PE-k perturbs the prompt "while the decoder configuration is fixed": every paraphrase vote is an independent stochastic draw at the same τ=0.7 as a canonical sample, so PE-k carries the same per-call decoding noise on top of prompt variation. The greedy-paraphrase control's development-suite-only scope is stated in Sections 3.3, 4.5, and Appendix A, and held-out paraphrase margins are read with that caveat (where the control exists, the Agnes models show PE^g-6/PE-6 modal agreement on 31/32 and 38/39 questions).

**6. TruthfulQA.** "Neutral in aggregate (ΔSC +0.8, ΔPE +3.1)" corrected to: near-neutral for resampling (ΔSC +0.8) while retaining a small prompt-space margin (ΔPE +3.1).

**7. Bibliography.** The Condorcet entry's author format is fixed ("Marquis de Condorcet", previously mangled by BibTeX into "M. d. C. de Caritat, Marie Jean Antoine Nicolas"); Gemini3.8-Flash now cites its **official Gemini 3.8 Flash model card** (Google DeepMind, September 2026) instead of the Gemini 2.5 technical report; and the bibliography's sentence-case artifacts are repaired (GPT-4, GPT-5, Agnes AI, Gemini titles).

**8. Endpoint verification.** The Apinex relay — an aggregator that served GPT-6-Luna, Gemini3.8-Flash, and the completed DeepSeek runs — is named explicitly: model identity/version and temperature compliance cannot be verified through it, no condition was replicated on a first-party API or an open-weight model, and findings therefore describe the accessed endpoints as of October 2026 (Sections 4.2 and 6.4).

**9. Data archival.** The data availability statement now points at a DOI-archived Zenodo snapshot in addition to GitHub: **this release is archived on Zenodo with DOI [10.5281/zenodo.23642990](https://doi.org/10.5281/zenodo.23642990)** (full repository snapshot: paper source, all raw call matrices, validated paraphrases, audits, analysis outputs, and the verification scripts). A `.zenodo.json` metadata file ships with the repo so future releases can be archived via the Zenodo–GitHub integration with correct metadata.

### Verification (all green from a fresh checkout)
- `scripts/recompute_all.py`: **145/145 checks pass** — every number in the paper re-derived from the raw call logs, including 39 new checks for the greedy-divergence count, the held-out fragility/AUROC/flagging numbers, and the instruction-variant control.
- `scripts/final_crosscheck.py`: **all in-text placements verified** against the rebuilt PDF (73 checks, including the new Table 9 numbers, the absence of the LaTeX residue, and the bibliography renderings).
- `scripts/analyze_rq23_expand.py`: the new held-out recomputation script; its output ships as `results/analysis/rq23_expand.json` and inside the supplementary data zip.
- Word version regenerated from the same LaTeX source: 42 references, 12 table captions (A.1/B.1/C.1 appendix numbering intact), appendix cross-references restored, URL artifacts cleaned.

### Assets
| File | Content |
|---|---|
| `paper_main.pdf` | Full manuscript (62 pages), submission layout |
| `paper_word_version.docx` | Word version with live caption fields and cross-references |
| `latex_source.zip` | Complete LaTeX source (main.tex, sections, tables, figures, refs.bib, main.bbl) |
| `highlights.txt` / `Highlights.docx` | 5 highlights, ≤85 characters each (editable docx for submission) |
| `cover_letter.docx` | Cover letter draft (updated data-availability wording) |
| `supplementary_data.zip` | Questions, paraphrases, validation reports, audits, all raw predictions incl. the complete held-out matrices, analysis JSONs incl. rq23_expand.json |

All numbers are regenerable from the released call matrices via `scripts/recompute_all.py` and `scripts/analyze_rq23_expand.py`.
"""

# plain-text DOI rendering for the release body (see note in step 4 below)
BODY_PLAIN = BODY.replace(
    "[10.5281/zenodo.23642990](https://doi.org/10.5281/zenodo.23642990)",
    "10.5281/zenodo.23642990 (https://doi.org/10.5281/zenodo.23642990)")

def api(url, data=None, method=None, ctype="application/json"):
    req = urllib.request.Request(url, method=method or ("POST" if data else "GET"))
    req.add_header("Authorization", f"Bearer {TOKEN}")
    if data is not None:
        req.add_header("Content-Type", ctype)
        data = data if isinstance(data, bytes) else json.dumps(data).encode()
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        body = e.read()[:800]
        print(f"HTTP {e.code} from {url}: {body.decode('utf-8', 'replace')}")
        sys.exit(1)

# 1. verify default branch head
status, repo = api(f"{API}")
head = repo["default_branch"]
status, ref = api(f"{API}/git/ref/heads/{head}")
sha = ref["object"]["sha"]
print(f"default branch {head} @ {sha[:7]}")

# tag v1.8.1 must already be pushed with git
status, tags = api(f"{API}/tags?per_page=10")
tag_obj = next((t for t in tags if t["name"] == TAG), None)
if tag_obj is None:
    sys.exit(f"tag {TAG} not found on remote")
print(f"tag {TAG} -> {tag_obj['commit']['sha'][:7]}")

# 2. create (or reuse) a DRAFT release. Publishing directly (draft=false) with a
#    body containing markdown links trips GitHub's 'links/0/schema' 422 bug, so
#    the flow is: draft -> upload assets -> PATCH draft=false. If the publish
#    PATCH still 422s, the DOI markdown link is downgraded to plain text.
NAME = f"{TAG} — submission-ready revision (corrected)"
status, rels = api(f"{API}/releases?per_page=100")
rel = next((r for r in rels if r["tag_name"] == TAG), None)
if rel is None:
    status, rel = api(f"{API}/releases",
                      {"tag_name": TAG, "name": NAME, "body": BODY,
                       "draft": True, "prerelease": False})
    print(f"draft release id={rel['id']}")
elif not rel["draft"]:
    sys.exit(f"published release for {TAG} already exists: {rel['html_url']}")
else:
    print(f"reusing draft release id={rel['id']}")
RID = rel["id"]

# 3. upload assets (skip ones already present)
status, have = api(f"{API}/releases/{RID}/assets")
have_names = {a["name"] for a in have}
for f in ["paper_main.pdf", "paper_word_version.docx", "latex_source.zip",
          "supplementary_data.zip", "highlights.txt", "Highlights.docx",
          "cover_letter.docx"]:
    if f in have_names:
        print(f"  {f} already uploaded, skipping")
        continue
    path = os.path.join(ASSETS, f)
    ctype = "application/zip" if f.endswith(".zip") else (
        "application/pdf" if f.endswith(".pdf") else (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if f.endswith(".docx") else "text/plain"))
    with open(path, "rb") as fh:
        data = fh.read()
    req = urllib.request.Request(
        f"{UPLOADS}/releases/{RID}/assets?name={f}", data=data, method="POST")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req) as r:
            out = json.loads(r.read() or b"{}")
        print(f"  uploaded {f} ({len(data)/1024:.0f} KB) -> {out.get('browser_download_url')}")
    except urllib.error.HTTPError as e:
        print(f"  upload {f}: HTTP {e.code} {e.read()[:200]}")
        sys.exit(1)
    time.sleep(1)

# 4. publish the draft: GitHub's new draft system ignores tag/name changes when
#    they are combined with the draft:false flip (the PATCH returns 200 but
#    applies nothing), so publish and relabel must be two separate PATCHes. The
#    body carries the DOI as plain text — a markdown link in a non-draft release
#    payload trips GitHub's 'links/0/schema' 422 bug.
def publish():
    return api(f"{API}/releases/{RID}", {"draft": False}, method="PATCH")

status, rel = publish()
if status != 200 or rel.get("draft"):
    sys.exit(f"could not publish the draft release (status={status} draft={rel.get('draft')})")
print(f"draft published -> {rel['html_url']}")

def relabel():
    return api(f"{API}/releases/{RID}",
               {"tag_name": TAG, "name": NAME, "body": BODY_PLAIN,
                "draft": False, "prerelease": False}, method="PATCH")

status, rel = relabel()
if status != 200 or rel.get("tag_name") != TAG:
    sys.exit(f"could not relabel the release to tag {TAG} (status={status})")
print(f"PUBLISHED: {rel['html_url']}")
print("done")
