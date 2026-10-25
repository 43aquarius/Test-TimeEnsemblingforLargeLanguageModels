#!/usr/bin/env python3
"""Build release assets for v1.8.1 (post-review correction pass: held-out RQ2/RQ3
recomputation, greedy-divergence count, instruction-variant control, LaTeX
residue cleanup, bibliography casing, Zenodo archival statement). Outputs into /home/z/my-project/release_assets:
paper_main.pdf, paper_word_version.docx, highlights.txt, Highlights.docx,
cover_letter.docx, latex_source.zip, supplementary_data.zip"""
import os, shutil, zipfile

ROOT = "/home/z/my-project/repo"
OUT = "/home/z/my-project/release_assets"
os.makedirs(OUT, exist_ok=True)

def zip_dir(src_dir, arc_root, dest, include_root=None, include_dirs=None):
    n = 0
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for root, dirs, files in os.walk(src_dir):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            rel_dir = os.path.relpath(root, src_dir)
            for f in sorted(files):
                if rel_dir == "." and include_root is not None and f not in include_root:
                    continue
                if rel_dir != "." and include_dirs is not None and rel_dir.split(os.sep)[0] not in include_dirs:
                    continue
                p = os.path.join(root, f)
                z.write(p, os.path.join(arc_root, os.path.relpath(p, src_dir)))
                n += 1
    print(f"  {dest}  ({os.path.getsize(dest)/1024:.0f} KB, {n} files)")

# ---- paper assets ----
print("Collecting paper assets ...")
shutil.copy2(os.path.join(ROOT, "paper", "main.pdf"), os.path.join(OUT, "paper_main.pdf"))
shutil.copy2(os.path.join(ROOT, "download", "paper_word_version.docx"),
             os.path.join(OUT, "paper_word_version.docx"))
shutil.copy2(os.path.join(ROOT, "paper", "highlights.txt"), os.path.join(OUT, "highlights.txt"))
shutil.copy2(os.path.join(ROOT, "download", "Highlights.docx"), os.path.join(OUT, "Highlights.docx"))
shutil.copy2(os.path.join(ROOT, "download", "cover_letter.docx"), os.path.join(OUT, "cover_letter.docx"))
for f in ("paper_main.pdf", "paper_word_version.docx", "highlights.txt",
          "Highlights.docx", "cover_letter.docx"):
    print(f"  {f}  ({os.path.getsize(os.path.join(OUT, f))/1024:.0f} KB)")

# ---- latex source ----
print("Building latex_source.zip ...")
zip_dir(os.path.join(ROOT, "paper"), "latex_source",
        os.path.join(OUT, "latex_source.zip"),
        include_root={"main.tex", "refs.bib", "main.bbl", "highlights.txt"},
        include_dirs={"sections", "tables", "figures"})

# ---- supplementary data ----
print("Building supplementary_data.zip ...")
stage = os.path.join(OUT, "_supp_stage", "supplementary_data")
if os.path.exists(os.path.dirname(stage)):
    shutil.rmtree(os.path.dirname(stage))
os.makedirs(stage)
for f in ["questions.json", "paraphrases.json", "para_validation.json", "mmlupro30.json",
          "nli_validation.json", "nli_summary.json", "nli_agnes_summary.json",
          "paraphrases_agnes.json", "para_sims_fresh.json",
          "questions_expand.json", "paraphrases_expand.json"]:
    shutil.copy2(os.path.join(ROOT, "data", f), os.path.join(stage, f))
for subdir in ("greedy_bias_audit", "greedy_bias_audit_expand"):
    dst = os.path.join(stage, subdir)
    os.makedirs(dst)
    src_sub = (os.path.join(ROOT, "results", "analysis", subdir)
               if subdir == "greedy_bias_audit"
               else os.path.join(ROOT, "supplementary_data", subdir))
    for f in os.listdir(src_sub):
        shutil.copy2(os.path.join(src_sub, f), os.path.join(dst, f))
rp = os.path.join(stage, "raw_predictions")
os.makedirs(rp)
for m in ["qwen3.8-max", "qwen3.8-omni", "agnes-3.0-flash", "agnes-2.5-flash",
          "gpt-6-luna", "gemini-3.8-flash"]:
    shutil.copy2(os.path.join(ROOT, "results", f"{m}.jsonl"), os.path.join(rp, f"{m}.jsonl"))
for cond in ["cond_greedypara", "cond_mmlupro", "cond_cot", "cond_agnespara"]:
    d = os.path.join(ROOT, "results", cond)
    if os.path.exists(d):
        os.makedirs(os.path.join(rp, cond), exist_ok=True)
        for f in os.listdir(d):
            if f.endswith(".jsonl"):
                shutil.copy2(os.path.join(d, f), os.path.join(rp, cond, f))
shutil.copytree(os.path.join(ROOT, "results", "analysis"), os.path.join(rp, "analysis"))
for f in ["status.txt", "cond_status.txt"]:
    p = os.path.join(ROOT, "results", f)
    if os.path.exists(p):
        shutil.copy2(p, os.path.join(rp, f))
exp = os.path.join(ROOT, "results", "expand")
os.makedirs(os.path.join(rp, "expand"), exist_ok=True)
for f in os.listdir(exp):
    if f.endswith(".jsonl") or f == "status.txt":
        shutil.copy2(os.path.join(exp, f), os.path.join(rp, "expand", f))

README = """Supplementary data for
"When Does Test-Time Ensembling Help Large Language Models?
 A Budget-Matched Study of Answer-Space and Prompt-Space Diversity"
Chang Tan, Dalian University of Technology
Preprint (revision v1.8.1, submission-ready), to be submitted to
Neurocomputing (Elsevier)

Contents
--------
questions.json          90-question development suite (6 benchmarks x 15, seed 42)
mmlupro30.json          30-question MMLU-Pro hard-task probe (seed 42, stratified)
paraphrases.json        paraphrases (6 per paraphrasable question) + instruction variants
paraphrases_agnes.json  second-generator paraphrases (Agnes3.0-Flash) + validation sims
para_validation.json    embedding-similarity validation report (original generator)
para_sims_fresh.json    fresh embedding similarities of the final paraphrase set
nli_validation.json     per-pair bidirectional entailment checks (267/270 pass)
nli_summary.json        NLI + stricter-threshold summary
nli_agnes_summary.json  second-generator NLI summary (269/270 pass)
questions_expand.json   119-question held-out suite (20 per benchmark, disjoint)
paraphrases_expand.json held-out paraphrases + validation
greedy_bias_audit/      raw evidence for the development-suite greedy-vs-S1 audit
greedy_bias_audit_expand/  same audit on the held-out suite (50/476 off-mode
                        greedy decodes pooled over the four fully covered models)
raw_predictions/analysis/rq23_expand.json
                        held-out RQ2/RQ3 recomputation (fragility by locus,
                        AUROC with bootstrap CIs, instruction-variant control)
raw_predictions/        per-call raw predictions, one JSONL per model
  *.jsonl                 16-call matrix, development suite (six systems + probes)
  cond_greedypara/        tau=0 decodes of each paraphrase (prompt-space isolation)
  cond_mmlupro/           MMLU-Pro probe: greedy + 6 samples per question
  cond_cot/               chain-of-thought condition (greedy + SC + stem PE)
  cond_agnespara/         second-generator paraphrase evaluation (partial, quota-limited)
  expand/                 16-call matrices on the 119-question held-out suite
                          (COMPLETE 119/119: agnes-3.0-flash, agnes-2.5-flash,
                           deepseek-v4.1-flash, deepseek-v4-pro-0813;
                           partial: qwen3.7-flash 60/119, deepseek-v4-flash-0731 13/119)
  analysis/               all aggregated numbers reported in the paper:
    results.json            v2 conditions + sensitivity (lenient rule, excluded-vs-included)
    results_v3.json         S1-baseline analysis, tie-randomized AURC, Spearman keys
    expand_v1.json          held-out per-model + pooled analysis (four full models)
    expand_pooled_suppl.json pooled gaps, strata, per-dataset decomposition
    recompute_report.json   independent recomputation: 106 checks re-deriving
                            every cited number from the raw logs (all pass), plus
                            Holm-adjusted p-values, the 90+119 combined analysis,
                            and per-system parse rates
Record fields: model, qid, dataset, para, sample, temp, answer, correct,
content_len, reasoning_len, snippet, usage, t

The full repository (experiment code, manuscript source, regeneration scripts
including scripts/recompute_all.py, which re-derives every table and statistic
from these raw logs):
https://github.com/43aquarius/Test-TimeEnsemblingforLargeLanguageModels

v1.8.0 note: the manuscript's 42 references were verified against publisher
records; preprints that have since appeared in peer-reviewed venues are cited
by their formal publications (ICML 2024, ICLR 2025, NAACL 2024, NeurIPS 2024,
AAAI 2020) and 11 DOIs were added.

License: code MIT; evaluation questions sampled from public benchmarks listed in
the repository (data/raw/README.md), their original licenses apply;
manuscript (c) 2026 Chang Tan.
"""
open(os.path.join(stage, "README.txt"), "w", encoding="utf-8").write(README)
zip_dir(stage, "supplementary_data", os.path.join(OUT, "supplementary_data.zip"))
shutil.rmtree(os.path.dirname(stage))
print("done")
