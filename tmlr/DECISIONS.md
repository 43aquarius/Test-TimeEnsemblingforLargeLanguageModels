# Decisions required from the author (new experiments, data, and sign-offs)

Everything below is needed before submission.  Items marked **(blocking)** gate
the OpenReview upload; the rest improve the paper but can proceed in parallel.

## 1. New experiments to run (scripts in `experiments/`, results are TODOs in the paper)

| # | Experiment | Script(s) | Needs from you | Where it lands |
|---|---|---|---|---|
| D1 | open-weight 16-call matrix on the 119 held-out questions | `run_vllm_matrix.py` | a machine with vLLM + one model id (e.g. Qwen3-8B); ~1.9k calls | tab_expand row; limitation 3; audit extension |
| D2 | held-out greedy-paraphrase control (PEg-6) | `run_greedy_para_heldout.py` + `endpoints.json` | working endpoints/keys for the four fully covered models; ~2.9k calls | Sections 5.2/B caveat; Appendix B table |
| D3 | SC-6 under the pre-registered best instruction, fresh SAT-Math draw | `select_best_instruction.py` (already run: selected P1, dev 89.9% vs canonical 90.6%) + `run_sc6_best_instruction.py` | the AGIEval SAT-Math source file path; endpoints | Section 5.3 TODO; limitation 6 |
| D4 | human equivalence spot-check, 100 LogiQA pairs | `make_equivalence_sample.py` (table already generated) + `summarize_equivalence.py` | one or two annotators for ~1-2 hours | limitation 4; fragility sensitivity |

After each run: paste the numbers into the TODO sites, extend
`audit_paper_numbers.py`, and re-run it.  **No number may be typed into the
paper without the log existing.**

## 2. Data and paths to supply

* **(blocking)** anonymous repository link for the Reproducibility Statement
  (OpenReview supplementary zip or anonymous GitHub).  The Zenodo DOI and the
  GitHub repo name stay out of the submission; add them only in the
  accepted/preprint variant.
* **(blocking)** AGIEval SAT-Math raw items file for D3b (any format with
  question/options/answer).
* raw log location, if different from the repository layout, for
  `audit_paper_numbers.py --root`.

## 3. Sign-offs and fact checks

* **(blocking)** fill `[TOOLS]` and `[PURPOSE]` in the AI declaration honestly;
  the current text explicitly states no experimental number was AI-generated.
* **(blocking)** verify every `[CHECK: ...]` model citation (Gemini3.8-Flash,
  GPT-6-Luna, Agnes 3.0/2.5, DeepSeek V4.1/Pro, Qwen 3.8/3.7) against the
  provider's official documentation; the served identity cannot be verified
  through the relays, which is why the flags exist.
* decide whether to keep "ten systems from five families" (includes both
  partial DeepSeek rows) -- currently kept as is, with the partials excluded
  from tabulation.

## 4. Editorial decisions already taken (confirm or override)

1. **Primary evidence**: held-out suite only; development suite is design-phase
   background in Appendix A.  Abstract carries one conclusion chain (B4).
2. **PE semantics**: every paraphrase margin is labelled "paraphrase ensemble
   (with sampling noise)"; the pure prompt-space claim is reserved for the
   dev-only greedy-paraphrase control.
3. **Error-signal claims**: per-model dominance downgraded to
   model-dependent; "Both strongest pooled" is descriptive (overlapping CIs);
   Either-coverage is an upper bound by construction.
4. **Mechanism wording**: the "answer-space diversity exhausted" reading is
   replaced everywhere by the instruction-effect reading, with the unrun
   best-instruction SC-6 control flagged.
5. **Numbers**: the audit script is authoritative; four paper numbers were
   corrected to recomputed values (see CHANGELOG C1-C4).
6. **Anonymization**: model names/endpoints kept (not author-identifying);
   author identity, repo, DOI removed; `accepted`/`preprint` style options
   re-enable them after acceptance.

## 5. Not attempted (and why)

* No rerun of RQ2/RQ3 on held-out **greedy-paraphrase** data: that is D2.
* No change to the benchmark suite or sample sizes: new data cannot be
  manufactured; scaling is listed as the first limitation.
* No fabricated annotation results: the D4 table ships blank by design.

## 6. Packaging (done; verify links before upload)

Two packages built by `scripts/build_tmlr_packages.py`, both re-scanned in-place
for identity strings (author name, institution, e-mail, repo name, Zenodo DOI,
API-key shapes) and internal documents:

| Package | Contents | Verified |
|---|---|---|
| `download/tmlr_submission_latex.zip` (36 files) | main.tex, refs.bib, tmlr.sty/.bst, math_commands.tex, fancyhdr.sty, sections/, tables/, figures/, compiled main.pdf (39 pp) | identity scan CLEAN; recompiles with tectonic (exit 0); no CHANGELOG/DECISIONS/REVIEW/audit files inside |
| `download/anonymous_repository.zip` (121 files) | data/, results/, supplementary_data/, pipeline scripts/, experiments/ (D1--D4), audit/audit_paper_numbers.py + sanitized 102/102 report, anonymous README + MIT LICENSE | identity scan CLEAN; audit re-run from the unzipped package reproduces 102/102 MATCH |

Excluded from the anonymous repository, with reasons:

1. `apinex_*.py` (6 probe scripts): contain a **hard-coded Apinex API key**.
   **Security: this key has been public since release v1.5.0 (GitHub) and is
   inside the Zenodo v1.8.1 archive -- rotate/revoke it at the provider.**
   The probes are exploratory and reproduce no paper number.
2. `final_crosscheck.py`: asserts against the de-anonymized Neurocomputing
   manuscript (Zenodo-DOI expectation, `paper/` paths); wrong manuscript for
   this package. `audit/audit_paper_numbers.py` is the TMLR verification pass.
3. Release/publishing and Word-building scripts, `scripts/word/` (creator
   field carries the author name): publication tooling, not research code.
4. `repo/paper/`, `repo/download/`, `.zenodo.json`, git history: de-anonymized
   or identity-bearing; never packaged.

The audit script's defaults were made portable (`--root .`), and one
determinism bug was fixed (an unsorted set changed bootstrap input order
across processes; now sorted, matching the release's recompute pass).
