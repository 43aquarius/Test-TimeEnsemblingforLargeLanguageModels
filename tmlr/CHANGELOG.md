# Modification log -- TMLR submission version

Old text refers to the Neurocomputing v1.8.1 manuscript (`repo/paper/`);
new text to the TMLR submission in this directory.  "Why" cites the user's
instruction sections (A/B/C/D/E).

## A. Format and anonymization

| # | Location | Old | New | Why |
|---|---|---|---|---|
| A1 | main.tex | `\documentclass[preprint,12pt]{elsarticle}` + `\journal{Neurocomputing}` | `\documentclass[10pt]{article}` + `\usepackage{tmlr}` (official TMLR style, submission mode: header "Under review as submission to TMLR", author block "Anonymous authors") | A: TMLR template, anonymous mode |
| A2 | main.tex | author name, `\ead`, `\cortext`, `\address`, `pdftitle/pdfauthor` with identity | removed; `\author{}` commented out | A: anonymization |
| A3 | main.tex | `\zenododoi` command; Data availability section with GitHub URL + Zenodo DOI | Reproducibility Statement pointing to an anonymous repository `\TODO{link}` | A: no identity info; "anonymous repository" placeholder |
| A4 | main.tex | CRediT / competing interest / funding sections | deleted | A: Elsevier declarations removed |
| A5 | main.tex | Elsevier AI declaration (generic tool names) | "Declaration on the Use of Generative AI" with `[TOOLS]` and `[PURPOSE]` as `\TODO` placeholders for the author to fill honestly | A: AI statement kept truthful, placeholders not invented |
| A6 | main.tex | `\journal{...}`, `Preprint submitted to Neurocomputing` | gone (the TMLR style prints its own header) | A |
| A7 | whole paper | "we release ... at github.com/43aquarius/..." (7 sites) | "released with the submission / in the repository accompanying this submission" | A: no repo names |
| A8 | refs.bib | `openai2023gpt4` (GPT-4 TR) and `openai2025gpt5` (GPT-5 card) cited for GPT-6-Luna | new `openai2026gpt6` entry (GPT-6 System Card, platform docs URL, `[CHECK: verify exact URL/version]`); GPT-4/GPT-5 entries removed (no longer cited) | A: model citations must match the served version; unverifiable through relays, so flagged |
| A9 | refs.bib | `qwen2024qwen` "Qwen Technical Report" (key/year mismatch, cited alongside Qwen3 TR for Qwen3.8) | removed; `yang2025qwen3` (Qwen3 TR) cited with `[CHECK: confirm a 3.8-series report/model card]` | A |
| A10 | refs.bib | Condorcet author `{Marquis de Condorcet}` (rendered oddly) | `author = {Condorcet, Marquis de}`; verified in-text citation now renders "(Condorcet, 1785)" | A: fix the garbled author field |
| A11 | refs.bib | Gemini/Qwen/Agnes/DeepSeek entries without verification notes | each model-card entry carries `[CHECK: verify URL/version against official docs]` | A: model citations vs actual versions |
| A12 | refs.bib | `bibliographystyle{elsarticle-num}` (numeric) | `\bibliographystyle{tmlr}` (author-year, natbib) | A: TMLR bib style |
| A13 | sections/appendix.tex | single appendix file, sections "Appendices Appendix A--C" phrasing risk | split into `appendix_greedypara/mmlupro/cot` with per-section `A.1/B.1/C.1` table numbering and unique hyperref anchors | A: format; fixes the old "Appendices Appendix" residue |

## B. Content changes

### B1 -- mechanism wording aligned with the instruction-variant control

| # | Location | Old | New | Why |
|---|---|---|---|---|
| B1.1 | abstract | "The margin is conditional: it concentrates where answer-space diversity is exhausted (computation-deterministic tasks), reverses where paraphrases distort verbal-reasoning stems" | "it concentrates on quantitative tasks, where the canonical directive under-elicits --- the best single instruction variant, selected post hoc, already reaches 95.0% pooled single-call accuracy against 91.2% for the six-variant ensemble --- it reverses where paraphrases shift verbal-reasoning stems" | B1: wording must match the SAT-Math instruction control |
| B1.2 | intro (RQ paragraph) | "where the prompt-space margin appears it concentrates exactly where resampling is exhausted --- a conditional answer" | "...it concentrates on quantitative tasks whose canonical instruction under-elicits" + the 95.0-vs-91.2 sentence + "whether six resamples under the single best instruction would aggregate a further margin ... is a control we did not run and flag explicitly" | B1 |
| B1.3 | intro, regime paragraph | "self-consistency and paraphrase ensembling both collapse onto both single-call baselines" (doubled "both") | "...collapse onto the single-call baselines" | editorial fix |
| B1.4 | 5.3 (heldout mechanism) | "part of this cell is plausibly an instruction effect rather than an aggregation effect" | full instruction-variant analysis: canonical directive suboptimal for quantitative items; best variant (post hoc, optimistic ceiling) 76.2->95.0 vs PE-6 91.2 (~80% captured); "What these logs cannot decide is whether six resamples under the single best instruction would aggregate a further margin ... we flag it explicitly as the one unrun control" + `\TODO{pre-registered follow-up}` | B1 |
| B1.5 | 5.9 (joint conclusion) | "prompt-space ensembling pays where answer-space diversity is exhausted --- on computation-deterministic tasks, where six samples re-derive the same wrong arithmetic and paraphrases recover it" | "the paraphrase-ensemble margin pays where the canonical instruction under-elicits --- on quantitative tasks, where the best single instruction variant (selected post hoc) already exceeds the six-variant ensemble and the ensemble captures most, not all, of that instruction effect" | B1 |
| B1.6 | 6.1 principal findings (2nd) | "the paraphrase vote wins where resampling is exhausted, as on computation-deterministic tasks" | "the paraphrase-side margin appears where the canonical instruction under-elicits --- on quantitative tasks, where the instruction-variant analysis ... shows the best single variant (selected post hoc) already exceeding the six-variant ensemble" | B1 |
| B1.7 | conclusion | "prompt-space ensembling pays where answer-space diversity is exhausted --- on computation-deterministic tasks, where six samples re-derive the same wrong arithmetic and paraphrases recover it --- and reverses..." | "pays on quantitative tasks, and the instruction-variant analysis shows why: the canonical directive under-elicits there ... whether six resamples under the pre-selected best instruction would add a further margin is untested and left open" | B1 |
| B1.8 | limitations | (no entry for the unrun control) | sixth limitation: post-hoc variant selection (optimistic ceiling) and the unrun best-instruction SC-6 control, with `\TODO{pre-registered follow-up}` | B1 |

### B2 -- error-detection claims corrected

| # | Location | Old | New | Why |
|---|---|---|---|---|
| B2.1 | 5.7 first reading | "each is the stronger single signal on the models where its source carries the accuracy margin --- paraphrase agreement on the two Agnes models (0.81 and 0.84 against 0.80 and 0.74)" | Agnes3.0's 0.81-vs-0.80 now stated as **comparable**; per-model dominance is model-dependent, not a tracker of the stronger diversity source | B2: "相当" not "更强"; 0.81 vs 0.80 is not a difference |
| B2.2 | 5.7 second reading | (no statement about the dev reading) | "the development-suite reading of a per-model dominant signal does not survive: ... 0.96 against 0.60 rested on three errors --- below the five-error rule --- and the held-out recomputation at eighteen errors overturns it" | B2: the 0.96-vs-0.60 reading was based on 3 errors |
| B2.3 | A.3 (dev appendix) | "for Agnes3.0-Flash, sample agreement is highly discriminative (0.96, CI [0.89,1.00])..." presented as a finding | same numbers kept, followed by: "The Agnes3.0-Flash reading is the one the held-out suite overturned: at eighteen errors the two signals are comparable there (0.80 against 0.81), so the development-suite contrast should be read as an artifact of the three-error denominator" | B2 |
| B2.4 | 5.7 fourth reading | "the summed disagreement score ... is the strongest pooled detector on the fresh questions (0.81 ...), and it is the best or within noise of the best single signal on every model" | adds: "we label this ranking **descriptive**, because its interval overlaps those of the single signals" | B2: mark interval overlap |
| B2.5 | 5.7 third reading | "either probe alone misses 23 to 26 errors where the pair misses eleven" | adds: "The union's flagged set contains each single set **by construction**, so the pair's coverage is an upper bound by definition; the empirical content is the partial disjointness --- fifteen and twelve errors reachable only through one source --- not the union size" | B2: Either coverage is higher by construction |
| B2.6 | table caption (tab:uncertexp) | "Both is the sum of the two disagreement scores" | adds "by construction the union of the two flagged sets contains each single set, so Either-coverage is an upper bound by definition" | B2 |
| B2.7 | 6.1 third finding | "the stronger single signal tracks the model's stronger diversity source (paraphrase agreement on the two Agnes models, sample agreement on the two DeepSeek tiers)" | "What does not survive: ... on the fresh questions the stronger single signal is model-dependent, not a tracker of the model's stronger diversity source" | B2 |
| B2.8 | appendix E (claims) | (n/a) | downgraded-claim list, item (i) | B2/B8 |

### B3 -- PE meaning made explicit everywhere

| # | Location | Old | New | Why |
|---|---|---|---|---|
| B3.1 | abstract | "aggregating semantically equivalent paraphrases (prompt space)" (implying deterministic decoding) | "aggregating semantically equivalent paraphrases, each call decoded stochastically" | B3 |
| B3.2 | intro paragraph 3 | "keep decoding deterministic or lightly stochastic, present several semantically equivalent paraphrases" | "each paraphrase call is decoded stochastically at the same temperature as a resampled call, so this source mixes prompt variation with per-call decoding noise rather than isolating the prompt effect" | B3: user flagged "perturbs the prompt while the decoder configuration is fixed" as misleading |
| B3.3 | 3.3 conditions | "the budget match is exact ... this is not a comparison of stochastic against deterministic decoding" (already present but the PE definition paragraph implied isolation) | new dedicated paragraph: "A PE-k margin ... characterizes paraphrase ensembles *with sampling noise mixed in*, not pure prompt-space effects; isolating the prompt component requires ... a control we collected on the development suite only" + "Wherever this paper interprets a paraphrase-ensemble margin, the statement is qualified accordingly" | B3 |
| B3.4 | 5.2 | (no qualifier at the end of the decomposition) | "All of these margins mix prompt variation with per-call sampling noise; no noise-free paraphrase control exists on this suite" | B3 |
| B3.5 | 5.9 / conclusion | "prompt-space ensembling produces the largest well-powered gains" | "the paraphrase ensemble --- each of whose votes mixes prompt variation with decoding noise --- produces the largest well-powered gains" | B3 |
| B3.6 | 5.9 | "within-family aggregation ... inside prompt space" | "within-condition aggregation ... inside the paraphrase ensemble" | B3: held-out conclusions limited to "paraphrase ensemble (with sampling noise)" |
| B3.7 | limitations | fourth limitation mentions self-preference etc. | new fifth limitation: "every paraphrase vote varies the prompt *and* carries tau=0.7 decoding noise, and the greedy-paraphrase control ... was collected on the development suite only" | B3 |

### B4 -- abstract

| # | Location | Old | New | Why |
|---|---|---|---|---|
| B4.1 | abstract | 274 words, multiple conclusions | ~252 words, one conclusion chain: both ensembles beat S1 out of sample (+2.4/+4.9/+4.1 with CIs) -> statistically inseparable (+2.5, touching zero) -> +1.9 difficulty offset -> conditional margin (instruction reading) -> PE-with-noise qualifier -> greedy endpoint-specific -> degeneracy -> S1 reporting recommendation -> adaptive rule value = call savings | B4: ~250 words, one main conclusion; dev suite one background clause |

### B5 -- structure slimmed

| # | Location | Old | New | Why |
|---|---|---|---|---|
| B5.1 | results section | development-suite analyses (overview/RQ1-4, efficiency) occupy the main results section | moved to Appendix A (`appendix_dev`); main text now holds only the held-out evaluation (5.1-5.9) | B5 |
| B5.2 | figures | conditions/auroc/regime/budget figures in the main text | all four in Appendix A | B5 |
| B5.3 | tables | tab_main/tests/uncert_full/regime/efficiency in the main text | all in Appendix A (numbered A.1-A.5) | B5 |
| B5.4 | every subsection | (no summary sentence) | one-sentence italic conclusion at the top of every subsection and appendix section | B5 |
| B5.5 | MMLU-Pro/CoT/greedy-para | already appendices in v1.8.1 | unchanged in role; renumbered B/C/D; per-section table numbering | B5/A13 |

### B6 -- limitations kept objective

| # | Location | Old | New | Why |
|---|---|---|---|---|
| B6.1 | 6.4 limitations | eight limitations with some defensive phrasing ("Both controls bound these readings only partially") | nine numbered limitations + a tenth cross-cutting one, stated plainly; free-tier withdrawal, unverifiable relay identity/temperature, no first-party/open-weight replication, automatic-filter-only equivalence (+ planned human spot-check TODO), self-preference of Qwen3.7-Flash, mixed perturbation, post-hoc instruction selection + unrun control, direct-answer vs CoT modes, high-dissent regime sparsely sampled, same-data caveat for detectors/rules | B6: no self-defence |
| B6.2 | setup (models) | long provider paragraph | kept the disclosure, added the `[CHECK: verify every model citation...]` marker | B6/A8 |

### B7 -- "first" claims

| # | Location | Old | New | Why |
|---|---|---|---|---|
| B7.1 | intro | "This paper presents, to our knowledge, the first budget-matched, within-question comparison" | kept "to our knowledge" and added the differentia from related work ("unlike prior prompt-ensembling work, which ... does not match call budgets against resampling on identical questions") | B7: to-our-knowledge + explicit difference |
| B7.2 | related work positioning | "no prior work, to our knowledge, measures all three under a single matched-budget protocol" | kept (already to-our-knowledge) | B7 |

### B8 -- claim-evidence map

| # | Location | Old | New | Why |
|---|---|---|---|---|
| B8.1 | appendix E | (did not exist) | `tab:claims`: every quantitative/causal claim in the abstract, intro, and conclusion mapped to its table/figure/test with CI and status (primary/exploratory/post hoc/by construction); four downgraded claims listed with reasons | B8 |

## C. Audit-driven corrections (from `audit_paper_numbers.py`)

| # | Location | Old | New | Why |
|---|---|---|---|---|
| C1 | 5.3 | "the paraphrases' pooled single-call advantage there (+4.7 over S1)" | "+4.8 over S1" | C: recomputed from raw logs (rounding order); script is authoritative |
| C2 | 5.2 | "Agnes2.5-Flash: the two sources converge (+2.2 each, CIs +0.6 to +3.9 and -0.4 to +4.9)" (unattributed) | "with the SC-6 interval at +0.6 to +3.9 and the PE-6 interval at -0.4 to +4.9" | C: recomputation showed the attribution was reversed/unstated |
| C3 | 5.2 | "Agnes2.5-Flash: Delta PE -1.7 on its 40-question development subset, +3.5 ..., +2.2 ..." | "PE-6 minus S1 is -1.7 ... (the within-condition Delta PE uses PE-1 and moves in the same direction)" | C: the -1.7/+3.5/+2.2 series is the PE-6-vs-S1 convention; the old label "Delta PE" contradicted the method definition |
| C4 | 5.3 | "the paraphrase side retains a small within-condition margin (Delta PE +3.1)" | "(Delta PE +3.1 pooled over the four models; on Agnes3.0 alone it is +0.8)" | C: +3.1 is the pooled value; the sentence sits in an Agnes3.0-specific paragraph |
| C5 | 5.7 (TruthfulQA neutrality, old text) | "TruthfulQA is near-neutral for the paraphrase side (Delta PE +3.1)" (v1.8.1 5.7 wording) | "the sample vote neither gains nor loses much there while the paraphrase vote keeps a modest advantage on this mixed-locus dataset" -- +3.1 no longer called neutral | B2/C (user: "Delta PE=+3.1 is not neutral") |

## D. Residual known issues (carried as TODOs, not silently fixed)

* three `\TODO{...}` placeholders for D1-D3 results (5.3, limitations, equivalence check);
* `[TOOLS]`/`[PURPOSE]` in the AI declaration, anonymous-repository link;
* `[CHECK: ...]` on every model-card citation (identity unverifiable through relays).
