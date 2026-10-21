#!/usr/bin/env python3
"""Build release assets for v1.4.0 (complete expansion set, two fully covered models)."""
import os, shutil, zipfile

SRC = "/home/z/my-project"
REPO = os.path.join(SRC, "github_repo")
OUT = os.path.join(SRC, "release_assets")
os.makedirs(OUT, exist_ok=True)


def zip_dir(src_dir, arc_root, dest, exclude_names=()):
    n = 0
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for root, dirs, files in os.walk(src_dir):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in sorted(files):
                if f in exclude_names:
                    continue
                p = os.path.join(root, f)
                z.write(p, os.path.join(arc_root, os.path.relpath(p, src_dir)))
                n += 1
    print(f"  {dest}  ({os.path.getsize(dest)/1024:.0f} KB, {n} files)")


shutil.copy2(os.path.join(SRC, "paper", "main.pdf"), os.path.join(OUT, "paper_main.pdf"))
shutil.copy2(os.path.join(SRC, "download", "paper_word_version.docx"),
             os.path.join(OUT, "paper_word_version.docx"))
print(f"  paper_main.pdf ({os.path.getsize(OUT+'/paper_main.pdf')/1024:.0f} KB)")
print(f"  paper_word_version.docx ({os.path.getsize(OUT+'/paper_word_version.docx')/1024:.0f} KB)")

print("Building latex_source.zip ...")
zip_dir(os.path.join(REPO, "paper"), "latex_source",
        os.path.join(OUT, "latex_source.zip"), exclude_names={"main.pdf", "main_flat.tex"})

print("Building supplementary_data.zip ...")
stage = os.path.join(OUT, "_supp_stage", "supplementary_data")
if os.path.exists(os.path.dirname(stage)):
    shutil.rmtree(os.path.dirname(stage))
os.makedirs(stage)
# data
for f in ["questions.json", "paraphrases.json", "para_validation.json", "mmlupro30.json",
          "nli_validation.json", "nli_summary.json", "nli_agnes_summary.json",
          "paraphrases_agnes.json", "para_sims_fresh.json",
          "questions_expand.json", "paraphrases_expand.json"]:
    shutil.copy2(os.path.join(SRC, "data", f), os.path.join(stage, f))
# greedy-bias audits (main suite v1.3.0 + expansion set v1.4.0)
for subdir in ("greedy_bias_audit", "greedy_bias_audit_expand"):
    dst = os.path.join(stage, subdir)
    os.makedirs(dst)
    src_d = os.path.join(SRC, "supplementary_data", subdir)
    for f in os.listdir(src_d):
        shutil.copy2(os.path.join(src_d, f), os.path.join(dst, f))
# raw predictions: main suite + all conditions + analysis
rp = os.path.join(stage, "raw_predictions")
os.makedirs(rp)
for m in ["qwen3.8-max", "qwen3.8-omni", "agnes-3.0-flash", "agnes-2.5-flash",
          "gpt-6-luna", "gemini-3.8-flash"]:
    shutil.copy2(os.path.join(SRC, "results", f"{m}.jsonl"), os.path.join(rp, f"{m}.jsonl"))
for cond in ["cond_greedypara", "cond_mmlupro", "cond_cot", "cond_agnespara"]:
    d = os.path.join(SRC, "results", cond)
    if os.path.exists(d):
        os.makedirs(os.path.join(rp, cond), exist_ok=True)
        for f in os.listdir(d):
            if f.endswith(".jsonl"):
                shutil.copy2(os.path.join(d, f), os.path.join(rp, cond, f))
shutil.copytree(os.path.join(SRC, "results", "analysis"), os.path.join(rp, "analysis"))
for f in ["status.txt", "cond_status.txt"]:
    shutil.copy2(os.path.join(SRC, "results", f), os.path.join(rp, f))
# expansion run: COMPLETE for both agnes models (v1.4.0), partial for the rest
exp = os.path.join(SRC, "results", "expand")
if os.path.exists(exp):
    os.makedirs(os.path.join(rp, "expand"), exist_ok=True)
    for f in os.listdir(exp):
        if f.endswith(".jsonl") or f == "status.txt":
            shutil.copy2(os.path.join(exp, f), os.path.join(rp, "expand", f))
# include the earlier probe-phase models too (kept from v1.0.0 set)
for m in ["agnes-2.5-pro", "agnes-2.5-alpha", "agnes-3.0-pro", "deepseek-v4.1",
          "glm-5.3-flash", "kimi-k3"]:
    p = os.path.join(SRC, "results", f"{m}.jsonl")
    if os.path.exists(p):
        shutil.copy2(p, os.path.join(rp, f"{m}.jsonl"))

SUPP_README = """Supplementary data for
"When Does Test-Time Ensembling Help Large Language Models?
 A Budget-Matched Study of Answer-Space and Prompt-Space Diversity"
Chang Tan, Dalian University of Technology
Preprint (revision v1.4.0), submitted to Neurocomputing (Elsevier)

Contents
--------
questions.json          90-question main evaluation set (6 benchmarks x 15, seed 42)
mmlupro30.json          30-question MMLU-Pro hard-task probe (seed 42, stratified)
paraphrases.json        paraphrases (6 per paraphrasable question) + instruction variants
paraphrases_agnes.json  second-generator paraphrases (Agnes3.0-Flash) + validation sims
para_validation.json    embedding-similarity validation report (original generator)
para_sims_fresh.json    fresh embedding similarities of the final paraphrase set
nli_validation.json     per-pair bidirectional entailment checks (267/270 pass)
nli_summary.json        NLI + stricter-threshold summary
questions_expand.json   119-question expansion set (20 per benchmark, disjoint from main)
paraphrases_expand.json expansion paraphrases + validation
greedy_bias_audit/      raw evidence for the main-suite greedy-vs-S1 audit (v1.3.0)
greedy_bias_audit_expand/  same audit on the expansion set (new in v1.4.0):
                        20/238 off-mode greedy decodes across the fully covered models
raw_predictions/        per-call raw predictions, one JSONL per model
  *.jsonl                 main 16-call matrix (six paper models + probe-phase models)
  cond_greedypara/        tau=0 decodes of each paraphrase (prompt-space isolation)
  cond_mmlupro/           MMLU-Pro probe: greedy + 6 samples per question
  cond_cot/               chain-of-thought condition (greedy + SC + stem PE)
  cond_agnespara/         second-generator paraphrase evaluation (partial, quota-limited)
  expand/                 expansion 16-call matrices on the 119-question set
                          (v1.4.0: COMPLETE for agnes-3.0-flash and agnes-2.5-flash,
                           119/119 each; qwen3.7-flash 60/119, deepseek models 9-13/119,
                           stopped by provider free-tier revocation)
  analysis/results.json   all aggregated numbers reported in the paper (v2 conditions)
  analysis/results_v3.json S1-baseline analysis with tie-randomized AURC and the
                          corrected Spearman keys (v1.3.0)
  analysis/expand_v1.json expansion-set per-model + pooled analysis (v1.4.0)
  analysis/expand_pooled_suppl.json  pooled PE-SC/PE-HB/COMB-PE gaps, strata, per-dataset
Record fields: model, qid, dataset, para, sample, temp, answer, correct,
content_len, reasoning_len, snippet, usage, t

The full repository (experiment code, manuscript source, regeneration scripts):
https://github.com/43aquaris/Test-TimeEnsemblingforLargeLanguageModels

License: code MIT; evaluation questions sampled from public benchmarks listed in
the repository (data/raw/README.md), their original licenses apply;
manuscript (c) 2026 Chang Tan.
"""
open(os.path.join(stage, "README.txt"), "w", encoding="utf-8").write(SUPP_README)
zip_dir(stage, "supplementary_data", os.path.join(OUT, "supplementary_data.zip"))
shutil.rmtree(os.path.dirname(stage))
print("Done.")
