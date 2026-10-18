#!/usr/bin/env python3
"""Full analysis: derives all conditions from raw logs, computes metrics, statistical tests,
and exports JSON results + LaTeX-ready numbers + matplotlib figures.
Usage: python3 analyze.py [models...]
"""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import json, math, sys, random, glob
from collections import defaultdict, Counter

DATA = ROOT + "/data"
RES = ROOT + "/results"
OUT = ROOT + "/results/analysis"
import os
os.makedirs(OUT, exist_ok=True)

questions = {q["id"]: q for q in json.load(open(f"{DATA}/questions.json"))}

def gold_of(q):
    if q["dataset"] == "gsm8k":
        return str(q["answer"])
    if q["dataset"] == "piqa":
        return str(q["answer_idx"] + 1)
    return "ABCDEFGHIJ"[q["answer_idx"]]

def load_model(alias):
    """Return {qid: {(para, sample): answer}} and {qid: {(para,sample): correct}} for complete matrices."""
    recs = [json.loads(l) for l in open(f"{RES}/{alias}.jsonl")]
    cells = defaultdict(dict)
    n_calls = n_failed = n_unparsed = 0
    for r in recs:
        if r.get("FAILED"):
            n_failed += 1
            continue
        n_calls += 1
        key = (r["para"], str(r["sample"]))
        cells[r["qid"]][key] = r
        if r["answer"] is None:
            n_unparsed += 1
    need = [(0, "g")] + [(0, str(s)) for s in range(1, 7)] + \
           [(p, str(s)) for p in (1, 2, 3) for s in (1, 2)] + [(p, "1") for p in (4, 5, 6)]
    complete = {}
    for qid, cellmap in cells.items():
        if all(k in cellmap and cellmap[k]["answer"] is not None for k in need):
            complete[qid] = {k: cellmap[k] for k in need}
    stats = {"calls": n_calls, "failed": n_failed, "unparsed": n_unparsed,
             "parse_rate": 1 - n_unparsed / max(1, n_calls),
             "complete_questions": len(complete),
             "tokens": {"pt": sum(c["usage"].get("pt") or 0 for cm in complete.values() for c in cm.values()),
                        "ct": sum(c["usage"].get("ct") or 0 for cm in complete.values() for c in cm.values())}}
    return complete, stats

def majority(votes):
    """Majority with tie-break toward earliest vote (canonical first)."""
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
    vs = [v for v in votes if v is not None]
    if len(vs) <= 1:
        return 0.0
    c = Counter(vs)
    h = -sum((n / len(vs)) * math.log(n / len(vs)) for n in c.values())
    return h / math.log(len(c)) if len(c) > 1 else 0.0

def auroc(scores, labels):
    """scores: higher = predicted positive (error). labels: 1=error."""
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
    """AURC: sort by score ascending (low risk first), average error rate of accepted prefixes."""
    pairs = sorted([(s, e) for s, e in zip(scores, errors) if s is not None])
    n = len(pairs)
    if n == 0:
        return None, None
    cum_err, total = 0.0, 0
    aurc = 0.0
    for i, (s, e) in enumerate(pairs):
        cum_err += e
        total += 1
        aurc += cum_err / total
    aurc /= n
    # E-AURC: oracle ranking (all correct first)
    sorted_err = sorted(e for _, e in pairs)
    cum, o_total, o_aurc = 0.0, 0, 0.0
    for e in sorted_err:
        cum += e
        o_total += 1
        o_aurc += cum / o_total
    o_aurc /= n
    return aurc, aurc - o_aurc

def mcnemar(b, c):
    """Exact binomial McNemar p-value for discordant counts b, c."""
    n = b + c
    if n == 0:
        return 1.0
    from math import comb
    k = min(b, c)
    p = sum(comb(n, i) for i in range(0, k + 1)) / 2**n * 2
    return min(1.0, p)

def bootstrap_ci_diff(paired, iters=10000, seed=42):
    """paired: list of (correct_A, correct_B). Returns (mean_diff, lo, hi)."""
    rng = random.Random(seed)
    n = len(paired)
    if n == 0:
        return (None, None, None)
    diffs = [a - b for a, b in paired]
    mean = sum(diffs) / n
    boots = []
    for _ in range(iters):
        s = [paired[rng.randrange(n)] for _ in range(n)]
        boots.append(sum(a - b for a, b in s) / n)
    boots.sort()
    return mean, boots[int(0.025 * iters)], boots[int(0.975 * iters)]

# ---------------- main analysis ----------------
def analyze(models):
    R = {"models": {}, "pooled": {}}
    for alias in models:
        complete, stats = load_model(alias)
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
                "dataset": q["dataset"], "gold": gold,
                "greedy": g, "greedy_ok": g == gold,
                "sc": {k: (v, v == gold) for k, v in sc.items()},
                "pe": {k: (v, v == gold) for k, v in pe.items()},
                "hb6": (hb, hb == gold), "comb12": (comb, comb == gold),
                "c_s": agreement(sc_votes), "c_p": agreement(pe_votes),
                "entropy": norm_entropy(sc_votes + pe_votes),
                "fragile": sc[6] != pe[6],
                "sc6_ok": sc[6] == gold, "pe6_ok": pe[6] == gold,
                "greedy_ok": g == gold, "comb12_ok": comb == gold, "hb6_ok": hb == gold,
            }
        # aggregate metrics
        qids = sorted(per_q)
        m = {"stats": stats, "n": len(qids), "per_q": per_q}
        def acc(f):
            vals = [per_q[q][f] for q in qids if per_q[q][f] is not None]
            return sum(vals) / len(vals) if vals else None
        m["acc"] = {
            "greedy": acc("greedy_ok"), "sc6": acc("sc6_ok"), "pe6": acc("pe6_ok"),
            "hb6": acc("hb6_ok"), "comb12": acc("comb12_ok"),
            "sc2": sum(1 for q in qids if per_q[q]["sc"][2][1]) / len(qids),
            "sc4": sum(1 for q in qids if per_q[q]["sc"][4][1]) / len(qids),
            "pe2": sum(1 for q in qids if per_q[q]["pe"][2][1]) / len(qids),
            "pe4": sum(1 for q in qids if per_q[q]["pe"][4][1]) / len(qids),
        }
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
        # paired comparisons
        pair_scpe = [(per_q[q]["sc6_ok"], per_q[q]["pe6_ok"]) for q in qids]
        b = sum(1 for a1, b1 in pair_scpe if a1 and not b1)
        c = sum(1 for a1, b1 in pair_scpe if not a1 and b1)
        mcn = mcnemar(b, c)
        diff, lo, hi = bootstrap_ci_diff(pair_scpe)
        m["sc_vs_pe"] = {"b": b, "c": c, "p": mcn, "diff": diff, "ci": [lo, hi]}
        pair_greedy_sc = [(per_q[q]["sc6_ok"], per_q[q]["greedy_ok"]) for q in qids]
        b2 = sum(1 for a1, b1 in pair_greedy_sc if a1 and not b1)
        c2 = sum(1 for a1, b1 in pair_greedy_sc if not a1 and b1)
        m["sc_vs_greedy"] = {"b": b2, "c": c2, "p": mcnemar(b2, c2)}
        pair_greedy_pe = [(per_q[q]["pe6_ok"], per_q[q]["greedy_ok"]) for q in qids]
        b3 = sum(1 for a1, b1 in pair_greedy_pe if a1 and not b1)
        c3 = sum(1 for a1, b1 in pair_greedy_pe if not a1 and b1)
        m["pe_vs_greedy"] = {"b": b3, "c": c3, "p": mcnemar(b3, c3)}
        # fragility & degeneracy
        m["fragile_rate"] = sum(per_q[q]["fragile"] for q in qids) / len(qids)
        m["degenerate_rate"] = sum(1 for q in qids if per_q[q]["c_s"] == 1 and per_q[q]["c_p"] == 1) / len(qids)
        m["degenerate_s_only"] = sum(1 for q in qids if per_q[q]["c_s"] == 1) / len(qids)
        m["mean_entropy"] = sum(per_q[q]["entropy"] for q in qids) / len(qids)
        m["mean_c_s"] = sum(per_q[q]["c_s"] for q in qids) / len(qids)
        m["mean_c_p"] = sum(per_q[q]["c_p"] for q in qids) / len(qids)
        # error detection (reference = comb12)
        errs = [0 if per_q[q]["comb12_ok"] else 1 for q in qids]
        m["err_rate"] = sum(errs) / len(errs)
        if len(set(errs)) > 1:
            m["auroc_cs"] = auroc([1 - per_q[q]["c_s"] for q in qids], errs)
            m["auroc_cp"] = auroc([1 - per_q[q]["c_p"] for q in qids], errs)
            m["auroc_both"] = auroc([2 - per_q[q]["c_s"] - per_q[q]["c_p"] for q in qids], errs)
            aurc, eaurc = risk_coverage([per_q[q]["c_s"] for q in qids], errs)
            m["aurc_cs"], m["eaurc_cs"] = aurc, eaurc
            aurc2, eaurc2 = risk_coverage([per_q[q]["c_p"] for q in qids], errs)
            m["aurc_cp"], m["eaurc_cp"] = aurc2, eaurc2
            aurc3, eaurc3 = risk_coverage([(per_q[q]["c_s"] + per_q[q]["c_p"]) / 2 for q in qids], errs)
            m["aurc_both"], m["eaurc_both"] = aurc3, eaurc3
        R["models"][alias] = m
        print(f"{alias}: n={m['n']} greedy={m['acc']['greedy']:.3f} sc6={m['acc']['sc6']:.3f} "
              f"pe6={m['acc']['pe6']:.3f} hb6={m['acc']['hb6']:.3f} comb12={m['acc']['comb12']:.3f} "
              f"frag={m['fragile_rate']:.3f} degen={m['degenerate_rate']:.3f} ent={m['mean_entropy']:.3f} "
              f"auroc_cs={m.get('auroc_cs')} auroc_cp={m.get('auroc_cp')}")
    json.dump(R, open(f"{OUT}/results.json", "w"), indent=1)
    return R

if __name__ == "__main__":
    models = sys.argv[1].split(",") if len(sys.argv) > 1 else ["qwen3.8-max", "qwen3.8-omni", "agnes-3.0-flash",
                              "agnes-2.5-flash", "gpt-6-luna", "gemini-3.8-flash"]
    analyze(models)

def pooled(models=None):
    """Pooled analysis over (model, question) pairs on the common question set."""
    from collections import Counter
    models = models or [m for m in ["qwen3.8-max", "qwen3.8-omni", "agnes-3.0-flash", "agnes-2.5-flash"]
                        if m in R["models"]]
    # intersection of complete questions
    sets = [set(R["models"][m]["per_q"].keys()) for m in models]
    common = sorted(set.intersection(*sets)) if sets else []
    rows = []
    for m in models:
        for qid in common:
            v = R["models"][m]["per_q"][qid]
            rows.append({"model": m, "qid": qid, "ds": v["dataset"],
                         "greedy": v["greedy_ok"], "sc6": v["sc6_ok"], "pe6": v["pe6_ok"],
                         "hb6": v["hb6_ok"], "comb12": v["comb12_ok"], "entropy": v["entropy"],
                         "c_s": v["c_s"], "c_p": v["c_p"], "fragile": v["fragile"]})
    n = len(rows)
    out = {"models": models, "n_pairs": n, "n_questions": len(common)}
    for cond in ["sc6", "pe6", "hb6", "comb12"]:
        gains = [r[cond] - r["greedy"] for r in rows]
        out[f"gain_{cond}"] = sum(gains) / n
        out[f"acc_{cond}"] = sum(r[cond] for r in rows) / n
        out[f"acc_greedy"] = sum(r["greedy"] for r in rows) / n
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
    # correlation entropy vs comb gain (spearman)
    try:
        def rank(xs):
            idx = sorted(range(len(xs)), key=lambda i: xs[i])
            rks = [0]*len(xs)
            i = 0
            while i < len(idx):
                j = i
                while j+1 < len(idx) and xs[idx[j+1]] == xs[idx[i]]: j += 1
                avg = (i + j)/2 + 1
                for k2 in range(i, j+1): rks[idx[k2]] = avg
                i = j+1
            return rks
        import math
        es = [r["entropy"] for r in rows]
        gs = [r["comb12"] - r["greedy"] for r in rows]
        re_, rg = rank(es), rank(gs)
        n2 = len(es)
        mu = (n2+1)/2
        num = sum((a-mu)*(b-mu) for a, b in zip(re_, rg))
        den = math.sqrt(sum((a-mu)**2 for a in re_) * sum((b-mu)**2 for b in rg))
        out["spearman_entropy_gain"] = num/den if den else None
    except Exception as e:
        out["spearman_entropy_gain"] = None
    # bootstrap CI for pooled SC-PE difference
    rng = random.Random(42)
    diffs = [r["sc6"] - r["pe6"] for r in rows]
    n3 = len(diffs)
    boots = []
    for _ in range(10000):
        s = [diffs[rng.randrange(n3)] for _ in range(n3)]
        boots.append(sum(s) / n3)
    boots.sort()
    out["sc_vs_pe_pooled_diff"] = sum(diffs) / n3
    out["sc_vs_pe_pooled_ci"] = [boots[250], boots[9750]]
    # pooled error detection on comb12 errors
    errs = [0 if r["comb12"] else 1 for r in rows]
    if len(set(errs)) > 1:
        out["auroc_cs_pooled"] = auroc([1 - r["c_s"] for r in rows], errs)
        out["auroc_cp_pooled"] = auroc([1 - r["c_p"] for r in rows], errs)
        out["auroc_both_pooled"] = auroc([2 - r["c_s"] - r["c_p"] for r in rows], errs)
    json.dump(out, open(f"{OUT}/pooled.json", "w"), indent=1)
    print("\nPooled:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in out.items() if not isinstance(v, (dict, list))})
    for name, d in out.get("strata", {}).items():
        print(f"  stratum {name}: n={d['n']} greedy={d['greedy']:.3f} sc6={d['sc6']:.3f} pe6={d['pe6']:.3f} comb12={d['comb12']:.3f} frag={d['fragile']:.3f}")
    return out
