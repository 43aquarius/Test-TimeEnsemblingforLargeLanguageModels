#!/usr/bin/env python3
"""Create GitHub Release v1.4.0 and upload assets (complete expansion set)."""
import json, os, sys, time, urllib.request

TOKEN = os.environ.get("GH_TOKEN")
if not TOKEN:
    sys.exit("Set GH_TOKEN")
OWNER_REPO = "43aquaris/Test-TimeEnsemblingforLargeLanguageModels"
API = f"https://api.github.com/repos/{OWNER_REPO}"
UPLOADS = f"https://uploads.github.com/repos/{OWNER_REPO}"
ASSETS = "/home/z/my-project/release_assets"
TAG = "v1.4.0"

BODY = """## When Does Test-Time Ensembling Help Large Language Models? (Revision v1.4.0)
**A Budget-Matched Study of Answer-Space and Prompt-Space Diversity**

Chang Tan - Dalian University of Technology

Preprint (fourth revision), to be submitted to *Neurocomputing* (Elsevier). This revision completes the fresh-question expansion set: both Agnes models now cover all 119 questions, turning the exploratory single-model expansion into a two-model out-of-sample validation.

### What changed from v1.3.0

**Complete expansion set (the headline of this revision)**
- **Agnes2.5-Flash expansion coverage completed: 119/119** (was 89/119 at v1.3.0 packaging). Together with Agnes3.0-Flash (119/119), the expansion set now supports a two-model pooled analysis over 238 model-question pairs, cluster-bootstrapped on questions.
- The aliyun free tier (Qwen3.7-Flash, both DeepSeek models) was revoked mid-collection; their partial matrices (60, 9, 13 of 119) are released as-is and excluded from tabulation.

**Out-of-sample results (new in the paper)**
- Pooled over the two fully covered models, **both ensembles separate from S1 with CIs excluding zero**: SC-6 +2.3 pp [+0.6, +4.1] and **PE-6 +5.7 pp [+2.3, +9.2]**, while **PE-SC remains within noise** (+3.4 pp [-0.4, +7.6]) - the main-suite null on the two-source ordering replicates, but the paraphrase ensemble is now the only condition with a well-powered pooled gain.
- Per-model: Agnes3.0 PE-6 87.4 vs S1 79.6 (+7.8 [+2.4, +13.7]); Agnes2.5 PE-6 91.6 vs S1 88.1 (+3.5 [+0.4, +7.0]), SC-6 +2.7 [+0.7, +4.9].
- **Stratum mechanism replicates in both models**: in the weak-majority stratum PE-6 reaches 54.2% against 29.2% for SC-6 and 29.5% for S1 (pooled, n=32) - a +25 pp prompt-space margin exactly where answer-space votes have nothing to aggregate; unanimous stratum saturated at 97.6%.
- **Dataset mechanism refined**: pooled SAT-Math carries the PE advantage (PE-6 100.0 vs SC-6 80.0; dPE +9.2 vs dSC +0.0), while on LogiQA the PE-SC ordering is model-dependent (reverses on Agnes2.5) - on stem-locus datasets the ordering is a property of the model-paraphrase interaction, not of the dataset.
- **Difficulty-confound decomposition extended to both models**: pooled PE-1 - S1 = +1.4 pp, so at most a quarter of the pooled PE-6-over-S1 margin is paraphrase difficulty; within-family aggregation gains are dPE +4.3 vs dSC +2.3.
- New pooled contrasts: **PE-6 beats HB-6** (+3.4 pp [+0.8, +5.9]) and **COMB-12 trails PE-6** (-3.4 pp [-6.7, -0.4]) - mixing the two diversity sources dilutes the prompt-space margin rather than hedging it, on this distribution.
- **Adaptive rule transfer test completed**: transfers in budget (79-86% of six-call budget) but not in allocation - it reproduces SC-6 exactly on Agnes3.0 (0-question gap) and trails the best fixed strategy by 1-2 questions on Agnes2.5, sitting up to 7 questions below PE-6 where its two-call probe routes prompt-rewarding questions to the hybrid vote.
- The tau=0 greedy anomaly does not replicate out of sample (S1 - greedy = -1.1/-1.8 pp on the two models vs +10.6 in the main suite; 20/238 off-mode decodes cost nothing on average), bounding the main-suite greedy audit as endpoint-specific.

**Artifacts**
- `greedy_bias_audit_expand/`: the same raw-evidence audit on the expansion set (15 + 5 off-mode decodes across the two covered models).
- `analysis/expand_v1.json` + `analysis/expand_pooled_suppl.json`: complete expansion-set per-model and pooled statistics.
- Expansion tables rebuilt (both models + pooled rows + per-dataset decomposition with PE-1); abstract, results, discussion, and conclusion updated for the two-model validation.

### Assets
| File | Content |
|---|---|
| `paper_main.pdf` | Full manuscript (51 pages) |
| `paper_word_version.docx` | Word version with live caption fields and cross-references |
| `latex_source.zip` | Complete LaTeX source |
| `supplementary_data.zip` | Questions, paraphrases, validation reports, audits, all raw predictions incl. the complete expansion matrices, analysis JSONs |

All numbers are regenerable from the released call matrices via the repository scripts (`analyze_expand.py`, `pooled_suppl.py`).
"""

def api(url, data=None, method=None, ctype="application/json", token=None):
    req = urllib.request.Request(url, method=method or ("POST" if data else "GET"))
    req.add_header("Authorization", f"Bearer {TOKEN}")
    if data is not None:
        req.add_header("Content-Type", ctype)
        data = data if isinstance(data, bytes) else json.dumps(data).encode()
    with urllib.request.urlopen(req, data=data) as r:
        return r.status, json.loads(r.read() or b"{}")

# 1. get default branch head
status, repo = api(f"{API}")
head = repo["default_branch"]
status, ref = api(f"{API}/git/ref/heads/{head}")
sha = ref["object"]["sha"]
print(f"default branch {head} @ {sha[:7]}")

# 2. create tag
status, tag = api(f"{API}/git/tags", {"tag": TAG, "message": f"Release {TAG}",
                                      "object": sha, "type": "commit"})
print(f"tag {TAG} -> {tag['object']['sha'][:7]}")
status, ref = api(f"{API}/git/refs", {"ref": f"refs/tags/{TAG}", "sha": tag["object"]["sha"]})
print(f"ref refs/tags/{TAG}: {status}")

# 3. create release
status, rel = api(f"{API}/releases", {"tag_name": TAG, "name": TAG,
                                      "body": BODY, "draft": False, "prerelease": False})
print(f"release id={rel['id']} url={rel['html_url']}")
RID = rel["id"]

# 4. upload assets
for fn in ["paper_main.pdf", "paper_word_version.docx", "latex_source.zip", "supplementary_data.zip"]:
    path = os.path.join(ASSETS, fn)
    ctype = "application/zip" if fn.endswith(".zip") else (
        "application/pdf" if fn.endswith(".pdf") else
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    url = f"{UPLOADS}/releases/{RID}/assets?name={fn}"
    req = urllib.request.Request(url, method="POST")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", ctype)
    with open(path, "rb") as f:
        data = f.read()
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, data=data) as r:
                a = json.loads(r.read())
                print(f"  uploaded {fn} ({len(data)/1024:.0f} KB) -> {a['browser_download_url']}")
            break
        except Exception as e:
            print(f"  retry {fn}: {e}")
            time.sleep(10)
print("done")
