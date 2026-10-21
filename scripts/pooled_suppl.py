#!/usr/bin/env python3
"""Supplementary pooled stats for the paper: PE-SC paired gap, adaptive vs
fixed-strategy comparisons, off-mode/tie rates, and per-dataset pooled table."""
import json, random
from collections import defaultdict

R = json.load(open('/home/z/my-project/results/analysis/expand_v1.json'))
POOL = ["agnes-3.0-flash", "agnes-2.5-flash"]
common = sorted(set.intersection(*[set(R["models"][a]["per_q"].keys()) for a in POOL]))
n_q = len(common)

# per-question, per-model values
def qval(a, qid, field):
    return R["models"][a]["per_q"][qid][field]

# ---- paired cluster bootstrap for PE-SC gap ----
def cluster_boot(field_fn, iters=10000, seed=42, alpha=0.05):
    by_q = {}
    for qid in common:
        by_q[qid] = [field_fn(a, qid) for a in POOL]
    qids = sorted(by_q)
    vals = {q: sum(by_q[q]) / len(by_q[q]) for q in qids}
    base = sum(vals.values()) / len(qids)
    rng = random.Random(seed)
    means = []
    for _ in range(iters):
        means.append(sum(vals[qids[rng.randrange(len(qids))]] for _ in range(len(qids))) / len(qids))
    means.sort()
    return base, means[int(alpha/2*iters)], means[int((1-alpha/2)*iters)-1]

out = {}
# PE - SC
base, lo, hi = cluster_boot(lambda a, q: (1 if qval(a, q, "pe6_ok") else 0) - (1 if qval(a, q, "sc6_ok") else 0))
out["pe_minus_sc_pooled"] = {"mean": base, "ci95": [lo, hi]}
print(f"pooled PE-SC: {100*base:+.1f} pp [{100*lo:+.1f},{100*hi:+.1f}]")
# PE - HB
base, lo, hi = cluster_boot(lambda a, q: (1 if qval(a, q, "pe6_ok") else 0) - (1 if qval(a, q, "hb6_ok") else 0))
out["pe_minus_hb_pooled"] = {"mean": base, "ci95": [lo, hi]}
print(f"pooled PE-HB: {100*base:+.1f} pp [{100*lo:+.1f},{100*hi:+.1f}]")
# COMB - PE
base, lo, hi = cluster_boot(lambda a, q: (1 if qval(a, q, "comb12_ok") else 0) - (1 if qval(a, q, "pe6_ok") else 0))
out["comb_minus_pe_pooled"] = {"mean": base, "ci95": [lo, hi]}
print(f"pooled COMB-PE: {100*base:+.1f} pp [{100*lo:+.1f},{100*hi:+.1f}]")

# ---- adaptive pooled ----
ad_rows = []
for a in POOL:
    ad = R["models"][a]["adaptive_alloc"]
    ad_rows.append({"model": a, "acc": ad["acc"], "budget": ad["mean_budget"],
                    "pct": ad["budget_pct_of_6"], "strategies": ad["strategy_counts"],
                    "gap_sc6_q": ad["gap_vs_sc6_q"], "gap_pe6_q": ad["gap_vs_pe6_q"],
                    "gap_best_q": ad["gap_vs_best_q"]})
out["adaptive"] = ad_rows
for r in ad_rows:
    print(f"adaptive {r['model']}: {100*r['acc']:.1f}% @ {r['budget']:.2f} calls ({100*r['pct']:.0f}%), "
          f"gap sc6={r['gap_sc6_q']}q pe6={r['gap_pe6_q']}q best={r['gap_best_q']}q, strat={r['strategies']}")

# ---- pooled per-dataset table ----
ds_tab = defaultdict(lambda: defaultdict(list))
for a in POOL:
    for ds, v in R["models"][a]["by_ds"].items():
        for k in ("greedy", "k1", "sc6", "pe6", "comb12"):
            ds_tab[ds][k].append(v[k])
out["by_ds_pooled"] = {ds: {k: sum(v)/len(v) for k, v in f.items()} for ds, f in ds_tab.items()}
print("\npooled per-dataset (mean over 2 models):")
hdr = ["dataset", "n", "greedy", "S1", "SC-6", "PE-6", "COMB-12"]
print("  " + " | ".join(f"{h:>9s}" for h in hdr))
for ds in sorted(ds_tab):
    f = ds_tab[ds]
    nn = R["models"][POOL[0]]["by_ds"][ds]["n"] + R["models"][POOL[1]]["by_ds"][ds]["n"]
    print("  " + " | ".join([
        f"{ds:>9s}", f"{nn:>9d}",
        f"{100*f['greedy'][0]:>8.1f}%", f"{100*f['k1'][0]:>8.1f}%",
        f"{100*f['sc6'][0]:>8.1f}%", f"{100*f['pe6'][0]:>8.1f}%",
        f"{100*f['comb12'][0]:>8.1f}%"]))

# ---- off-mode & unanimous pooled ----
off = sum(R["models"][a]["off_mode_n"] for a in POOL)
unan = sum(R["models"][a]["unanimous_rate"] for a in POOL) / 2
out["off_mode_pooled_n"] = off
out["off_mode_pooled_rate"] = off / (2 * n_q)
out["unanimous_pooled_rate"] = unan
print(f"\npooled off-mode: {off}/{2*n_q} ({100*off/(2*n_q):.1f}%), unanimous: {100*unan:.1f}%")

# ---- discordant counts pooled ----
disc = {k: sum(R["models"][a]["sc_pe_discordant"][k] for a in POOL) for k in ("sc_only", "pe_only")}
out["sc_pe_discordant_pooled"] = disc
print(f"pooled SC/PE discordant: sc_only={disc['sc_only']} pe_only={disc['pe_only']} of {2*n_q}")

# ---- strata pooled ----
strata_out = {}
for sname in R["models"][POOL[0]]["strata"]:
    rows = []
    for a in POOL:
        s = R["models"][a]["strata"][sname]
        rows.append(s)
    strata_out[sname] = {k: (sum(r[k] for r in rows if r[k] is not None) /
                             max(1, sum(1 for r in rows if r[k] is not None)))
                         for k in ("k1", "sc6", "pe6", "comb12", "greedy")}
    strata_out[sname]["n_per_model"] = [r["n"] for r in rows]
out["strata_pooled"] = strata_out
print("\npooled strata (mean of 2 models):")
for sname, s in strata_out.items():
    print(f"  {sname}: n/model={s['n_per_model']} k1={100*s['k1']:.1f} sc6={100*s['sc6']:.1f} "
          f"pe6={100*s['pe6']:.1f} comb12={100*s['comb12']:.1f} greedy={100*s['greedy']:.1f}")

json.dump(out, open('/home/z/my-project/results/analysis/expand_pooled_suppl.json', 'w'), indent=1)
print("\nwrote results/analysis/expand_pooled_suppl.json")
