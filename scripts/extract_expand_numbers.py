#!/usr/bin/env python3
"""Extract all exact numbers needed to update the expand tables and text."""
import json

R = json.load(open('/home/z/my-project/results/analysis/expand_v1.json'))
S = json.load(open('/home/z/my-project/results/analysis/expand_pooled_suppl.json'))

def pct(x):
    return f"{100*x:.1f}"

for a in ("agnes-3.0-flash", "agnes-2.5-flash"):
    m = R["models"][a]
    acc = m["acc"]
    print(f"=== {a} (n={m['n']}) ===")
    print(f"greedy={pct(acc['greedy_ok'])} S1={pct(acc['k1_acc'])} SC6={pct(acc['sc6_ok'])} "
          f"PE6={pct(acc['pe6_ok'])} HB6={pct(acc['hb6_ok'])} COMB12={pct(acc['comb12_ok'])}")
    print(f"unan_rate={pct(m['unanimous_rate'])} off_mode={m['off_mode_n']} "
          f"s1_minus_greedy={m['s1_minus_greedy']:+.3f}")
    es = m["early_stop_unanimous"]
    print(f"unan_rule: acc={pct(es['acc'])} kbar={es['mean_budget']:.1f}")
    ad = m["adaptive_alloc"]
    print(f"adaptive: acc={pct(ad['acc'])} kbar={ad['mean_budget']:.2f} "
          f"pct={100*ad['budget_pct_of_6']:.0f}% gaps: sc6={ad['gap_vs_sc6_q']} "
          f"pe6={ad['gap_vs_pe6_q']} hb6={ad['gap_vs_hb6_q']} best={ad['gap_vs_best_q']}")
    print(f"strategies={ad['strategy_counts']}")
    print("strata:")
    for name, s in m["strata"].items():
        if s["n"]:
            print(f"  {name}: n={s['n']} k1={pct(s['k1'])} sc6={pct(s['sc6'])} "
                  f"pe6={pct(s['pe6'])} comb12={pct(s['comb12'])} greedy={pct(s['greedy'])}")
    print("gains vs S1:", {c: f"{m[f'gain_vs_s1_{c}']:+.3f}" for c in ("sc6", "pe6", "comb12")})
    print("CIs:")
    for c in ("sc6", "pe6", "comb12"):
        lo, hi = m[f"ci_{c}_minus_s1"]
        print(f"  {c}-S1: [{100*lo:+.1f},{100*hi:+.1f}]")
    lo, hi = m["ci_sc_minus_pe"]
    print(f"  PE-SC (sc_minus_pe CI): [{100*lo:+.1f},{100*hi:+.1f}]")
    print(f"sc_pe_discordant={m['sc_pe_discordant']}")
    # PE-1 = mean first-sample accuracy over paraphrases
    pq = m["per_q"]
    pe1_vals = []
    for qid, v in pq.items():
        # recompute from jsonl? PE-1 not stored; approximate via analysis: use R per_q missing -> skip
        pass
    print("by_ds:")
    for ds, v in m["by_ds"].items():
        print(f"  {ds}: n={v['n']} greedy={pct(v['greedy'])} k1={pct(v['k1'])} "
              f"sc6={pct(v['sc6'])} pe6={pct(v['pe6'])} comb12={pct(v['comb12'])}")
    print()

print("=== POOLED (from expand_v1.json) ===")
P = R["pooled"]
for f in ("greedy_ok", "k1", "sc6_ok", "pe6_ok", "hb6_ok", "comb12_ok"):
    v = P[f]
    print(f"{f}: {pct(v['mean'])} [{pct(v['ci95'][0])},{pct(v['ci95'][1])}]")
for c in ("sc6", "pe6", "comb12"):
    v = P[f"gain_vs_s1_{c}"]
    print(f"{c}-S1: {100*v['mean']:+.1f} [{100*v['ci95'][0]:+.1f},{100*v['ci95'][1]:+.1f}]")
print()
print("=== POOLED supplementary ===")
for k in ("pe_minus_sc_pooled", "pe_minus_hb_pooled", "comb_minus_pe_pooled"):
    v = S[k]
    print(f"{k}: {100*v['mean']:+.1f} [{100*v['ci95'][0]:+.1f},{100*v['ci95'][1]:+.1f}]")
print(f"off_mode pooled: {S['off_mode_pooled_n']}/{2*119} = {100*S['off_mode_pooled_rate']:.1f}%")
print(f"unanimous pooled: {100*S['unanimous_pooled_rate']:.1f}%")
print(f"discordant pooled: {S['sc_pe_discordant_pooled']}")
print("strata pooled:")
for name, s in S["strata_pooled"].items():
    print(f"  {name}: n/model={s['n_per_model']} k1={pct(s['k1'])} sc6={pct(s['sc6'])} "
          f"pe6={pct(s['pe6'])} comb12={pct(s['comb12'])} greedy={pct(s['greedy'])}")
print("by_ds pooled:")
for ds, v in S["by_ds_pooled"].items():
    print(f"  {ds}: greedy={pct(v['greedy'])} k1={pct(v['k1'])} sc6={pct(v['sc6'])} "
          f"pe6={pct(v['pe6'])} comb12={pct(v['comb12'])}")
