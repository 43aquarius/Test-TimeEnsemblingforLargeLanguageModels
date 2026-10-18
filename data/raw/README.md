# Source benchmark files

`build_dataset_v2.py` samples 15 questions per benchmark (seed 42) from the
official public release of each dataset. The source files are **not**
redistributed in this repository — download them from their official sources
below and place them in this directory with these exact filenames:

| File | Benchmark | Official source | License |
|------|-----------|-----------------|---------|
| `gsm8k_test.jsonl` | GSM8K (test) | https://github.com/openai/grade-school-math (`grade_school_math/data/test.jsonl`) | MIT |
| `truthfulqa.csv` | TruthfulQA (MC1) | https://github.com/sylinrl/TruthfulQA (`TruthfulQA.csv`) | Apache-2.0 |
| `piqa_valid.jsonl` | PIQA (valid) | https://yonatanbisk.com/piqa/data/ (`valid.jsonl` → `piqa_valid.jsonl`) | AFL-3.0 |
| `piqa_valid_labels.lst` | PIQA labels | same (`valid-labels.lst`) | AFL-3.0 |
| `lsat_lr.jsonl` | LSAT-LR | https://github.com/ruixiangcui/AGIEval (`data/lsat-lr.jsonl`) | MIT |
| `logiqa_en.jsonl` | LogiQA (EN) | https://github.com/ruixiangcui/AGIEval (`data/logiqa-en.jsonl`) | MIT |
| `sat_math.jsonl` | SAT-Math | https://github.com/ruixiangcui/AGIEval (`data/sat-math.jsonl`) | MIT |

Notes:

- AGIEval files use a unified `{passage, question, options, label}` schema;
  the LSAT-LR and LogiQA items in the paper are the English versions.
- PIQA data is distributed under AFL-3.0; by not redistributing it we keep
  this repository free of license ambiguity — the 15 sampled items inside
  `data/questions.json` are used for research evaluation with attribution.
- With all seven files present, `python scripts/build_dataset_v2.py`
  reproduces `data/questions.json` exactly (fixed seed and shuffle order).
