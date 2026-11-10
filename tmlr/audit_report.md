# Number-consistency audit (TMLR submission)

Input logs: this repository (`data/`, `results/`)

**102 claims audited: 102 MATCH, 0 MISMATCH, 0 UNVERIFIABLE.**

Verdicts: MATCH = recomputed from raw logs and agrees with the paper (tolerances: points 0.06; CI endpoints 0.35; AUROC 0.006). MISMATCH = the paper must be corrected to the recomputed value, or the logs re-checked. UNVERIFIABLE = the raw logs available to this run cannot produce the paper number (flag [UNVERIFIED] in the manuscript, or supply the missing log).

| # | Location | Claim | Paper | Recomputed | Verdict |
|---|---|---|---|---|---|
| 1 | Abstract | SC-6 pooled gain over S1 (+2.4) | 2.4 | 2.4 | **MATCH** |
| 2 | Abstract | PE-6 pooled gain over S1 (+4.9) | 4.9 | 4.9 | **MATCH** |
| 3 | Abstract | COMB-12 pooled gain over S1 (+4.1) | 4.1 | 4.1 | **MATCH** |
| 4 | Abstract | SC-6 CI (+1.1, +3.7) | [1.1, 3.7] | [1.1, 3.7] | **MATCH** |
| 5 | Abstract | PE-6 CI (+2.3, +7.6) | [2.3, 7.6] | [2.4, 7.6] | **MATCH** |
| 6 | Abstract | PE-SC gap (+2.5, interval touching zero) | 2.5 | 2.5 | **MATCH** |
| 7 | Abstract | PE-SC CI (-0.6, +5.7) | [-0.6, 5.7] | [-0.6, 5.7] | **MATCH** |
| 8 | Abstract | difficulty offset (+1.9) | 1.9 | 1.9 | **MATCH** |
| 9 | Abstract | within-condition aggregation +3.0 vs +2.4 | [3.0, 2.4] | [3.0, 2.4] | **MATCH** |
| 10 | Abstract | held-out 119 questions / 476 pairs | [119, 476] | [119, 476] | **MATCH** |
| 11 | Abstract | best instruction variant 95.0% vs PE-6 91.2% (SAT-Math pooled) | [95.0, 91.2] | [95.0, 91.2] | **MATCH** |
| 12 | Abstract | adaptive rule saves 13-21% of the six-call budget (uses 79-87%) | [13, 21] | [13, 21] | **MATCH** |
| 13 | Intro | pooled +2.4 / +4.9 with CIs excluding zero (same as abstract) | None | 0.0 | **MATCH** |
| 14 | Intro | dev coverage 12 to 90; held-out four fully covered models | [12, 90] | [12, 90] | **MATCH** |
| 15 | 5.1 | Agnes3.0: PE-6 87.4 / S1 79.6 / +7.8 | [87.4, 79.6, 7.8] | [87.4, 79.6, 7.8] | **MATCH** |
| 16 | 5.1 | Agnes3.0: PE-6 CI (+2.4, +13.7) | [2.4, 13.7] | [2.4, 13.6] | **MATCH** |
| 17 | 5.1 | Agnes3.0: SC-6 +2.0 CI (-1.0, +5.0); COMB 82.4 | [2.0, -1.0, 5.0, 82.4] | [2.0, -1.0, 4.9, 82.4] | **MATCH** |
| 18 | 5.1 | Agnes2.5: PE-6 91.6 / S1 88.1 / +3.5 CI (+0.4,+7.0); SC-6 90.8 / +2.7 CI (+0.7,+4.9); COMB 89.9 | [91.6, 88.1, 3.5, 0.4, 7.0, 90.8, 2.7, 0.7, 4.9, 89.9] | [91.6, 88.1, 3.5, 0.3, 6.9, 90.8, 2.7, 0.7, 4.9, 89.9] | **MATCH** |
| 19 | 5.1 | DSV4.1: PE-6 81.5 / S1 77.6 / +3.9 CI (-0.8,+8.7); SC-6 79.8 / +2.2 CI (-0.4,+4.9); HB=COMB 83.2 / +5.6 CIs (+1.5,+9.8)/(+1.7,+9.7) | [81.5, 77.6, 3.9, -0.8, 8.7, 79.8, 2.2, -0.4, 4.9, 83.2, 5.6, 1.5, 9.8 | [81.5, 77.6, 3.9, -0.7, 8.8, 79.8, 2.2, -0.6, 5.0, 83.2, 5.6, 1.5, 9.8 | **MATCH** |
| 20 | 5.1 | Pro tier: COMB 84.0 / +6.0 CI (+2.1,+10.2); SC-6 80.7 / +2.7 CI (+0.1,+5.5); PE=HB 82.4 / +4.3 CIs (-0.7,+9.4)/(-0.4,+9.1) | [84.0, 6.0, 2.1, 10.2, 80.7, 2.7, 0.1, 5.5, 82.4, 4.3, -0.7, 9.4, -0.4 | [84.0, 6.0, 2.1, 10.2, 80.7, 2.7, 0.1, 5.3, 82.4, 4.3, -0.8, 9.5, -0.4 | **MATCH** |
| 21 | 5.1 | Holm-adjusted p: SC-S1 0.0008 | 0.0008 | 0.0 | **MATCH** |
| 22 | 5.1 | Holm-adjusted p: PE-S1 <0.0001 | <0.0001 | 0.0 | **MATCH** |
| 23 | 5.1 | Holm-adjusted p: COMB-S1 <0.0001 | <0.0001 | 0.0 | **MATCH** |
| 24 | 5.1 | Holm-adjusted p: PE-SC 0.14 | 0.14 | 0.13 | **MATCH** |
| 25 | 5.1 | PE-HB +1.3 CI (-0.4,+2.9); COMB-PE -0.8 CI (-2.9,+1.3) | [1.3, -0.4, 2.9, -0.8, -2.9, 1.3] | [1.3, -0.2, 2.9, -0.8, -2.9, 1.3] | **MATCH** |
| 26 | 5.1 | Qwen3.7-Flash partial: 82% unanimous; within 1.1 of S1; replays match SC-6 85.0 | [82, 1.1, 85.0] | [82, 1.1, 85.0] | **MATCH** |
| 27 | 5.2 | pooled PE-1 82.7 / PE-6 85.7 / S1 80.8 / SC-6 83.2 | [82.7, 85.7, 80.8, 83.2] | [82.7, 85.7, 80.8, 83.2] | **MATCH** |
| 28 | 5.2 | Agnes3.0: PE-1 81.2 / S1 79.6 / dPE +6.2 / dSC +2.0 | [81.2, 79.6, 6.2, 2.0] | [81.2, 79.6, 6.2, 2.0] | **MATCH** |
| 29 | 5.2 | Agnes2.5: PE-1 89.2 / S1 88.1 / dPE +2.4 / dSC +2.7 | [89.2, 88.1, 2.4, 2.7] | [89.2, 88.1, 2.4, 2.7] | **MATCH** |
| 30 | 5.2 | DSV4.1: PE-1 79.1 / S1 77.6 / dPE +2.4 / dSC +2.2 | [79.1, 77.6, 2.4, 2.2] | [79.1, 77.6, 2.4, 2.2] | **MATCH** |
| 31 | 5.2 | Pro: PE-1 81.1 / S1 78.0 / dSC +2.7 vs dPE +1.3 | [81.1, 78.0, 2.7, 1.3] | [81.1, 78.0, 2.7, 1.3] | **MATCH** |
| 32 | 5.2 | union Agnes3.0: n=152, PE-6 +6.5 CI (+2.2,+11.1); SC-6 +1.9 CI (-0.7,+4.4) | [152, 6.5, 2.2, 11.1, 1.9, -0.7, 4.4] | [152, 6.5, 2.1, 11.1, 1.9, -0.5, 4.4] | **MATCH** |
| 33 | 5.2 | union Agnes2.5: n=159, +2.2 both; SC-6 CI (+0.6,+3.9), PE-6 CI (-0.4,+4.9) | [159, 2.2, 2.2, 0.6, 3.9, -0.4, 4.9] | [159, 2.2, 2.2, 0.6, 3.9, -0.3, 4.8] | **MATCH** |
| 34 | 5.2 | Agnes2.5 PE-6 minus S1: dev -1.7 (40q) / held-out +3.5 / union +2.2 | [-1.7, 3.5, 2.2] | [-1.7, 3.5, 2.2] | **MATCH** |
| 35 | 5.3 | Agnes3.0 SAT-Math: S1 61.7 / SC-6 60.0 (dSC -1.7) / PE-6 100.0 (dPE +17.5); 8 flips all won by PE | [61.7, 60.0, -1.7, 100.0, 17.5, 8] | [61.7, 60.0, -1.7, 100.0, 17.5, None] | **MATCH** |
| 36 | 5.3 | Agnes3.0 SAT-Math: PE-1 82.5 (+20.8 over S1) | [82.5, 20.8] | [82.5, 20.8] | **MATCH** |
| 37 | 5.3 | SAT-Math instruction: canonical 76.2 -> best 95.0; PE-6 91.2 (~80%) | [76.2, 95.0, 91.2] | [76.2, 95.0, 91.2] | **MATCH** |
| 38 | 5.3 | SAT-Math per-model canonical->best: Agnes3.0 61.7->100.0; DSV4.1 75.8->90.0; pro 69.2->90.0 | [61.7, 100.0, 75.8, 90.0, 69.2, 90.0] | [61.7, 100.0, 75.8, 90.0, 69.2, 90.0] | **MATCH** |
| 39 | 5.3 | PIQA best variant 86.2 vs canonical 87.9 | [86.2, 87.9] | [86.2, 87.9] | **MATCH** |
| 40 | 5.3 | Agnes3.0 GSM8K: PE-6 100.0, dPE +2.5, floor 95.0 | [100.0, 2.5, 95.0] | [100.0, 2.5, 95.0] | **MATCH** |
| 41 | 5.3 | Agnes3.0 LogiQA: PE-1 63.3 vs S1 75.0 (-11.7); SC-6 90.0 dSC +15.0 vs dPE +1.7; 5/7 flips SC | [63.3, 75.0, -11.7, 90.0, 15.0, 1.7] | [63.3, 75.0, -11.7, 90.0, 15.0, 1.7] | **MATCH** |
| 42 | 5.3 | Agnes3.0 TruthfulQA: SC-6 65.0 vs S1 70.8; pooled dPE +3.1 | [65.0, 70.8, 3.1] | [65.0, 70.8, 3.1] | **MATCH** |
| 43 | 5.3 | Agnes2.5 floors SAT 98.3 / GSM 94.2; pooled dPE +2.4; LogiQA PE-6 80.0 vs SC-6 70.0 dPE +2.5 dSC -3.3 | [98.3, 94.2, 2.4, 80.0, 70.0, 2.5, -3.3] | [98.3, 94.2, 2.4, 80.0, 70.0, 2.5, -3.3] | **MATCH** |
| 44 | 5.3 | DSV4.1 LogiQA: PE-1 65.0 vs S1 52.5 (+12.5); dSC +7.5 dPE 0.0; SAT -0.8/+5.8; TruthfulQA dSC +5.0 | [65.0, 52.5, 12.5, 7.5, 0.0, -0.8, 5.8, 5.0] | [65.0, 52.5, 12.5, 7.5, 0.0, -0.8, 5.8, 5.0] | **MATCH** |
| 45 | 5.3 | Pro LogiQA: PE-1 68.3 vs S1 54.2 (+14.1); PE-6 70.0 vs SC-6 55.0; dPE +1.7 dSC +0.8 | [68.3, 54.2, 14.1, 70.0, 55.0, 1.7, 0.8] | [68.3, 54.2, 14.1, 70.0, 55.0, 1.7, 0.8] | **MATCH** |
| 46 | 5.3 | Pro PIQA: paraphrases 6.7 harder; PE-6 80.0 vs SC-6 95.0 (15 pts); -10.0 vs S1 (6.7 base, -3.3 within); dSC +5.0 | [6.7, 80.0, 95.0, 15.0, -10.0, 6.7, -3.3, 5.0] | [6.7, 80.0, 95.0, 15.0, -10.0, 6.7, -3.3, 5.0] | **MATCH** |
| 47 | 5.3 | pooled dSAT: dPE +7.5 vs dSC 0.0; GSM +2.1/+0.8; LogiQA dSC +5.0 vs dPE +1.5; LogiQA single-call +4.8; TruthfulQA dSC +0.8 dPE +3.1 | [7.5, 0.0, 2.1, 0.8, 5.0, 1.5, 4.8, 0.8, 3.1] | [7.5, -0.0, 2.1, 0.8, 5.0, 1.5, 4.8, 0.8, 3.1] | **MATCH** |
| 48 | 5.3 | LogiQA difficulty swing across models: -11.7 / +12.5 / +14.1 | [-11.7, 12.5, 14.1] | [-11.7, 12.5, 14.099999999999994] | **MATCH** |
| 49 | 5.4 | weak-majority n: 24 / 8 / 14 / 15 | [24, 8, 14, 15] | [24, 8, 14, 15] | **MATCH** |
| 50 | 5.4 | weak stratum PE/SC/S1 per model: 58.3/33.3/31.9; 50.0/25.0/27.1; 50.0/35.7/33.3; 53.3/33.3/31.1 | [58.3, 33.3, 31.9, 50.0, 25.0, 27.1, 50.0, 35.7, 33.3, 53.3, 33.3, 31. | [58.3, 33.3, 31.9, 50.0, 25.0, 27.1, 50.0, 35.7, 33.3, 53.3, 33.3, 31. | **MATCH** |
| 51 | 5.4 | weak stratum model-mean PE 52.9 / SC 31.8 / S1 30.9; 61 pairs | [52.9, 31.8, 30.9, 61] | [52.9, 31.8, 30.9, 61] | **MATCH** |
| 52 | 5.4 | DS weak COMB 57.1 vs PE 50.0; pro 60.0 vs 53.3 | [57.1, 50.0, 60.0, 53.3] | [57.1, 50.0, 60.0, 53.3] | **MATCH** |
| 53 | 5.4 | unanimous n 70/90/69/73 at 96.3%; strong n 25/21/36/31, S1 67.0 | [70, 90, 69, 73, 96.3, 25, 21, 36, 31, 67.0] | [70, 90, 69, 73, 96.3, 25, 21, 36, 31, 67.0] | **MATCH** |
| 54 | 5.5 | S1-greedy held-out: Agnes3.0 -1.1 / Agnes2.5 -1.8 / pro -1.0; DSV4.1 +4.5 (73.1 vs 77.6) | [-1.1, -1.8, -1.0, 4.5, 73.1, 77.6] | [-1.1, -1.8, -1.0, 4.5, 73.1, 77.6] | **MATCH** |
| 55 | 5.5 | off-mode greedy: DSV4.1 16 (13 wrong); pro 14 (10/4); pooled 50/476 (10.5%) | [16, 13, 14, 10, 4, 50, 476, 10.5] | [16, None, 14, None, None, 50, 476, 10.5] | **MATCH** |
| 56 | 5.6 | held-out flips: stem 41/236 (17.4%); instruction 23/240 (9.6%) | [41, 236, 17.4, 23, 240, 9.6] | [41, 236, 17.4, 23, 240, 9.6] | **MATCH** |
| 57 | 5.6 | LogiQA fragility per model: 40 / 15 / 35 / 35 | [40, 15, 35, 35] | [40.0, 15.0, 35.0, 35.0] | **MATCH** |
| 58 | 5.6 | SAT-Math instruction-locus flips per model: 40 / 0 / 15 / 20 | [40, 0, 15, 20] | [40.0, 0.0, 15.0, 20.0] | **MATCH** |
| 59 | 5.6 | dev-suite instruction-locus flips 0/52; stem pooled 3.3% (P4 common set) | [0, 52, 3.3] | [0, 52, 3.3] | **MATCH** |
| 60 | A.2 | GPT stem-locus 28.6% / Gemini 20.0% (per-model stem rates) | [28.6, 20.0] | [28.6, 20.0] | **MATCH** |
| 61 | A.2 | tight-0.80 fragility: GPT 33.3% (n=6) / Gemini 25.0% / Omni 4.8% | [33.3, 25.0, 4.8] | [33.3, 25.0, 4.8] | **MATCH** |
| 62 | 5.7 | pooled AUROC: sample 0.75 CI (0.67,0.84); paraphrase 0.74 CI (0.65,0.83); Both 0.81 CI (0.73,0.89) | [0.75, 0.67, 0.84, 0.74, 0.65, 0.83, 0.81, 0.73, 0.89] | [0.75, 0.69, 0.82, 0.74, 0.68, 0.8, 0.81, 0.75, 0.86] | **MATCH** |
| 63 | 5.7 | per-model errors: 21 / 12 / 20 / 19 (12-21 range); pooled 72 | [21, 12, 20, 19, 72] | [21, 12, 20, 19, 72] | **MATCH** |
| 64 | 5.7 | Agnes3.0 held-out AUROC: paraphrase 0.81 vs sample 0.80 (comparable) | [0.81, 0.8] | [0.81, 0.8] | **MATCH** |
| 65 | 5.7 | Agnes2.5: paraphrase 0.84 vs sample 0.74; DS tiers: sample 0.70/0.74 vs paraphrase 0.62/0.69 | [0.84, 0.74, 0.7, 0.74, 0.62, 0.69] | [0.84, 0.74, 0.7, 0.74, 0.62, 0.69] | **MATCH** |
| 66 | 5.7 | flagged: sample 49 / paraphrase 46; only-sample 15 / only-paraphrase 12 | [49, 46, 15, 12] | [49, 46, 15, 12] | **MATCH** |
| 67 | 5.7 | non-degenerate error rate 35.1% vs unanimous 3.6%; nd AUROC range 0.49-0.86 (all detectors, FULL4) | [35.1, 3.6, 0.49, 0.86] | [35.1, 3.6, 0.49, 0.86] | **MATCH** |
| 68 | 5.8 | Agnes3.0 rule: 81.5% at 5.2 calls (86%); seven questions below PE-6 | [81.5, 5.2, 86] | [81.5, 5.2, 86] | **MATCH** |
| 69 | 5.8 | Agnes2.5 rule: 89.9 vs SC 90.8 vs PE 91.6 (-1/-2) at 4.7 calls (79%); routes 97/10/9/3 | [89.9, 90.8, 91.6, 4.7, 79, 97, 10, 9, 3] | [89.9, 90.8, 91.6, 4.7, 79, 97, 10, 9, 3] | **MATCH** |
| 70 | 5.8 | DSV4.1 rule: 84.0% at 5.2 (87%), +5 over SC-6, +3 over PE-6, +1 over HB/COMB; routes 83/18/12/6 | [84.0, 5.2, 87, 83, 18, 12, 6] | [84.0, 5.2, 87, 83, 18, 12, 6] | **MATCH** |
| 71 | 5.8 | pro rule: 83.2% at 5.1 (85%), one below COMB 84.0; routes 86/20/9/4 | [83.2, 5.1, 85, 86, 20, 9, 4] | [83.2, 5.1, 85, 86, 20, 9, 4] | **MATCH** |
| 72 | 5.8 | rule pooled 84.7% at mean 5.1 (84%) | [84.7, 5.1, 84] | [84.7, 5.1, 84] | **MATCH** |
| 73 | 5.9 | per-model dSC across both suites: -3.3 to +2.7 | [-3.3, 2.7] | [-3.3, 2.7] | **MATCH** |
| 74 | A.1 | Qwen3.8-Max all conditions 93.3; Omni 93.0 | [93.3, 93.0] | [93.3, 93.0] | **MATCH** |
| 75 | A.1 | dev pooled: SC +0.9 / PE -0.9 over 112 pairs on 28 questions | [0.9, -0.9, 112, 28] | [0.9, -0.9, 112, 28] | **MATCH** |
| 76 | A.1 | GPT-6 PE-6 +10.0 over S1 CI (0.0,+22.2) n=15; Gemini +5.6 CI (0.0,+13.9) n=12; SC -3.3/-2.8 | [10.0, 15, -3.3, 5.6, 12, -2.8] | [10.0, 15, -3.3, 5.6, 12, -2.8] | **MATCH** |
| 77 | A.1 | dev pooled S1 96.4 / greedy 92.0 / SC 97.3 / PE 95.5 / COMB 96.4; SC-PE 1.8 CI (0.0,+5.4), 90% CI (0.0,+3.6) | [96.4, 92.0, 97.3, 95.5, 96.4, 1.8, 0.0, 5.4, 0.0, 3.6] | [96.4, 92.0, 97.3, 95.5, 96.4, 1.8, 0.0, 5.4, 0.0, 3.6] | **MATCH** |
| 78 | A.1 | S1-greedy dev pooled +4.5 CI (+0.9,+8.8) | [4.5, 0.9, 8.8] | [4.5, 0.9, 8.9] | **MATCH** |
| 79 | A.1 | greedy divergence dev: Agnes3.0 10.6 / Agnes2.5 4.2 below; GPT -3.3 / Gemini -5.6 | [10.6, 4.2, -3.3, -5.6] | [10.6, 4.2, -3.3, -5.6] | **MATCH** |
| 80 | A.1 | hybrid trails by one question: Max 92.2 vs 93.3; Omni 91.5 vs 93.0; Agnes2.5 92.5 vs 95.0; GPT-6 HB/PE 86.7 SC 73.3 | [92.2, 93.3, 91.5, 93.0, 92.5, 95.0, 86.7, 73.3] | [92.2, 93.3, 91.5, 93.0, 92.5, 95.0, 86.7, 73.3] | **MATCH** |
| 81 | A.2 | dev fragility: Max 1.1% / Omni 4.2%; LogiQA 6.7%/21.4%; GPT 13.3% (LogiQA 40%); Gemini 8.3% (33.3%); Agnes3.0 zero | [1.1, 4.2, 6.7, 21.4, 13.3, 40.0, 8.3, 33.3, 0] | [1.1, 4.2, None, None, 13.3, None, 8.3, None, 0] | **MATCH** |
| 82 | A.3 | dev AUROC: Max 0.58 CI (0.50,0.78); Omni 0.79; Agnes3.0 0.96 CI (0.89,1.00) vs 0.60; GPT 0.92 vs 0.58 | [0.58, 0.79, 0.96, 0.6, 0.92, 0.58] | [0.58, 0.79, 0.96, 0.6, 0.92, 0.58] | **MATCH** |
| 83 | A.3 | dev AURC: Omni 0.031 (err 7.0%); Agnes3.0 0.009 (9.1%); PE 0.032/0.073; Max 0.057 (6.7%) | [0.031, 7.0, 0.009, 9.1, 0.032, 0.073, 0.057, 6.7] | [0.031, 7.0, 0.009, 9.1, 0.032, 0.073, 0.056, 6.7] | **MATCH** |
| 84 | A.3 | dev pooled AUROC: sample 0.74 CI (0.71,0.75); paraphrase 0.60 CI (0.46,0.73) | [0.74, 0.71, 0.75, 0.6, 0.46, 0.73] | [0.74, 0.71, 0.75, 0.6, 0.46, 0.73] | **MATCH** |
| 85 | A.3 | dev flagged: Agnes3.0 sample flags 3, paraphrase 1; GPT paraphrase 2, sample 1 | [3, 1, 2, 1] | [3, 1, 2, 1] | **MATCH** |
| 86 | A.4 | Spearman(dissent, S1-greedy)=+0.80; (dissent, COMB-S1)=+0.17; non-unanimous +0.57; disjoint -0.20/+0.54 | [0.8, 0.17, 0.57, -0.2, 0.54] | [0.8, 0.17, None, -0.2, 0.54] | **MATCH** |
| 87 | A.4 | strata: 104 unanimous / 5 strong / 3 weak; unanimous k1 98.1 greedy 97.1; strong 76.7->80.0; weak k1 72.2 SC 100 PE 33.3 COMB 66.7 | [104, 5, 3, 98.1, 97.1, 76.7, 80.0, 72.2, 100.0, 33.3, 66.7] | [104, 5, 3, 98.1, 97.1, 76.7, 80.0, 72.2, 100.0, 33.3, 66.7] | **MATCH** |
| 88 | A.4 | GPT LogiQA: S1 50 / SC 40 / PE 80 (+30.0, n=5); Gemini 44.4/33.3/66.7 (+22.2, n=3); LSAT Agnes3.0 loss -5.6 | [50.0, 40.0, 80.0, 5, 44.4, 33.3, 66.7, 3, -5.6] | [None, None, None, 5, None, None, None, 3, None] | **MATCH** |
| 89 | A.4 | budget curves: Agnes3.0 PE full 90.9 at k=2, SC needs k=4; Agnes2.5 SC 95.0 by k=6, PE plateau 92.5 | [90.9, 95.0, 92.5] | [90.9, 95.0, 92.5] | **MATCH** |
| 90 | A.5 | dev efficiency: ES 2.0-2.7 calls; adaptive 4.1-4.7 (68-78%); trails by one on Omni/Agnes2.5; GPT-6 86.7 at 4.5 vs SC 73.3 | [2.0, 2.7, 4.1, 4.7, 68, 78, 86.7, 73.3] | [2.0, 2.7, 4.1, 4.7, 68, 78, 86.7, 73.3] | **MATCH** |
| 91 | A.1 | lenient rule: Agnes3.0 78.8->88.1/92.3 on 42/39 (strict 90.9/90.9); excluded harder: Omni 84.2 vs 93.0; Agnes2.5 60.0 vs 90.0 | [88.1, 92.3, 42, 39, 90.9, 84.2, 93.0, 60.0, 90.0] | [None, None, None, None, 90.9, None, None, None, None] | **MATCH** |
| 92 | A.1 | tokens: Max 223 vs 219; GPT 505 vs 528 | [223, 219, 505, 528] | [223, 219, 505, 528] | **MATCH** |
| 93 | Setup | parse rates 94.7-100% | [94.7, 100.0] | [94.7, 100.0] | **MATCH** |
| 94 | B | Qwen3.8-Max: 98.9% degeneracy under greedy paraphrases; PEg=PE on 88/88 | [98.9, 88, 88] | [98.9, 88, 88] | **MATCH** |
| 95 | B | Agnes3.0 PEg/PE agree 31/32; Agnes2.5 38/39 | [31, 32, 38, 39] | [31, 32, 38, 39] | **MATCH** |
| 96 | B | GPT-6: PEg 80.0 vs PE 86.7 (agree 11/15); Gemini 83.3 vs 91.7 (10/12) | [80.0, 86.7, 11, 15, 83.3, 91.7, 10, 12] | [80.0, 86.7, 11, 15, 83.3, 91.7, 10, 12] | **MATCH** |
| 97 | B | noise-free fragility: GPT-6 40.0%; Gemini 25.0% | [40.0, 25.0] | [40.0, 25.0] | **MATCH** |
| 98 | C | GPT-6 MMLU-Pro: greedy 66.7 / SC 73.3; entropy 0.26; degen 66.7%; n=15 | [66.7, 73.3, 0.26, 66.7, 15] | [66.7, 73.3, 0.26, 66.7, 15] | **MATCH** |
| 99 | C | Agnes3.0 probe: entropy 0.94, degen 0, greedy 12.5%, SC 0%, n=8; Agnes2.5 84.6% | [0.94, 0.0, 12.5, 0.0, 8, 84.6] | [0.94, 0.0, 12.5, 0.0, 8, 84.6] | **MATCH** |
| 100 | C | Qwen3.8-Max probe: 6 complete (8 lenient); 7/8 single answer | [6, 8, 7] | [6, 8, 7] | **MATCH** |
| 101 | D | CoT tab_cot rows (n, Grd, SC, PE | Grd_dir, SC_dir, PE_dir): Max 9: 100/100/100 | 88.9/88.9/75.0; Agnes3.0 12: 100/100/100 | 83.3/100/100; Agnes2.5 33: 87.9/93.9/93.3 | 90.9/93.9/86.7; GPT 13: 92.3/100/100 | 84.6/76.9/100 | [9, 100.0, 100.0, 100.0, 88.9, 88.9, 75.0, 12, 100.0, 100.0, 100.0, 83 | [9, 100.0, 100.0, 100.0, 88.9, 88.9, 75.0, 12, 100.0, 100.0, 100.0, 83 | **MATCH** |
| 102 | Setup | NLI bidirectional 267/270; second generator 269/270 (recomputed) | [267, 270, 269] | [267, 270, 269] | **MATCH** |

## Recomputed key statistics

```json
{
 "dev_pooled": {
  "n_pairs": 112,
  "n_q": 28,
  "s1": 96.42857142857143,
  "greedy": 91.96428571428571,
  "sc6": 97.32142857142857,
  "pe6": 95.53571428571429,
  "comb": 96.42857142857143,
  "sc_s1": 0.8928571428571388,
  "pe_s1": -0.8928571428571388,
  "sc_pe": 1.7857142857142856,
  "sc_pe_ci": [
   0.0,
   5.357142857142857
  ],
  "sc_pe_ci90": [
   0.0,
   3.571428571428571
  ],
  "s1_greedy": 4.464285714285714,
  "s1_greedy_ci": [
   0.8928571428571428,
   8.928571428571429
  ],
  "unanimous": 104
 },
 "rq4": {
  "spearman_dissent_gap": 0.7952593486312177,
  "spearman_dissent_comb": 0.165879651057525,
  "spearman_sampdiss_pegain": -0.19717834017416633,
  "spearman_paradiss_scgain": 0.5427283534584608,
  "n_unanimous_pairs": 104,
  "n_strong_pairs": 5,
  "n_weak_pairs": 3,
  "unan": {
   "n": 104,
   "k1": 98.07692307692308,
   "greedy": 97.11538461538461
  },
  "strong": {
   "n": 5,
   "k1": 76.66666666666667,
   "sc6": 80.0
  },
  "weak": {
   "n": 3,
   "k1": 72.22222222222221,
   "sc6": 100.0,
   "pe6": 33.333333333333336,
   "comb": 66.66666666666667
  }
 },
 "primary": {
  "sc6_ok": {
   "mean": 2.3809523809523814,
   "ci": [
    1.085434173669468,
    3.746498599439776
   ],
   "p": 0.0,
   "p_holm": 0.0
  },
  "pe6_ok": {
   "mean": 4.901960784313726,
   "ci": [
    2.3809523809523814,
    7.598039215686275
   ],
   "p": 0.0,
   "p_holm": 0.0
  },
  "comb12_ok": {
   "mean": 4.061624649859945,
   "ci": [
    1.9607843137254901,
    6.23249299719888
   ],
   "p": 0.0,
   "p_holm": 0.0
  },
  "hb6_ok": {
   "mean": 3.6414565826330536,
   "ci": [
    1.1554621848739497,
    6.23249299719888
   ],
   "p": 0.0052
  },
  "pe_sc": {
   "mean": 2.5210084033613445,
   "ci": [
    -0.6302521008403361,
    5.6722689075630255
   ],
   "p": 0.1314,
   "p_holm": 0.1314
  },
  "pe_hb": {
   "mean": 1.2605042016806722,
   "ci": [
    -0.21008403361344538,
    2.941176470588235
   ],
   "p": 0.1536
  },
  "comb_pe": {
   "mean": -0.8403361344537815,
   "ci": [
    -2.941176470588235,
    1.2605042016806722
   ],
   "p": 0.4872
  }
 },
 "exp_pooled": {
  "greedy": 80.67226890756302,
  "s1": 80.812324929972,
  "sc6": 83.19327731092437,
  "pe6": 85.71428571428571,
  "comb": 84.87394957983193,
  "hb": 84.45378151260505,
  "pe1": 82.66806722689076,
  "difficulty_offset": 1.8557422969187627,
  "dpe": 3.0462184873949525,
  "dsc": 2.3809523809523796,
  "n_pairs": 476,
  "n_q": 119
 },
 "strata_pooled": {
  "weak": {
   "n": 61,
   "s1": 30.868055555555554,
   "sc6": 31.845238095238095,
   "pe6": 52.91666666666667
  },
  "strong": {
   "s1": 67.04207202594299
  },
  "unan": {
   "max_cond": 96.332851186931
  }
 },
 "greedy_divergence": {
  "qwen3.8-max": {
   "greedy": 93.3,
   "s1": 93.3,
   "gap": 0.0
  },
  "qwen3.8-omni": {
   "greedy": 93.0,
   "s1": 93.9,
   "gap": 0.9
  },
  "agnes-3.0-flash": {
   "greedy": 78.8,
   "s1": 89.4,
   "gap": 10.6
  },
  "agnes-2.5-flash": {
   "greedy": 90.0,
   "s1": 94.2,
   "gap": 4.2
  },
  "gpt-6-luna": {
   "greedy": 80.0,
   "s1": 76.7,
   "gap": -3.3
  },
  "gemini-3.8-flash": {
   "greedy": 91.7,
   "s1": 86.1,
   "gap": -5.6
  },
  "agnes-3.0-flash (held-out)": {
   "greedy": 80.7,
   "s1": 79.6,
   "gap": -1.1
  },
  "agnes-2.5-flash (held-out)": {
   "greedy": 89.9,
   "s1": 88.1,
   "gap": -1.8
  },
  "qwen3.7-flash (held-out)": {
   "greedy": 85.0,
   "s1": 86.1,
   "gap": 1.1
  },
  "deepseek-v4.1-flash (held-out)": {
   "greedy": 73.1,
   "s1": 77.6,
   "gap": 4.5
  },
  "deepseek-v4-flash-0731 (held-out)": {
   "greedy": 92.3,
   "s1": 92.3,
   "gap": 0.0
  },
  "deepseek-v4-pro-0813 (held-out)": {
   "greedy": 79.0,
   "s1": 78.0,
   "gap": -1.0
  }
 },
 "frag_ho": {
  "stem": [
   41,
   236
  ],
  "inst": [
   23,
   240
  ],
  "stem_rate": 17.372881355932204,
  "inst_rate": 9.583333333333334,
  "logiqa": {
   "agnes-3.0-flash": 40.0,
   "agnes-2.5-flash": 15.0,
   "deepseek-v4.1-flash": 35.0,
   "deepseek-v4-pro-0813": 35.0
  },
  "sat_inst": {
   "agnes-3.0-flash": 40.0,
   "agnes-2.5-flash": 0.0,
   "deepseek-v4.1-flash": 15.0,
   "deepseek-v4-pro-0813": 20.0
  }
 }
}
```
