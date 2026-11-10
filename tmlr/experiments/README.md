# Planned experiments (D1--D4): protocols and scripts

These four experiments close the evidence gaps identified in the TMLR
submission.  **None of their results is in the paper yet**; each is carried in
the manuscript as an explicit `\TODO{...}` placeholder, to be filled only from
the logs these scripts produce.  After each run, re-run
`audit_paper_numbers.py` so the new numbers enter the consistency audit.

Shared conventions with the released pipeline (identical by construction):
prompt bank (`data/paraphrases*.json` instructions + paraphrases), parser
(`Answer:<letter/number>` with fallback scan), per-call log schema, majority
tie-breaking (earliest vote in canonical order), question-level cluster
bootstrap.  Endpoint calls read keys from environment variables; see
`endpoints.example.json`.

## D1 -- open-weight replication of the 16-call matrix (held-out suite)

*Why:* the paper's findings describe third-party endpoints whose model identity
and temperature cannot be verified.  A local open-weight run removes that
confound for one model.

*How:* `run_vllm_matrix.py --model <hf-id>` runs the full matrix
(1 greedy + 6 canonical samples + 6+3 paraphrase decodes, tau=0.7, per-call
deterministic seeds) over `data/questions_expand.json`, writing logs in the
release format.  `--dry-run` prints the call plan and two sample prompts.

*Then:* add the model row to `tab_expand`, extend `audit_paper_numbers.py`
(EXP_MODELS), fill the paper's TODO, and update the third limitation in
Section 6.4.

## D2 -- held-out greedy-paraphrase control (PE-g-6)

*Why:* held-out paraphrase margins currently mix prompt variation with decoding
noise; only the development suite has the noise-free control.

*How:* `run_greedy_para_heldout.py --models <aliases> --config endpoints.json`
re-decodes each of the six paraphrases at tau=0 for every held-out question,
per model, appending to `results/cond_greedypara_heldout/`.  Pair the resulting
PEg-6 with the existing SC-6 rows; report the PEg-6-vs-PE-6 agreement rate as
in Appendix B.

*Then:* if the agreement rate is high (as on the two Agnes development models),
the "sampling noise mixed in" caveat in Sections 5.2/B can be softened;
otherwise it must be kept and quantified.

## D3 -- SC-6 under a pre-registered best instruction (fresh SAT-Math draw)

*Why:* the current instruction-variant analysis is post hoc (an optimistic
ceiling), and the canonical-directive SC-6 control was never run.

*How (two stages, pre-registration enforced by hash):*
1. `select_best_instruction.py` (run **before** any new data exists) scores the
   six handcrafted SAT-Math variants on the **development** logs only and
   writes `prereg_best_instruction.json` (variant, wording, scores, SHA-256).
   Already executed for this submission: it selected **P1** at 89.9% pooled
   single-call on the development SAT-Math items -- slightly **below** the
   canonical directive (90.6%) there, which is itself a finding worth carrying:
   on the development draw the canonical directive was not suboptimal, so the
   held-out SAT-Math instruction effect (best post-hoc variant 95.0%) does not
   generalize trivially and the fresh-draw test is exactly what is needed.
2. `run_sc6_best_instruction.py --prereg prereg_best_instruction.json
   --source <agieval sat-math items> --n 40 --seed 20261110` draws fresh items
   (excluding every consumed stem), runs 6 samples + greedy under P0 and 6
   samples under the pre-registered variant, and writes paired bootstrap CIs
   for SC-6(best) -- SC-6(canonical).

*Then:* replace the `\TODO` in Section 5.3 and the sixth limitation; if
SC-6(best) does not beat SC-6(canonical), the "instruction effect" reading
must be weakened accordingly.

## D4 -- human equivalence spot-check of LogiQA stem rewrites

*Why:* paraphrase equivalence is currently certified only by embedding
similarity + LLM bidirectional entailment; the model--paraphrase difficulty
swings (LogiQA: -11.7 to +14.1 across models) could be equivalence failures.

*How:* `make_equivalence_sample.py --n 100 --seed 20261110` emits a
fill-in table (already generated: `equivalence_annotation.csv`, 100 of 210
LogiQA stem pairs, seed 20261110).  Annotate `equivalent? (Y/N)` -- Y only if
the full problem statement survives; note what changed otherwise.  Two
independent annotators are recommended; `summarize_equivalence.py` then
reports the equivalence rate with CI, per-annotator agreement, the
non-equivalent items, and an illustration of how excluding non-equivalent
rewrites would move the held-out stem-locus flip count (17.4%).

*Then:* if the equivalence rate is high, the automatic filters are validated
and the fourth limitation can cite the check; if it is low, the fragility
statistics need a sensitivity re-run with the flagged rewrites excluded.

## What must NOT happen

No number from these experiments may enter the paper before the logs exist;
each script writes per-call records precisely so that every quoted figure can
be audited afterwards by `audit_paper_numbers.py`.
