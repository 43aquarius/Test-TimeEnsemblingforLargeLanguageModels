#!/usr/bin/env python3
"""v1.7.0 results.tex paragraph-level patches (anchors are unique substrings)."""
import sys

P = "/home/z/my-project/paper/sections/results.tex"
txt = open(P).read()
orig = txt

def rep(anchor_start, anchor_end, new_text, label):
    """Replace text from anchor_start (inclusive) to anchor_end (exclusive)."""
    global txt
    i = txt.find(anchor_start)
    if i < 0:
        sys.exit(f"PATCH {label}: start anchor not found: {anchor_start[:60]!r}")
    j = txt.find(anchor_end, i + len(anchor_start))
    if j < 0:
        sys.exit(f"PATCH {label}: end anchor not found: {anchor_end[:60]!r}")
    txt = txt[:i] + new_text + txt[j:]
    print(f"patched: {label}")

# ---- P1: pooled paragraph tail (Holm + drop two-model-pool phrasing) ----
rep(
    "so on fresh questions both sources of diversity deliver measurable aggregation gains.",
    "The Qwen3.7-Flash partial replication behaves",
    """so on fresh questions both sources of diversity deliver measurable aggregation gains; designated as the study's primary contrasts (Section~\\ref{sec:method}), all three gains survive Holm adjustment within the four-contrast family (adjusted $p = 0.0008$, $<0.0001$, and $<0.0001$, respectively). The orderings between conditions, however, remain unresolvable at this sample size: PE$-$SC is $+2.5$ points (CI $-$0.6 to +5.7; Holm-adjusted $p = 0.14$), PE$-$HB $+$1.3 points (CI $-$0.4 to +2.9), and COMB$-$PE $-$0.8 points (CI $-$2.9 to +1.3), so no allocation separates from any other; in particular, the mixed allocations are among the best conditions for the two DeepSeek models, which limits how far a pure prompt-space recommendation can be pushed. """,
    "P1-pooled-Holm")

rep(
    "behaves like the main-suite flagship models: 82\\% of its questions are unanimous",
    "Table~\\ref{tab:expand_ds} separates the two",
    """behaves like the development-suite flagship models: 82\\% of its questions are unanimous, every fixed condition lies within 1.1 points of S1, and both rule replays match SC-6 (85.0\\%) at a fraction of the budget; its paraphrase-condition cells carry the self-preference caveat of Section~\\ref{sec:setup}.

A difficulty confound must be separated from the ensembling effect before the margins can be read as aggregation: paraphrases could simply be easier than the original stems, and the comparison against S1 would then mix a difficulty margin with an aggregation margin. """,
    "P1b-qwen-caveat")

# ---- P2: difficulty paragraph fixes ----
rep(
    "DeepSeekV4.1 behaves like the pooled pair in miniature",
    "All margins can be re-derived from the released call matrices.",
    """DeepSeekV4.1-Flash shows the same configuration at a smaller scale (PE-1 79.1 against S1 77.6, $+$1.5; $\\Delta$PE $+$2.4, $\\Delta$SC $+$2.2). The pro-tier DeepSeek shifts the balance: its paraphrases are the easiest in the pool at the single-call level (PE-1 81.1 against S1 78.0, $+$3.1), and its answer-space aggregation margin exceeds its prompt-space margin ($\\Delta$SC $+$2.7 against $\\Delta$PE $+$1.3), so its significant combined condition rests on the two sources jointly rather than on a dominant prompt-space component. Pooled over the four models, six-vote aggregation buys $+$3.0 points inside prompt space (PE-6 85.7 against PE-1 82.7) against $+$2.4 inside answer space (SC-6 83.2 against S1 80.8), with the single-call difficulty margin at $+$1.9 points contributing well under half of the pooled PE-6 advantage; the prompt-space aggregation margin is roughly 1.3 times the answer-space margin, and because $+1.9$ of the $+4.9$ headline gap is a difficulty offset, the aggregation-against-aggregation comparison is $+3.0$ versus $+2.4$ rather than the raw four-versus-two spread. All margins can be re-derived from the released call matrices.""",
    "P2-difficulty")

# ---- P3: insert combined cross-suite paragraph before the dataset-decomposition paragraph ----
COMBINED = """A cross-suite consistency check pools every question completed by the two models covered in both suites (development plus held-out: 152 questions for Agnes3.0-Flash, 159 for Agnes2.5-Flash). The held-out pattern survives the union: on Agnes3.0-Flash, PE-6 sits 6.5 points above S1 (CI $+$2.2 to $+$11.1) while SC-6 gains $+$1.9 (CI $-$0.7 to $+$4.4); on Agnes2.5-Flash the two sources converge ($+$2.2 each, CIs $+$0.6 to $+$3.9 and $-$0.4 to $+$4.9). The per-model point estimates nonetheless move several points between suites (Agnes2.5-Flash: $\\Delta$PE $-$1.7 on its 40-question development subset, $+$3.5 on the 119 held-out questions, $+$2.2 on the 159-question union), a spread that is what unevenly truncated small samples deliver and that cautions against reading any single per-model cell as an effect size; the pooled four-model contrasts, not per-model cells, are where the study's power lies.

"""
anchor = "The dataset decomposition carries the mechanism."
i = txt.find(anchor)
if i < 0:
    sys.exit("P3: anchor not found")
txt = txt[:i] + COMBINED + txt[i:]
print("patched: P3-combined")

open(P, "w").write(txt)
print(f"\nwrote {P}: {len(orig)} -> {len(txt)} chars")
