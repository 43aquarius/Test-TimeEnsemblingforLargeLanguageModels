#!/usr/bin/env python3
"""Analysis v3 (second revision): implements the reviewer's core corrections.

R2  S1 (expected accuracy of ONE tau=0.7 sample, mean over the 6 P0 samples)
    becomes the primary k=1 baseline.  All gains are re-expressed vs S1;
    greedy is kept as a reference column plus a quantified tau=0 anomaly
    block (off-mode rate, S1-greedy gap, truncation evidence).
R3  AURC recomputed with ties broken uniformly at random (mean over 1000
    permutations, fixed seed); random-order baseline (error rate) reported
    alongside so AURC < baseline means the signal helps.
R4  Mode share (fraction of COMB-12 votes on the modal answer) replaces
    support-normalized entropy as the headline disagreement metric; strata
    re-cut at share=1 / [2/3,1) / <2/3; Spearman re-run on mode share vs
    gain-over-S1.  Old entropy kept for comparison only.
R5  Adaptive rule: exact per-model comparison vs every fixed strategy
    (question-count gaps), mean budget as % of the 6-call budget.
R6  greedypara: per-question answer identity between PE-g-6 and PE-6 modes.
Plus: COMB-12/SC-6 tie rates, TOST 3pp->questions conversion, cluster
bootstrap CIs for SC-S1 / PE-S1 pooled.

Writes results/analysis/results_v3.json and results/analysis/numbers_v3.json.
"""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import json, math, os, random
from collections import defaultdict, Counter

DATA = ROOT + "/data"
RES = ROOT + "/results"
OUT = ROOT + "/results/analysis"
os.makedirs(OUT, exist_ok=True)

questions = {q["id"]: q for q in json.load(open(f"{DATA}/questions.json"))}
STEM_DS = {"truthfulqa", "lsat_lr", "logiqa"}
MODELS = ["qwen3.8-max", "qwen3.8-omni", "agnes-3.0-flash",
          "agnes-2.5-flash", "gpt-6-luna", "gemini-3.8-flash"]
MAIN_NEED = [(0, "g")] + [(0, str(s)) for s in range(1, 7)] + \
            [(p, str(s)) for p in (1, 2, 3) for s in (1, 2)] + [(p, "1") for p in (4, 5, 6)]

def gold_of(q):
    if q["dataset"] == "gsm8k":
        return str(q["answer"])
    if q["dataset"] == "piqa":
        return str(q["answer_idx"] + 1)
    return "ABCDEFGHIJ"[q["answer_idx"]]

def locus_of(q):
    return "stem" if q["dataset"] in STEM_DS else "instruction"

def load_model(alias):
    cells = defaultdict(dict)
    n_calls = n_unparsed = 0
    for line in open(f"{RES}/{alias}.jsonl"):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("FAILED"):
            continue
        n_calls += 1
        if r.get("answer") is None:
            n_unparsed += 1
        cells[r["qid"]][(r["para"], str(r["sample"]))] = r
    complete = {}
    for qid, cm in cells.items():
        if all(k in cm and cm[k]["answer"] is not None for k in MAIN_NEED):
            complete[qid] = {k: cm[k] for k in MAIN_NEED}
    return complete, {"calls": n_calls, "unparsed": n_unparsed,
                      "parse_rate": 1 - n_unparsed / max(1, n_calls),
                      "n_complete": len(complete)}

def majority(votes):
    """First-appearing winner among tied leaders (deterministic; tie rate tracked)."""
    vs = [v for v in votes if v is not None]
    if not vs:
        return None
    c = Counter(vs)
    top = max(c.values())
    winners = set(v for v, n in c.items() if n == top)
    for v in vs:
        if v in winners:
            return v

def mode_share(votes):
    vs = [v for v in votes if v is not None]
    if not vs:
        return None
    return max(Counter(vs).values()) / len(vs)

def norm_entropy(votes):
    vs = [v for v in votes if v is not None]
    if len(vs) <= 1:
        return 0.0
    c = Counter(vs)
    h = -sum((n / len(vs)) * math.log(n / len(vs)) for n in c.values())
    return h / math.log(len(c)) if len(c) > 1 else 0.0

def auroc(scores, labels):
    pairs = [(s, l) for s, l in zip(scores, labels) if s is not None]
    if len(set(l for _, l in pairs)) < 2:
        return None
    pos = [s for s, l in pairs if l == 1]
    neg = [s for s, l in pairs if l == 0]
    if not pos or not neg:
        return None
    wins = ties = 0
    for p in pos:
        for n in neg:
            if p > n: wins += 1
            elif p == n: ties += 1
    return (wins + 0.5 * ties) / (len(pos) * len(neg))

def aurc_random(scores, errors, perms=1000, seed=42):
    """AURC with ties broken uniformly at random; mean over permutations."""
    idx = [i for i, s in enumerate(scores) if s is not None]
    n = len(idx)
    if n == 0:
        return None, None
    rng = random.Random(seed)
    vals = []
    for _ in range(perms):
        order = sorted(idx, key=lambda i: (-scores[i], rng.random()))
        cum = tot = 0
        a = 0.0
        for i in order:
            cum += errors[i]; tot += 1; a += cum / tot
        vals.append(a / n)
    mean = sum(vals) / len(vals)
    sd = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
    return mean, sd

def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    from math import comb
    k = min(b, c)
    p = sum(comb(n, i) for i in range(0, k + 1)) / 2 ** n * 2
    return min(1.0, p)

def boot_ci(values, iters=10000, seed=42, alpha=0.05):
    rng = random.Random(seed)
    n = len(values)
    if n == 0:
        return (None, None, None)
    mean = sum(values) / n
    boots = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(iters))
    return mean, boots[int(alpha / 2 * iters)], boots[int((1 - alpha / 2) * iters)]

def tost(diffs, bound, iters=10000, seed=42):
    n = len(diffs)
    mean = sum(diffs) / n
    rng = random.Random(seed + 1)
    boots = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(iters))
    lo, hi = boots[500], boots[9500]
    return {"bound": bound, "mean_diff": mean, "ci90": [lo, hi],
            "equivalent": (lo > -bound and hi < bound)}

def rank_avg(xs):
    idx = sorted(range(len(xs)), key=lambda i: xs[i])
    rks = [0.0] * len(xs)
    i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and xs[idx[j + 1]] == xs[idx[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            rks[idx[k]] = avg
        i = j + 1
    return rks

def spearman(xs, ys):
    rx, ry = rank_avg(xs), rank_avg(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else None

# ---------------- per-model main-suite analysis ----------------
R = {"models": {}}
for alias in MODELS:
    complete, stats = load_model(alias)
    if not complete:
        continue
    per_q = {}
    for qid, cm in complete.items():
        q = questions[qid]
        gold = gold_of(q)
        g = cm[(0, "g")]["answer"]
        gr = cm[(0, "g")]
        sv = [cm[(0, str(s))]["answer"] for s in range(1, 7)]
        pv = [cm[(p, "1")]["answer"] for p in range(1, 7)]
        sc6, pe6 = majority(sv), majority(pv)
        comb = majority(sv + pv)
        hb = majority([cm[(p, str(s))]["answer"] for p in (1, 2, 3) for s in (1, 2)])
        k1 = sum(v == gold for v in sv) / 6.0
        s_counts = Counter(sv)
        winners = set(v for v, n in s_counts.items() if n == max(s_counts.values()))
        per_q[qid] = {
            "dataset": q["dataset"], "locus": locus_of(q), "gold": gold,
            "greedy": g, "greedy_ok": g == gold,
            "k1_acc": k1, "s1": k1,
            "sc6": sc6, "sc6_ok": sc6 == gold,
            "pe6": pe6, "pe6_ok": pe6 == gold,
            "hb6": hb, "hb6_ok": hb == gold,
            "comb12": comb, "comb12_ok": comb == gold,
            "c_s": max(s_counts.values()) / 6, "c_p": mode_share(pv),
            "mode_share": mode_share(sv + pv),
            "mode_share_sc": max(s_counts.values()) / 6,
            "mode_share_pe": mode_share(pv),
            "entropy": norm_entropy(sv + pv),           # legacy, comparison only
            "sc6_tie": max(s_counts.values()) == 3,
            "comb12_tie": mode_share(sv + pv) == 0.5,
            "off_mode": g not in winners,
            "greedy_ct": gr["usage"].get("ct"),
            "greedy_truncated": (gr["usage"].get("ct") or 0) >= 1000,
            "fragile": sc6 != pe6,
        }
    qids = sorted(per_q)
    n = len(qids)
    m = {"stats": stats, "n": n, "per_q": per_q}
    def acc(f):
        return sum(per_q[q][f] for q in qids) / n
    m["acc"] = {k: acc(k) for k in
                ("greedy_ok", "k1_acc", "sc6_ok", "pe6_ok", "hb6_ok", "comb12_ok")}
    # budget-curve points (SC-k / PE-k for k=2,4)
    for k in (2, 4):
        sv_ok = []
        for qid, cm in complete.items():
            gold = gold_of(questions[qid])
            votes = [cm[(0, str(s))]["answer"] for s in range(1, k + 1)]
            sv_ok.append(majority(votes) == gold)
        m[f"acc_sc{k}"] = sum(sv_ok) / len(sv_ok)
        pv_ok = []
        for qid, cm in complete.items():
            gold = gold_of(questions[qid])
            votes = [cm[(p, "1")]["answer"] for p in range(1, k + 1)]
            pv_ok.append(majority(votes) == gold)
        m[f"acc_pe{k}"] = sum(pv_ok) / len(pv_ok)
    # per-dataset aggregation
    m["by_ds"] = {}
    for ds in sorted(set(v["dataset"] for v in per_q.values())):
        dq = [q for q in qids if per_q[q]["dataset"] == ds]
        m["by_ds"][ds] = {
            "n": len(dq),
            "greedy": sum(per_q[q]["greedy_ok"] for q in dq) / len(dq),
            "k1": sum(per_q[q]["k1_acc"] for q in dq) / len(dq),
            "sc6": sum(per_q[q]["sc6_ok"] for q in dq) / len(dq),
            "pe6": sum(per_q[q]["pe6_ok"] for q in dq) / len(dq),
            "comb12": sum(per_q[q]["comb12_ok"] for q in dq) / len(dq),
            "mode_share": sum(per_q[q]["mode_share"] for q in dq) / len(dq),
            "entropy": sum(per_q[q]["entropy"] for q in dq) / len(dq),
        }
    # gains vs S1 (primary) and vs greedy (secondary)
    for cond in ("sc6", "pe6", "hb6", "comb12"):
        m[f"gain_vs_s1_{cond}"] = sum(per_q[q][f"{cond}_ok"] - per_q[q]["k1_acc"] for q in qids) / n
        m[f"gain_vs_greedy_{cond}"] = sum(
            (1 if per_q[q][f"{cond}_ok"] else 0) - (1 if per_q[q]["greedy_ok"] else 0)
            for q in qids) / n
    m["s1_minus_greedy"] = sum(per_q[q]["k1_acc"] - (1 if per_q[q]["greedy_ok"] else 0)
                               for q in qids) / n
    m["off_mode_rate"] = sum(per_q[q]["off_mode"] for q in qids) / n
    m["off_mode_n"] = int(sum(per_q[q]["off_mode"] for q in qids))
    m["off_mode_list"] = [q for q in qids if per_q[q]["off_mode"]]
    m["greedy_truncated_n"] = int(sum(per_q[q]["greedy_truncated"] for q in qids))
    m["sc6_tie_rate"] = sum(per_q[q]["sc6_tie"] for q in qids) / n
    m["comb12_tie_rate"] = sum(per_q[q]["comb12_tie"] for q in qids) / n
    m["mean_mode_share"] = sum(per_q[q]["mode_share"] for q in qids) / n
    m["unanimous_rate"] = sum(1 for q in qids if per_q[q]["mode_share"] == 1) / n
    # accuracy CIs (question-level bootstrap)
    for cond in ("greedy_ok", "k1_acc", "sc6_ok", "pe6_ok", "hb6_ok", "comb12_ok"):
        m[f"ci_{cond}"] = boot_ci([per_q[q][cond] for q in qids])
    # McNemar (SC/PE vs greedy -- kept for reference; S1 is continuous so no McNemar)
    for name, fa, fb in [("sc_vs_greedy", "sc6_ok", "greedy_ok"),
                         ("pe_vs_greedy", "pe6_ok", "greedy_ok")]:
        b = sum(1 for q in qids if per_q[q][fa] and not per_q[q][fb])
        c = sum(1 for q in qids if not per_q[q][fa] and per_q[q][fb])
        m[name + "_p"] = mcnemar(b, c)
    # cluster bootstrap CI for sc6-s1 and pe6-s1 (per model)
    for cond in ("sc6", "pe6", "comb12"):
        mean, lo, hi = boot_ci([per_q[q][f"{cond}_ok"] - per_q[q]["k1_acc"] for q in qids])
        m[f"ci_{cond}_minus_s1"] = [lo, hi]
    # TOST SC vs PE + 3pp->questions conversion
    m["tost3_sc_pe"] = tost([per_q[q]["sc6_ok"] - per_q[q]["pe6_ok"] for q in qids], 0.03)
    m["tost3_questions"] = round(0.03 * n, 1)
    # error detection: AUROC + tie-randomized AURC
    errs = [0 if per_q[q]["comb12_ok"] else 1 for q in qids]
    m["n_errors"] = int(sum(errs))
    m["err_rate"] = sum(errs) / n
    m["descriptive_only"] = m["n_errors"] < 5
    if len(set(errs)) > 1:
        for sig, key in (("cs", "mode_share_sc"), ("cp", "mode_share_pe")):
            m[f"auroc_{sig}"] = auroc([1 - per_q[q][key] for q in qids], errs)
            a_mean, a_sd = aurc_random([per_q[q][key] for q in qids], errs)
            m[f"aurc_{sig}"], m[f"aurc_{sig}_sd"] = a_mean, a_sd
    # mode-share strata (replaces entropy strata)
    strata = {"unanimous (share=1)": [], "strong majority (2/3<=share<1)": [],
              "weak/no majority (share<2/3)": []}
    for q in qids:
        s = per_q[q]["mode_share"]
        if s == 1:
            strata["unanimous (share=1)"].append(q)
        elif s >= 2 / 3:
            strata["strong majority (2/3<=share<1)"].append(q)
        else:
            strata["weak/no majority (share<2/3)"].append(q)
    m["strata"] = {name: {
        "n": len(qs),
        "k1": sum(per_q[q]["k1_acc"] for q in qs) / len(qs) if qs else None,
        "sc6": sum(per_q[q]["sc6_ok"] for q in qs) / len(qs) if qs else None,
        "pe6": sum(per_q[q]["pe6_ok"] for q in qs) / len(qs) if qs else None,
        "comb12": sum(per_q[q]["comb12_ok"] for q in qs) / len(qs) if qs else None,
        "greedy": sum(per_q[q]["greedy_ok"] for q in qs) / len(qs) if qs else None,
    } for name, qs in strata.items()}
    # early stopping + adaptive (same rules as v2, now also vs S1)
    def early_stop(unanimous_at):
        accs, budgets = [], []
        for qid, cm in complete.items():
            gold = gold_of(questions[qid])
            votes = [cm[(0, str(s))]["answer"] for s in range(1, 7)]
            stop = 6
            if unanimous_at:
                for s in range(2, 7):
                    if len(set(votes[:s])) == 1:
                        stop = s
                        break
            accs.append(majority(votes[:stop]) == gold)
            budgets.append(stop)
        return {"acc": sum(accs) / len(accs), "mean_budget": sum(budgets) / len(budgets)}
    m["early_stop_unanimous"] = early_stop(True)

    def adaptive():
        accs, budgets = [], []
        for qid, cm in complete.items():
            gold = gold_of(questions[qid])
            s2 = [cm[(0, str(s))]["answer"] for s in (1, 2)]
            p2 = [cm[(p, "1")]["answer" ] for p in (1, 2)]
            if len(set(s2)) == 1 and len(set(p2)) == 1 and s2[0] == p2[0]:
                ans, used = s2[0], 4
            elif len(set(s2)) == 1 and len(set(p2)) > 1:
                votes = [cm[(0, str(s))]["answer"] for s in range(1, 7)]
                ans, used = majority(votes), 8
            elif len(set(p2)) == 1:
                votes = [cm[(p, "1")]["answer"] for p in range(1, 7)]
                ans, used = majority(votes), 8
            else:
                votes = [cm[(p, str(s))]["answer"] for p in (1, 2, 3) for s in (1, 2)]
                ans, used = majority(votes), 8
            accs.append(ans == gold)
            budgets.append(used)
        return {"acc": sum(accs) / len(accs), "mean_budget": sum(budgets) / len(budgets)}
    m["adaptive_alloc"] = adaptive()
    ad = m["adaptive_alloc"]
    ad["budget_pct_of_6"] = ad["mean_budget"] / 6
    ad["gap_vs_sc6_q"] = int(round((m["acc"]["sc6_ok"] - ad["acc"]) * n))
    ad["gap_vs_pe6_q"] = int(round((m["acc"]["pe6_ok"] - ad["acc"]) * n))
    ad["gap_vs_hb6_q"] = int(round((m["acc"]["hb6_ok"] - ad["acc"]) * n))
    ad["gap_vs_best_q"] = int(round((max(m["acc"]["sc6_ok"], m["acc"]["pe6_ok"]) - ad["acc"]) * n))
    R["models"][alias] = m
    print(f"{alias}: n={n} greedy={m['acc']['greedy_ok']:.3f} S1={m['acc']['k1_acc']:.3f} "
          f"sc6={m['acc']['sc6_ok']:.3f} pe6={m['acc']['pe6_ok']:.3f} "
          f"| g_sc6-s1={m['gain_vs_s1_sc6']:+.3f} g_pe6-s1={m['gain_vs_s1_pe6']:+.3f} "
          f"s1-greedy={m['s1_minus_greedy']:+.3f} offmode={m['off_mode_n']}/{n} "
          f"adapt={ad['acc']:.3f}@{ad['mean_budget']:.2f} (gap_sc6={ad['gap_vs_sc6_q']}q)")

# ---------------- greedypara: per-question PE-g-6 vs PE-6 answer identity (R6) ----------
gp_out = {}
for alias in MODELS:
    path = f"{RES}/cond_greedypara/{alias}.jsonl"
    if not os.path.exists(path):
        continue
    cells = defaultdict(dict)
    for line in open(path):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("FAILED") or r.get("answer") is None:
            continue
        cells[r["qid"]][(r["para"], str(r["sample"]))] = r
    main = R["models"].get(alias, {}).get("per_q", {})
    n = same_ans = same_ok = 0
    for qid, cm in cells.items():
        need = [(p, "g") for p in range(1, 7)]
        if not all(k in cm for k in need):
            continue
        if qid not in main:
            continue
        gp_votes = [cm[(p, "g")]["answer"] for p in range(1, 7)]
        peg6 = majority(gp_votes)
        n += 1
        if peg6 == main[qid]["pe6"]:
            same_ans += 1
        if (peg6 == main[qid]["gold"]) == main[qid]["pe6_ok"]:
            same_ok += 1
    if n:
        gp_out[alias] = {"n": n, "answer_identical": same_ans, "answer_identical_rate": same_ans / n,
                         "correctness_identical": same_ok, "correctness_identical_rate": same_ok / n}
        print(f"greedypara {alias}: n={n} PE-g-6 answer identical to PE-6 on {same_ans}/{n}")
R["greedypara_identity"] = gp_out

# ---------------- pooled analysis (4 models with full common coverage) ----------------
POOL = ["qwen3.8-max", "qwen3.8-omni", "agnes-3.0-flash", "agnes-2.5-flash"]
sets = [set(R["models"][mm]["per_q"].keys()) for mm in POOL]
common = sorted(set.intersection(*sets))
rows = []
for mm in POOL:
    for qid in common:
        v = R["models"][mm]["per_q"][qid]
        rows.append({"model": mm, "qid": qid, "greedy": 1 if v["greedy_ok"] else 0,
                     "k1": v["k1_acc"], "sc6": 1 if v["sc6_ok"] else 0,
                     "pe6": 1 if v["pe6_ok"] else 0, "hb6": 1 if v["hb6_ok"] else 0,
                     "comb12": 1 if v["comb12_ok"] else 0,
                     "mode_share": v["mode_share"], "entropy": v["entropy"],
                     "mode_share_sc": v["mode_share_sc"], "mode_share_pe": v["mode_share_pe"]})
npairs = len(rows)
P = {"models": POOL, "n_pairs": npairs, "n_questions": len(common)}
for cond in ("sc6", "pe6", "hb6", "comb12"):
    P[f"gain_vs_s1_{cond}"] = sum(r[cond] - r["k1"] for r in rows) / npairs
    P[f"gain_vs_greedy_{cond}"] = sum(r[cond] - r["greedy"] for r in rows) / npairs
    P[f"acc_{cond}"] = sum(r[cond] for r in rows) / npairs
P["acc_s1"] = sum(r["k1"] for r in rows) / npairs
P["acc_greedy"] = sum(r["greedy"] for r in rows) / npairs
P["s1_minus_greedy"] = P["acc_s1"] - P["acc_greedy"]

# question-level cluster bootstrap for key differences
by_q = defaultdict(list)
for r in rows:
    by_q[r["qid"]].append(r)
qids_p = sorted(by_q)
def cluster_ci(fn, iters=10000, seed=42, alpha=0.05):
    rng = random.Random(seed)
    vals = []
    stat = fn(rows)
    for _ in range(iters):
        samp = []
        for _ in range(len(qids_p)):
            samp += by_q[qids_p[rng.randrange(len(qids_p))]]
        vals.append(fn(samp))
    vals.sort()
    return {"mean": stat, "ci95": [vals[int(alpha/2*iters)], vals[int((1-alpha/2)*iters)]]}
for cond in ("sc6", "pe6", "comb12"):
    P[f"clci_{cond}_minus_s1"] = cluster_ci(lambda rr, c=cond: sum(r[c] - r["k1"] for r in rr) / len(rr))
    P[f"clci_{cond}_minus_greedy"] = cluster_ci(lambda rr, c=cond: sum(r[c] - r["greedy"] for r in rr) / len(rr))
P["clci_sc6_minus_pe6"] = cluster_ci(lambda rr: sum(r["sc6"] - r["pe6"] for r in rr) / len(rr))
P["clci_s1_minus_greedy"] = cluster_ci(lambda rr: sum(r["k1"] - r["greedy"] for r in rr) / len(rr))
# TOST pooled
P["tost3_sc_pe"] = tost([r["sc6"] - r["pe6"] for r in rows], 0.03)

# mode-share strata pooled
strata = {"unanimous (share=1)": [], "strong majority (2/3<=share<1)": [],
          "weak/no majority (share<2/3)": []}
for r in rows:
    s = r["mode_share"]
    if s == 1: strata["unanimous (share=1)"].append(r)
    elif s >= 2/3: strata["strong majority (2/3<=share<1)"].append(r)
    else: strata["weak/no majority (share<2/3)"].append(r)
P["strata"] = {}
for name, sr in strata.items():
    if not sr: continue
    d = {"n": len(sr)}
    for cond in ("greedy", "k1", "sc6", "pe6", "hb6", "comb12"):
        d[cond] = sum(r[cond] for r in sr) / len(sr)
    P["strata"][name] = d
# Spearman: mode share vs gain-over-S1 (primary), + disjoint variants
P["spearman_share_gaincomb"] = spearman([r["mode_share"] for r in rows],
                                        [r["comb12"] - r["k1"] for r in rows])
P["spearman_share_gainsc"] = spearman([r["mode_share"] for r in rows],
                                      [r["sc6"] - r["k1"] for r in rows])
P["spearman_share_gainpe"] = spearman([r["mode_share"] for r in rows],
                                      [r["pe6"] - r["k1"] for r in rows])
P["spearman_share_greedydrop"] = spearman([r["mode_share"] for r in rows],
                                          [r["k1"] - r["greedy"] for r in rows])
# legacy entropy spearman kept for comparison
P["spearman_entropy_gaincomb_vs_s1"] = spearman([r["entropy"] for r in rows],
                                                [r["comb12"] - r["k1"] for r in rows])
# pooled error detection (AUROC unchanged; AURC tie-randomized pooled)
errs = [0 if r["comb12"] else 1 for r in rows]
P["auroc_cs_pooled"] = auroc([1 - r["mode_share_sc"] for r in rows], errs)
P["auroc_cp_pooled"] = auroc([1 - r["mode_share_pe"] for r in rows], errs)
P["auroc_both_pooled"] = auroc([2 - r["mode_share_sc"] - r["mode_share_pe"] for r in rows], errs)
a_cs, _ = aurc_random([r["mode_share_sc"] for r in rows], errs, perms=1000)
a_cp, _ = aurc_random([r["mode_share_pe"] for r in rows], errs, perms=1000)
P["aurc_cs_pooled"], P["aurc_cp_pooled"] = a_cs, a_cp
P["err_rate_pooled"] = sum(errs) / len(errs)
R["pooled"] = P
print(f"\npooled(4 models, {npairs} pairs over {len(common)} questions): "
      f"S1={P['acc_s1']:.3f} greedy={P['acc_greedy']:.3f} "
      f"sc6={P['acc_sc6']:.3f} pe6={P['acc_pe6']:.3f} comb12={P['acc_comb12']:.3f}")
print(f"  gains vs S1: sc6 {P['gain_vs_s1_sc6']:+.3f} pe6 {P['gain_vs_s1_pe6']:+.3f} "
      f"comb12 {P['gain_vs_s1_comb12']:+.3f}")
print(f"  cluster CI sc6-s1: {P['clci_sc6_minus_s1']}")
print(f"  cluster CI sc6-greedy: {P['clci_sc6_minus_greedy']}")
print(f"  spearman share-vs-gain(comb,s1): {P['spearman_share_gaincomb']:.3f}")

json.dump(R, open(f"{OUT}/results_v3.json", "w"), indent=1)
print(f"\nsaved -> {OUT}/results_v3.json")

# ---------------- compact numbers file for tables/figures ----------------
N = {"models": {}, "pooled": {}, "greedypara_identity": gp_out}
for alias, m in R["models"].items():
    n = m["n"]
    N["models"][alias] = {
        "n": n,
        "greedy": m["acc"]["greedy_ok"], "s1": m["acc"]["k1_acc"],
        "sc6": m["acc"]["sc6_ok"], "pe6": m["acc"]["pe6_ok"],
        "hb6": m["acc"]["hb6_ok"], "comb12": m["acc"]["comb12_ok"],
        "gain_vs_s1_sc6": m["gain_vs_s1_sc6"], "gain_vs_s1_pe6": m["gain_vs_s1_pe6"],
        "gain_vs_s1_hb6": m["gain_vs_s1_hb6"], "gain_vs_s1_comb12": m["gain_vs_s1_comb12"],
        "gain_vs_greedy_sc6": m["gain_vs_greedy_sc6"], "gain_vs_greedy_pe6": m["gain_vs_greedy_pe6"],
        "s1_minus_greedy": m["s1_minus_greedy"], "off_mode_n": m["off_mode_n"],
        "greedy_truncated_n": m["greedy_truncated_n"],
        "sc_vs_greedy_p": m["sc_vs_greedy_p"], "pe_vs_greedy_p": m["pe_vs_greedy_p"],
        "ci_sc6_minus_s1": m["ci_sc6_minus_s1"], "ci_pe6_minus_s1": m["ci_pe6_minus_s1"],
        "tost3_sc_pe": m["tost3_sc_pe"], "tost3_questions": m["tost3_questions"],
        "mean_mode_share": m["mean_mode_share"], "unanimous_rate": m["unanimous_rate"],
        "sc6_tie_rate": m["sc6_tie_rate"], "comb12_tie_rate": m["comb12_tie_rate"],
        "auroc_cs": m.get("auroc_cs"), "auroc_cp": m.get("auroc_cp"),
        "aurc_cs": m.get("aurc_cs"), "aurc_cp": m.get("aurc_cp"),
        "aurc_cs_sd": m.get("aurc_cs_sd"), "aurc_cp_sd": m.get("aurc_cp_sd"),
        "err_rate": m["err_rate"], "n_errors": m["n_errors"],
        "descriptive": m["descriptive_only"],
        "strata": m["strata"],
        "adaptive": m["adaptive_alloc"], "early_stop": m["early_stop_unanimous"],
        "acc_sc2": m["acc_sc2"], "acc_sc4": m["acc_sc4"],
        "acc_pe2": m["acc_pe2"], "acc_pe4": m["acc_pe4"],
        "by_ds": m["by_ds"],
    }
N["pooled"] = {k: v for k, v in P.items() if not k.startswith("clci")} 
N["pooled"].update({k: v for k, v in P.items() if k.startswith("clci")})
json.dump(N, open(f"{OUT}/numbers_v3.json", "w"), indent=1)
print(f"saved -> {OUT}/numbers_v3.json")
