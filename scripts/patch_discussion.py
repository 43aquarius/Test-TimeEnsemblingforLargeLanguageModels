#!/usr/bin/env python3
"""v1.7.0 discussion.tex patches: integrated headline, endpoint-specific greedy,
honest adaptive numbers, limitations fixes."""
import sys

P = "/home/z/my-project/paper/sections/discussion.tex"
txt = open(P).read()
orig = txt

def rep(start_anchor, end_anchor, new_text, label):
    global txt
    i = txt.find(start_anchor)
    if i < 0:
        sys.exit(f"PATCH {label}: start anchor not found: {start_anchor[:70]!r}")
    j = txt.find(end_anchor, i + len(start_anchor))
    if j < 0:
        sys.exit(f"PATCH {label}: end anchor not found: {end_anchor[:70]!r}")
    txt = txt[:i] + new_text + txt[j:]
    print(f"patched: {label}")

# ---- D1: principal findings (full rewrite of the paragraph) ----
FINDINGS = r"""The study yields four principal findings. First, the effectiveness of every test-time aggregation strategy is governed by a precondition that the literature rarely states explicitly: the model must produce diverse answers at all. For the flagship models in our pool, five of six benchmarks sit in a degenerate regime in which six stochastic samples and six paraphrases return the same answer for almost every question, and in that regime self-consistency, paraphrase ensembling, and the combined ensemble reproduce both single-call baselines exactly, with the hybrid allocation differing by at most one question. This part of the degeneracy result is structural rather than empirical: when all votes coincide, every aggregation of them returns the same answer by construction. The empirical content lies in how common the coincidence is, and in its consequence that agreement-based uncertainty scores are uninformative exactly there. Second, measured against the correct $k{=}1$ baseline, the single-sample expectation S1, the two diversity sources deliver small, reliable, and statistically inseparable aggregation gains on the held-out suite: pooled over its four fully covered models (476 model--question pairs), self-consistency gains $+2.4$ points over S1, the paraphrase ensemble $+4.9$, and the twelve-vote combination $+4.1$, all with intervals excluding zero and surviving Holm correction within the designated primary family (Section~\ref{sec:method}); the paraphrase margin over self-consistency ($+2.5$, CI $-$0.6 to $+5.7$) does not separate from zero, and after removing the paraphrase difficulty margin ($+1.9$ at the single-call level) the like-for-like aggregation comparison is $+3.0$ against $+2.4$ --- roughly a factor of 1.25, not the factor of two that the raw headline suggests. On the development suite, whose per-model coverage was truncated unevenly (12 to 90 questions), the same pooled comparison sits at noise (SC-6 $+0.9$, PE-6 $-$0.9 over 112 pairs), and the per-model gains measured against greedy decoding are largely artifacts of a greedy reference that diverges from the sampled expectation on specific endpoints; we therefore treat the held-out suite as the primary evidence and the development suite as the design phase whose role was to fix the conditions, strata, and rules. Where the modal answer is wrong, the two sources pull in opposite directions, and the sign of the margin is model- and dataset-conditional: the paraphrase vote wins where resampling is exhausted, as on computation-deterministic tasks, and reverses where paraphrases shift verbal semantics (LogiQA for one model, PIQA for another), and the allocation that realizes the gain varies across models. Third, paraphrase agreement functions as an error signal in its own right, and its error coverage overlaps only partially with that of sample agreement: across models, the stronger source differs, so neither signal subsumes the other, and a deployment that can afford both probes obtains partially disjoint evidence, although the simple sum of the two disagreement scores does not dominate the best single signal in our data. Fourth, fragility, the fraction of questions whose answer flips under paraphrasing alone, tracks answer disagreement, concentrates entirely in stem-locus paraphrasing, and appears in the same model-task cells that carry disagreement, which supports the interpretation that paraphrase disagreement and sampling disagreement are two observable symptoms of the same underlying instability."""

rep("The study yields four principal findings.",
    "\n\n\\subsection{A practical allocation rule",
    FINDINGS, "D1-findings")

# ---- D2: adaptive paragraph fixes ----
txt = txt.replace(
    "it trails the best fixed strategy by one to two questions on Agnes2.5-Flash at 79 percent; and on the pro-tier DeepSeek it sits one question below the combined ensemble at 85 percent --- while on DeepSeekV4.1-Flash it strictly dominates every fixed allocation (84.0 percent at 87 percent of budget), the first instance in either suite where the probe converts into a strict win.",
    "it trails PE-6 by two questions on Agnes2.5-Flash at 79 percent; and on the pro-tier DeepSeek it sits one question below the combined ensemble at 85 percent --- while on DeepSeekV4.1-Flash it exceeds every fixed allocation (84.0 percent at 87 percent of budget, one question above the best of them), the only instance in either suite where the probe converts into a win over the whole fixed frontier.")
txt = txt.replace("Across all six models, an even simpler sequential rule",
                  "Across the development suite's six models, an even simpler sequential rule")
txt = txt.replace("the fresh-question expansion set of Section~\\ref{sec:expand} supplies the transfer test",
                  "the held-out set of Section~\\ref{sec:expand} supplies the transfer test")
print("patched: D2-adaptive")

# ---- D3: implications (greedy endpoint-specific) ----
txt = txt.replace(
    "The single-sample baseline S1 deserves the same reporting discipline, because greedy decoding and a single stochastic draw differ by up to ten points in the high-entropy cells of our data, in both directions.",
    "The single-sample baseline S1 deserves the same reporting discipline, because greedy decoding and a single stochastic draw differ by four to eleven points on three of the ten model--endpoint configurations we measured, in both directions, and are statistically indistinguishable on the rest, including three of the four held-out endpoints; the divergence is an endpoint property to be checked per deployment, not a universal offset.")
print("patched: D3-implications")

# ---- D4: limitations fixes ----
txt = txt.replace(
    "the 119-question expansion set of Section~\\ref{sec:expand} multiplies per-model coverage for three models (two Agnes flashes and one mid-tier DeepSeek), while two of its five models remain partially covered",
    "the 119-question held-out set of Section~\\ref{sec:expand} multiplies per-model coverage for four systems (two Agnes generations and two DeepSeek tiers), while two of its six systems remain partially covered")
txt = txt.replace(
    "the MMLU-Pro probe of Section~\\ref{sec:mmlupro} begins to broaden this, at small scale",
    "the MMLU-Pro probe of Appendix~\\ref{app:mmlupro} begins to broaden this, at small scale")
txt = txt.replace(
    "the follow-up condition of Section~\\ref{sec:cot} measures the mode effect directly",
    "the follow-up condition of Appendix~\\ref{app:cot} measures the mode effect directly")
txt = txt.replace(
    "stricter thresholds or human-curated paraphrases could shift the fragility statistics.",
    "stricter thresholds or human-curated paraphrases could shift the fragility statistics; a related caveat is that Qwen3.7-Flash, the stem-paraphrase generator, is itself evaluated in the held-out suite, so its paraphrase-condition cells carry a self-preference risk, and its partial coverage (60 of 119) keeps them out of the pooled analyses.")
txt = txt.replace(
    "and the adaptive allocation rule was designed and evaluated on the same collected matrices, so both carry a same-data caveat",
    "and the adaptive allocation rule was designed and evaluated on the same development-suite matrices, so both carry a same-data caveat; the held-out set mitigates but does not eliminate it, because the strata and the rule were fixed after the development-suite results were known")
txt = txt.replace(
    "the expansion set of Section~\\ref{sec:expand} now provides the fresh-question evaluation of the allocation rule",
    "the held-out set of Section~\\ref{sec:expand} now provides the fresh-question evaluation of the allocation rule")
print("patched: D4-limitations")

open(P, "w").write(txt)
print(f"\nwrote {P}: {len(orig)} -> {len(txt)} chars")
