# When Does Test-Time Ensembling Help Large Language Models?

**A Budget-Matched Study of Answer-Space and Prompt-Space Diversity**

Chang Tan · Dalian University of Technology · aquars43@foxmail.com

> Preprint, submitted to *Neurocomputing* (Elsevier).
> 📦 Manuscript and full research artifacts: **[Release v1.1.0 (revised)](https://github.com/43aquarius/Test-TimeEnsemblingforLargeLanguageModels/releases/tag/v1.1.0)** · [v1.0.0 (original)](https://github.com/43aquarius/Test-TimeEnsemblingforLargeLanguageModels/releases/tag/v1.0.0)

---

## Overview

Test-time ensembling improves the reliability of large language models by aggregating answers from multiple model calls instead of trusting a single greedy prediction. Two families of strategies dominate practice:

- **Self-consistency (SC)** resamples the stochastic decoder on one fixed prompt — the ensemble varies along the *answer space*.
- **Prompt ensembling (PE)** fixes the decoding configuration and varies the prompt over semantically equivalent paraphrases — the ensemble varies along the *prompt space*.

Both families consume the same scarce resource — the number of model calls — yet prior work studies them in isolation. This repository accompanies a controlled, **budget-matched comparison** across **six commercial LLMs** (Qwen3.8-Max, Qwen3.8-Omni, Agnes3.0-Flash, Agnes2.5-Flash, GPT-6-Luna, Gemini3.8-Flash) and **six benchmarks** (GSM8K, TruthfulQA-MC1, PIQA, LSAT-LR, LogiQA, SAT-Math). Under a unified protocol, every question is answered **16 times per model**:

| Condition | Calls | Composition |
|---|---|---|
| Greedy | 1 | temperature-0 decode of the original prompt |
| SC-6 | 6 | 6 stochastic decodes (T = 0.7) of the original prompt |
| PE-6 | 6 | 6 validated paraphrases, one decode each |
| HB-6 | 6 | 3 paraphrases × 2 decodes each (hybrid) |
| COMB-12 | 12 | union of SC-6 and PE-6 |

Paraphrases were generated with an LLM and retained only if their sentence-embedding cosine similarity to the original stayed ≥ 0.75 (see `data/para_validation.json`).

## Key findings

1. **A regime structure governs everything.** On benchmarks that modern flagships saturate, the sampled answer distribution degenerates to a single value: both ensembles collapse exactly onto the greedy baseline, and consistency-based uncertainty estimation loses its discriminative power — a caution for hallucination-detection methods built on sampling.
2. **Against the correct k=1 baseline, no systematic gain is detected in this data.** Measured against S1 (the expected accuracy of one stochastic draw), pooled SC-6 is +0.9 pp and PE-6 is −0.9 pp, with COMB-12 exactly at S1; 104 of the 112 pooled model-question pairs are unanimous and the two six-vote ensembles differ on only two pairs. The much larger greedy-referenced gains reported in v1.0.0/v1.1.0 (e.g. Agnes3.0-Flash +12.1 pp) are mostly an artifact of the greedy reference, which sits 4–11 pp below the sampled expectation on two models (mode locking + one truncation artifact; raw evidence in `results/analysis/greedy_bias_audit/`). For greedy-only deployments, switching to a single stochastic draw recovers the gap at no extra cost.
3. **The differences that do appear are exploratory and track whether the modal answer is correct.** On the two least-covered models (n=15, n=12), where the sample-side modal answer is wrong on their LogiQA subsets (5 and 3 questions), PE-6 gains +10.0/+5.6 pp over S1 (intervals touching zero) while SC-6 loses 3.3/2.8 pp (intervals spanning zero) — the direction of the plurality-vote signature, read as descriptive.
4. **The two agreement signals are complementary.** Paraphrase agreement and sample agreement each predict ensemble errors (AUROC), but which one is stronger differs across models; neither subsumes the other.
5. **Practical rule: measure agreement first, then allocate the budget.** Disagreement strongly predicts the fragility of the greedy reference (Spearman +0.80 between dissent share and the S1−greedy gap, driven by the 8 non-unanimous of 112 pooled pairs) but only weakly the ensemble gain over S1 (+0.17); a sequential unanimity rule (a special case of early-stopping self-consistency) preserves SC-6 accuracy within one question at 2–3 calls, and an adaptive probe rule reproduces fixed PE-6 on five of six models at 68–78% of its calls (matching the best fixed strategy on four of six) — its measured value is the call saving, not accuracy.


## Version history

- **v1.5.0 (Oct 2026) — third fully covered expansion model: DeepSeekV4.1-Flash (119/119, second free provider).** After the original endpoint exhausted its free tier at 9 questions, the matrix was rerun from scratch on a second free endpoint (direct-answer mode, parse rate 99.9%; the 9-question aliyun original is kept as `results/expand/deepseek-v4.1-flash.aliyun.jsonl`). The sibling DeepSeekV4-Flash-0731 stopped at 13/119 when that endpoint moved it behind a paid subscription mid-collection and is excluded from tabulation. With three fully covered models the pooled analysis runs over 357 model-question pairs: SC-6 +2.3 pp [+0.8, +3.8], PE-6 +5.1 pp [+2.6, +7.8], COMB-12 +3.4 pp [+1.4, +5.5] over S1, all excluding zero, while PE-SC stays within noise (+2.8 pp [−0.3, +5.9]); the two pooled separations v1.4.0 carried (PE>HB, COMB<PE) disappear once the third model joins, whose significant conditions are its mixed allocations (HB-6/COMB-12 83.2%, +5.6 pp [+1.5, +9.8] over S1) — what replicates is the prompt-space margin, not a single winning allocation. Weak-majority stratum now 46 pairs: PE-6 52.8% vs SC-6 31.3% vs S1 30.8%. The tau=0 greedy anomaly reappears on exactly one of the three models (DeepSeekV4.1: S1-greedy +4.5 pp, 13 of 16 off-mode greedy answers wrong, no truncation) — a model-endpoint property, not a question-draw property. The adaptive rule strictly dominates every fixed allocation on that model (84.0% at 87% of budget, +1q over HB/COMB), the first such instance in either suite; pooled it returns 85.2% at 84% of budget. Expansion tables rebuilt with three model blocks and correct 3-model pooled rows (a first-model-only indexing bug in the pooled per-dataset console print was fixed; the released tables and JSON were always correct); abstract, results, discussion, conclusion updated; greedy off-mode audit re-exported (36/357 pooled).
- **v1.4.0 (Oct 2026) — complete expansion set: two-model out-of-sample validation.** Agnes2.5-Flash expansion coverage completed (119/119; was 89/119), joining Agnes3.0-Flash (119/119) for a pooled analysis over 238 model–question pairs (cluster bootstrap on questions). Pooled, both ensembles separate from S1 with CIs excluding zero — SC-6 +2.3 pp [+0.6, +4.1], PE-6 +5.7 pp [+2.3, +9.2] — while PE−SC stays within noise (+3.4 pp [−0.4, +7.6]): the paraphrase ensemble is the only condition with a well-powered pooled gain, but the two-source ordering remains unresolved. The stratum mechanism replicates in both models (weak-majority stratum: PE-6 54.2% vs SC-6 29.2% vs S1 29.5%, pooled n=32). Dataset mechanism refined: pooled SAT-Math carries the PE advantage (PE-6 100.0 vs SC-6 80.0), while on LogiQA the ordering reverses on Agnes2.5 — on stem-locus datasets it is a property of the model–paraphrase interaction. New pooled contrasts: PE-6 > HB-6 (+3.4 [+0.8, +5.9]) and COMB-12 < PE-6 (−3.4 [−6.7, −0.4]). Adaptive rule transfer test: budget transfers (79–86% of six-call budget), allocation does not (reproduces SC-6 exactly on Agnes3.0, trails best fixed by 1–2 questions on Agnes2.5, up to 7 below PE-6). The τ=0 greedy anomaly does not replicate out of sample (S1−greedy −1.1/−1.8 pp vs +10.6 in the main suite). Expansion tables rebuilt with both models and pooled rows; abstract, results, discussion, and conclusion updated. New artifacts: `greedy_bias_audit_expand/`, `analysis/expand_v1.json`, `analysis/expand_pooled_suppl.json`.
- **v1.3.0 (Oct 2026) — consistency fixes and claim calibration.** Corrects the sign convention of the two headline Spearman correlations (dissent share vs. S1−greedy is +0.80, not −0.80; dissent vs. COMB−S1 gain is +0.17), and adds the tie-structure caveat (104/112 pooled pairs unanimous; within the 8 non-unanimous pairs the gap correlation is +0.57; |gap| variant unchanged). Replaces the previously mislabeled "disjoint-vote" correlations with the correctly disjoint computations (sample-side dissent vs. PE−S1: −0.20; paraphrase-side dissent vs. SC−S1: +0.54). Fixes a 100× scaling error in the Diss.% column of the regime table (1.1/2.8/33.3, not 111/278/3333), redraws the regime figure against the dissent share with the S1-referenced gains, and rewrites its caption and the high-dissent paragraph to match (the two largest gains over S1 are the two highest-dissent LogiQA cells, +30.0 and +22.2). Corrects the pooled SC−PE interval to the cluster-bootstrap 95% CI [0.0, +5.4] (the previously quoted [0.0, +3.6] was the TOST 90% interval) and notes that the 1.8 pp pooled difference is carried by exactly two (model, question) pairs. Removes in-text version-history comparisons from the manuscript. Adds the fixed-paraphrase-ensemble comparison for the adaptive rule (equals PE-6 on 5/6 models; increment is the call saving), a decoding recommendation for greedy-only deployments, and a greedy-bias audit export with raw outputs of every audited question (results/analysis/greedy_bias_audit/). Word version rebuilt with real caption numbering (SEQ fields) and live cross-references (REF fields), Unicode τ, and the corrected figures; two unresolved citations ([10, ?]) repaired.
- **v1.2.0 (Oct 2026) — S1-baseline revision.** The single-sample expectation S1 replaces greedy decoding as the primary k=1 baseline throughout; all gains, figures, and the abstract are recomputed (pooled SC-6−S1 = +0.9 pp, PE-6−S1 = −0.9 pp, COMB-12 = S1). The greedy reference is retained as a secondary column with a quantified audit of its bias (one truncation artifact, two mode-locking cases). AURC is recomputed with uniformly random tie-breaking (1,000 permutations), fixing an ordering artifact (e.g. Qwen3.8-Omni cs 0.009 → 0.031; Agnes3.0-Flash cp 0.158 → 0.073). The support-normalized entropy is replaced by the modal vote share as the headline disagreement statistic, with strata re-cut at share = 1 / [2/3, 1) / < 2/3. The greedy-paraphrase control now reports per-question answer identity between PE-g-6 and PE-6 (88/88, 31/32, 38/39, 11/15, 10/12). The Condorcet-style section is restated as a heuristic model with an asymptotic claim and an explicit idealization list. Adaptive-allocation claims are restated exactly (matches best fixed on 4/6 models, trails by one question on 2/6, 68–78% of budget, same-data caveat), and the early-stopping rule is positioned as a reproduction of Adaptive-Consistency/ESC. A 119-question expansion set (data/questions_expand.json) and a partial agnes-3.0-flash expansion run (results/expand/) are included; the run is rate-limited and in progress.
- **v1.1.0 (Oct 2026)** — first revision: corrected AURC direction, cluster bootstrap, McNemar/TOST, follow-up conditions (greedy paraphrases, MMLU-Pro, CoT), NLI validation, expanded limitations.
- **v1.0.0 (Oct 2026)** — original release.

## Repository structure

```
.
├── paper/                  # Manuscript (LaTeX source + compiled main.pdf)
│   ├── main.tex            # elsarticle preprint format
│   ├── sections/           # 7 section files
│   ├── tables/             # auto-generated from results (gen_tables.py)
│   ├── figures/            # auto-generated from results (make_figures.py)
│   └── refs.bib            # 29 references
├── scripts/                # Full experiment pipeline (Python + Node)
│   ├── run_experiment.py   # 16-call matrix per question × model
│   ├── analyze.py          # conditions, AUROC, statistical tests
│   ├── gen_tables.py       # LaTeX tables
│   ├── make_figures.py     # publication figures
│   ├── word/               # Word manuscript generator (Node, docx)
│   └── credentials.example.py
├── data/
│   ├── questions.json      # 90 questions = 6 benchmarks × 15 (seed 42)
│   ├── paraphrases.json    # 6 paraphrases per paraphrasable question
│   ├── para_validation.json# embedding-similarity validation report
│   └── raw/                # where to put the source benchmark files (see README)
└── results/
    ├── *.jsonl             # raw per-call predictions, 6 models
    ├── analysis/           # results.json (all reported numbers), pooled.json
    └── status.txt          # experiment run log (rate-limit context)
```

## Reproducing the study

### 0. Setup

```bash
pip install aiohttp matplotlib      # Python 3.10+
cp scripts/credentials.example.py scripts/credentials.py   # fill in your keys
```

### 1. Build the question set (optional — `data/questions.json` is included)

Download the six source benchmark files listed in [`data/raw/README.md`](data/raw/README.md), then:

```bash
python scripts/build_dataset_v2.py     # seed 42 → same 90 questions
```

### 2. Generate and validate paraphrases (optional — included)

```bash
python scripts/gen_paraphrases.py          # LLM-generated paraphrases
python scripts/validate_paraphrases.py     # embedding similarity gate (≥ 0.75)
python scripts/update_instructions.py      # hand-written instruction variants
```

### 3. Run the experiment (needs API keys)

```bash
python scripts/run_experiment.py           # resumable JSONL output
```

Provider rate limits differ; `results/status.txt` shows the rate environment of
the reported run. Coverage therefore differs across models (Qwen models: 88/71
of 90 questions; others less — all within-model comparisons are paired, see
paper Section 5).

### 4. Analyze (no API needed — works on the included predictions)

```bash
python scripts/analyze.py        # → results/analysis/results.json
python scripts/check_quality.py  # sanity checks on the raw data
```

### 5. Regenerate paper artifacts

```bash
python scripts/gen_tables.py     # → paper/tables/*.tex
python scripts/make_figures.py   # → paper/figures/*.pdf
cd paper && latexmk -pdf main.tex            # or pdflatex + bibtex
npm install docx image-size && node scripts/word/generate.js   # Word version
```

## Benchmark sources

The evaluation questions are sampled (seed 42, 15 each) from the official
public releases of six benchmarks. The source files are **not** redistributed
here; download them per [`data/raw/README.md`](data/raw/README.md) and follow
their original licenses.

## Revision v1.1.0 — what changed

The revision adds follow-up conditions and controls, and corrects the analysis:

- **Corrected AURC** (acceptance order now confidence-descending) and added bootstrap CIs, question-level cluster bootstrap for pooled statistics, McNemar tests, and TOST equivalence tests; "no difference detected" language replaces "statistically indistinguishable".
- **Single-sample baseline (S1)** added throughout; greedy is not interchangeable with one stochastic draw.
- **Greedy-paraphrase control**: every paraphrase re-decoded at τ=0, isolating prompt-space effects from decoding noise (5 models).
- **MMLU-Pro hard-task probe** (30 questions, 10 options) and a **chain-of-thought condition** (4 models + flagship subset).
- **Paraphrase robustness**: second generator (Agnes3.0-Flash), bidirectional NLI validation (267/270 and 269/270 pass), stricter-threshold fragility.
- **Budget-efficiency simulations**: sequential unanimity early stopping (SC-6 accuracy at 2-3 calls mean) and adaptive allocation (matches or beats fixed strategies at ~4.5 calls).
- **Condorcet-style model** of when majority voting helps or hurts.
- Full comparison coverage for Qwen3.8-Max (90/90 questions), parse-failure retry + sensitivity analysis, per-locus (stem vs instruction) stratification, token-cost accounting, expanded limitations.

## Release contents (v1.4.0)

| Asset | Description |
|---|---|
| `paper_main.pdf` | Manuscript PDF (51 pages, submission version) |
| `paper_word_version.docx` | Manuscript, Word format |
| `latex_source.zip` | Complete LaTeX source (elsarticle) |
| `supplementary_data.zip` | Questions, paraphrases, validation reports, MMLU-Pro probe, raw predictions for all conditions, greedy-bias audit evidence, expansion set, and aggregated analysis |

## Citation

```bibtex
@article{tan2026testtime,
  title   = {When Does Test-Time Ensembling Help Large Language Models?
             A Budget-Matched Study of Answer-Space and Prompt-Space Diversity},
  author  = {Tan, Chang},
  journal = {Preprint, submitted to Neurocomputing},
  year    = {2026},
  note    = {\url{https://github.com/43aquarius/Test-TimeEnsemblingforLargeLanguageModels}}
}
```

## License

- **Code and scripts:** MIT (see [LICENSE](LICENSE)).
- **Evaluation questions:** sampled from the benchmarks above; each subset is governed by its original license.
- **Manuscript:** © 2026 Chang Tan. Preprint submitted to *Neurocomputing* (Elsevier).

---

## 中文简介

本仓库配套论文《When Does Test-Time Ensembling Help Large Language Models? A Budget-Matched Study of Answer-Space and Prompt-Space Diversity》（投稿至 Neurocomputing）。研究在严格对齐调用预算的条件下（每题每模型16次调用），系统比较了自一致性（答案空间多样性）与提示改写集成（提示空间多样性）两种测试时集成策略，覆盖6个商用大模型与6个推理/知识基准。核心发现：集成策略的有效性由“答案分布是否退化”这一前提决定——旗舰模型在饱和基准上答案分布塌缩，一切集成与一致性不确定性信号均失效；而在高熵区域，两种多样性来源均显著提升准确率，且两种一致性信号在错误检测上互补。仓库包含论文全文（LaTeX/PDF/Word）、完整实验代码、90道评测题、验证过的改写、以及全部原始预测结果（见 Release v1.0.0）。
