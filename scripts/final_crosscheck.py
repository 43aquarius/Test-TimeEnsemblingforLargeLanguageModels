#!/usr/bin/env python3
"""Final cross-check v2: robust to pdftotext Unicode/ligature/hyphen quirks."""
import json, re, subprocess

PDF = "/home/z/my-project/release_assets/paper_main.pdf"
REP = "/home/z/my-project/results/analysis/recompute_report.json"

out = subprocess.run(["pdftotext", PDF, "-"], capture_output=True, text=True, timeout=120).stdout
for ch, rep in {'\ufb00':'ff','\ufb01':'fi','\ufb02':'fl','\ufb03':'ffi','\ufb04':'ffl'}.items():
    out = out.replace(ch, rep)
flat = re.sub(r"\s+", " ", out)

def norm(s):
    s = s.replace("\u2206", "\u0394")          # increment -> Greek Delta
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("\u2212", "-")                # minus sign -> hyphen
    s = s.replace("< ", "<").replace("> ", ">")
    s = re.sub(r"\s+", " ", s)
    return s

flat = norm(flat)

def has(needle):
    n = norm(needle)
    return n in flat or n.replace("-", "") in flat.replace("-", "")

rep = json.load(open(REP))
new = rep["new"]

fails = []
def expect(name, cond):
    print(f"  {'OK ' if cond else 'FAIL'} {name}")
    if not cond:
        fails.append(name)

expect("abstract: SC/PE CIs", has("+2.4 points and the paraphrase ensemble by +4.9 (95% cluster-bootstrap intervals +1.1 to +3.7 and +2.3 to +7.6"))
expect("abstract: Holm <= 0.001", has("Holm-adjusted p ≤ 0.001") or has("Holm-adjusted p≤0.001"))
expect("abstract: difficulty split", has("+1.9 points of the paraphrase headline is a single-call difficulty offset, leaving +3.0 of within-family aggregation against +2.4"))
expect("abstract: greedy 3/10", has("endpoint-specific, four to eleven points on three of ten"))
expect("abstract: adaptive 1-to-7", has("trailing the best fixed conditions elsewhere by one to seven"))

expect("results: Holm family", has("(adjusted p = 0.0008, <0.0001, and <0.0001, respectively)") or has("adjusted p = 0.0008, < 0.0001, and < 0.0001"))
expect("results: PE-SC Holm 0.14", has("Holm-adjusted p = 0.14"))
h = new["holm"]
expect("recompute Holm consistent", abs(h["SC-S1"]["p_holm"] - 0.0008) < 0.0001 and h["PE-SC"]["p_holm"] > 0.10)

expect("combined: n 152/159", has("152 questions for Agnes3.0-Flash, 159 for Agnes2.5-Flash"))
expect("combined: A3 PE +6.5", has("6.5 points above S1 (CI +2.2 to +11.1)"))
expect("combined: A3 SC +1.9", has("gains +1.9 (CI -0.7 to +4.4)"))
expect("combined: A2 +2.2 both", has("+2.2 each, CIs +0.6 to +3.9 and -0.4 to +4.9"))
c30 = new["combined_agnes-3.0-flash"]; c25 = new["combined_agnes-2.5-flash"]
expect("recompute combined consistent", c30["n"] == 152 and c25["n"] == 159
       and abs(c30["dpe6"]["mean"] - 6.5) < 0.06 and abs(c25["dpe6"]["mean"] - 2.2) < 0.06)
expect("combined: A25 dev -1.7", has("ΔPE -1.7 on its 40-question development subset, +3.5 on the 119"))

expect("mech: pooled SAT-Math", has("SAT-Math ΔPE +7.5 against ΔSC +0.0"))
expect("mech: GSM8K", has("GSM8K +2.1 against +0.8"))
expect("mech: LogiQA pooled", has("ΔSC +5.0 against ΔPE +1.5"))
expect("mech: TruthfulQA", has("TruthfulQA is neutral in aggregate (ΔSC +0.8, ΔPE +3.1)"))
expect("mech: pro LogiQA within-family", has("within-family gains are small (ΔPE +1.7 against ΔSC +0.8)"))
expect("mech: pro PIQA decomposition", has("of which 6.7 is the harder single-call base and -3.3 the within-family change"))
expect("mech: 12-point swing", has("swing by more than twelve points across models"))
expect("mech: SAT instruction effect", has("instruction effect rather than an aggregation effect"))
expect("mech: PE-1 82.5 (+20.8)", has("20.8 points above S1 there (PE-1 82.5"))

expect("strata: decomposition disclaimer", has("a localization of that gap, not an independent replication"))
expect("strata: 61 pairs", has("averaging the four models' strata (61 pairs in total) gives PE-6 52.9%"))
expect("strata: 96.3 unanimous", has("saturated at 96.3% pooled"))

expect("adaptive: frontier phrasing", has("the only model in either suite on which the rule exceeds every fixed allocation"))
expect("adaptive: Agnes2.5 two below PE-6", has("two below PE-6"))
expect("adaptive: summary one/two/seven", has("one question to its best fixed condition on the pro tier and two to PE-6 on Agnes2.5"))

expect("greedy: 1 of 4 endpoints", has("reappears on only one of four endpoints"))
expect("greedy: pooled within 0.1", has("pooled greedy and S1 sit within 0.1 points"))

expect("difficulty: PE-1 81.2 line", has("PE-1 81.2% against S1 79.6%, +1.7 points"))
expect("term: development suite", flat.count("development suite") >= 12)
expect("term: no blind", not has("blind replication") and not has("drawn blind"))
expect("term: no two-model pool", not has("two-model pool"))
expect("term: held-out primary", has("primary evaluation"))
expect("qwen self-preference", has("self-preference risk"))
expect("limitations: four systems", has("per-model coverage for four systems (two Agnes generations and two DeepSeek tiers), while two of its six systems remain partially covered"))

print()
if fails:
    print(f"{len(fails)} FAILURES: {fails}")
    raise SystemExit(1)
print("ALL FINAL CROSS-CHECKS PASS")
