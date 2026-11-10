# Simulated TMLR review of the revised submission

Criteria (TMLR accepts a paper when both hold; novelty is NOT required):
(C1) the claims are supported by accurate, convincing, and clear evidence;
(C2) a portion of the readership will find it interesting.

Reviewer role: TMLR reviewer, post-revision, listing what still stands between
this manuscript and acceptance.  Section references are to the TMLR version.

## C1 -- is every claim supported?

### Claims that still lack direct evidence (and how the paper handles them)

| Claim | Status in the manuscript | Gap |
|---|---|---|
| Best instruction's SC-6 would (or would not) beat canonical SC-6 | flagged as the one unrun control, TODO + D3 protocol queued (5.3, limitation 6) | only D3 can close it |
| Held-out paraphrase margins are prompt-space effects | explicitly NOT claimed; labelled "paraphrase ensemble (with sampling noise)" (5.2, B3 fixes) | closed by D2 if run |
| Endpoint identity/temperature as requested | disclosed as unverifiable (setup, limitation 3); logs released for audit | closed by D1 (open-weight) for at least one model |
| Paraphrase equivalence item-by-item | bounded "in distribution" by automatic filters; human spot-check queued (limitation 4) | closed by D4 |
| "Both" is the strongest detector | downgraded to descriptive, overlapping intervals stated (5.7, B2.4) | a formal paired test of correlated AUROCs would settle it; optional |

Verdict on C1 as it stands: the four designated primary contrasts are
supported (Holm-adjusted, CIs excluding zero, audited 102/102 against the raw
logs); every other quantitative claim is labelled exploratory/descriptive/post
hoc/by construction in Appendix E, and the audit script reproduces all of it.
The remaining C1 risk is concentrated in the four queued experiments, not in
any claim currently made.

### Wording that was still too strong and has now been fixed (this pass)

1. Intro: "render answer-space ensembling inert precisely where deployments
   are most common" (no evidence for deployment shares) -> "...inert on
   exactly those benchmarks."
2. 5.3: "The instruction effect is therefore real" -> "On this data the
   instruction effect is present ... a post-hoc reading, since the variant was
   selected on the same items."
3. Abstract: adaptive rule "at matched accuracy" -> "at equal or slightly
   lower accuracy" (one model loses by a single question, one by seven).
   The conclusion already carried the one-to-seven-questions qualifier.

### Experiments a reviewer may still ask for (beyond D1-D4)

* weighted/ranked voting or learned vote combination at the same budget
  (limitation 10 already concedes the point);
* free-form generation with semantic clustering (future work, listed);
* larger per-benchmark samples (listed as the first limitation);
* a formal test comparing the correlated AUROCs of Both vs the singles.

None of these blocks C1 for the claims as stated, because the claims are
conditional and labelled; but D1 is the one most likely to be requested
outright, since "commercial endpoint" findings are otherwise anecdotal.

## C2 -- will some readers care?

Yes, and the paper now says so efficiently: the regime map (degeneracy vs
high-entropy), the S1-vs-greedy reporting recommendation, the instruction
effect on quantitative benchmarks, and the call-saving rules are each of
independent practical interest to evaluation and deployment readers.  The
abstract now carries a single conclusion chain, so the interest case is
legible on page 1.

## Anonymization check (this pass)

* PDF metadata: no Author/Title fields (verified with pdfinfo); TMLR header
  "Under review as submission to TMLR"; author block "Anonymous authors".
* Identity strings absent from the full text layer: author name, institution,
  e-mail, GitHub, Zenodo DOI, repo name (grep-verified).
* Model/endpoint names retained deliberately (not author-identifying); the
  third-party-endpoint disclosure is part of the evidence, not a leak.
* Remaining anonymization to-dos are packaging-level -- **now resolved**: the
  OpenReview supplementary zip contains none of `CHANGELOG.md`,
  `DECISIONS.md`, `REVIEW.md`, or worklog-style files (verified
  programmatically); git history is absent from both packages; the released
  logs carry no `user`/`owner` fields (scanned); the Zenodo DOI and repo name
  appear nowhere in either package (scanned, plus `pdfinfo` Author empty).
  The two packages (`tmlr_submission_latex.zip`, `anonymous_repository.zip`)
  are built and re-verified by `scripts/build_tmlr_packages.py`.

## Final pre-submission checklist

Blocking (from DECISIONS.md and this review):

1. Run D1-D4; fill the three `\TODO` result placeholders from their logs only.
2. Fill `[TOOLS]`/`[PURPOSE]` in the AI declaration (honest statement).
3. Verify every `[CHECK: ...]` model citation against official docs.
4. Supply the anonymous repository link for the Reproducibility Statement.
5. Re-run `audit_paper_numbers.py` after each new experiment; 102/102 must
   hold with the extended claims.
6. Re-verify anonymization of the packaged zip (metadata, git history, stray
   fields) and the PDF (pdfinfo Author empty).

Non-blocking, recommended:

7. Optional formal comparison of correlated AUROCs (Both vs singles).
8. Consider adding the D3a observation (dev-selected variant P1 scores below
   the canonical directive on the development draw: 89.9 vs 90.6) to Section
   5.3 as a sentence -- it pre-empts the "why pre-register" question and is
   already recorded in `experiments/prereg_best_instruction.json`.
9. After acceptance: switch to `\usepackage[accepted]{tmlr}`, restore the
   repository/DOI links, and re-enable the de-anonymized declarations.

Overall: with the four queued experiments completed (or their TODOs honestly
retained as future work), both C1 and C2 are met under TMLR's stated
criteria; the paper makes no novelty claim, and none is needed.
