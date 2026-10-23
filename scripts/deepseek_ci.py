#!/usr/bin/env python3
"""Per-model question-level bootstrap CIs for expansion gains (v1.5.0 paper text).

Convention (matches the v1.4.0 paper text): for each model, the per-question
gain is (condition_ok - s1_fraction); cluster bootstrap over questions.
"""
import json, random

R = json.load(open('/home/z/my-project/results/analysis/expand_v1.json'))

def boot(model, cond, iters=10000, seed=42):
    pq = R['models'][model]['per_q']
    qids = sorted(pq)
    vals = {q: (1 if pq[q][f'{cond}_ok'] else 0) - pq[q]['k1_acc'] for q in qids}
    base = sum(vals.values()) / len(qids)
    rng = random.Random(seed)
    means = []
    for _ in range(iters):
        means.append(sum(vals[qids[rng.randrange(len(qids))]] for _ in range(len(qids))) / len(qids))
    means.sort()
    return base, means[int(0.025*iters)], means[int(0.975*iters)-1]

def fmt(b, lo, hi):
    return f"+{100*b:.1f} (CI {100*lo:+.1f} to {100*hi:+.1f})"

for model in ("agnes-3.0-flash", "agnes-2.5-flash", "deepseek-v4.1-flash",
               "deepseek-v4-pro-0813"):
    print(f"=== {model} (n={R['models'][model]['n']}) ===")
    for cond in ("sc6", "pe6", "hb6", "comb12"):
        b, lo, hi = boot(model, cond)
        print(f"  {cond:7s}-S1: {fmt(b, lo, hi)}")
    # PE-SC paired gap
    pq = R['models'][model]['per_q']
    qids = sorted(pq)
    vals = {q: (1 if pq[q]['pe6_ok'] else 0) - (1 if pq[q]['sc6_ok'] else 0) for q in qids}
    base = sum(vals.values()) / len(qids)
    rng = random.Random(43)
    means = []
    for _ in range(10000):
        means.append(sum(vals[qids[rng.randrange(len(qids))]] for _ in range(len(qids))) / len(qids))
    means.sort()
    print(f"  PE-SC  : {fmt(base, means[250], means[9749])}")
