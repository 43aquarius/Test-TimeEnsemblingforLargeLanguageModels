# Experiment pipeline

Ten Python scripts plus a Node-based Word generator reproduce the paper
end-to-end. They are the exact scripts used for the reported experiments,
with one packaging change: absolute paths from the original research
environment were rewritten to a portable `ROOT` variable computed from each
script's location, so the pipeline runs from any checkout.

## Order of execution

| # | Script | Purpose | Needs API keys? |
|---|--------|---------|-----------------|
| 1 | `build_dataset_v2.py` | Sample 90 questions (6 benchmarks × 15, seed 42) from `data/raw/*` → `data/questions.json` | no |
| 2 | `gen_paraphrases.py` | Generate 6 paraphrases per paraphrasable question → `data/paraphrases.json` | yes |
| 3 | `validate_paraphrases.py` | Score paraphrases with sentence-embedding cosine similarity → `data/para_validation.json` | yes |
| 4 | `validate_v2.py` | Re-validate after manual edits; writes back `paraphrases.json` | yes |
| 5 | `update_instructions.py` | Apply hand-written instruction variants for instruction-type datasets | no |
| 6 | `run_experiment.py` | The 16-call matrix per (model, question) → `results/<model>.jsonl` | yes |
| 7 | `analyze.py` | Compute all conditions, AUROCs, statistical tests → `results/analysis/` | no |
| 8 | `check_quality.py` | Sanity checks over raw predictions | no |
| 9 | `gen_tables.py` | Regenerate `paper/tables/*.tex` from `results/analysis/results.json` | no |
| 10 | `make_figures.py` | Regenerate `paper/figures/*.pdf` | no |
| 11 | `word/generate.js` | Regenerate the Word manuscript (`docx` + `image-size` npm packages) | no |

## Credentials

Scripts 2, 3, 4, and 6 import provider endpoints from a local module:

```bash
cp credentials.example.py credentials.py   # then edit in your own keys
```

`credentials.py` is git-ignored. Every provider endpoint in the study is
OpenAI-compatible (`/v1/chat/completions`).

## Notes

- **Answer extraction.** Multiple-choice tasks use a direct-answer instruction
  ("Reply with only the letter..."); GSM8K keeps chain-of-thought and extracts
  the final number. `run_experiment.py` records extraction success per call.
- **Resumability.** `run_experiment.py` appends to per-model JSONL files and
  skips (model, question, condition) tuples already present, so it survives
  interruptions and rate-limit windows.
- **Rate limits.** Providers differ by orders of magnitude (from ~0.1 to ~10
  req/s in our run). `results/status.txt` shows the throughput environment of
  the reported run.
- **Analysis needs no API access.** Steps 7–11 run offline on the committed
  predictions, so every number and figure in the paper can be regenerated
  without spending a single API call.
- **Python dependencies:** `aiohttp`, `matplotlib` (everything else is
  stdlib). **Node dependencies:** `docx`, `image-size`.
