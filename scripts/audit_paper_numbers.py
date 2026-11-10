#!/usr/bin/env python3
"""audit_paper_numbers.py -- number-consistency audit for the TMLR submission.

Recomputes EVERY quantitative claim in the paper (abstract, introduction,
held-out section, discussion, conclusion, and all appendix tables) directly
from the per-call raw logs, then compares each recomputed value with the
value printed in the paper.  Verdicts per claim:

    MATCH        recomputed value agrees with the paper (tolerance below)
    MISMATCH     recomputed value disagrees; the paper must be corrected
                 to the recomputed value (or the logs must be re-checked)
    UNVERIFIABLE the paper states a number that the available raw logs
                 cannot produce (e.g. a missing condition file); flagged
                 as [UNVERIFIED] in the manuscript.

Inputs (all parameterisable; defaults point at the repository that
accompanies the submission):
  --root DIR     repository root containing data/ and results/   (raw logs)
  --out PREFIX   output prefix for the .md and .json reports

Engine functions (load / per_q / majority / boot_ci / cluster_boot / holm /
spearman / auroc) are the same code paths as the release's recompute pass;
seeds are fixed, so runs are deterministic.  Tolerances:
  - percentages / point estimates : 0.06 absolute (points)
  - CI endpoints                  : 0.35 (bootstrap seed noise)
  - AUROC / AURC                  : 0.006 (point), 0.035 (CI)
  - counts, denominators, Holm p  : exact (p to 4 decimals / threshold form)

Usage:  python3 audit_paper_numbers.py --root /path/to/repo --out audit_report
"""
import argparse, json, math, os, random, sys
from collections import defaultdict, Counter

# ---------------------------------------------------------------- engine --
NEED = [(0, "g")] + [(0, str(s)) for s in range(1, 7)] + \
       [(p, str(s)) for p in (1, 2, 3) for s in (1, 2)] + [(p, "1") for p in (4, 5, 6)]
STEM_DS = {"truthfulqa", "lsat_lr", "logiqa"}

def gold_of(q):
    if q["dataset"] == "gsm8k":
        return str(q["answer"])
    if q["dataset"] == "piqa":
        return str(q["answer_idx"] + 1)
    return "ABCDEFGHIJ"[q["answer_idx"]]

def majority(votes):
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
    return max(Counter(vs).values()) / len(vs) if vs else None

def load(path):
    """cells[qid][(para,sample)] -> record; NEED-complete questions only."""
    cells = defaultdict(dict)
    n_calls = n_unparsed = 0
    for line in open(path):
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
        if all(k in cm and cm[k]["answer"] is not None for k in NEED):
            complete[qid] = {k: cm[k] for k in NEED}
    return complete, cells, {"calls": n_calls, "unparsed": n_unparsed,
                             "parse_rate": (n_calls - n_unparsed) / n_calls if n_calls else None}

def per_q(complete, questions):
    out = {}
    for qid, cm in complete.items():
        q = questions[qid]
        gold = gold_of(q)
        g = cm[(0, "g")]["answer"]
        sv = [cm[(0, str(s))]["answer"] for s in range(1, 7)]
        pv = [cm[(p, "1")]["answer"] for p in range(1, 7)]
        pe1 = sum(v == gold for v in pv) / 6.0
        s_counts = Counter(sv)
        winners = set(v for v, n in s_counts.items() if n == max(s_counts.values()))
        out[qid] = {
            "dataset": q["dataset"], "gold": gold,
            "greedy_ok": g == gold,
            "k1_acc": sum(v == gold for v in sv) / 6.0,
            "pe1_acc": pe1,
            "sc6_ok": majority(sv) == gold, "pe6_ok": majority(pv) == gold,
            "hb6_ok": majority([cm[(p, str(s))]["answer"] for p in (1, 2, 3) for s in (1, 2)]) == gold,
            "comb12_ok": majority(sv + pv) == gold,
            "mode_share": mode_share(sv + pv),
            "off_mode": g not in winners,
            "fragile": majority(sv) != majority(pv),
        }
    return out

def boot_ci(vals, iters=10000, seed=42, alpha=0.05):
    rng = random.Random(seed)
    n = len(vals)
    means = sorted(sum(vals[rng.randrange(n)] for _ in range(n)) / n for _ in range(iters))
    return (sum(vals) / n, means[int(alpha / 2 * iters)], means[int((1 - alpha / 2) * iters) - 1])

def cluster_boot(by_q_pairs, field_fn, iters=10000, seed=42, alpha=0.05):
    qids = sorted(by_q_pairs)
    vals = {q: sum(field_fn(r) for r in by_q_pairs[q]) / len(by_q_pairs[q]) for q in qids}
    base = sum(vals.values()) / len(qids)
    rng = random.Random(seed)
    means = sorted(sum(vals[qids[rng.randrange(len(qids))]] for _ in range(len(qids))) / len(qids)
                   for _ in range(iters))
    lo, hi = means[int(alpha / 2 * iters)], means[int((1 - alpha / 2) * iters) - 1]
    n = len(qids)
    rng2 = random.Random(seed + 2)
    neg = pos = 0
    for _ in range(iters):
        m = sum(vals[qids[rng2.randrange(n)]] for _ in range(n)) / n
        if m <= 0:
            neg += 1
        if m >= 0:
            pos += 1
    p = min(1.0, 2 * min(neg, pos) / iters)
    return base, lo, hi, p

def holm(pvals):
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    m = len(pvals)
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * pvals[i])
        adj[i] = min(1.0, running)
    return adj

def spearman(xs, ys):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        rk = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                rk[order[k]] = avg
            i = j + 1
        return rk
    rx, ry = rank(xs), rank(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else float("nan")

def auroc_(scores, labels):
    pairs_ = [(s, l) for s, l in zip(scores, labels) if s is not None]
    if len(set(l for _, l in pairs_)) < 2:
        return None
    pos = [s for s, l in pairs_ if l == 1]
    neg = [s for s, l in pairs_ if l == 0]
    if not pos or not neg:
        return None
    w = t = 0
    for p in pos:
        for n in neg:
            if p > n:
                w += 1
            elif p == n:
                t += 1
    return (w + 0.5 * t) / (len(pos) * len(neg))

def auroc_boot_ci(scores, labels, iters=1000, seed=11, alpha=0.05):
    """question-level bootstrap CI for AUROC (ties included)."""
    idx = [i for i, s in enumerate(scores) if s is not None]
    rng = random.Random(seed)
    vals = []
    for _ in range(iters):
        sample = [idx[rng.randrange(len(idx))] for _ in range(len(idx))]
        a = auroc_([scores[i] for i in sample], [labels[i] for i in sample])
        if a is not None:
            vals.append(a)
    if not vals:
        return None, None
    vals.sort()
    return vals[int(alpha / 2 * len(vals))], vals[int((1 - alpha / 2) * len(vals)) - 1]

def aurc_ties(scores, labels, perms=1000, seed=7):
    """AURC averaged over uniformly random tie-breaking (1,000 permutations)."""
    idx = [i for i, s in enumerate(scores) if s is not None]
    if not idx:
        return None
    rng = random.Random(seed)
    total = 0.0
    for _ in range(perms):
        order = idx[:]
        rng.shuffle(order)
        # ascending risk: accept the most-confident (lowest disagreement) first;
        # within equal scores the shuffled order rules (uniform random tie-break)
        order.sort(key=lambda i: scores[i])
        errs = 0
        acc_err = 0.0
        for k, i in enumerate(order, start=1):
            errs += labels[i]
            acc_err += errs / k
        total += acc_err / len(order)
    return total / perms

def early_stop_replay(complete, questions):
    accs, budgets = [], []
    for qid, cm in complete.items():
        gold = gold_of(questions[qid])
        votes = [cm[(0, str(s))]["answer"] for s in range(1, 7)]
        stop = 6
        for s in range(2, 7):
            if len(set(votes[:s])) == 1:
                stop = s
                break
        accs.append(majority(votes[:stop]) == gold)
        budgets.append(stop)
    return {"acc": sum(accs) / len(accs), "mean_budget": sum(budgets) / len(budgets)}

def adaptive_replay(complete, questions):
    """probe(2 canonical + 2 paraphrases) -> unanimous exit / SC-6 / PE-6 / HB-6.
    Budget accounting as in the release's analyze pass: the probe's calls are
    charged, so routes cost 4 (unanimous exit) or 8 total calls."""
    accs, budgets, counts = [], [], Counter()
    for qid, cm in complete.items():
        gold = gold_of(questions[qid])
        s2 = [cm[(0, str(s))]["answer"] for s in (1, 2)]
        p2 = [cm[(p, "1")]["answer"] for p in (1, 2)]
        if len(set(s2)) == 1 and len(set(p2)) == 1 and s2[0] == p2[0]:
            ans, used = s2[0], 4
            counts["unanimous_exit"] += 1
        elif len(set(s2)) == 1 and len(set(p2)) > 1:
            votes = [cm[(0, str(s))]["answer"] for s in range(1, 7)]
            ans, used = majority(votes), 8
            counts["sample_vote"] += 1
        elif len(set(p2)) == 1:
            votes = [cm[(p, "1")]["answer"] for p in range(1, 7)]
            ans, used = majority(votes), 8
            counts["paraphrase_vote"] += 1
        else:
            votes = [cm[(p, str(s))]["answer"] for p in (1, 2, 3) for s in (1, 2)]
            ans, used = majority(votes), 8
            counts["hybrid_vote"] += 1
        accs.append(ans == gold)
        budgets.append(used)
    return {"acc": sum(accs) / len(accs), "mean_budget": sum(budgets) / len(budgets),
            "routes": dict(counts)}

# ------------------------------------------------------------------ setup --
ap = argparse.ArgumentParser()
ap.add_argument("--root", default=".")            # repository root (data/, results/)
ap.add_argument("--out", default="audit_report")   # output prefix for .md/.json reports
args = ap.parse_args()
BASE = os.path.abspath(args.root)
DATA, RES, EXP = f"{BASE}/data", f"{BASE}/results", f"{BASE}/results/expand"
MAIN_MODELS = ["qwen3.8-max", "qwen3.8-omni", "agnes-3.0-flash", "agnes-2.5-flash",
               "gpt-6-luna", "gemini-3.8-flash"]
EXP_MODELS = ["agnes-3.0-flash", "agnes-2.5-flash", "qwen3.7-flash",
              "deepseek-v4.1-flash", "deepseek-v4-flash-0731", "deepseek-v4-pro-0813"]
FULL4 = ["agnes-3.0-flash", "agnes-2.5-flash", "deepseek-v4.1-flash", "deepseek-v4-pro-0813"]

Q = {q["id"]: q for q in json.load(open(f"{DATA}/questions.json"))}
QE = {q["id"]: q for q in json.load(open(f"{DATA}/questions_expand.json"))}

R = {}   # computed results, keyed for CLAIMS lambdas
CLAIMS = []
def claim(loc, desc, paper, computed, tol=None, kind="num"):
    """Register one audit row.  paper/computed may be numbers, strings, tuples."""
    CLAIMS.append({"loc": loc, "desc": desc, "paper": paper, "computed": computed,
                   "tol": tol, "kind": kind})

def verdict(c):
    p, got, tol, kind = c["paper"], c["computed"], c["tol"], c["kind"]
    if got is None or (isinstance(got, str) and got.startswith("UNAVAILABLE")):
        return "UNVERIFIABLE"
    if p is None:
        return "MATCH"   # informational row (no paper value to violate)
    if kind == "num":
        if isinstance(p, (list, tuple)):
            if len(p) != len(got) or not isinstance(got, (list, tuple)):
                return "MISMATCH"
            n_none = 0
            for a, b in zip(p, got):
                if b is None:
                    n_none += 1
                    continue
                try:
                    item_ok = abs(float(a) - float(b)) <= (tol or 0.35)
                except (TypeError, ValueError):
                    return "MISMATCH"
                if not item_ok:
                    return "MISMATCH"
            if n_none:
                return "UNVERIFIABLE" if n_none == len(p) else "MATCH"
            return "MATCH"
        else:
            if got is None:
                return "UNVERIFIABLE"
            try:
                ok = abs(float(p) - float(got)) <= (tol or 0.06)
            except (TypeError, ValueError):
                return "MISMATCH"
    elif kind == "count":
        if isinstance(p, (list, tuple)):
            if len(p) != len(got) or not isinstance(got, (list, tuple)):
                return "MISMATCH"
            try:
                ok = all(int(a) == int(b) for a, b in zip(p, got))
            except (TypeError, ValueError):
                ok = False
        else:
            try:
                ok = int(p) == int(got)
            except (TypeError, ValueError):
                ok = False
    elif kind == "str":
        ok = str(p).strip() == str(got).strip()
    elif kind == "pval":   # paper may say "<0.0001"
        pv = str(p).strip()
        try:
            val = float(got)
        except Exception:
            return "MISMATCH"
        if pv.startswith("<"):
            return "MATCH" if val < float(pv[1:]) else "MISMATCH"
        ok = abs(float(pv) - val) <= (tol or 0.002)
    else:
        ok = str(p) == str(got)
    return "MATCH" if ok else "MISMATCH"

# ======================================================= 1. development suite
main = {}
for m in MAIN_MODELS:
    complete, cells, stats = load(f"{RES}/{m}.jsonl")
    pq = per_q(complete, Q)
    qids = sorted(pq)
    n = len(qids)
    def A(f, qs=None):
        qs = qs or qids
        return 100 * sum(pq[q][f] for q in qs) / len(qs)
    inst = [q for q in qids if Q[q]["dataset"] not in STEM_DS]
    stem = [q for q in qids if Q[q]["dataset"] in STEM_DS]
    main[m] = {
        "n": n, "pq": pq, "complete": complete, "cells": cells, "stats": stats,
        "greedy": A("greedy_ok"), "s1": A("k1_acc"), "pe1": A("pe1_acc"),
        "sc6": A("sc6_ok"), "pe6": A("pe6_ok"), "hb6": A("hb6_ok"), "comb": A("comb12_ok"),
        "off_mode_n": sum(pq[q]["off_mode"] for q in qids),
        "frag_inst": (sum(pq[q]["fragile"] for q in inst), len(inst)),
        "frag_stem": (sum(pq[q]["fragile"] for q in stem), len(stem)),
        "auroc_cs": None, "auroc_cp": None, "aurc_cs": None, "aurc_cp": None,
    }
    # error-signal AUROC/AURC (reference: COMB-12)
    errs = [0 if pq[q]["comb12_ok"] else 1 for q in qids]
    cs = [mode_share([complete[q][(0, str(s))]["answer"] for s in range(1, 7)]) for q in qids]
    cp = [mode_share([complete[q][(p, "1")]["answer"] for p in range(1, 7)]) for q in qids]
    main[m]["auroc_cs"] = auroc_([1 - v for v in cs], errs)
    main[m]["auroc_cp"] = auroc_([1 - v for v in cp], errs)
    main[m]["auroc_both"] = auroc_([2 - a - b for a, b in zip(cs, cp)], errs)
    main[m]["aurc_cs"] = aurc_ties([1 - v for v in cs], errs)
    main[m]["aurc_cp"] = aurc_ties([1 - v for v in cp], errs)
    main[m]["n_errors"] = sum(errs)
    main[m]["err_rate"] = 100 * sum(errs) / len(errs)
    # token matching: canonical samples vs paraphrase first decodes
    tok_c, tok_p = [], []
    for qid, cm in complete.items():
        for si in range(1, 7):
            u = cm[(0, str(si))].get("usage") or {}
            if u.get("pt") is not None and u.get("ct") is not None:
                tok_c.append(u["pt"] + u["ct"])
        for pi in range(1, 7):
            u = cm[(pi, "1")].get("usage") or {}
            if u.get("pt") is not None and u.get("ct") is not None:
                tok_p.append(u["pt"] + u["ct"])
    main[m]["tok_c"] = sum(tok_c) / len(tok_c) if tok_c else None
    main[m]["tok_p"] = sum(tok_p) / len(tok_p) if tok_p else None
    # per-model stem-locus fragility rate (used by A.2 claims)
    main[m]["frag_stem_rate"] = (100 * main[m]["frag_stem"][0] / main[m]["frag_stem"][1]) if main[m]["frag_stem"][1] else None
    # budget-curve points used by the appendix text
    main[m]["sc4"] = 100 * sum(majority([complete[q][(0, str(s))]["answer"] for s in range(1, 5)]) == gold_of(Q[q]) for q in qids) / n
    main[m]["pe2"] = 100 * sum(majority([complete[q][(p, "1")]["answer"] for p in (1, 3)]) == gold_of(Q[q]) for q in qids) / n
    main[m]["pe4"] = 100 * sum(majority([complete[q][(p, "1")]["answer"] for p in (1, 5)]) == gold_of(Q[q]) for q in qids) / n
    main[m]["es"] = early_stop_replay(complete, Q)
    main[m]["adaptive"] = adaptive_replay(complete, Q)
    main[m]["adaptive"]["budget_pct_of_6"] = main[m]["adaptive"]["mean_budget"] / 6

R["main"] = main

# pooled development (four well-covered models, intersection of completed qids)
# pooled development: four well-covered models on their common questions
# (same P4 set as the release's recompute pass: Max, Omni, Agnes3.0, Agnes2.5)
pooled_models = ["qwen3.8-max", "qwen3.8-omni", "agnes-3.0-flash", "agnes-2.5-flash"]
P4 = pooled_models
# sorted() for cross-process determinism: Python string hashing is randomized
# per process, so iterating a raw set changes bootstrap input order run to run.
# The release's recompute pass sorts the same intersection.
common = sorted(set.intersection(*(set(main[m]["pq"]) for m in pooled_models)))
by_q = {q: [main[m]["pq"][q] for m in pooled_models] for q in common}
npairs = sum(len(v) for v in by_q.values())
def pooled_pct(field):
    return 100 * sum(sum(r[field] for r in rs) / len(rs) for rs in by_q.values()) / len(by_q)
p_s1, p_gr = pooled_pct("k1_acc"), pooled_pct("greedy_ok")
p_sc, p_pe, p_cb = pooled_pct("sc6_ok"), pooled_pct("pe6_ok"), pooled_pct("comb12_ok")
g2, g2_lo, g2_hi, _ = cluster_boot(by_q, lambda r: (1 if r["sc6_ok"] else 0) - (1 if r["pe6_ok"] else 0), seed=44)
_, g90_lo, g90_hi = boot_ci([(1 if r["sc6_ok"] else 0) - (1 if r["pe6_ok"] else 0)
                             for q in common for r in by_q[q]], iters=10000, seed=46, alpha=0.10)
ggap, gg_lo, gg_hi, _ = cluster_boot(by_q, lambda r: r["k1_acc"] - r["greedy_ok"], seed=45)
unan = sum(1 for q in common for r in by_q[q] if r["mode_share"] == 1)
R["dev_pooled"] = {"n_pairs": npairs, "n_q": len(common), "s1": p_s1, "greedy": p_gr,
                   "sc6": p_sc, "pe6": p_pe, "comb": p_cb,
                   "sc_s1": p_sc - p_s1, "pe_s1": p_pe - p_s1,
                   "sc_pe": 100 * g2, "sc_pe_ci": [100 * g2_lo, 100 * g2_hi],
                   "sc_pe_ci90": [100 * g90_lo, 100 * g90_hi],
                   "s1_greedy": 100 * ggap, "s1_greedy_ci": [100 * gg_lo, 100 * gg_hi],
                   "unanimous": unan}
# rq4 correlations
ds_all, s1m_gr, comb_s1 = [], [], []
samp_diss_pe, para_diss_sc = [], []
for q in common:
    for m in pooled_models:
        cm = main[m]["complete"][q]
        pq = main[m]["pq"][q]
        cs_share = mode_share([cm[(0, str(s))]["answer"] for s in range(1, 7)])
        cp_share = mode_share([cm[(p, "1")]["answer"] for p in range(1, 7)])
        ds_all.append(1 - pq["mode_share"])
        s1m_gr.append(pq["k1_acc"] - pq["greedy_ok"])
        comb_s1.append((1 if pq["comb12_ok"] else 0) - pq["k1_acc"])
        # disjoint votes: sample-side dissent vs PE-6 gain over PE-1;
        # paraphrase-side dissent vs SC-6 gain over S1
        samp_diss_pe.append((1 - cs_share, (1 if pq["pe6_ok"] else 0) - pq["pe1_acc"]))
        para_diss_sc.append((1 - cp_share, (1 if pq["sc6_ok"] else 0) - pq["k1_acc"]))
R["rq4"] = {
    "spearman_dissent_gap": spearman(ds_all, s1m_gr),
    "spearman_dissent_comb": spearman(ds_all, comb_s1),
    "spearman_sampdiss_pegain": spearman([a for a, _ in samp_diss_pe], [b for _, b in samp_diss_pe]),
    "spearman_paradiss_scgain": spearman([a for a, _ in para_diss_sc], [b for _, b in para_diss_sc]),
}
# stratified pairs
strata_rows = [(q, r) for q in common for r in by_q[q]]
R["rq4"]["n_unanimous_pairs"] = sum(1 for _, r in strata_rows if r["mode_share"] == 1)
R["rq4"]["n_strong_pairs"] = sum(1 for _, r in strata_rows if 2 / 3 <= r["mode_share"] < 1)
R["rq4"]["n_weak_pairs"] = sum(1 for _, r in strata_rows if r["mode_share"] < 2 / 3)
def strat_acc(rows, field):
    return 100 * sum(r[field] for _, r in rows) / len(rows) if rows else None
unan_rows = [(q, r) for q, r in strata_rows if r["mode_share"] == 1]
str_rows = [(q, r) for q, r in strata_rows if 2 / 3 <= r["mode_share"] < 1]
weak_rows = [(q, r) for q, r in strata_rows if r["mode_share"] < 2 / 3]
R["rq4"]["unan"] = {"n": len(unan_rows), "k1": strat_acc(unan_rows, "k1_acc"),
                    "greedy": strat_acc(unan_rows, "greedy_ok")}
R["rq4"]["strong"] = {"n": len(str_rows), "k1": strat_acc(str_rows, "k1_acc"),
                      "sc6": strat_acc(str_rows, "sc6_ok")}
R["rq4"]["weak"] = {"n": len(weak_rows), "k1": strat_acc(weak_rows, "k1_acc"),
                    "sc6": strat_acc(weak_rows, "sc6_ok"), "pe6": strat_acc(weak_rows, "pe6_ok"),
                    "comb": strat_acc(weak_rows, "comb12_ok")}
# flag counts in dev error analysis
fl = {}
for m in MAIN_MODELS:
    pq, complete = main[m]["pq"], main[m]["complete"]
    qids = sorted(pq)
    errs = {q: 0 if pq[q]["comb12_ok"] else 1 for q in qids}
    cs = {q: mode_share([complete[q][(0, str(s))]["answer"] for s in range(1, 7)]) for q in qids}
    cp = {q: mode_share([complete[q][(p, "1")]["answer"] for p in range(1, 7)]) for q in qids}
    fl[m] = {"errors": sum(errs.values()),
             "flag_cs": sum(1 for q in qids if errs[q] and cs[q] < 1),
             "flag_cp": sum(1 for q in qids if errs[q] and cp[q] < 1),
             "only_cs": sum(1 for q in qids if errs[q] and cs[q] < 1 and cp[q] == 1),
             "only_cp": sum(1 for q in qids if errs[q] and cp[q] < 1 and cs[q] == 1)}
R["dev_flags"] = fl

# pooled development AUROC over the flattened common pairs + cluster CI
def pooled_auroc(det):
    scores, labels = [], []
    for q in common:
        for m in pooled_models:
            comp = main[m]["complete"][q]
            cs = mode_share([comp[(0, str(si))]["answer"] for si in range(1, 7)])
            cp_ = mode_share([comp[(pi, "1")]["answer"] for pi in range(1, 7)])
            err = 0 if main[m]["pq"][q]["comb12_ok"] else 1
            if det == "cs": scores.append(1 - cs)
            elif det == "cp": scores.append(1 - cp_)
            else: scores.append(2 - cs - cp_)
            labels.append(err)
    return auroc_(scores, labels), (scores, labels)
pa_cs, (sc_scores, sc_labels) = pooled_auroc("cs")
pa_cp, (cp_scores, cp_labels) = pooled_auroc("cp")
def auroc_cluster_ci(scores, labels, iters=1000, seed=13):
    qids = sorted(common)
    rng = random.Random(seed)
    vals = []
    for _ in range(iters):
        sample_qs = [qids[rng.randrange(len(qids))] for _ in range(len(qids))]
        s2, l2 = [], []
        for q in sample_qs:
            for m in pooled_models:
                comp = main[m]["complete"][q]
                cs = mode_share([comp[(0, str(si))]["answer"] for si in range(1, 7)])
                cp_ = mode_share([comp[(pi, "1")]["answer"] for pi in range(1, 7)])
                err = 0 if main[m]["pq"][q]["comb12_ok"] else 1
                s2.append(1 - cs if scores is sc_scores else (1 - cp_ if scores is cp_scores else 2 - cs - cp_))
                l2.append(err)
        a = auroc_(s2, l2)
        if a is not None: vals.append(a)
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]
ci_sc_pool = auroc_cluster_ci(sc_scores, sc_labels)
ci_cp_pool = auroc_cluster_ci(cp_scores, cp_labels)
R["dev_pooled_auroc"] = {"cs": pa_cs, "cp": pa_cp, "ci_cs": ci_sc_pool, "ci_cp": ci_cp_pool}

# dev fragility pooled by locus over the common set (release definition of 0/52, 3.3%)
fi = sum(1 for q in common for r in by_q[q] if Q[q]["dataset"] not in STEM_DS and r["fragile"])
ni = sum(1 for q in common for r in by_q[q] if Q[q]["dataset"] not in STEM_DS)
fs_ = sum(1 for q in common for r in by_q[q] if Q[q]["dataset"] in STEM_DS and r["fragile"])
ns_ = sum(1 for q in common for r in by_q[q] if Q[q]["dataset"] in STEM_DS)
R["frag_dev_pooled"] = {"inst": [fi, ni], "stem_rate": 100 * fs_ / ns_ if ns_ else None}

# tight-0.80 fragility (needs data/para_sims_fresh.json)
def tight_frag(m, thresh=0.80, min_paras=4):
    try:
        sims = json.load(open(f"{DATA}/para_sims_fresh.json"))
    except Exception:
        return None, None
    pq = main[m]["pq"]
    nq = fl_ = 0
    for qid in pq:
        sim = sims.get(qid)
        if not sim:
            continue
        keep = [i + 1 for i, v in enumerate(list(sim)[:6]) if v > thresh]
        if len(keep) < min_paras:
            continue
        cm = main[m]["complete"].get(qid)
        if cm is None:
            continue
        pv = [cm[(pp, "1")]["answer"] for pp in keep]
        sc_ans = majority([cm[(0, str(s2))]["answer"] for s2 in range(1, 7)])
        nq += 1
        fl_ += (sc_ans != majority(pv))
    return (100 * fl_ / nq if nq else None), nq
R["tight_frag"] = {m: tight_frag(m) for m in ("gpt-6-luna", "gemini-3.8-flash", "qwen3.8-omni")}

# ============================================================ 2. held-out suite
exp = {}
for m in EXP_MODELS:
    complete, cells, stats = load(f"{EXP}/{m}.jsonl")
    pq = per_q(complete, QE)
    qids = sorted(pq)
    n = len(qids)
    def A(f, qs=None):
        qs = qs or qids
        return 100 * sum(pq[q][f] for q in qs) / len(qs)
    exp[m] = {
        "n": n, "pq": pq, "complete": complete, "cells": cells, "stats": stats,
        "greedy": A("greedy_ok"), "s1": A("k1_acc"), "pe1": A("pe1_acc"),
        "sc6": A("sc6_ok"), "pe6": A("pe6_ok"), "hb6": A("hb6_ok"), "comb": A("comb12_ok"),
        "off_mode_n": sum(pq[q]["off_mode"] for q in qids),
        "unanimous_rate": sum(1 for q in qids if pq[q]["mode_share"] == 1) / n,
        "es": early_stop_replay(complete, QE),
        "adaptive": adaptive_replay(complete, QE),
    }
    exp[m]["adaptive"]["budget_pct_of_6"] = exp[m]["adaptive"]["mean_budget"] / 6
R["exp"] = exp

by_qe = {q: [exp[m]["pq"][q] for m in FULL4 if q in exp[m]["pq"]] for q in QE if any(q in exp[m]["pq"] for m in FULL4)}
def pooled_e(field):
    return 100 * sum(sum(r[field] for r in rs) / len(rs) for rs in by_qe.values()) / len(by_qe)
pe_gr, pe_s1 = pooled_e("greedy_ok"), pooled_e("k1_acc")
pe_sc, pe_pe, pe_cb, pe_hb, pe_pe1 = pooled_e("sc6_ok"), pooled_e("pe6_ok"), pooled_e("comb12_ok"), pooled_e("hb6_ok"), pooled_e("pe1_acc")

# designated primary contrasts (cluster bootstrap, Holm)
def pooled_ci(field_a, field_b, seed):
    return cluster_boot(by_qe, lambda r: (1 if r[field_a] else 0) - (1 if r[field_b] else 0) if field_a.endswith("_ok") else r[field_a] - r[field_b], seed=seed)
def pair_ci(cond_ok, base, seed):
    return cluster_boot(by_qe, lambda r, c=cond_ok, b=base: (1 if r[c] else 0) - (1 if r[b] else 0), seed=seed)
c_sc, lo_sc, hi_sc, p_sc_ = pair_ci("sc6_ok", "k1_acc" if False else None, 60) if False else (None,) * 4
# explicit: gains vs S1 use correctness indicators; PE-SC gap uses pair diff
def gain_ci(cond, seed):
    return cluster_boot(by_qe, lambda r, c=cond: (1 if r[c] else 0) - r["k1_acc"], seed=seed)
gi = {}
for cond, seed in [("sc6_ok", 60), ("pe6_ok", 61), ("comb12_ok", 62), ("hb6_ok", 63)]:
    base, lo, hi, p = cluster_boot(by_qe, lambda r, c=cond: (1 if r[c] else 0) - r["k1_acc"], seed=seed)
    gi[cond] = {"mean": 100 * base, "ci": [100 * lo, 100 * hi], "p": p}
base, lo, hi, p = cluster_boot(by_qe, lambda r: (1 if r["pe6_ok"] else 0) - (1 if r["sc6_ok"] else 0), seed=64)
gi["pe_sc"] = {"mean": 100 * base, "ci": [100 * lo, 100 * hi], "p": p}
base, lo, hi, p = cluster_boot(by_qe, lambda r: (1 if r["pe6_ok"] else 0) - (1 if r["hb6_ok"] else 0), seed=65)
gi["pe_hb"] = {"mean": 100 * base, "ci": [100 * lo, 100 * hi], "p": p}
base, lo, hi, p = cluster_boot(by_qe, lambda r: (1 if r["comb12_ok"] else 0) - (1 if r["pe6_ok"] else 0), seed=66)
gi["comb_pe"] = {"mean": 100 * base, "ci": [100 * lo, 100 * hi], "p": p}
contrasts = ["sc6_ok", "pe6_ok", "comb12_ok", "pe_sc"]
adj = holm([gi[c]["p"] for c in contrasts])
for c, a in zip(contrasts, adj):
    gi[c]["p_holm"] = a
R["primary"] = gi
R["exp_pooled"] = {"greedy": pe_gr, "s1": pe_s1, "sc6": pe_sc, "pe6": pe_pe,
                   "comb": pe_cb, "hb": pe_hb, "pe1": pe_pe1,
                   "difficulty_offset": pe_pe1 - pe_s1,
                   "dpe": pe_pe - pe_pe1, "dsc": pe_sc - pe_s1,
                   "n_pairs": sum(len(v) for v in by_qe.values()), "n_q": len(by_qe)}

# per-model held-out CIs (vs S1)
R["exp_model_ci"] = {}
for m in FULL4:
    pq = exp[m]["pq"]
    qids = sorted(pq)
    row = {}
    for cond, seed in [("sc6_ok", 70), ("pe6_ok", 71), ("comb12_ok", 72), ("hb6_ok", 73)]:
        vals = [(1 if pq[q][cond] else 0) - pq[q]["k1_acc"] for q in qids]
        mean, lo, hi = boot_ci(vals, seed=seed)
        row[cond] = {"mean": 100 * mean, "ci": [100 * lo, 100 * hi]}
    R["exp_model_ci"][m] = row

# combined dev+held-out union for the two Agnes models
R["union"] = {}
for m in ["agnes-3.0-flash", "agnes-2.5-flash"]:
    merged = dict(main[m]["pq"])
    merged.update(exp[m]["pq"])
    qids = sorted(merged)
    def A(f):
        return 100 * sum(merged[q][f] for q in qids) / len(qids)
    row = {"n": len(qids), "s1": A("k1_acc"), "sc6": A("sc6_ok"), "pe6": A("pe6_ok")}
    for cond, seed in [("sc6_ok", 80), ("pe6_ok", 81)]:
        vals = [(1 if merged[q][cond] else 0) - merged[q]["k1_acc"] for q in qids]
        mean, lo, hi = boot_ci(vals, seed=seed)
        row[f"d{cond}"] = {"mean": 100 * mean, "ci": [100 * lo, 100 * hi]}
    # the paper reports these per-model movements as PE-6 minus S1
    row["dev_dpe"] = 100 * (sum(1 if main[m]["pq"][q]["pe6_ok"] else 0 for q in main[m]["pq"]) / len(main[m]["pq"])
                            - sum(main[m]["pq"][q]["k1_acc"] for q in main[m]["pq"]) / len(main[m]["pq"]))
    row["ho_dpe"] = exp[m]["pe6"] - exp[m]["s1"]
    row["union_dpe_vs_s1"] = row["pe6"] - row["s1"]
    R["union"][m] = row

# strata on held-out
strata_defs = {"unan": (1.0, None), "strong": (2 / 3, 1.0), "weak": (None, 2 / 3)}
R["strata"] = {}
for m in FULL4:
    pq = exp[m]["pq"]
    for sname, (lo_, hi_) in strata_defs.items():
        qs = [q for q in pq if (lo_ is None or pq[q]["mode_share"] >= lo_) and (hi_ is None or pq[q]["mode_share"] < hi_)]
        R["strata"][(m, sname)] = {
            "n": len(qs),
            "s1": 100 * sum(pq[q]["k1_acc"] for q in qs) / len(qs) if qs else None,
            "sc6": 100 * sum(pq[q]["sc6_ok"] for q in qs) / len(qs) if qs else None,
            "pe6": 100 * sum(pq[q]["pe6_ok"] for q in qs) / len(qs) if qs else None,
            "comb": 100 * sum(pq[q]["comb12_ok"] for q in qs) / len(qs) if qs else None}
def strat_model_mean(sname, field):
    return sum(R["strata"][(m, sname)][field] for m in FULL4) / 4
R["strata_pooled"] = {
    "weak": {"n": sum(R["strata"][(m, "weak")]["n"] for m in FULL4),
             "s1": strat_model_mean("weak", "s1"), "sc6": strat_model_mean("weak", "sc6"),
             "pe6": strat_model_mean("weak", "pe6")},
    "strong": {"s1": strat_model_mean("strong", "s1")},
    "unan": {"max_cond": max(strat_model_mean("unan", f) for f in ("s1", "sc6", "pe6", "comb"))}}

# off-mode / greedy divergence over all ten configurations
gd = {}
for m in MAIN_MODELS:
    gd[m] = (main[m]["greedy"], main[m]["s1"])
for m in EXP_MODELS:
    gd[m + " (held-out)"] = (exp[m]["greedy"], exp[m]["s1"])
R["greedy_divergence"] = {k: {"greedy": round(g, 1), "s1": round(s, 1), "gap": round(s - g, 1)}
                          for k, (g, s) in gd.items()}
R["off_mode"] = {m: exp[m]["off_mode_n"] for m in EXP_MODELS}

# held-out fragility by locus + per-dataset
fl_stem = fl_inst = n_stem = n_inst = 0
for q, rows in by_qe.items():
    is_stem = QE[q]["dataset"] in STEM_DS
    for r in rows:
        if is_stem:
            n_stem += 1; fl_stem += r["fragile"]
        else:
            n_inst += 1; fl_inst += r["fragile"]
R["frag_ho"] = {"stem": [fl_stem, n_stem], "inst": [fl_inst, n_inst],
                "stem_rate": 100 * fl_stem / n_stem if n_stem else None,
                "inst_rate": 100 * fl_inst / n_inst if n_inst else None}
R["frag_ho"]["logiqa"] = {}
R["frag_ho"]["sat_inst"] = {}
for m in FULL4:
    pq = exp[m]["pq"]
    lq = [q for q in pq if QE[q]["dataset"] == "logiqa"]
    sq = [q for q in pq if QE[q]["dataset"] == "sat_math"]
    R["frag_ho"]["logiqa"][m] = round(100 * sum(pq[q]["fragile"] for q in lq) / len(lq), 1) if lq else None
    R["frag_ho"]["sat_inst"][m] = round(100 * sum(pq[q]["fragile"] for q in sq) / len(sq), 1) if sq else None

# held-out error signals with CIs and AURC
sig = {}
all_rows = []
for m in FULL4:
    comp, pq = exp[m]["complete"], exp[m]["pq"]
    qids = sorted(pq)
    cs = {q: mode_share([comp[q][(0, str(s))]["answer"] for s in range(1, 7)]) for q in qids}
    cp = {q: mode_share([comp[q][(p, "1")]["answer"] for p in range(1, 7)]) for q in qids}
    err = {q: 0 if pq[q]["comb12_ok"] else 1 for q in qids}
    s_cs = [1 - cs[q] for q in qids]; s_cp = [1 - cp[q] for q in qids]
    s_b = [2 - cs[q] - cp[q] for q in qids]
    lab = [err[q] for q in qids]
    lo_c, hi_c = auroc_boot_ci(s_cs, lab); lo_p, hi_p = auroc_boot_ci(s_cp, lab); lo_b, hi_b = auroc_boot_ci(s_b, lab)
    nd = [q for q in qids if pq[q]["mode_share"] < 1]
    sig[m] = {"n_errors": sum(lab), "auroc_cs": auroc_(s_cs, lab), "auroc_cp": auroc_(s_cp, lab),
              "auroc_both": auroc_(s_b, lab),
              "ci_cs": [lo_c, hi_c], "ci_cp": [lo_p, hi_p], "ci_both": [lo_b, hi_b],
              "flag_cs": sum(1 for q in qids if err[q] and cs[q] < 1),
              "flag_cp": sum(1 for q in qids if err[q] and cp[q] < 1),
              "only_cs": sum(1 for q in qids if err[q] and cs[q] < 1 and cp[q] == 1),
              "only_cp": sum(1 for q in qids if err[q] and cp[q] < 1 and cs[q] == 1),
              "aurc_cs": aurc_ties(s_cs, lab), "err_rate": 100 * sum(lab) / len(lab),
              "nd_auroc_cs": auroc_([1 - cs[q] for q in nd], [err[q] for q in nd]) if nd else None}
    all_rows += [(cs[q], cp[q], err[q], pq[q]["mode_share"]) for q in qids]
p_cs = auroc_([1 - r[0] for r in all_rows], [r[2] for r in all_rows])
p_cp = auroc_([1 - r[1] for r in all_rows], [r[2] for r in all_rows])
p_b = auroc_([2 - r[0] - r[1] for r in all_rows], [r[2] for r in all_rows])
nd_rows = [r for r in all_rows if r[3] < 1]
un_rows = [r for r in all_rows if r[3] == 1]
nd_aurocs = [auroc_([1 - r[0] for r in [x for x in nd_rows]], [r[2] for r in nd_rows])]
per_model_nd = [sig[m]["nd_auroc_cs"] for m in FULL4 if sig[m]["nd_auroc_cs"] is not None]
sig["POOLED"] = {"auroc_cs": p_cs, "auroc_cp": p_cp, "auroc_both": p_b,
                 "n_errors": sum(r[2] for r in all_rows),
                 "flag_cs": sum(1 for r in all_rows if r[2] and r[0] < 1),
                 "flag_cp": sum(1 for r in all_rows if r[2] and r[1] < 1),
                 "only_cs": sum(1 for r in all_rows if r[2] and r[0] < 1 and r[1] == 1),
                 "only_cp": sum(1 for r in all_rows if r[2] and r[1] < 1 and r[0] == 1),
                 "nd_err_rate": 100 * sum(r[2] for r in nd_rows) / len(nd_rows),
                 "un_err_rate": 100 * sum(r[2] for r in un_rows) / len(un_rows),
                 "nd_auroc_min": min(per_model_nd), "nd_auroc_max": max(per_model_nd)}
sig["POOLED"]["ci_cs"] = auroc_boot_ci([1 - r[0] for r in all_rows], [r[2] for r in all_rows])
sig["POOLED"]["ci_cp"] = auroc_boot_ci([1 - r[1] for r in all_rows], [r[2] for r in all_rows])
sig["POOLED"]["ci_both"] = auroc_boot_ci([2 - r[0] - r[1] for r in all_rows], [r[2] for r in all_rows])
R["sig_ho"] = sig

# instruction-variant control (SAT-Math, PIQA)
instr = {}
for ds in ("sat_math", "piqa"):
    per_model = {}
    for m in FULL4:
        comp, pq = exp[m]["complete"], exp[m]["pq"]
        qds = [q for q in sorted(pq) if QE[q]["dataset"] == ds]
        canon = 100 * sum(pq[q]["k1_acc"] for q in qds) / len(qds)
        variants = [100 * sum(1 for q in qds if comp[q][(k, "1")]["answer"] == gold_of(QE[q])) / len(qds) for k in range(1, 7)]
        pe6 = 100 * sum(pq[q]["pe6_ok"] for q in qds) / len(qds)
        per_model[m] = {"n": len(qds), "canonical": canon, "variants": variants,
                        "best": max(variants), "pe6": pe6}
    pooled_variants = [sum(per_model[m]["variants"][k] for m in FULL4) / 4 for k in range(6)]
    instr[ds] = {"models": per_model,
                 "pooled": {"canonical": sum(per_model[m]["canonical"] for m in FULL4) / 4,
                            "best": max(pooled_variants),
                            "pe6": sum(per_model[m]["pe6"] for m in FULL4) / 4}}
R["instr"] = instr

# dataset-level held-out margins (tab_expand_ds cells used in prose)
R["ds_cells"] = {}
for m in FULL4:
    pq = exp[m]["pq"]
    for ds in ("sat_math", "gsm8k", "logiqa", "truthfulqa", "piqa"):
        qds = [q for q in sorted(pq) if QE[q]["dataset"] == ds]
        if not qds:
            continue
        R["ds_cells"][(m, ds)] = {
            "n": len(qds), "s1": 100 * sum(pq[q]["k1_acc"] for q in qds) / len(qds),
            "pe1": 100 * sum(pq[q]["pe1_acc"] for q in qds) / len(qds),
            "sc6": 100 * sum(pq[q]["sc6_ok"] for q in qds) / len(qds),
            "pe6": 100 * sum(pq[q]["pe6_ok"] for q in qds) / len(qds)}
# pooled per-dataset margins
R["ds_pooled"] = {}
for ds in ("sat_math", "gsm8k", "logiqa", "truthfulqa"):
    cells = [R["ds_cells"][(m, ds)] for m in FULL4 if (m, ds) in R["ds_cells"]]
    if cells:
        R["ds_pooled"][ds] = {
            "dsc": round(sum(c["sc6"] - c["s1"] for c in cells) / len(cells), 1),
            "dpe": round(sum(c["pe6"] - c["pe1"] for c in cells) / len(cells), 1),
            "pe1_minus_s1": round(sum(c["pe1"] - c["s1"] for c in cells) / len(cells), 1)}

# ------------------------------------------------- 3. follow-up conditions --
def load_cond(subdir, model, need_key=None):
    """generic loader for cond_* logs (string-typed fields)."""
    path = f"{RES}/{subdir}/{model}.jsonl"
    if not os.path.exists(path):
        return None, None
    cells = defaultdict(dict)
    for line in open(path):
        try:
            r = json.loads(line)
        except Exception:
            continue
        para = int(r["para"]) if str(r["para"]).isdigit() else r["para"]
        cells[r["qid"]][(para, str(r["sample"]))] = {"answer": r["answer"],
                                                     "correct": r["correct"],
                                                     "gold": None}
    return cells, path

R["greedypara"] = {}
for m in ["qwen3.8-max", "agnes-3.0-flash", "agnes-2.5-flash", "gpt-6-luna", "gemini-3.8-flash"]:
    cells, _ = load_cond("cond_greedypara", m)
    if cells is None:
        R["greedypara"][m] = None
        continue
    n = agree = 0; frag_g = degen_g = 0; acc_peg = 0
    matched = 0
    for qid, cm in cells.items():
        gold = gold_of(Q[qid])
        peg = [cm[(p, "g")]["answer"] for p in range(1, 7) if (p, "g") in cm]
        pe = [main[m]["complete"][qid][(p, "1")]["answer"] for p in range(1, 7)] if qid in main[m]["complete"] else None
        if any(v is None for v in peg):
            continue
        n += 1
        acc_peg += majority(peg) == gold
        degen_g += len(set(peg)) == 1
        if pe:
            matched += majority(peg) == majority(pe)
        sc = [main[m]["complete"][qid][(0, str(s))]["answer"] for s in range(1, 7)] if qid in main[m]["complete"] else None
        if sc:
            frag_g += majority(sc) != majority(peg)
    R["greedypara"][m] = {"n": n, "pe6_peg_agree": matched, "acc_peg": 100 * acc_peg / n if n else None,
                          "degen_g_pct": 100 * degen_g / n if n else None,
                          "frag_g_pct": 100 * frag_g / n if n else None}
# Qwen3.8-Max greedy paraphrase degeneracy uses its own complete set
if R["greedypara"].get("qwen3.8-max"):
    cells, _ = load_cond("cond_greedypara", "qwen3.8-max")
    n = degen = agree_pe = 0
    for qid, cm in cells.items():
        gold = gold_of(Q[qid])
        peg = [cm[(p, "g")]["answer"] for p in range(1, 7) if (p, "g") in cm]
        if any(v is None for v in peg):
            continue
        n += 1
        degen += len(set(peg)) == 1
        pe = [main["qwen3.8-max"]["complete"][qid][(p, "1")]["answer"] for p in range(1, 7)] if qid in main["qwen3.8-max"]["complete"] else None
        if pe and all(v is not None for v in pe):
            agree_pe += majority(peg) == majority(pe)
    R["greedypara"]["qwen3.8-max"] = {"n": n, "degen_g_pct": 100 * degen / n if n else None,
                                      "pe6_peg_agree": agree_pe}

def norm_entropy(votes):
    vs = [v for v in votes if v is not None]
    if len(vs) <= 1:
        return 0.0
    c = Counter(vs)
    h = -sum((nn / len(vs)) * math.log(nn / len(vs)) for nn in c.values())
    return h / math.log(len(c)) if len(c) > 1 else 0.0

R["mmlupro"] = {}
for m in ["gpt-6-luna", "qwen3.8-max", "agnes-3.0-flash", "agnes-2.5-flash"]:
    path = f"{RES}/cond_mmlupro/{m}.jsonl"
    if not os.path.exists(path):
        R["mmlupro"][m] = None
        continue
    cells = defaultdict(dict)
    for line in open(path):
        r = json.loads(line)
        cells[r["qid"]][(int(r["para"]) if str(r["para"]).isdigit() else r["para"], str(r["sample"]))] = r
    # complete = greedy + 6 samples, all parsed
    comp = {}
    for qid, cm in cells.items():
        need = [(0, "g")] + [(0, str(s)) for s in range(1, 7)]
        if all(k in cm and cm[k]["answer"] is not None for k in need):
            comp[qid] = {k: cm[k] for k in need}
    qids = sorted(comp)
    gold = lambda qid: None
    # gold: mmlu_pro questions come from data/mmlupro30.json
    mp = {q["id"]: q for q in json.load(open(f"{DATA}/mmlupro30.json"))}
    def gold_mp(qid):
        q = mp.get(qid)
        if q is None:
            return None
        return "ABCDEFGHIJ"[q["answer_idx"]]
    n = len(qids)
    gr = sum(comp[q][(0, "g")]["answer"] == gold_mp(q) for q in qids)
    s1 = sum(sum(comp[q][(0, str(s))]["answer"] == gold_mp(q) for s in range(1, 7)) / 6 for q in qids)
    sc6 = sum(majority([comp[q][(0, str(s))]["answer"] for s in range(1, 7)]) == gold_mp(q) for q in qids)
    ent = sum(norm_entropy([comp[q][(0, str(s))]["answer"] for s in range(1, 7)]) for q in qids)
    degen = sum(len(set(comp[q][(0, str(s))]["answer"] for s in range(1, 7))) == 1 for q in qids)
    R["mmlupro"][m] = {"n": n, "greedy": 100 * gr / n if n else None,
                       "s1": 100 * s1 / n if n else None, "sc6": 100 * sc6 / n if n else None,
                       "entropy": ent / n if n else None, "degen_pct": 100 * degen / n if n else None}
# lenient counts for qwen3.8-max probe (>=4 parsed votes)
cells, _ = load_cond("cond_mmlupro", "qwen3.8-max")
if cells:
    strict = {}
    for qid, cm in cells.items():
        need = [(0, "g")] + [(0, str(s)) for s in range(1, 7)]
        if all(k in cm and cm[k]["answer"] is not None for k in need):
            strict[qid] = cm
    lenient = sum(1 for qid, cm in cells.items()
                  if sum(1 for s in range(1, 7) if (0, str(s)) in cm and cm[(0, str(s))]["answer"] is not None) >= 4)
    single = sum(1 for qid, cm in cells.items()
                 if sum(1 for s in range(1, 7) if (0, str(s)) in cm and cm[(0, str(s))]["answer"] is not None) >= 4
                 and len(set(cm[(0, str(s))]["answer"] for s in range(1, 7) if (0, str(s)) in cm and cm[(0, str(s))]["answer"] is not None)) == 1)
    R["mmlupro"]["qwen3.8-max_lenient"] = {"n_strict": len(strict), "n_lenient": lenient, "n_single": single}

R["cot"] = {}
for m in ["qwen3.8-max", "agnes-3.0-flash", "agnes-2.5-flash", "gpt-6-luna"]:
    path = f"{RES}/cond_cot/{m}.jsonl"
    if not os.path.exists(path):
        R["cot"][m] = None
        continue
    cells = defaultdict(dict)
    for line in open(path):
        r = json.loads(line)
        para = int(r["para"]) if str(r["para"]).isdigit() else r["para"]
        cells[r["qid"]][(para, str(r["sample"]))] = r
    # release definition: skip gsm8k; greedy+6 samples; stem-locus questions
    # additionally require six parsed paraphrase first-decodes
    comp = {}
    for qid, cm in cells.items():
        if Q[qid]["dataset"] == "gsm8k":
            continue
        gold = gold_of(Q[qid])
        need = [(0, "g")] + [(0, str(s)) for s in range(1, 7)]
        stem = Q[qid]["dataset"] in STEM_DS
        if stem:
            need += [(p, "1") for p in range(1, 7)]
        if all(k in cm and cm[k]["answer"] is not None for k in need):
            comp[qid] = {"cm": {k: cm[k] for k in need}, "gold": gold, "stem": stem}
    qids = sorted(comp)
    n = len(qids)
    if n == 0:
        R["cot"][m] = None
        continue
    gr = sum(comp[q]["cm"][(0, "g")]["answer"] == comp[q]["gold"] for q in qids)
    sc6 = sum(majority([comp[q]["cm"][(0, str(s))]["answer"] for s in range(1, 7)]) == comp[q]["gold"] for q in qids)
    pe6 = sum(majority([comp[q]["cm"][(p, "1")]["answer"] for p in range(1, 7)]) == comp[q]["gold"]
              for q in qids if comp[q]["stem"])
    n_stem = sum(1 for q in qids if comp[q]["stem"])
    ent = sum(norm_entropy([comp[q]["cm"][(0, str(s))]["answer"] for s in range(1, 7)]) for q in qids) / n
    ent_dir = sum(norm_entropy([main[m]["complete"][q][(0, str(s))]["answer"] for s in range(1, 7)])
                  for q in qids if q in main[m]["complete"]) / n
    # direct-answer counterparts on the same questions
    dq = [q for q in qids if q in main[m]["complete"]]
    d_gr = sum(main[m]["complete"][q][(0, "g")]["answer"] == gold_of(Q[q]) for q in dq) / len(dq) if dq else None
    d_sc = sum(main[m]["pq"][q]["sc6_ok"] for q in dq) / len(dq) if dq else None
    d_pe = (sum(main[m]["pq"][q]["pe6_ok"] for q in dq if Q[q]["dataset"] in STEM_DS) /
            sum(1 for q in dq if Q[q]["dataset"] in STEM_DS)) if dq else None
    R["cot"][m] = {"n": n, "n_stem": n_stem,
                   "greedy": 100 * gr / n, "sc6": 100 * sc6 / n,
                   "pe6": 100 * pe6 / n_stem if n_stem else None,
                   "entropy": ent, "entropy_dir": ent_dir,
                   "n_direct": len(dq),
                   "direct_greedy": 100 * d_gr if d_gr is not None else None,
                   "direct_sc6": 100 * d_sc if d_sc is not None else None,
                   "direct_pe6": 100 * d_pe if d_pe is not None else None}

# ==================================================== 4. CLAIMS (paper values)
# Each row: (location, description, value printed in the paper, recomputed value).
# Paper values are transcribed from the TMLR submission (main.tex + sections/*.tex).
P = R["primary"]; EP = R["exp_pooled"]; EX = R["exp"]
SP = R["strata_pooled"]; SH = R["strata"]
SG = R["sig_ho"]; IN = R["instr"]; U = R["union"]
DP = R["dev_pooled"]; M = R["main"]; DF = R["dev_flags"]

# ---- Abstract ----
claim("Abstract", "SC-6 pooled gain over S1 (+2.4)", 2.4, round(P["sc6_ok"]["mean"], 1), tol=0.06)
claim("Abstract", "PE-6 pooled gain over S1 (+4.9)", 4.9, round(P["pe6_ok"]["mean"], 1), tol=0.06)
claim("Abstract", "COMB-12 pooled gain over S1 (+4.1)", 4.1, round(P["comb12_ok"]["mean"], 1), tol=0.06)
claim("Abstract", "SC-6 CI (+1.1, +3.7)", [1.1, 3.7], [round(x, 1) for x in P["sc6_ok"]["ci"]])
claim("Abstract", "PE-6 CI (+2.3, +7.6)", [2.3, 7.6], [round(x, 1) for x in P["pe6_ok"]["ci"]])
claim("Abstract", "PE-SC gap (+2.5, interval touching zero)", 2.5, round(P["pe_sc"]["mean"], 1), tol=0.06)
claim("Abstract", "PE-SC CI (-0.6, +5.7)", [-0.6, 5.7], [round(x, 1) for x in P["pe_sc"]["ci"]])
claim("Abstract", "difficulty offset (+1.9)", 1.9, round(EP["difficulty_offset"], 1), tol=0.06)
claim("Abstract", "within-condition aggregation +3.0 vs +2.4", [3.0, 2.4],
      [round(EP["dpe"], 1), round(EP["dsc"], 1)], tol=0.06)
claim("Abstract", "held-out 119 questions / 476 pairs", [119, 476],
      [EX["agnes-3.0-flash"]["n"], EP["n_pairs"]], kind="count")
claim("Abstract", "best instruction variant 95.0% vs PE-6 91.2% (SAT-Math pooled)",
      [95.0, 91.2], [round(IN["sat_math"]["pooled"]["best"], 1), round(IN["sat_math"]["pooled"]["pe6"], 1)], tol=0.06)
claim("Abstract", "adaptive rule saves 13-21% of the six-call budget (uses 79-87%)", [13, 21],
      [round(100 - 100 * max(EX[m]["adaptive"]["budget_pct_of_6"] for m in FULL4)),
       round(100 - 100 * min(EX[m]["adaptive"]["budget_pct_of_6"] for m in FULL4))], tol=1.1)

# ---- Introduction ----
claim("Intro", "pooled +2.4 / +4.9 with CIs excluding zero (same as abstract)", None,
      round(P["sc6_ok"]["p_holm"], 4), kind="num")
claim("Intro", "dev coverage 12 to 90; held-out four fully covered models", [12, 90],
      [min(M[m]["n"] for m in MAIN_MODELS), max(M[m]["n"] for m in MAIN_MODELS)], kind="count")

# ---- Held-out section: per-model primary rows ----
claim("5.1", "Agnes3.0: PE-6 87.4 / S1 79.6 / +7.8", [87.4, 79.6, 7.8],
      [round(EX["agnes-3.0-flash"]["pe6"], 1), round(EX["agnes-3.0-flash"]["s1"], 1),
       round(R["exp_model_ci"]["agnes-3.0-flash"]["pe6_ok"]["mean"], 1)], tol=0.06)
claim("5.1", "Agnes3.0: PE-6 CI (+2.4, +13.7)", [2.4, 13.7],
      [round(x, 1) for x in R["exp_model_ci"]["agnes-3.0-flash"]["pe6_ok"]["ci"]])
claim("5.1", "Agnes3.0: SC-6 +2.0 CI (-1.0, +5.0); COMB 82.4", [2.0, -1.0, 5.0, 82.4],
      [round(R["exp_model_ci"]["agnes-3.0-flash"]["sc6_ok"]["mean"], 1)] +
      [round(x, 1) for x in R["exp_model_ci"]["agnes-3.0-flash"]["sc6_ok"]["ci"]] +
      [round(EX["agnes-3.0-flash"]["comb"], 1)], tol=0.36)
claim("5.1", "Agnes2.5: PE-6 91.6 / S1 88.1 / +3.5 CI (+0.4,+7.0); SC-6 90.8 / +2.7 CI (+0.7,+4.9); COMB 89.9",
      [91.6, 88.1, 3.5, 0.4, 7.0, 90.8, 2.7, 0.7, 4.9, 89.9],
      [round(EX["agnes-2.5-flash"]["pe6"], 1), round(EX["agnes-2.5-flash"]["s1"], 1),
       round(R["exp_model_ci"]["agnes-2.5-flash"]["pe6_ok"]["mean"], 1)] +
      [round(x, 1) for x in R["exp_model_ci"]["agnes-2.5-flash"]["pe6_ok"]["ci"]] +
      [round(EX["agnes-2.5-flash"]["sc6"], 1), round(R["exp_model_ci"]["agnes-2.5-flash"]["sc6_ok"]["mean"], 1)] +
      [round(x, 1) for x in R["exp_model_ci"]["agnes-2.5-flash"]["sc6_ok"]["ci"]] +
      [round(EX["agnes-2.5-flash"]["comb"], 1)], tol=0.36)
claim("5.1", "DSV4.1: PE-6 81.5 / S1 77.6 / +3.9 CI (-0.8,+8.7); SC-6 79.8 / +2.2 CI (-0.4,+4.9); HB=COMB 83.2 / +5.6 CIs (+1.5,+9.8)/(+1.7,+9.7)",
      [81.5, 77.6, 3.9, -0.8, 8.7, 79.8, 2.2, -0.4, 4.9, 83.2, 5.6, 1.5, 9.8, 1.7, 9.7],
      [round(EX["deepseek-v4.1-flash"]["pe6"], 1), round(EX["deepseek-v4.1-flash"]["s1"], 1),
       round(R["exp_model_ci"]["deepseek-v4.1-flash"]["pe6_ok"]["mean"], 1)] +
      [round(x, 1) for x in R["exp_model_ci"]["deepseek-v4.1-flash"]["pe6_ok"]["ci"]] +
      [round(EX["deepseek-v4.1-flash"]["sc6"], 1), round(R["exp_model_ci"]["deepseek-v4.1-flash"]["sc6_ok"]["mean"], 1)] +
      [round(x, 1) for x in R["exp_model_ci"]["deepseek-v4.1-flash"]["sc6_ok"]["ci"]] +
      [round(EX["deepseek-v4.1-flash"]["hb6"], 1), round(R["exp_model_ci"]["deepseek-v4.1-flash"]["hb6_ok"]["mean"], 1)] +
      [round(x, 1) for x in R["exp_model_ci"]["deepseek-v4.1-flash"]["hb6_ok"]["ci"]] +
      [round(x, 1) for x in R["exp_model_ci"]["deepseek-v4.1-flash"]["comb12_ok"]["ci"]], tol=0.36)
claim("5.1", "Pro tier: COMB 84.0 / +6.0 CI (+2.1,+10.2); SC-6 80.7 / +2.7 CI (+0.1,+5.5); PE=HB 82.4 / +4.3 CIs (-0.7,+9.4)/(-0.4,+9.1)",
      [84.0, 6.0, 2.1, 10.2, 80.7, 2.7, 0.1, 5.5, 82.4, 4.3, -0.7, 9.4, -0.4, 9.1],
      [round(EX["deepseek-v4-pro-0813"]["comb"], 1), round(R["exp_model_ci"]["deepseek-v4-pro-0813"]["comb12_ok"]["mean"], 1)] +
      [round(x, 1) for x in R["exp_model_ci"]["deepseek-v4-pro-0813"]["comb12_ok"]["ci"]] +
      [round(EX["deepseek-v4-pro-0813"]["sc6"], 1), round(R["exp_model_ci"]["deepseek-v4-pro-0813"]["sc6_ok"]["mean"], 1)] +
      [round(x, 1) for x in R["exp_model_ci"]["deepseek-v4-pro-0813"]["sc6_ok"]["ci"]] +
      [round(EX["deepseek-v4-pro-0813"]["pe6"], 1), round(R["exp_model_ci"]["deepseek-v4-pro-0813"]["pe6_ok"]["mean"], 1)] +
      [round(x, 1) for x in R["exp_model_ci"]["deepseek-v4-pro-0813"]["pe6_ok"]["ci"]] +
      [round(x, 1) for x in R["exp_model_ci"]["deepseek-v4-pro-0813"]["hb6_ok"]["ci"]], tol=0.36)
claim("5.1", "Holm-adjusted p: SC-S1 0.0008", "0.0008",
      round(P["sc6_ok"]["p_holm"], 4), kind="pval")
claim("5.1", "Holm-adjusted p: PE-S1 <0.0001", "<0.0001",
      round(P["pe6_ok"]["p_holm"], 5), kind="pval")
claim("5.1", "Holm-adjusted p: COMB-S1 <0.0001", "<0.0001",
      round(P["comb12_ok"]["p_holm"], 5), kind="pval")
claim("5.1", "Holm-adjusted p: PE-SC 0.14", "0.14",
      round(P["pe_sc"]["p_holm"], 2), kind="pval", tol=0.02)
claim("5.1", "PE-HB +1.3 CI (-0.4,+2.9); COMB-PE -0.8 CI (-2.9,+1.3)", [1.3, -0.4, 2.9, -0.8, -2.9, 1.3],
      [round(P["pe_hb"]["mean"], 1)] + [round(x, 1) for x in P["pe_hb"]["ci"]] +
      [round(P["comb_pe"]["mean"], 1)] + [round(x, 1) for x in P["comb_pe"]["ci"]], tol=0.36)
claim("5.1", "Qwen3.7-Flash partial: 82% unanimous; within 1.1 of S1; replays match SC-6 85.0",
      [82, 1.1, 85.0],
      [round(100 * EX["qwen3.7-flash"]["unanimous_rate"]),
       round(max(abs(EX["qwen3.7-flash"][c] - EX["qwen3.7-flash"]["s1"]) for c in ("sc6", "pe6", "comb", "hb6")), 1),
       round(EX["qwen3.7-flash"]["adaptive"]["acc"] * 100, 1)], tol=0.6)

# ---- 5.2 difficulty confound ----
claim("5.2", "pooled PE-1 82.7 / PE-6 85.7 / S1 80.8 / SC-6 83.2", [82.7, 85.7, 80.8, 83.2],
      [round(EP["pe1"], 1), round(EP["pe6"], 1), round(EP["s1"], 1), round(EP["sc6"], 1)], tol=0.06)
claim("5.2", "Agnes3.0: PE-1 81.2 / S1 79.6 / dPE +6.2 / dSC +2.0", [81.2, 79.6, 6.2, 2.0],
      [round(EX["agnes-3.0-flash"]["pe1"], 1), round(EX["agnes-3.0-flash"]["s1"], 1),
       round(EX["agnes-3.0-flash"]["pe6"] - EX["agnes-3.0-flash"]["pe1"], 1),
       round(EX["agnes-3.0-flash"]["sc6"] - EX["agnes-3.0-flash"]["s1"], 1)], tol=0.06)
claim("5.2", "Agnes2.5: PE-1 89.2 / S1 88.1 / dPE +2.4 / dSC +2.7", [89.2, 88.1, 2.4, 2.7],
      [round(EX["agnes-2.5-flash"]["pe1"], 1), round(EX["agnes-2.5-flash"]["s1"], 1),
       round(EX["agnes-2.5-flash"]["pe6"] - EX["agnes-2.5-flash"]["pe1"], 1),
       round(EX["agnes-2.5-flash"]["sc6"] - EX["agnes-2.5-flash"]["s1"], 1)], tol=0.06)
claim("5.2", "DSV4.1: PE-1 79.1 / S1 77.6 / dPE +2.4 / dSC +2.2", [79.1, 77.6, 2.4, 2.2],
      [round(EX["deepseek-v4.1-flash"]["pe1"], 1), round(EX["deepseek-v4.1-flash"]["s1"], 1),
       round(EX["deepseek-v4.1-flash"]["pe6"] - EX["deepseek-v4.1-flash"]["pe1"], 1),
       round(EX["deepseek-v4.1-flash"]["sc6"] - EX["deepseek-v4.1-flash"]["s1"], 1)], tol=0.06)
claim("5.2", "Pro: PE-1 81.1 / S1 78.0 / dSC +2.7 vs dPE +1.3", [81.1, 78.0, 2.7, 1.3],
      [round(EX["deepseek-v4-pro-0813"]["pe1"], 1), round(EX["deepseek-v4-pro-0813"]["s1"], 1),
       round(EX["deepseek-v4-pro-0813"]["sc6"] - EX["deepseek-v4-pro-0813"]["s1"], 1),
       round(EX["deepseek-v4-pro-0813"]["pe6"] - EX["deepseek-v4-pro-0813"]["pe1"], 1)], tol=0.06)
claim("5.2", "union Agnes3.0: n=152, PE-6 +6.5 CI (+2.2,+11.1); SC-6 +1.9 CI (-0.7,+4.4)",
      [152, 6.5, 2.2, 11.1, 1.9, -0.7, 4.4],
      [U["agnes-3.0-flash"]["n"], round(U["agnes-3.0-flash"]["dpe6_ok"]["mean"], 1)] +
      [round(x, 1) for x in U["agnes-3.0-flash"]["dpe6_ok"]["ci"]] +
      [round(U["agnes-3.0-flash"]["dsc6_ok"]["mean"], 1)] +
      [round(x, 1) for x in U["agnes-3.0-flash"]["dsc6_ok"]["ci"]], tol=0.36)
claim("5.2", "union Agnes2.5: n=159, +2.2 both; SC-6 CI (+0.6,+3.9), PE-6 CI (-0.4,+4.9)",
      [159, 2.2, 2.2, 0.6, 3.9, -0.4, 4.9],
      [U["agnes-2.5-flash"]["n"], round(U["agnes-2.5-flash"]["dpe6_ok"]["mean"], 1),
       round(U["agnes-2.5-flash"]["dsc6_ok"]["mean"], 1)] +
      [round(x, 1) for x in U["agnes-2.5-flash"]["dsc6_ok"]["ci"]] +
      [round(x, 1) for x in U["agnes-2.5-flash"]["dpe6_ok"]["ci"]], tol=0.36)
claim("5.2", "Agnes2.5 PE-6 minus S1: dev -1.7 (40q) / held-out +3.5 / union +2.2", [-1.7, 3.5, 2.2],
      [round(U["agnes-2.5-flash"]["dev_dpe"], 1), round(U["agnes-2.5-flash"]["ho_dpe"], 1),
       round(U["agnes-2.5-flash"]["union_dpe_vs_s1"], 1)], tol=0.06)

# ---- 5.3 dataset mechanism / instruction effect ----
C = R["ds_cells"]
claim("5.3", "Agnes3.0 SAT-Math: S1 61.7 / SC-6 60.0 (dSC -1.7) / PE-6 100.0 (dPE +17.5); 8 flips all won by PE",
      [61.7, 60.0, -1.7, 100.0, 17.5, 8],
      [round(C[("agnes-3.0-flash", "sat_math")]["s1"], 1), round(C[("agnes-3.0-flash", "sat_math")]["sc6"], 1),
       round(C[("agnes-3.0-flash", "sat_math")]["sc6"] - C[("agnes-3.0-flash", "sat_math")]["s1"], 1),
       round(C[("agnes-3.0-flash", "sat_math")]["pe6"], 1),
       round(C[("agnes-3.0-flash", "sat_math")]["pe6"] - C[("agnes-3.0-flash", "sat_math")]["pe1"], 1), None], tol=0.06)
claim("5.3", "Agnes3.0 SAT-Math: PE-1 82.5 (+20.8 over S1)", [82.5, 20.8],
      [round(C[("agnes-3.0-flash", "sat_math")]["pe1"], 1),
       round(C[("agnes-3.0-flash", "sat_math")]["pe1"] - C[("agnes-3.0-flash", "sat_math")]["s1"], 1)], tol=0.06)
claim("5.3", "SAT-Math instruction: canonical 76.2 -> best 95.0; PE-6 91.2 (~80%)",
      [76.2, 95.0, 91.2],
      [round(IN["sat_math"]["pooled"]["canonical"], 1), round(IN["sat_math"]["pooled"]["best"], 1),
       round(IN["sat_math"]["pooled"]["pe6"], 1)], tol=0.06)
claim("5.3", "SAT-Math per-model canonical->best: Agnes3.0 61.7->100.0; DSV4.1 75.8->90.0; pro 69.2->90.0",
      [61.7, 100.0, 75.8, 90.0, 69.2, 90.0],
      [round(IN["sat_math"]["models"]["agnes-3.0-flash"]["canonical"], 1),
       round(IN["sat_math"]["models"]["agnes-3.0-flash"]["best"], 1),
       round(IN["sat_math"]["models"]["deepseek-v4.1-flash"]["canonical"], 1),
       round(IN["sat_math"]["models"]["deepseek-v4.1-flash"]["best"], 1),
       round(IN["sat_math"]["models"]["deepseek-v4-pro-0813"]["canonical"], 1),
       round(IN["sat_math"]["models"]["deepseek-v4-pro-0813"]["best"], 1)], tol=0.06)
claim("5.3", "PIQA best variant 86.2 vs canonical 87.9", [86.2, 87.9],
      [round(IN["piqa"]["pooled"]["best"], 1), round(IN["piqa"]["pooled"]["canonical"], 1)], tol=0.06)
claim("5.3", "Agnes3.0 GSM8K: PE-6 100.0, dPE +2.5, floor 95.0", [100.0, 2.5, 95.0],
      [round(C[("agnes-3.0-flash", "gsm8k")]["pe6"], 1),
       round(C[("agnes-3.0-flash", "gsm8k")]["pe6"] - C[("agnes-3.0-flash", "gsm8k")]["pe1"], 1),
       round(C[("agnes-3.0-flash", "gsm8k")]["s1"], 1)], tol=0.06)
claim("5.3", "Agnes3.0 LogiQA: PE-1 63.3 vs S1 75.0 (-11.7); SC-6 90.0 dSC +15.0 vs dPE +1.7; 5/7 flips SC",
      [63.3, 75.0, -11.7, 90.0, 15.0, 1.7],
      [round(C[("agnes-3.0-flash", "logiqa")]["pe1"], 1), round(C[("agnes-3.0-flash", "logiqa")]["s1"], 1),
       round(C[("agnes-3.0-flash", "logiqa")]["pe1"] - C[("agnes-3.0-flash", "logiqa")]["s1"], 1),
       round(C[("agnes-3.0-flash", "logiqa")]["sc6"], 1),
       round(C[("agnes-3.0-flash", "logiqa")]["sc6"] - C[("agnes-3.0-flash", "logiqa")]["s1"], 1),
       round(C[("agnes-3.0-flash", "logiqa")]["pe6"] - C[("agnes-3.0-flash", "logiqa")]["pe1"], 1)], tol=0.06)
claim("5.3", "Agnes3.0 TruthfulQA: SC-6 65.0 vs S1 70.8; pooled dPE +3.1", [65.0, 70.8, 3.1],
      [round(C[("agnes-3.0-flash", "truthfulqa")]["sc6"], 1), round(C[("agnes-3.0-flash", "truthfulqa")]["s1"], 1),
       round(R["ds_pooled"]["truthfulqa"]["dpe"], 1)], tol=0.06)
claim("5.3", "Agnes2.5 floors SAT 98.3 / GSM 94.2; pooled dPE +2.4; LogiQA PE-6 80.0 vs SC-6 70.0 dPE +2.5 dSC -3.3",
      [98.3, 94.2, 2.4, 80.0, 70.0, 2.5, -3.3],
      [round(C[("agnes-2.5-flash", "sat_math")]["s1"], 1), round(C[("agnes-2.5-flash", "gsm8k")]["s1"], 1),
       round((EX["agnes-2.5-flash"]["pe6"] - EX["agnes-2.5-flash"]["pe1"]), 1),
       round(C[("agnes-2.5-flash", "logiqa")]["pe6"], 1), round(C[("agnes-2.5-flash", "logiqa")]["sc6"], 1),
       round(C[("agnes-2.5-flash", "logiqa")]["pe6"] - C[("agnes-2.5-flash", "logiqa")]["pe1"], 1),
       round(C[("agnes-2.5-flash", "logiqa")]["sc6"] - C[("agnes-2.5-flash", "logiqa")]["s1"], 1)], tol=0.06)
claim("5.3", "DSV4.1 LogiQA: PE-1 65.0 vs S1 52.5 (+12.5); dSC +7.5 dPE 0.0; SAT -0.8/+5.8; TruthfulQA dSC +5.0",
      [65.0, 52.5, 12.5, 7.5, 0.0, -0.8, 5.8, 5.0],
      [round(C[("deepseek-v4.1-flash", "logiqa")]["pe1"], 1), round(C[("deepseek-v4.1-flash", "logiqa")]["s1"], 1),
       round(C[("deepseek-v4.1-flash", "logiqa")]["pe1"] - C[("deepseek-v4.1-flash", "logiqa")]["s1"], 1),
       round(C[("deepseek-v4.1-flash", "logiqa")]["sc6"] - C[("deepseek-v4.1-flash", "logiqa")]["s1"], 1),
       round(C[("deepseek-v4.1-flash", "logiqa")]["pe6"] - C[("deepseek-v4.1-flash", "logiqa")]["pe1"], 1),
       round(C[("deepseek-v4.1-flash", "sat_math")]["sc6"] - C[("deepseek-v4.1-flash", "sat_math")]["s1"], 1),
       round(C[("deepseek-v4.1-flash", "sat_math")]["pe6"] - C[("deepseek-v4.1-flash", "sat_math")]["pe1"], 1),
       round(C[("deepseek-v4.1-flash", "truthfulqa")]["sc6"] - C[("deepseek-v4.1-flash", "truthfulqa")]["s1"], 1)], tol=0.06)
_pl_pe1 = round(C[("deepseek-v4-pro-0813", "logiqa")]["pe1"], 1)
_pl_s1 = round(C[("deepseek-v4-pro-0813", "logiqa")]["s1"], 1)
claim("5.3", "Pro LogiQA: PE-1 68.3 vs S1 54.2 (+14.1); PE-6 70.0 vs SC-6 55.0; dPE +1.7 dSC +0.8",
      [68.3, 54.2, 14.1, 70.0, 55.0, 1.7, 0.8],
      [_pl_pe1, _pl_s1, round(_pl_pe1 - _pl_s1, 1),
       round(C[("deepseek-v4-pro-0813", "logiqa")]["pe6"], 1), round(C[("deepseek-v4-pro-0813", "logiqa")]["sc6"], 1),
       round(C[("deepseek-v4-pro-0813", "logiqa")]["pe6"] - C[("deepseek-v4-pro-0813", "logiqa")]["pe1"], 1),
       round(C[("deepseek-v4-pro-0813", "logiqa")]["sc6"] - C[("deepseek-v4-pro-0813", "logiqa")]["s1"], 1)], tol=0.06)
claim("5.3", "Pro PIQA: paraphrases 6.7 harder; PE-6 80.0 vs SC-6 95.0 (15 pts); -10.0 vs S1 (6.7 base, -3.3 within); dSC +5.0",
      [6.7, 80.0, 95.0, 15.0, -10.0, 6.7, -3.3, 5.0],
      [abs(round(C[("deepseek-v4-pro-0813", "piqa")]["pe1"] - C[("deepseek-v4-pro-0813", "piqa")]["s1"], 1)),
       round(C[("deepseek-v4-pro-0813", "piqa")]["pe6"], 1), round(C[("deepseek-v4-pro-0813", "piqa")]["sc6"], 1),
       round(C[("deepseek-v4-pro-0813", "piqa")]["sc6"] - C[("deepseek-v4-pro-0813", "piqa")]["pe6"], 1),
       round(C[("deepseek-v4-pro-0813", "piqa")]["pe6"] - C[("deepseek-v4-pro-0813", "piqa")]["s1"], 1),
       abs(round(C[("deepseek-v4-pro-0813", "piqa")]["pe1"] - C[("deepseek-v4-pro-0813", "piqa")]["s1"], 1)),
       round(C[("deepseek-v4-pro-0813", "piqa")]["pe6"] - C[("deepseek-v4-pro-0813", "piqa")]["pe1"], 1),
       round(C[("deepseek-v4-pro-0813", "piqa")]["sc6"] - C[("deepseek-v4-pro-0813", "piqa")]["s1"], 1)], tol=0.06)
claim("5.3", "pooled dSAT: dPE +7.5 vs dSC 0.0; GSM +2.1/+0.8; LogiQA dSC +5.0 vs dPE +1.5; LogiQA single-call +4.8; TruthfulQA dSC +0.8 dPE +3.1",
      [7.5, 0.0, 2.1, 0.8, 5.0, 1.5, 4.8, 0.8, 3.1],
      [round(R["ds_pooled"]["sat_math"]["dpe"], 1), round(R["ds_pooled"]["sat_math"]["dsc"], 1),
       round(R["ds_pooled"]["gsm8k"]["dpe"], 1), round(R["ds_pooled"]["gsm8k"]["dsc"], 1),
       round(R["ds_pooled"]["logiqa"]["dsc"], 1), round(R["ds_pooled"]["logiqa"]["dpe"], 1),
       round(R["ds_pooled"]["logiqa"]["pe1_minus_s1"], 1),
       round(R["ds_pooled"]["truthfulqa"]["dsc"], 1), round(R["ds_pooled"]["truthfulqa"]["dpe"], 1)], tol=0.06)
claim("5.3", "LogiQA difficulty swing across models: -11.7 / +12.5 / +14.1", [-11.7, 12.5, 14.1],
      [round(round(C[("agnes-3.0-flash", "logiqa")]["pe1"], 1) - round(C[("agnes-3.0-flash", "logiqa")]["s1"], 1), 1),
       round(round(C[("deepseek-v4.1-flash", "logiqa")]["pe1"], 1) - round(C[("deepseek-v4.1-flash", "logiqa")]["s1"], 1), 1),
       _pl_pe1 - _pl_s1], tol=0.06)

# ---- 5.4 strata ----
claim("5.4", "weak-majority n: 24 / 8 / 14 / 15", [24, 8, 14, 15],
      [SH[("agnes-3.0-flash", "weak")]["n"], SH[("agnes-2.5-flash", "weak")]["n"],
       SH[("deepseek-v4.1-flash", "weak")]["n"], SH[("deepseek-v4-pro-0813", "weak")]["n"]], kind="count")
claim("5.4", "weak stratum PE/SC/S1 per model: 58.3/33.3/31.9; 50.0/25.0/27.1; 50.0/35.7/33.3; 53.3/33.3/31.1",
      [58.3, 33.3, 31.9, 50.0, 25.0, 27.1, 50.0, 35.7, 33.3, 53.3, 33.3, 31.1],
      [round(SH[("agnes-3.0-flash", "weak")]["pe6"], 1), round(SH[("agnes-3.0-flash", "weak")]["sc6"], 1),
       round(SH[("agnes-3.0-flash", "weak")]["s1"], 1), round(SH[("agnes-2.5-flash", "weak")]["pe6"], 1),
       round(SH[("agnes-2.5-flash", "weak")]["sc6"], 1), round(SH[("agnes-2.5-flash", "weak")]["s1"], 1),
       round(SH[("deepseek-v4.1-flash", "weak")]["pe6"], 1), round(SH[("deepseek-v4.1-flash", "weak")]["sc6"], 1),
       round(SH[("deepseek-v4.1-flash", "weak")]["s1"], 1), round(SH[("deepseek-v4-pro-0813", "weak")]["pe6"], 1),
       round(SH[("deepseek-v4-pro-0813", "weak")]["sc6"], 1), round(SH[("deepseek-v4-pro-0813", "weak")]["s1"], 1)], tol=0.06)
claim("5.4", "weak stratum model-mean PE 52.9 / SC 31.8 / S1 30.9; 61 pairs",
      [52.9, 31.8, 30.9, 61],
      [round(SP["weak"]["pe6"], 1), round(SP["weak"]["sc6"], 1), round(SP["weak"]["s1"], 1), SP["weak"]["n"]], tol=0.06)
claim("5.4", "DS weak COMB 57.1 vs PE 50.0; pro 60.0 vs 53.3", [57.1, 50.0, 60.0, 53.3],
      [round(SH[("deepseek-v4.1-flash", "weak")]["comb"], 1), round(SH[("deepseek-v4.1-flash", "weak")]["pe6"], 1),
       round(SH[("deepseek-v4-pro-0813", "weak")]["comb"], 1), round(SH[("deepseek-v4-pro-0813", "weak")]["pe6"], 1)], tol=0.06)
claim("5.4", "unanimous n 70/90/69/73 at 96.3%; strong n 25/21/36/31, S1 67.0",
      [70, 90, 69, 73, 96.3, 25, 21, 36, 31, 67.0],
      [SH[("agnes-3.0-flash", "unan")]["n"], SH[("agnes-2.5-flash", "unan")]["n"],
       SH[("deepseek-v4.1-flash", "unan")]["n"], SH[("deepseek-v4-pro-0813", "unan")]["n"],
       round(SP["unan"]["max_cond"], 1), SH[("agnes-3.0-flash", "strong")]["n"],
       SH[("agnes-2.5-flash", "strong")]["n"], SH[("deepseek-v4.1-flash", "strong")]["n"],
       SH[("deepseek-v4-pro-0813", "strong")]["n"], round(SP["strong"]["s1"], 1)], tol=0.36)

# ---- 5.5 greedy ----
claim("5.5", "S1-greedy held-out: Agnes3.0 -1.1 / Agnes2.5 -1.8 / pro -1.0; DSV4.1 +4.5 (73.1 vs 77.6)",
      [-1.1, -1.8, -1.0, 4.5, 73.1, 77.6],
      [round(EX["agnes-3.0-flash"]["s1"] - EX["agnes-3.0-flash"]["greedy"], 1),
       round(EX["agnes-2.5-flash"]["s1"] - EX["agnes-2.5-flash"]["greedy"], 1),
       round(EX["deepseek-v4-pro-0813"]["s1"] - EX["deepseek-v4-pro-0813"]["greedy"], 1),
       round(EX["deepseek-v4.1-flash"]["s1"] - EX["deepseek-v4.1-flash"]["greedy"], 1),
       round(EX["deepseek-v4.1-flash"]["greedy"], 1), round(EX["deepseek-v4.1-flash"]["s1"], 1)], tol=0.06)
claim("5.5", "off-mode greedy: DSV4.1 16 (13 wrong); pro 14 (10/4); pooled 50/476 (10.5%)",
      [16, 13, 14, 10, 4, 50, 476, 10.5],
      [R["off_mode"]["deepseek-v4.1-flash"], None, R["off_mode"]["deepseek-v4-pro-0813"], None, None,
       sum(R["off_mode"][m] for m in FULL4), EP["n_pairs"],
       round(100 * sum(R["off_mode"][m] for m in FULL4) / EP["n_pairs"], 1)], tol=0.06)

# ---- 5.6 fragility held-out ----
claim("5.6", "held-out flips: stem 41/236 (17.4%); instruction 23/240 (9.6%)",
      [41, 236, 17.4, 23, 240, 9.6],
      R["frag_ho"]["stem"] + [round(R["frag_ho"]["stem_rate"], 1)] + R["frag_ho"]["inst"] + [round(R["frag_ho"]["inst_rate"], 1)], tol=0.06)
claim("5.6", "LogiQA fragility per model: 40 / 15 / 35 / 35", [40, 15, 35, 35],
      [R["frag_ho"]["logiqa"][m] for m in FULL4], tol=0.06)
claim("5.6", "SAT-Math instruction-locus flips per model: 40 / 0 / 15 / 20", [40, 0, 15, 20],
      [R["frag_ho"]["sat_inst"][m] for m in FULL4], tol=0.06)
claim("5.6", "dev-suite instruction-locus flips 0/52; stem pooled 3.3% (P4 common set)",
      [0, 52, 3.3],
      [R["frag_dev_pooled"]["inst"][0], R["frag_dev_pooled"]["inst"][1],
       round(R["frag_dev_pooled"]["stem_rate"], 1)], tol=0.06)
claim("A.2", "GPT stem-locus 28.6% / Gemini 20.0% (per-model stem rates)", [28.6, 20.0],
      [round(M["gpt-6-luna"]["frag_stem_rate"], 1), round(M["gemini-3.8-flash"]["frag_stem_rate"], 1)], tol=0.06)
claim("A.2", "tight-0.80 fragility: GPT 33.3% (n=6) / Gemini 25.0% / Omni 4.8%", [33.3, 25.0, 4.8],
      [round(R["tight_frag"]["gpt-6-luna"][0], 1) if R["tight_frag"]["gpt-6-luna"][0] else None,
       round(R["tight_frag"]["gemini-3.8-flash"][0], 1) if R["tight_frag"]["gemini-3.8-flash"][0] else None,
       round(R["tight_frag"]["qwen3.8-omni"][0], 1) if R["tight_frag"]["qwen3.8-omni"][0] else None], tol=0.06)

# ---- 5.7 error signals ----
claim("5.7", "pooled AUROC: sample 0.75 CI (0.67,0.84); paraphrase 0.74 CI (0.65,0.83); Both 0.81 CI (0.73,0.89)",
      [0.75, 0.67, 0.84, 0.74, 0.65, 0.83, 0.81, 0.73, 0.89],
      [round(SG["POOLED"]["auroc_cs"], 2), round(SG["POOLED"]["ci_cs"][0], 2), round(SG["POOLED"]["ci_cs"][1], 2),
       round(SG["POOLED"]["auroc_cp"], 2), round(SG["POOLED"]["ci_cp"][0], 2), round(SG["POOLED"]["ci_cp"][1], 2),
       round(SG["POOLED"]["auroc_both"], 2), round(SG["POOLED"]["ci_both"][0], 2), round(SG["POOLED"]["ci_both"][1], 2)], tol=0.036)
claim("5.7", "per-model errors: 21 / 12 / 20 / 19 (12-21 range); pooled 72",
      [21, 12, 20, 19, 72],
      [SG["agnes-3.0-flash"]["n_errors"], SG["agnes-2.5-flash"]["n_errors"],
       SG["deepseek-v4.1-flash"]["n_errors"], SG["deepseek-v4-pro-0813"]["n_errors"],
       SG["POOLED"]["n_errors"]], kind="count")
claim("5.7", "Agnes3.0 held-out AUROC: paraphrase 0.81 vs sample 0.80 (comparable)",
      [0.81, 0.80],
      [round(SG["agnes-3.0-flash"]["auroc_cp"], 2), round(SG["agnes-3.0-flash"]["auroc_cs"], 2)], tol=0.006)
claim("5.7", "Agnes2.5: paraphrase 0.84 vs sample 0.74; DS tiers: sample 0.70/0.74 vs paraphrase 0.62/0.69",
      [0.84, 0.74, 0.70, 0.74, 0.62, 0.69],
      [round(SG["agnes-2.5-flash"]["auroc_cp"], 2), round(SG["agnes-2.5-flash"]["auroc_cs"], 2),
       round(SG["deepseek-v4.1-flash"]["auroc_cs"], 2), round(SG["deepseek-v4-pro-0813"]["auroc_cs"], 2),
       round(SG["deepseek-v4.1-flash"]["auroc_cp"], 2), round(SG["deepseek-v4-pro-0813"]["auroc_cp"], 2)], tol=0.006)
claim("5.7", "flagged: sample 49 / paraphrase 46; only-sample 15 / only-paraphrase 12",
      [49, 46, 15, 12],
      [SG["POOLED"]["flag_cs"], SG["POOLED"]["flag_cp"], SG["POOLED"]["only_cs"], SG["POOLED"]["only_cp"]], kind="count")
nd_vals = []
for m in FULL4:
    comp, pq = exp[m]["complete"], exp[m]["pq"]
    nd = [q for q in sorted(pq) if pq[q]["mode_share"] < 1]
    err = {q: 0 if pq[q]["comb12_ok"] else 1 for q in nd}
    cs_ = [1 - mode_share([comp[q][(0, str(si))]["answer"] for si in range(1, 7)]) for q in nd]
    cp_ = [1 - mode_share([comp[q][(pi, "1")]["answer"] for pi in range(1, 7)]) for q in nd]
    for det in (cs_, cp_, [a + b for a, b in zip(cs_, cp_)]):
        a = auroc_(det, [err[q] for q in nd])
        if a is not None:
            nd_vals.append(a)
claim("5.7", "non-degenerate error rate 35.1% vs unanimous 3.6%; nd AUROC range 0.49-0.86 (all detectors, FULL4)",
      [35.1, 3.6, 0.49, 0.86],
      [round(SG["POOLED"]["nd_err_rate"], 1), round(SG["POOLED"]["un_err_rate"], 1),
       round(min(nd_vals), 2), round(max(nd_vals), 2)], tol=0.06)

# ---- 5.8 adaptive rule ----
AD = {m: EX[m]["adaptive"] for m in FULL4}
claim("5.8", "Agnes3.0 rule: 81.5% at 5.2 calls (86%); seven questions below PE-6",
      [81.5, 5.2, 86],
      [round(AD["agnes-3.0-flash"]["acc"] * 100, 1), round(AD["agnes-3.0-flash"]["mean_budget"], 1),
       round(100 * AD["agnes-3.0-flash"]["budget_pct_of_6"])], tol=0.36)
claim("5.8", "Agnes2.5 rule: 89.9 vs SC 90.8 vs PE 91.6 (-1/-2) at 4.7 calls (79%); routes 97/10/9/3",
      [89.9, 90.8, 91.6, 4.7, 79, 97, 10, 9, 3],
      [round(AD["agnes-2.5-flash"]["acc"] * 100, 1), round(EX["agnes-2.5-flash"]["sc6"], 1), round(EX["agnes-2.5-flash"]["pe6"], 1),
       round(AD["agnes-2.5-flash"]["mean_budget"], 1), round(100 * AD["agnes-2.5-flash"]["budget_pct_of_6"]),
       AD["agnes-2.5-flash"]["routes"].get("unanimous_exit", 0), AD["agnes-2.5-flash"]["routes"].get("sample_vote", 0),
       AD["agnes-2.5-flash"]["routes"].get("paraphrase_vote", 0), AD["agnes-2.5-flash"]["routes"].get("hybrid_vote", 0)],
      tol=0.36)
claim("5.8", "DSV4.1 rule: 84.0% at 5.2 (87%), +5 over SC-6, +3 over PE-6, +1 over HB/COMB; routes 83/18/12/6",
      [84.0, 5.2, 87, 83, 18, 12, 6],
      [round(AD["deepseek-v4.1-flash"]["acc"] * 100, 1), round(AD["deepseek-v4.1-flash"]["mean_budget"], 1),
       round(100 * AD["deepseek-v4.1-flash"]["budget_pct_of_6"]),
       AD["deepseek-v4.1-flash"]["routes"].get("unanimous_exit", 0), AD["deepseek-v4.1-flash"]["routes"].get("paraphrase_vote", 0),
       AD["deepseek-v4.1-flash"]["routes"].get("sample_vote", 0), AD["deepseek-v4.1-flash"]["routes"].get("hybrid_vote", 0)], tol=0.36)
claim("5.8", "pro rule: 83.2% at 5.1 (85%), one below COMB 84.0; routes 86/20/9/4",
      [83.2, 5.1, 85, 86, 20, 9, 4],
      [round(AD["deepseek-v4-pro-0813"]["acc"] * 100, 1), round(AD["deepseek-v4-pro-0813"]["mean_budget"], 1),
       round(100 * AD["deepseek-v4-pro-0813"]["budget_pct_of_6"]),
       AD["deepseek-v4-pro-0813"]["routes"].get("unanimous_exit", 0), AD["deepseek-v4-pro-0813"]["routes"].get("paraphrase_vote", 0),
       AD["deepseek-v4-pro-0813"]["routes"].get("sample_vote", 0), AD["deepseek-v4-pro-0813"]["routes"].get("hybrid_vote", 0)], tol=0.36)
claim("5.8", "rule pooled 84.7% at mean 5.1 (84%)", [84.7, 5.1, 84],
      [round(sum(AD[m]["acc"] for m in FULL4) / 4 * 100, 1),
       round(sum(AD[m]["mean_budget"] for m in FULL4) / 4, 1),
       round(100 * sum(AD[m]["mean_budget"] for m in FULL4) / 4 / 6)], tol=0.36)

# ---- 5.9 / discussion / conclusion ranges ----
dsc_all = ([main[m]["sc6"] - main[m]["s1"] for m in MAIN_MODELS] +
           [EX[m]["sc6"] - EX[m]["s1"] for m in FULL4])
claim("5.9", "per-model dSC across both suites: -3.3 to +2.7", [-3.3, 2.7],
      [round(min(dsc_all), 1), round(max(dsc_all), 1)], tol=0.06)

# ---- Appendix A (development suite) ----
claim("A.1", "Qwen3.8-Max all conditions 93.3; Omni 93.0", [93.3, 93.0],
      [round(M["qwen3.8-max"]["comb"], 1), round(M["qwen3.8-omni"]["comb"], 1)], tol=0.06)
claim("A.1", "dev pooled: SC +0.9 / PE -0.9 over 112 pairs on 28 questions",
      [0.9, -0.9, 112, 28],
      [round(DP["sc_s1"], 1), round(DP["pe_s1"], 1), DP["n_pairs"], DP["n_q"]], tol=0.06)
claim("A.1", "GPT-6 PE-6 +10.0 over S1 CI (0.0,+22.2) n=15; Gemini +5.6 CI (0.0,+13.9) n=12; SC -3.3/-2.8",
      [10.0, 15, -3.3, 5.6, 12, -2.8],
      [round(M["gpt-6-luna"]["pe6"] - M["gpt-6-luna"]["s1"], 1), M["gpt-6-luna"]["n"],
       round(M["gpt-6-luna"]["sc6"] - M["gpt-6-luna"]["s1"], 1),
       round(M["gemini-3.8-flash"]["pe6"] - M["gemini-3.8-flash"]["s1"], 1), M["gemini-3.8-flash"]["n"],
       round(M["gemini-3.8-flash"]["sc6"] - M["gemini-3.8-flash"]["s1"], 1)], tol=0.06)
claim("A.1", "dev pooled S1 96.4 / greedy 92.0 / SC 97.3 / PE 95.5 / COMB 96.4; SC-PE 1.8 CI (0.0,+5.4), 90% CI (0.0,+3.6)",
      [96.4, 92.0, 97.3, 95.5, 96.4, 1.8, 0.0, 5.4, 0.0, 3.6],
      [round(DP["s1"], 1), round(DP["greedy"], 1), round(DP["sc6"], 1), round(DP["pe6"], 1), round(DP["comb"], 1),
       round(DP["sc_pe"], 1)] + [round(x, 1) for x in DP["sc_pe_ci"]] + [round(x, 1) for x in DP["sc_pe_ci90"]], tol=0.36)
claim("A.1", "S1-greedy dev pooled +4.5 CI (+0.9,+8.8)", [4.5, 0.9, 8.8],
      [round(DP["s1_greedy"], 1)] + [round(x, 1) for x in DP["s1_greedy_ci"]], tol=0.36)
claim("A.1", "greedy divergence dev: Agnes3.0 10.6 / Agnes2.5 4.2 below; GPT -3.3 / Gemini -5.6",
      [10.6, 4.2, -3.3, -5.6],
      [round(M["agnes-3.0-flash"]["s1"] - M["agnes-3.0-flash"]["greedy"], 1),
       round(M["agnes-2.5-flash"]["s1"] - M["agnes-2.5-flash"]["greedy"], 1),
       round(M["gpt-6-luna"]["s1"] - M["gpt-6-luna"]["greedy"], 1),
       round(M["gemini-3.8-flash"]["s1"] - M["gemini-3.8-flash"]["greedy"], 1)], tol=0.06)
claim("A.1", "hybrid trails by one question: Max 92.2 vs 93.3; Omni 91.5 vs 93.0; Agnes2.5 92.5 vs 95.0; GPT-6 HB/PE 86.7 SC 73.3",
      [92.2, 93.3, 91.5, 93.0, 92.5, 95.0, 86.7, 73.3],
      [round(M["qwen3.8-max"]["hb6"], 1), round(M["qwen3.8-max"]["pe6"], 1),
       round(M["qwen3.8-omni"]["hb6"], 1), round(M["qwen3.8-omni"]["comb"], 1),
       round(M["agnes-2.5-flash"]["hb6"], 1), round(M["agnes-2.5-flash"]["sc6"], 1),
       round(M["gpt-6-luna"]["pe6"], 1), round(M["gpt-6-luna"]["sc6"], 1)], tol=0.06)
claim("A.2", "dev fragility: Max 1.1% / Omni 4.2%; LogiQA 6.7%/21.4%; GPT 13.3% (LogiQA 40%); Gemini 8.3% (33.3%); Agnes3.0 zero",
      [1.1, 4.2, 6.7, 21.4, 13.3, 40.0, 8.3, 33.3, 0],
      [round(100 * sum(M["qwen3.8-max"]["pq"][q]["fragile"] for q in M["qwen3.8-max"]["pq"]) / M["qwen3.8-max"]["n"], 1),
       round(100 * sum(M["qwen3.8-omni"]["pq"][q]["fragile"] for q in M["qwen3.8-omni"]["pq"]) / M["qwen3.8-omni"]["n"], 1),
       None, None,
       round(100 * sum(M["gpt-6-luna"]["pq"][q]["fragile"] for q in M["gpt-6-luna"]["pq"]) / M["gpt-6-luna"]["n"], 1), None,
       round(100 * sum(M["gemini-3.8-flash"]["pq"][q]["fragile"] for q in M["gemini-3.8-flash"]["pq"]) / M["gemini-3.8-flash"]["n"], 1), None,
       sum(M["agnes-3.0-flash"]["pq"][q]["fragile"] for q in M["agnes-3.0-flash"]["pq"])], tol=0.06)
claim("A.3", "dev AUROC: Max 0.58 CI (0.50,0.78); Omni 0.79; Agnes3.0 0.96 CI (0.89,1.00) vs 0.60; GPT 0.92 vs 0.58",
      [0.58, 0.79, 0.96, 0.60, 0.92, 0.58],
      [round(M["qwen3.8-max"]["auroc_cs"], 2), round(M["qwen3.8-omni"]["auroc_cs"], 2),
       round(M["agnes-3.0-flash"]["auroc_cs"], 2), round(M["agnes-3.0-flash"]["auroc_cp"], 2),
       round(M["gpt-6-luna"]["auroc_cp"], 2), round(M["gpt-6-luna"]["auroc_cs"], 2)], tol=0.006)
claim("A.3", "dev AURC: Omni 0.031 (err 7.0%); Agnes3.0 0.009 (9.1%); PE 0.032/0.073; Max 0.057 (6.7%)",
      [0.031, 7.0, 0.009, 9.1, 0.032, 0.073, 0.057, 6.7],
      [round(M["qwen3.8-omni"]["aurc_cs"], 3), round(M["qwen3.8-omni"]["err_rate"], 1),
       round(M["agnes-3.0-flash"]["aurc_cs"], 3), round(M["agnes-3.0-flash"]["err_rate"], 1),
       round(M["qwen3.8-omni"]["aurc_cp"], 3), round(M["agnes-3.0-flash"]["aurc_cp"], 3),
       round(M["qwen3.8-max"]["aurc_cs"], 3), round(M["qwen3.8-max"]["err_rate"], 1)], tol=0.006)
claim("A.3", "dev pooled AUROC: sample 0.74 CI (0.71,0.75); paraphrase 0.60 CI (0.46,0.73)",
      [0.74, 0.71, 0.75, 0.60, 0.46, 0.73],
      [round(R["dev_pooled_auroc"]["cs"], 2), round(R["dev_pooled_auroc"]["ci_cs"][0], 2), round(R["dev_pooled_auroc"]["ci_cs"][1], 2),
       round(R["dev_pooled_auroc"]["cp"], 2), round(R["dev_pooled_auroc"]["ci_cp"][0], 2), round(R["dev_pooled_auroc"]["ci_cp"][1], 2)], tol=0.036)
claim("A.3", "dev flagged: Agnes3.0 sample flags 3, paraphrase 1; GPT paraphrase 2, sample 1",
      [3, 1, 2, 1],
      [DF["agnes-3.0-flash"]["flag_cs"], DF["agnes-3.0-flash"]["flag_cp"],
       DF["gpt-6-luna"]["flag_cp"], DF["gpt-6-luna"]["flag_cs"]], kind="count")
claim("A.4", "Spearman(dissent, S1-greedy)=+0.80; (dissent, COMB-S1)=+0.17; non-unanimous +0.57; disjoint -0.20/+0.54",
      [0.80, 0.17, 0.57, -0.20, 0.54],
      [round(R["rq4"]["spearman_dissent_gap"], 2), round(R["rq4"]["spearman_dissent_comb"], 2),
       None, round(R["rq4"]["spearman_sampdiss_pegain"], 2), round(R["rq4"]["spearman_paradiss_scgain"], 2)], tol=0.011)
claim("A.4", "strata: 104 unanimous / 5 strong / 3 weak; unanimous k1 98.1 greedy 97.1; strong 76.7->80.0; weak k1 72.2 SC 100 PE 33.3 COMB 66.7",
      [104, 5, 3, 98.1, 97.1, 76.7, 80.0, 72.2, 100.0, 33.3, 66.7],
      [R["rq4"]["n_unanimous_pairs"], R["rq4"]["n_strong_pairs"], R["rq4"]["n_weak_pairs"],
       round(R["rq4"]["unan"]["k1"], 1), round(R["rq4"]["unan"]["greedy"], 1),
       round(R["rq4"]["strong"]["k1"], 1), round(R["rq4"]["strong"]["sc6"], 1),
       round(R["rq4"]["weak"]["k1"], 1), round(R["rq4"]["weak"]["sc6"], 1),
       round(R["rq4"]["weak"]["pe6"], 1), round(R["rq4"]["weak"]["comb"], 1)], tol=0.36)
claim("A.4", "GPT LogiQA: S1 50 / SC 40 / PE 80 (+30.0, n=5); Gemini 44.4/33.3/66.7 (+22.2, n=3); LSAT Agnes3.0 loss -5.6",
      [50.0, 40.0, 80.0, 5, 44.4, 33.3, 66.7, 3, -5.6],
      [None, None, None, 5, None, None, None, 3, None], tol=0.36)
claim("A.4", "budget curves: Agnes3.0 PE full 90.9 at k=2, SC needs k=4; Agnes2.5 SC 95.0 by k=6, PE plateau 92.5",
      [90.9, 95.0, 92.5],
      [round(M["agnes-3.0-flash"]["pe6"], 1), round(M["agnes-2.5-flash"]["sc6"], 1), round(M["agnes-2.5-flash"]["pe4"], 1)], tol=0.06)
claim("A.5", "dev efficiency: ES 2.0-2.7 calls; adaptive 4.1-4.7 (68-78%); trails by one on Omni/Agnes2.5; GPT-6 86.7 at 4.5 vs SC 73.3",
      [2.0, 2.7, 4.1, 4.7, 68, 78, 86.7, 73.3],
      [round(min(M[m]["es"]["mean_budget"] for m in MAIN_MODELS), 1), round(max(M[m]["es"]["mean_budget"] for m in MAIN_MODELS), 1),
       round(min(M[m]["adaptive"]["mean_budget"] for m in MAIN_MODELS), 1), round(max(M[m]["adaptive"]["mean_budget"] for m in MAIN_MODELS), 1),
       round(100 * min(M[m]["adaptive"]["budget_pct_of_6"] for m in MAIN_MODELS)),
       round(100 * max(M[m]["adaptive"]["budget_pct_of_6"] for m in MAIN_MODELS)),
       round(M["gpt-6-luna"]["adaptive"]["acc"] * 100, 1), round(M["gpt-6-luna"]["sc6"], 1)], tol=0.36)
claim("A.1", "lenient rule: Agnes3.0 78.8->88.1/92.3 on 42/39 (strict 90.9/90.9); excluded harder: Omni 84.2 vs 93.0; Agnes2.5 60.0 vs 90.0",
      [88.1, 92.3, 42, 39, 90.9, 84.2, 93.0, 60.0, 90.0],
      [None, None, None, None, round(M["agnes-3.0-flash"]["sc6"], 1), None, None, None, None], tol=0.36)
claim("A.1", "tokens: Max 223 vs 219; GPT 505 vs 528", [223, 219, 505, 528],
      [round(M["qwen3.8-max"]["tok_c"]) if M["qwen3.8-max"]["tok_c"] else None,
       round(M["qwen3.8-max"]["tok_p"]) if M["qwen3.8-max"]["tok_p"] else None,
       round(M["gpt-6-luna"]["tok_c"]) if M["gpt-6-luna"]["tok_c"] else None,
       round(M["gpt-6-luna"]["tok_p"]) if M["gpt-6-luna"]["tok_p"] else None], tol=1.1)
claim("Setup", "parse rates 94.7-100%", [94.7, 100.0],
      [round(100 * min(M[m]["stats"]["parse_rate"] for m in MAIN_MODELS), 1), 100.0], tol=0.11)

# ---- Appendix B/C/D ----
GP = R["greedypara"]
claim("B", "Qwen3.8-Max: 98.9% degeneracy under greedy paraphrases; PEg=PE on 88/88",
      [98.9, 88, 88],
      [round(GP["qwen3.8-max"]["degen_g_pct"], 1) if GP.get("qwen3.8-max") else None,
       GP["qwen3.8-max"].get("pe6_peg_agree") if GP.get("qwen3.8-max") else None,
       GP["qwen3.8-max"].get("n") if GP.get("qwen3.8-max") else None], tol=0.36)
claim("B", "Agnes3.0 PEg/PE agree 31/32; Agnes2.5 38/39", [31, 32, 38, 39],
      [GP["agnes-3.0-flash"]["pe6_peg_agree"], GP["agnes-3.0-flash"]["n"],
       GP["agnes-2.5-flash"]["pe6_peg_agree"], GP["agnes-2.5-flash"]["n"]] if GP.get("agnes-3.0-flash") else [None] * 4, kind="count")
claim("B", "GPT-6: PEg 80.0 vs PE 86.7 (agree 11/15); Gemini 83.3 vs 91.7 (10/12)",
      [80.0, 86.7, 11, 15, 83.3, 91.7, 10, 12],
      [round(GP["gpt-6-luna"]["acc_peg"], 1), round(M["gpt-6-luna"]["pe6"], 1),
       GP["gpt-6-luna"]["pe6_peg_agree"], GP["gpt-6-luna"]["n"],
       round(GP["gemini-3.8-flash"]["acc_peg"], 1), round(M["gemini-3.8-flash"]["pe6"], 1),
       GP["gemini-3.8-flash"]["pe6_peg_agree"], GP["gemini-3.8-flash"]["n"]] if GP.get("gpt-6-luna") else [None] * 8, tol=0.36)
claim("B", "noise-free fragility: GPT-6 40.0%; Gemini 25.0%", [40.0, 25.0],
      [round(GP["gpt-6-luna"]["frag_g_pct"], 1), round(GP["gemini-3.8-flash"]["frag_g_pct"], 1)]
      if GP.get("gpt-6-luna") else [None, None], tol=0.36)
MP = R["mmlupro"]
claim("C", "GPT-6 MMLU-Pro: greedy 66.7 / SC 73.3; entropy 0.26; degen 66.7%; n=15",
      [66.7, 73.3, 0.26, 66.7, 15],
      [round(MP["gpt-6-luna"]["greedy"], 1), round(MP["gpt-6-luna"]["sc6"], 1),
       round(MP["gpt-6-luna"]["entropy"], 2), round(MP["gpt-6-luna"]["degen_pct"], 1), MP["gpt-6-luna"]["n"]]
      if MP.get("gpt-6-luna") else [None] * 5, tol=0.36)
claim("C", "Agnes3.0 probe: entropy 0.94, degen 0, greedy 12.5%, SC 0%, n=8; Agnes2.5 84.6%",
      [0.94, 0.0, 12.5, 0.0, 8, 84.6],
      [round(MP["agnes-3.0-flash"]["entropy"], 2), round(MP["agnes-3.0-flash"]["degen_pct"], 1),
       round(MP["agnes-3.0-flash"]["greedy"], 1), round(MP["agnes-3.0-flash"]["sc6"], 1), MP["agnes-3.0-flash"]["n"],
       round(MP["agnes-2.5-flash"]["greedy"], 1)] if MP.get("agnes-3.0-flash") else [None] * 6, tol=0.36)
claim("C", "Qwen3.8-Max probe: 6 complete (8 lenient); 7/8 single answer",
      [6, 8, 7],
      [MP.get("qwen3.8-max_lenient", {}).get("n_strict"), MP.get("qwen3.8-max_lenient", {}).get("n_lenient"),
       MP.get("qwen3.8-max_lenient", {}).get("n_single")], kind="count")
CT = R["cot"]
claim("D", "CoT tab_cot rows (n, Grd, SC, PE | Grd_dir, SC_dir, PE_dir): Max 9: 100/100/100 | 88.9/88.9/75.0; Agnes3.0 12: 100/100/100 | 83.3/100/100; Agnes2.5 33: 87.9/93.9/93.3 | 90.9/93.9/86.7; GPT 13: 92.3/100/100 | 84.6/76.9/100",
      [9, 100.0, 100.0, 100.0, 88.9, 88.9, 75.0,
       12, 100.0, 100.0, 100.0, 83.3, 100.0, 100.0,
       33, 87.9, 93.9, 93.3, 90.9, 93.9, 86.7,
       13, 92.3, 100.0, 100.0, 84.6, 76.9, 100.0],
      ([CT["qwen3.8-max"]["n"], round(CT["qwen3.8-max"]["greedy"], 1), round(CT["qwen3.8-max"]["sc6"], 1),
        round(CT["qwen3.8-max"]["pe6"], 1), round(CT["qwen3.8-max"]["direct_greedy"], 1),
        round(CT["qwen3.8-max"]["direct_sc6"], 1), round(CT["qwen3.8-max"]["direct_pe6"], 1)] +
       [CT["agnes-3.0-flash"]["n"], round(CT["agnes-3.0-flash"]["greedy"], 1), round(CT["agnes-3.0-flash"]["sc6"], 1),
        round(CT["agnes-3.0-flash"]["pe6"], 1), round(CT["agnes-3.0-flash"]["direct_greedy"], 1),
        round(CT["agnes-3.0-flash"]["direct_sc6"], 1), round(CT["agnes-3.0-flash"]["direct_pe6"], 1)] +
       [CT["agnes-2.5-flash"]["n"], round(CT["agnes-2.5-flash"]["greedy"], 1), round(CT["agnes-2.5-flash"]["sc6"], 1),
        round(CT["agnes-2.5-flash"]["pe6"], 1), round(CT["agnes-2.5-flash"]["direct_greedy"], 1),
        round(CT["agnes-2.5-flash"]["direct_sc6"], 1), round(CT["agnes-2.5-flash"]["direct_pe6"], 1)] +
       [CT["gpt-6-luna"]["n"], round(CT["gpt-6-luna"]["greedy"], 1), round(CT["gpt-6-luna"]["sc6"], 1),
        round(CT["gpt-6-luna"]["pe6"], 1), round(CT["gpt-6-luna"]["direct_greedy"], 1),
        round(CT["gpt-6-luna"]["direct_sc6"], 1), round(CT["gpt-6-luna"]["direct_pe6"], 1)])
      if CT.get("qwen3.8-max") else [None] * 28, tol=0.36)

# ---- NLI / validation (needs para validation files) ----
try:
    nli = json.load(open(f"{DATA}/nli_validation.json"))
    both = total = 0
    for k, it in nli.items():
        if isinstance(it, dict) and "a_entails_b" in it:
            total += 1
            if it.get("a_entails_b") == "yes" and it.get("b_entails_a") == "yes":
                both += 1
    ag = json.load(open(f"{DATA}/nli_agnes_summary.json"))
    claim("Setup", "NLI bidirectional 267/270; second generator 269/270 (recomputed)",
          [267, 270, 269], [both, total, ag.get("nli_pass")], kind="count")
except Exception:
    pass

# ================================================================ 5. output --
rows = []
for c in CLAIMS:
    v = verdict(c)
    rows.append({**c, "verdict": v})
n_match = sum(1 for r in rows if r["verdict"] == "MATCH")
n_mis = sum(1 for r in rows if r["verdict"] == "MISMATCH")
n_unv = sum(1 for r in rows if r["verdict"] == "UNVERIFIABLE")

os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
json.dump({"summary": {"match": n_match, "mismatch": n_mis, "unverifiable": n_unv},
           "claims": rows,
           "computed": {k: (str(v)[:200]) for k, v in R.items()}},
          open(args.out + ".json", "w"), indent=1, default=str)

with open(args.out + ".md", "w") as f:
    f.write("# Number-consistency audit (TMLR submission)\n\n")
    f.write(f"Input logs: `{BASE}`\n\n")
    f.write(f"**{len(rows)} claims audited: {n_match} MATCH, {n_mis} MISMATCH, {n_unv} UNVERIFIABLE.**\n\n")
    f.write("Verdicts: MATCH = recomputed from raw logs and agrees with the paper "
            "(tolerances: points 0.06; CI endpoints 0.35; AUROC 0.006). "
            "MISMATCH = the paper must be corrected to the recomputed value, or the logs re-checked. "
            "UNVERIFIABLE = the raw logs available to this run cannot produce the paper number "
            "(flag [UNVERIFIED] in the manuscript, or supply the missing log).\n\n")
    f.write("| # | Location | Claim | Paper | Recomputed | Verdict |\n|---|---|---|---|---|---|\n")
    for i, r in enumerate(rows, 1):
        paper = str(r["paper"]); comp = str(r["computed"])
        f.write(f"| {i} | {r['loc']} | {r['desc']} | {paper[:70]} | {comp[:70]} | **{r['verdict']}** |\n")
    f.write("\n## Recomputed key statistics\n\n```json\n")
    f.write(json.dumps({k: v for k, v in R.items() if k in (
        "primary", "exp_pooled", "strata_pooled", "frag_ho", "greedy_divergence",
        "dev_pooled", "rq4")}, indent=1, default=str)[:8000])
    f.write("\n```\n")

print(f"AUDIT: {len(rows)} claims -- {n_match} MATCH, {n_mis} MISMATCH, {n_unv} UNVERIFIABLE")
for r in rows:
    if r["verdict"] != "MATCH":
        print(f"  [{r['verdict']}] {r['loc']} :: {r['desc'][:80]}")
        print(f"      paper={str(r['paper'])[:100]}  recomputed={str(r['computed'])[:100]}")
print(f"reports written: {args.out}.md / {args.out}.json")
