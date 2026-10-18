# When Does Test-Time Ensembling Help Large Language Models?

**A Budget-Matched Study of Answer-Space and Prompt-Space Diversity**

Chang Tan · Dalian University of Technology · aquars43@foxmail.com

> Preprint, submitted to *Neurocomputing* (Elsevier).
> 📦 Manuscript and full research artifacts: **[Release v1.0.0](https://github.com/43aquarius/Test-TimeEnsemblingforLargeLanguageModels/releases/tag/v1.0.0)**

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
2. **Where genuine answer entropy exists, both diversity sources help.** Example: Agnes3.0-Flash improves from 78.8% (greedy) to 90.9% under both SC-6 and PE-6 on its completed question set.
3. **Majority voting can hurt.** When the modal answer is wrong, voting locks the error in — spending the same budget on paraphrases can recover it.
4. **The two agreement signals are complementary.** Paraphrase agreement and sample agreement each predict ensemble errors (AUROC), but which one is stronger differs across models; neither subsumes the other.
5. **Practical rule: measure agreement first, then allocate the budget.** Answer entropy (cheap to estimate) predicts where ensembling pays off; aggregation configuration belongs in the reporting standard of every evaluation that uses it.

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

## Release contents (v1.0.0)

| Asset | Description |
|---|---|
| `paper_main.pdf` | Manuscript PDF (26 pages, submission version) |
| `paper_word_version.docx` | Manuscript, Word format |
| `latex_source.zip` | Complete LaTeX source (elsarticle) |
| `supplementary_data.zip` | Questions, paraphrases, validation report, raw predictions for all models, and aggregated analysis |

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
