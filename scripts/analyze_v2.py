#!/usr/bin/env python3
"""Analysis v2 (revision): fixes AURC direction, adds clustered bootstrap, McNemar,
TOST equivalence, AUROC/AURC CIs, signal-overlap, k=1 baseline, token costs,
locus stratification, early-stopping + adaptive-allocation simulations, parse-failure
sensitivity, and the three new experimental conditions (greedypara/mmlupro/cot).

Writes results/analysis/results.json + pooled.json (superset of v1 keys).
Usage: python3 analyze_v2.py
"""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import json, math, os, random, glob
from collections import defaultdict, Counter

DATA = ROOT + "/data"
RES = ROOT + "/results"
OUT = ROOT + "/results/analysis"
os.makedirs(OUT, exist_ok=True)

questions = {q["id"]: q for q in json.load(open(f"{DATA}/questions.json"))}
mmlupro_q = {q["id"]: q for q in json.load(open(f"{DATA}/mmlupro30.json"))}
STEM_DS = {"truthfulqa", "lsat_lr", "logiqa"}   # paraphrase-locus datasets
INSTR_DS = {"gsm8k", "piqa", "sat_math"}

def gold_of(q):
    if q["dataset"] == "gsm8k":
        return str(q["answer"])
    if q["dataset"] == "piqa":
        return str(q["answer_idx"] + 1)
    return "ABCDEFGHIJ"[q["answer_idx"]]

def locus_of(q):
    return "stem" if q["dataset"] in STEM_DS else "instruction"

# ---------------- generic loaders ----------------
def load_cells(path):
    cells = defaultdict(dict)
    n_calls = n_failed = n_unparsed = 0
    for line in open(path):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("FAILED"):
            n_failed += 1
            continue
        n_calls += 1
        cells[(r["model"], r["qid"])][(r["para"], str(r["sample"]))] = r
        if r["answer"] is None:
            n_unparsed += 1
    return cells, {"calls": n_calls, "failed": n_failed, "unparsed": n_unparsed}

MAIN_NEED = [(0, "g")] + [(0, str(s)) for s in range(1, 7)] + \
            [(p, str(s)) for p in (1, 2, 3) for s in (1, 2)] + [(p, "1") for p in (4, 5, 6)]

def load_model(alias, res_dir=RES):
    cells, stats = load_cells(f"{res_dir}/{alias}.jsonl")
    complete = {}
    for (m, qid), cm in cells.items():
        if m != alias:
            continue
        if all(k in cm and cm[k]["answer"] is not None for k in MAIN_NEED):
            complete[qid] = {k: cm[k] for k in MAIN_NEED}
    stats["parse_rate"] = 1 - stats["unparsed"] / max(1, stats["calls"])
    stats["complete_questions"] = len(complete)
    stats["tokens"] = {
        "pt": sum(c["usage"].get("pt") or 0 for cm in complete.values() for c in cm.values()),
        "ct": sum(c["usage"].get("ct") or 0 for cm in complete.values() for c in cm.values())}
    return complete, stats, cells

# ---------------- primitives ----------------
def majority(votes):
    vs = [v for v in votes if v is not None]
    if not vs:
        return None
    c = Counter(vs)
    top = c.most_common()
    best = top[0][1]
    winners = set(v for v, n in top if n == best)
    for v in vs:
        if v in winners:
            return v

def agreement(votes):
    vs = [v for v in votes if v is not None]
    if not vs:
        return None
    return Counter(vs).most_common(1)[0][1] / len(vs)

def norm_entropy(votes):
    """Entropy of the empirical answer distribution divided by log of the
    observed number of distinct answers (support-normalized; 1 = uniform)."""
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

def risk_coverage(scores, errors):
    """AURC with confidence-descending order (most confident accepted first).
    scores: confidence (higher = accept earlier). Returns (AURC, E-AURC=excess over oracle)."""
    pairs = sorted([(s, e) for s, e in zip(scores, errors) if s is not None],
                   key=lambda x: -x[0])
    n = len(pairs)
    if n == 0:
        return None, None
    cum_err, total, aurc = 0.0, 0, 0.0
    for s, e in pairs:
        cum_err += e
        total += 1
        aurc += cum_err / total
    aurc /= n
    sorted_err = sorted(e for _, e in pairs)          # oracle: correct first
    cum, o_total, o_aurc = 0.0, 0, 0.0
    for e in sorted_err:
        cum += e
        o_total += 1
        o_aurc += cum / o_total
    o_aurc /= n
    return aurc, aurc - o_aurc

def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    from math import comb
    k = min(b, c)
    p = sum(comb(n, i) for i in range(0, k + 1)) / 2**n * 2
    return min(1.0, p)

def boot_ci(values, iters=10000, seed=42, alpha=0.05):
    """values: per-unit statistics; returns (mean, lo, hi) resampling units."""
    rng = random.Random(seed)
    n = len(values)
    if n == 0:
        return (None, None, None)
    mean = sum(values) / n
    boots = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(iters))
    return mean, boots[int(alpha / 2 * iters)], boots[int((1 - alpha / 2) * iters)]

def tost(paired, bound, iters=10000, seed=42):
    """TOST via bootstrap 90% CI inside (-bound, +bound). paired: (a,b) bools."""
    diffs = [a - b for a, b in paired]
    mean, _, _ = boot_ci(diffs, iters, seed)
    rng = random.Random(seed + 1)
    n = len(diffs)
    boots = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(iters))
    lo, hi = boots[500], boots[9500]        # 90% CI
    return {"bound": bound, "mean_diff": mean, "ci90": [lo, hi],
            "equivalent": (lo > -bound and hi < bound)}

# ---------------- main-suite analysis ----------------
def analyze_main(models):
    R = {"models": {}, "pooled": {}}
    for alias in models:
        complete, stats, all_cells = load_model(alias)
        if not complete:
            print(f"{alias}: no complete questions, skipping")
            continue
        per_q = {}
        for qid, cm in complete.items():
            q = questions[qid]
            gold = gold_of(q)
            g = cm[(0, "g")]["answer"]
            sc = {k: majority([cm[(0, str(s))]["answer"] for s in range(1, k + 1)]) for k in (2, 4, 6)}
            pe = {k: majority([cm[(p, "1")]["answer"] for p in range(1, k + 1)]) for k in (2, 4, 6)}
            hb = majority([cm[(p, str(s))]["answer"] for p in (1, 2, 3) for s in (1, 2)])
            comb = majority([cm[(0, str(s))]["answer"] for s in range(1, 7)] +
                            [cm[(p, "1")]["answer"] for p in range(1, 7)])
            sc_votes = [cm[(0, str(s))]["answer"] for s in range(1, 7)]
            pe_votes = [cm[(p, "1")]["answer"] for p in range(1, 7)]
            per_q[qid] = {
                "dataset": q["dataset"], "locus": locus_of(q), "gold": gold,
                "greedy": g, "greedy_ok": g == gold,
                "sc": {k: (v, v == gold) for k, v in sc.items()},
                "pe": {k: (v, v == gold) for k, v in pe.items()},
                "hb6": (hb, hb == gold), "comb12": (comb, comb == gold),
                "c_s": agreement(sc_votes), "c_p": agreement(pe_votes),
                "entropy": norm_entropy(sc_votes + pe_votes),
                "entropy_sc": norm_entropy(sc_votes), "entropy_pe": norm_entropy(pe_votes),
                "fragile": sc[6] != pe[6],
                "sc6_ok": sc[6] == gold, "pe6_ok": pe[6] == gold,
                "comb12_ok": comb == gold, "hb6_ok": hb == gold,
                "k1_acc": sum(cm[(0, str(s))]["answer"] == gold for s in range(1, 7)) / 6.0,
                "greedy_ok": g == gold,
            }
        qids = sorted(per_q)
        m = {"stats": stats, "n": len(qids), "per_q": per_q}
        def acc(f):
            vals = [per_q[q][f] for q in qids if per_q[q][f] is not None]
            return sum(vals) / len(vals) if vals else None
        m["acc"] = {
            "greedy": acc("greedy_ok"), "sc6": acc("sc6_ok"), "pe6": acc("pe6_ok"),
            "hb6": acc("hb6_ok"), "comb12": acc("comb12_ok"), "k1": acc("k1_acc"),
            "sc2": sum(1 for q in qids if per_q[q]["sc"][2][1]) / len(qids),
            "sc4": sum(1 for q in qids if per_q[q]["sc"][4][1]) / len(qids),
            "pe2": sum(1 for q in qids if per_q[q]["pe"][2][1]) / len(qids),
            "pe4": sum(1 for q in qids if per_q[q]["pe"][4][1]) / len(qids),
        }
        # accuracy CIs (question-level bootstrap)
        for cond in ("greedy", "sc6", "pe6", "hb6", "comb12", "k1"):
            vals = [per_q[q]["k1_acc"] if cond == "k1" else
                    (1 if per_q[q][f"{cond}_ok"] else 0) for q in qids]
            m[f"ci_{cond}"] = boot_ci(vals)
        # per-dataset
        m["by_ds"] = {}
        for ds in sorted(set(v["dataset"] for v in per_q.values())):
            dq = [q for q in qids if per_q[q]["dataset"] == ds]
            m["by_ds"][ds] = {
                "n": len(dq),
                "greedy": sum(per_q[q]["greedy_ok"] for q in dq) / len(dq),
                "sc6": sum(per_q[q]["sc6_ok"] for q in dq) / len(dq),
                "pe6": sum(per_q[q]["pe6_ok"] for q in dq) / len(dq),
                "comb12": sum(per_q[q]["comb12_ok"] for q in dq) / len(dq),
                "entropy": sum(per_q[q]["entropy"] for q in dq) / len(dq),
                "fragile": sum(per_q[q]["fragile"] for q in dq) / len(dq),
                "degenerate": sum(1 for q in dq if per_q[q]["c_s"] == 1 and per_q[q]["c_p"] == 1) / len(dq),
            }
        # locus strata (B10)
        m["by_locus"] = {}
        for loc in ("stem", "instruction"):
            lq = [q for q in qids if per_q[q]["locus"] == loc]
            if not lq:
                continue
            m["by_locus"][loc] = {
                "n": len(lq),
                "greedy": sum(per_q[q]["greedy_ok"] for q in lq) / len(lq),
                "sc6": sum(per_q[q]["sc6_ok"] for q in lq) / len(lq),
                "pe6": sum(per_q[q]["pe6_ok"] for q in lq) / len(lq),
                "comb12": sum(per_q[q]["comb12_ok"] for q in lq) / len(lq),
                "gain_sc6": (sum(per_q[q]["sc6_ok"] for q in lq) - sum(per_q[q]["greedy_ok"] for q in lq)) / len(lq),
                "gain_pe6": (sum(per_q[q]["pe6_ok"] for q in lq) - sum(per_q[q]["greedy_ok"] for q in lq)) / len(lq),
                "entropy": sum(per_q[q]["entropy"] for q in lq) / len(lq),
                "fragile": sum(per_q[q]["fragile"] for q in lq) / len(lq),
            }
        # paired comparisons: SC vs PE, greedy vs each (C2)
        for name, fa, fb in [("sc_vs_pe", "sc6_ok", "pe6_ok"),
                             ("sc_vs_greedy", "sc6_ok", "greedy_ok"),
                             ("pe_vs_greedy", "pe6_ok", "greedy_ok"),
                             ("hb_vs_greedy", "hb6_ok", "greedy_ok"),
                             ("comb_vs_greedy", "comb12_ok", "greedy_ok")]:
            pair = [(per_q[q][fa], per_q[q][fb]) for q in qids]
            b = sum(1 for a1, b1 in pair if a1 and not b1)
            c = sum(1 for a1, b1 in pair if not a1 and b1)
            diff, lo, hi = boot_ci([a - b_ for a, b_ in pair])
            m[name] = {"b": b, "c": c, "p": mcnemar(b, c),
                       "diff": diff, "ci": [lo, hi],
                       "tost_3pp": tost(pair, 0.03), "tost_5pp": tost(pair, 0.05)}
        # fragility & degeneracy
        m["fragile_rate"] = sum(per_q[q]["fragile"] for q in qids) / len(qids)
        m["degenerate_rate"] = sum(1 for q in qids if per_q[q]["c_s"] == 1 and per_q[q]["c_p"] == 1) / len(qids)
        m["degenerate_s_only"] = sum(1 for q in qids if per_q[q]["c_s"] == 1) / len(qids)
        m["mean_entropy"] = sum(per_q[q]["entropy"] for q in qids) / len(qids)
        m["mean_c_s"] = sum(per_q[q]["c_s"] for q in qids) / len(qids)
        m["mean_c_p"] = sum(per_q[q]["c_p"] for q in qids) / len(qids)
        # error detection with bootstrap CIs (C3); reference = COMB-12
        errs = [0 if per_q[q]["comb12_ok"] else 1 for q in qids]
        m["err_rate"] = sum(errs) / len(errs)
        m["n_errors"] = int(sum(errs))
        m["descriptive_only"] = m["n_errors"] < 5
        if len(set(errs)) > 1:
            for sig, key in [("cs", "c_s"), ("cp", "c_p")]:
                m[f"auroc_{sig}"] = auroc([1 - per_q[q][key] for q in qids], errs)
                aurc, eaurc = risk_coverage([per_q[q][key] for q in qids], errs)
                m[f"aurc_{sig}"], m[f"eaurc_{sig}"] = aurc, eaurc
            m["auroc_both"] = auroc([2 - per_q[q]["c_s"] - per_q[q]["c_p"] for q in qids], errs)
            aurc3, eaurc3 = risk_coverage([(per_q[q]["c_s"] + per_q[q]["c_p"]) / 2 for q in qids], errs)
            m["aurc_both"], m["eaurc_both"] = aurc3, eaurc3
            # bootstrap CIs (resample questions)
            def _boot_metric(fn):
                rng = random.Random(42)
                vals = []
                for _ in range(2000):
                    sq = [qids[rng.randrange(len(qids))] for _ in range(len(qids))]
                    e2 = [0 if per_q[q]["comb12_ok"] else 1 for q in sq]
                    if len(set(e2)) < 2:
                        continue
                    v = fn(sq, e2)
                    if v is not None:
                        vals.append(v)
                if not vals:
                    return [None, None]
                vals.sort()
                return [vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals))]]
            m["auroc_cs_ci"] = _boot_metric(lambda sq, e2: auroc([1 - per_q[q]["c_s"] for q in sq], e2))
            m["auroc_cp_ci"] = _boot_metric(lambda sq, e2: auroc([1 - per_q[q]["c_p"] for q in sq], e2))
            m["aurc_cs_ci"] = _boot_metric(lambda sq, e2: risk_coverage([per_q[q]["c_s"] for q in sq], e2)[0])
            m["aurc_cp_ci"] = _boot_metric(lambda sq, e2: risk_coverage([per_q[q]["c_p"] for q in sq], e2)[0])
            # signal overlap on COMB-12 errors (A5)
            err_q = [q for q in qids if not per_q[q]["comb12_ok"]]
            flagged_s = {q for q in err_q if per_q[q]["c_s"] < 1}
            flagged_p = {q for q in err_q if per_q[q]["c_p"] < 1}
            err_set = set(err_q)
            m["overlap"] = {
                "n_errors": len(err_set),
                "flagged_by_cs": len(flagged_s), "flagged_by_cp": len(flagged_p),
                "flagged_by_both": len(flagged_s & flagged_p),
                "only_cs": len(flagged_s - flagged_p), "only_cp": len(flagged_p - flagged_s),
                "missed_by_both": len(err_set - flagged_s - flagged_p),
                "jaccard": (len(flagged_s & flagged_p) / len(flagged_s | flagged_p))
                           if (flagged_s | flagged_p) else None,
            }
        # strict-threshold fragility (B9): only paraphrases with fresh sim >= 0.80
        try:
            fresh = json.load(open(f"{DATA}/para_sims_fresh.json"))
            n_strict_q = 0
            flips = 0
            for qid, cm in complete.items():
                if qid not in fresh or questions[qid]["instruction_type"] != "stem":
                    continue
                keep = [i + 1 for i, s in enumerate(fresh[qid]) if s >= 0.80]
                if len(keep) < 4:
                    continue
                gold = gold_of(questions[qid])
                pv = [cm[(p, "1")]["answer"] for p in keep]
                sc6 = majority([cm[(0, str(s))]["answer"] for s in range(1, 7)])
                n_strict_q += 1
                flips += int(majority(pv) != sc6)
            m["fragility_strict"] = {"n": n_strict_q, "rate": flips / max(1, n_strict_q)}
        except FileNotFoundError:
            pass
        # token accounting (B8)
        tok = {"sc_call": [], "pe_call": [], "greedy_call": []}
        plens = {"orig": [], "para": []}
        para_data = json.load(open(f"{DATA}/paraphrases.json"))["paraphrases"]
        for qid, cm in complete.items():
            q = questions[qid]
            tok["greedy_call"].append((cm[(0, "g")]["usage"].get("pt") or 0) + (cm[(0, "g")]["usage"].get("ct") or 0))
            for s in range(1, 7):
                tok["sc_call"].append((cm[(0, str(s))]["usage"].get("pt") or 0) + (cm[(0, str(s))]["usage"].get("ct") or 0))
            for p in range(1, 7):
                u = cm[(p, "1")]["usage"]
                tok["pe_call"].append((u.get("pt") or 0) + (u.get("ct") or 0))
            if q["id"] in para_data:
                plens["orig"].append(len(q["stem"]))
                plens["para"] += [len(t) for t in para_data[q["id"]]]
        m["tokens"] = {k: (sum(v) / len(v) if v else None) for k, v in tok.items()}
        if plens["para"]:
            ratios = [p / o for p, o in zip(sorted(plens["para"]), sorted(plens["orig"]) * 6)]
            m["paraphrase_char_ratio_mean"] = sum(plens["para"]) / len(plens["para"]) / (sum(plens["orig"]) / len(plens["orig"]))
        # early stopping simulation (E2): sequential SC, stop at first unanimity
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
        m["early_stop_fixed6"] = early_stop(False)
        # adaptive allocation simulation (B11): probe 2 samples + 2 paras, then branch
        def adaptive():
            accs, budgets = [], []
            for qid, cm in complete.items():
                gold = gold_of(questions[qid])
                s2 = [cm[(0, str(s))]["answer"] for s in (1, 2)]
                p2 = [cm[(p, "1")]["answer"] for p in (1, 2)]
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
        R["models"][alias] = m
        print(f"{alias}: n={m['n']} greedy={m['acc']['greedy']:.3f} sc6={m['acc']['sc6']:.3f} "
              f"pe6={m['acc']['pe6']:.3f} hb6={m['acc']['hb6']:.3f} comb12={m['acc']['comb12']:.3f} "
              f"k1={m['acc']['k1']:.3f} aurc_cs={m.get('aurc_cs')} overlap={m.get('overlap',{}).get('only_cs')}/"
              f"{m.get('overlap',{}).get('only_cp')} es={m['early_stop_unanimous']}")
    return R

# ---------------- parse-failure sensitivity (B7) ----------------
def sensitivity(models):
    out = {}
    for alias in models:
        complete, stats, all_cells = load_model(alias)
        cells = {qid: cm for (m, qid), cm in all_cells.items() if m == alias}
        called_q = sorted(cells)
        incl, excl = set(complete), [q for q in called_q if q not in complete]
        # greedy accuracy on included vs excluded (where greedy parsed)
        def greedy_acc(qs):
            ok = tot = 0
            for qid in qs:
                r = cells[qid].get((0, "g"))
                if r is not None and r["answer"] is not None:
                    tot += 1
                    ok += r["answer"] == gold_of(questions[qid])
            return (ok / tot if tot else None, tot)
        # lenient conditions: majority over available parsed votes (min 4 of 6, 10 of 12)
        lenient = {"sc6": [], "pe6": [], "comb12": []}
        for qid in called_q:
            cm = cells[qid]
            gold = gold_of(questions[qid])
            sv = [cm.get((0, str(s)), {}).get("answer") for s in range(1, 7)]
            pv = [cm.get((p, "1"), {}).get("answer") for p in range(1, 7)]
            sv_ok = [v for v in sv if v is not None]
            pv_ok = [v for v in pv if v is not None]
            if len(sv_ok) >= 4:
                lenient["sc6"].append(majority(sv_ok) == gold)
            if len(pv_ok) >= 4:
                lenient["pe6"].append(majority(pv_ok) == gold)
            cv = [v for v in sv + pv if v is not None]
            if len(sv_ok) >= 4 and len(pv_ok) >= 4:
                lenient["comb12"].append(majority(cv) == gold)
        out[alias] = {
            "n_called": len(called_q), "n_complete": len(complete), "n_excluded": len(excl),
            "unparsed_cells": stats["unparsed"], "parse_rate": stats["parse_rate"],
            "greedy_acc_included": greedy_acc(sorted(incl)),
            "greedy_acc_excluded": greedy_acc(excl),
            "lenient_acc": {k: (sum(v) / len(v) if v else None, len(v)) for k, v in lenient.items()},
        }
    return out

# ---------------- new conditions ----------------
def analyze_greedypara(models):
    out = {}
    for alias in models:
        path = f"{RES}/cond_greedypara/{alias}.jsonl"
        if not os.path.exists(path):
            continue
        cells, _ = load_cells(path)
        main_complete, _, _ = load_model(alias)
        per_q = {}
        for (m, qid), cm in cells.items():
            if m != alias:
                continue
            need = [(p, "g") for p in range(1, 7)]
            if not all(k in cm and cm[k]["answer"] is not None for k in need):
                continue
            gold = gold_of(questions[qid])
            gp_votes = [cm[(p, "g")]["answer"] for p in range(1, 7)]
            if qid not in main_complete:
                continue
            cm_main = main_complete[qid]
            sc_votes = [cm_main[(0, str(s))]["answer"] for s in range(1, 7)]
            pe_votes = [cm_main[(p, "1")]["answer"] for p in range(1, 7)]
            per_q[qid] = {
                "peg6_ok": majority(gp_votes) == gold,
                "c_pg": agreement(gp_votes),
                "greedy_ok": cm_main[(0, "g")]["answer"] == gold,
                "sc6_ok": majority(sc_votes) == gold,
                "pe6_ok": majority(pe_votes) == gold,
                "fragile_greedy": majority(sc_votes) != majority(gp_votes),
                "degenerate_pg": agreement(gp_votes) == 1,
                "degenerate_sc": agreement(sc_votes) == 1,
            }
        if not per_q:
            continue
        qids = sorted(per_q)
        out[alias] = {
            "n": len(qids), "per_q": per_q,
            "acc": {k: sum(per_q[q][k] for q in qids) / len(qids)
                    for k in ("peg6_ok", "greedy_ok", "sc6_ok", "pe6_ok")},
            "fragile_greedy_rate": sum(per_q[q]["fragile_greedy"] for q in qids) / len(qids),
            "degenerate_pg_rate": sum(per_q[q]["degenerate_pg"] for q in qids) / len(qids),
            "mean_c_pg": sum(per_q[q]["c_pg"] for q in qids) / len(qids),
        }
        print(f"greedypara {alias}: n={out[alias]['n']} peg6={out[alias]['acc']['peg6_ok']:.3f} "
              f"pe6={out[alias]['acc']['pe6_ok']:.3f} sc6={out[alias]['acc']['sc6_ok']:.3f} "
              f"frag_greedy={out[alias]['fragile_greedy_rate']:.3f} degen_pg={out[alias]['degenerate_pg_rate']:.3f}")
    return out

def analyze_mmlupro(models):
    out = {}
    for alias in models:
        path = f"{RES}/cond_mmlupro/{alias}.jsonl"
        if not os.path.exists(path):
            continue
        cells, _ = load_cells(path)
        per_q = {}
        for (m, qid), cm in cells.items():
            if m != alias:
                continue
            need = [(0, "g")] + [(0, str(s)) for s in range(1, 7)]
            if not all(k in cm and cm[k]["answer"] is not None for k in need):
                continue
            q = mmlupro_q[qid]
            gold = "ABCDEFGHIJ"[q["answer_idx"]]
            votes = [cm[(0, str(s))]["answer"] for s in range(1, 7)]
            per_q[qid] = {
                "subject": q["subject"],
                "greedy_ok": cm[(0, "g")]["answer"] == gold,
                "sc6_ok": majority(votes) == gold,
                "k1_acc": sum(v == gold for v in votes) / 6.0,
                "c_s": agreement(votes),
                "entropy": norm_entropy(votes),
            }
        if not per_q:
            continue
        qids = sorted(per_q)
        acc = {k: sum(per_q[q][k] for q in qids) / len(qids) for k in ("greedy_ok", "sc6_ok", "k1_acc")}
        out[alias] = {
            "n": len(qids), "per_q": per_q, "acc": acc,
            "degenerate_rate": sum(1 for q in qids if per_q[q]["c_s"] == 1) / len(qids),
            "mean_entropy": sum(per_q[q]["entropy"] for q in qids) / len(qids),
            "mean_c_s": sum(per_q[q]["c_s"] for q in qids) / len(qids),
        }
        print(f"mmlupro {alias}: n={out[alias]['n']} greedy={acc['greedy_ok']:.3f} "
              f"sc6={acc['sc6_ok']:.3f} k1={acc['k1_acc']:.3f} ent={out[alias]['mean_entropy']:.3f} "
              f"degen={out[alias]['degenerate_rate']:.3f}")
    return out

def analyze_cot(models):
    out = {}
    for alias in models:
        path = f"{RES}/cond_cot/{alias}.jsonl"
        if not os.path.exists(path):
            continue
        cells, _ = load_cells(path)
        main_complete, _, _ = load_model(alias)
        per_q = {}
        for (m, qid), cm in cells.items():
            if m != alias:
                continue
            if questions[qid]["dataset"] == "gsm8k":
                continue    # already CoT in the main suite
            gold = gold_of(questions[qid])
            need = [(0, "g")] + [(0, str(s)) for s in range(1, 7)]
            stem = questions[qid]["instruction_type"] == "stem"
            if stem:
                need += [(p, "1") for p in range(1, 7)]
            if not all(k in cm and cm[k]["answer"] is not None for k in need):
                continue
            votes = [cm[(0, str(s))]["answer"] for s in range(1, 7)]
            entry = {
                "greedy_ok": cm[(0, "g")]["answer"] == gold,
                "sc6_ok": majority(votes) == gold,
                "c_s": agreement(votes), "entropy": norm_entropy(votes),
                "degenerate": agreement(votes) == 1,
                "direct_greedy_ok": main_complete[qid][(0, "g")]["answer"] == gold,
                "direct_sc6_ok": majority([main_complete[qid][(0, str(s))]["answer"]
                                           for s in range(1, 7)]) == gold,
                "direct_entropy": norm_entropy([main_complete[qid][(0, str(s))]["answer"]
                                                for s in range(1, 7)]),
            }
            if stem:
                pv = [cm[(p, "1")]["answer"] for p in range(1, 7)]
                entry["pe6_ok"] = majority(pv) == gold
                entry["direct_pe6_ok"] = majority([main_complete[qid][(p, "1")]["answer"]
                                                   for p in range(1, 7)]) == gold
            per_q[qid] = entry
        if not per_q:
            continue
        qids = sorted(per_q)
        stem_q = [q for q in qids if "pe6_ok" in per_q[q]]
        d = {"n": len(qids), "n_stem": len(stem_q), "per_q": per_q,
             "greedy": sum(per_q[q]["greedy_ok"] for q in qids) / len(qids),
             "sc6": sum(per_q[q]["sc6_ok"] for q in qids) / len(qids),
             "direct_greedy": sum(per_q[q]["direct_greedy_ok"] for q in qids) / len(qids),
             "direct_sc6": sum(per_q[q]["direct_sc6_ok"] for q in qids) / len(qids),
             "mean_entropy": sum(per_q[q]["entropy"] for q in qids) / len(qids),
             "mean_direct_entropy": sum(per_q[q]["direct_entropy"] for q in qids) / len(qids),
             "degenerate_rate": sum(per_q[q]["degenerate"] for q in qids) / len(qids)}
        if stem_q:
            d["pe6"] = sum(per_q[q]["pe6_ok"] for q in stem_q) / len(stem_q)
            d["direct_pe6"] = sum(per_q[q]["direct_pe6_ok"] for q in stem_q) / len(stem_q)
        out[alias] = d
        print(f"cot {alias}: n={d['n']} greedy={d['greedy']:.3f} (direct {d['direct_greedy']:.3f}) "
              f"sc6={d['sc6']:.3f} (direct {d['direct_sc6']:.3f}) ent={d['mean_entropy']:.3f} "
              f"(direct {d['mean_direct_entropy']:.3f}) degen={d['degenerate_rate']:.3f}")
    return out

# ---------------- pooled analysis (cluster bootstrap, C1) ----------------
def pooled(R, models=None):
    models = models or [m for m in ["qwen3.8-max", "qwen3.8-omni", "agnes-3.0-flash",
                                    "agnes-2.5-flash"] if m in R["models"]]
    sets = [set(R["models"][m]["per_q"].keys()) for m in models]
    common = sorted(set.intersection(*sets)) if sets else []
    rows = []
    for m in models:
        for qid in common:
            v = R["models"][m]["per_q"][qid]
            rows.append({"model": m, "qid": qid, "ds": v["dataset"], "locus": v["locus"],
                         "greedy": v["greedy_ok"], "sc6": v["sc6_ok"], "pe6": v["pe6_ok"],
                         "hb6": v["hb6_ok"], "comb12": v["comb12_ok"], "entropy": v["entropy"],
                         "entropy_sc": v["entropy_sc"], "entropy_pe": v["entropy_pe"],
                         "c_s": v["c_s"], "c_p": v["c_p"], "fragile": v["fragile"],
                         "k1": v["k1_acc"]})
    n = len(rows)
    out = {"models": models, "n_pairs": n, "n_questions": len(common)}
    for cond in ["sc6", "pe6", "hb6", "comb12", "k1"]:
        out[f"gain_{cond}"] = sum(r[cond] - r["greedy"] for r in rows) / n
        out[f"acc_{cond}"] = sum(r[cond] for r in rows) / n
    out["acc_greedy"] = sum(r["greedy"] for r in rows) / n
    # question-level CLUSTER bootstrap for pooled differences (C1)
    by_q = defaultdict(list)
    for r in rows:
        by_q[r["qid"]].append(r)
    qids = sorted(by_q)
    def cluster_boot(fn, iters=10000, seed=42):
        rng = random.Random(seed)
        vals = []
        for _ in range(iters):
            sq = [qids[rng.randrange(len(qids))] for _ in range(len(qids))]
            sub = [r for q in sq for r in by_q[q]]
            vals.append(fn(sub))
        vals.sort()
        return vals[int(0.025 * iters)], vals[int(0.975 * iters)]
    for a, b in [("sc6", "pe6"), ("sc6", "greedy"), ("pe6", "greedy"), ("comb12", "greedy"), ("hb6", "greedy")]:
        diff = sum(r[a] - r[b] for r in rows) / n
        lo, hi = cluster_boot(lambda sub, a=a, b=b: sum(r[a] - r[b] for r in sub) / len(sub))
        out[f"diff_{a}_vs_{b}"] = diff
        out[f"ci_{a}_vs_{b}"] = [lo, hi]
        # TOST at 3pp and 5pp (90% CI)
        lo90, hi90 = cluster_boot(lambda sub, a=a, b=b: sum(r[a] - r[b] for r in sub) / len(sub),
                                  seed=43)
        out[f"tost_{a}_vs_{b}"] = {"bound3pp": {"ci90": [lo90, hi90], "equivalent": lo90 > -0.03 and hi90 < 0.03},
                                   "bound5pp": {"ci90": [lo90, hi90], "equivalent": lo90 > -0.05 and hi90 < 0.05}}
    # entropy strata
    strata = {"degenerate (H=0)": [], "low (0<H<=0.15)": [], "high (H>0.15)": []}
    for r in rows:
        if r["entropy"] == 0: strata["degenerate (H=0)"].append(r)
        elif r["entropy"] <= 0.15: strata["low (0<H<=0.15)"].append(r)
        else: strata["high (H>0.15)"].append(r)
    out["strata"] = {}
    for name, srows in strata.items():
        if not srows: continue
        d = {"n": len(srows)}
        for cond in ["greedy", "sc6", "pe6", "hb6", "comb12"]:
            d[cond] = sum(r[cond] for r in srows) / len(srows)
        d["fragile"] = sum(r["fragile"] for r in srows) / len(srows)
        out["strata"][name] = d
    # locus strata pooled (B10)
    out["by_locus"] = {}
    for loc in ("stem", "instruction"):
        lrows = [r for r in rows if r["locus"] == loc]
        if not lrows: continue
        out["by_locus"][loc] = {
            "n": len(lrows),
            "gain_sc6": sum(r["sc6"] - r["greedy"] for r in lrows) / len(lrows),
            "gain_pe6": sum(r["pe6"] - r["greedy"] for r in lrows) / len(lrows),
            "fragile": sum(r["fragile"] for r in lrows) / len(lrows),
            "entropy": sum(r["entropy"] for r in lrows) / len(lrows)}
    # spearman entropy-gain (original) + disjoint-vote variants (C4)
    def rank(xs):
        idx = sorted(range(len(xs)), key=lambda i: xs[i])
        rks = [0] * len(xs)
        i = 0
        while i < len(idx):
            j = i
            while j + 1 < len(idx) and xs[idx[j + 1]] == xs[idx[i]]: j += 1
            avg = (i + j) / 2 + 1
            for k2 in range(i, j + 1): rks[idx[k2]] = avg
            i = j + 1
        return rks
    def spearman(xs, ys):
        re_, rg = rank(xs), rank(ys)
        n2 = len(xs)
        mu = (n2 + 1) / 2
        num = sum((a - mu) * (b - mu) for a, b in zip(re_, rg))
        den = math.sqrt(sum((a - mu) ** 2 for a in re_) * sum((b - mu) ** 2 for b in rg))
        return num / den if den else None
    out["spearman_entropy_gain"] = spearman([r["entropy"] for r in rows],
                                            [r["comb12"] - r["greedy"] for r in rows])
    # circularity-robust: entropy from SC votes only vs PE-6 gain (disjoint votes)
    out["spearman_entropysc_pegain"] = spearman([r["entropy_sc"] for r in rows],
                                                [r["pe6"] - r["greedy"] for r in rows])
    out["spearman_entropype_scgain"] = spearman([r["entropy_pe"] for r in rows],
                                                [r["sc6"] - r["greedy"] for r in rows])
    # pooled error detection with cluster bootstrap CIs
    errs = [0 if r["comb12"] else 1 for r in rows]
    if len(set(errs)) > 1:
        out["auroc_cs_pooled"] = auroc([1 - r["c_s"] for r in rows], errs)
        out["auroc_cp_pooled"] = auroc([1 - r["c_p"] for r in rows], errs)
        out["auroc_both_pooled"] = auroc([2 - r["c_s"] - r["c_p"] for r in rows], errs)
        def cluster_boot_auroc(key, iters=2000, seed=42):
            rng = random.Random(seed)
            vals = []
            for _ in range(iters):
                sq = [qids[rng.randrange(len(qids))] for _ in range(len(qids))]
                sub = [r for q in sq for r in by_q[q]]
                e2 = [0 if r["comb12"] else 1 for r in sub]
                if len(set(e2)) < 2:
                    continue
                v = auroc([1 - r[key] for r in sub], e2)
                if v is not None:
                    vals.append(v)
            if not vals:
                return [None, None]
            vals.sort()
            return [vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals))]]
        out["auroc_cs_pooled_ci"] = cluster_boot_auroc("c_s")
        out["auroc_cp_pooled_ci"] = cluster_boot_auroc("c_p")
        # pooled overlap
        err_rows = [r for r in rows if not r["comb12"]]
        fs = {r["qid"] + r["model"] for r in err_rows if r["c_s"] < 1}
        fp = {r["qid"] + r["model"] for r in err_rows if r["c_p"] < 1}
        out["overlap_pooled"] = {
            "n_errors": len(err_rows), "flagged_by_cs": len(fs), "flagged_by_cp": len(fp),
            "only_cs": len(fs - fp), "only_cp": len(fp - fs),
            "flagged_by_both": len(fs & fp), "missed_by_both": len(err_rows) - len(fs | fp)}
    return out

# ---------------- run everything ----------------
if __name__ == "__main__":
    models = ["qwen3.8-max", "qwen3.8-omni", "agnes-3.0-flash",
              "agnes-2.5-flash", "gpt-6-luna", "gemini-3.8-flash"]
    R = analyze_main(models)
    R["sensitivity"] = sensitivity(models)
    R["conditions"] = {
        "greedypara": analyze_greedypara(models),
        "mmlupro": analyze_mmlupro(models),
        "cot": analyze_cot(models),
    }
    R["pooled"] = pooled(R)
    json.dump(R, open(f"{OUT}/results.json", "w"), indent=1)
    json.dump(R["pooled"], open(f"{OUT}/pooled.json", "w"), indent=1)
    P = R["pooled"]
    print("\nPooled:", {k: (round(v, 3) if isinstance(v, float) else v)
                        for k, v in P.items() if not isinstance(v, (dict, list))})
    for name, d in P.get("strata", {}).items():
        print(f"  stratum {name}: n={d['n']} greedy={d['greedy']:.3f} sc6={d['sc6']:.3f} "
              f"pe6={d['pe6']:.3f} comb12={d['comb12']:.3f} frag={d['fragile']:.3f}")
