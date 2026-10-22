#!/usr/bin/env python3
"""Expansion-set analysis: replicate the main-suite per-model metrics on the
independent 119-question set (e000-e119, zero overlap with the main 90).

Computes for each model with data in results/expand/:
  greedy / S1 (mean of 6 P0 samples) / SC-6 / PE-6 / HB-6 / COMB-12
  gains vs S1 and greedy, bootstrap CIs, McNemar, TOST(SC vs PE)
  mode-share strata, off-mode (tau=0 anomaly), SC/PE/COMB tie rates
  early-stop-unanimous and the adaptive allocation rule (same code as v3)
  per-dataset breakdown

Writes results/analysis/expand_v1.json and prints a compact summary.
Seed 42 everywhere; deterministic.
"""
import json, math, os, random
from collections import defaultdict, Counter

DATA = "/home/z/my-project/data"
RES = "/home/z/my-project/results/expand"
OUT = "/home/z/my-project/results/analysis"
os.makedirs(OUT, exist_ok=True)

questions = {q["id"]: q for q in json.load(open(f"{DATA}/questions_expand.json"))}
STEM_DS = {"truthfulqa", "lsat_lr", "logiqa"}
MODELS = ["agnes-3.0-flash", "agnes-2.5-flash", "qwen3.7-flash",
          "deepseek-v4.1-flash", "deepseek-v4-flash-0731"]
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

def mcnemar(b, c):
    if b + c == 0:
        return 1.0
    x = min(b, c)
    n = b + c
    p = sum(math.comb(n, k) for k in range(0, x + 1)) * (0.5 ** n) * 2
    return min(1.0, p)

def boot_ci(values, iters=10000, seed=42, alpha=0.05):
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(iters):
        s = sum(values[rng.randrange(n)] for _ in range(n)) / n
        means.append(s)
    means.sort()
    return sum(values) / n, means[int(alpha / 2 * iters)], means[int((1 - alpha / 2) * iters) - 1]

def tost(diffs, bound, iters=10000, seed=42):
    rng = random.Random(seed)
    n = len(diffs)
    mean = sum(diffs) / n
    lo90 = hi90 = mean
    if n > 1 and (any(d != diffs[0] for d in diffs)):
        means = []
        for _ in range(iters):
            means.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
        means.sort()
        lo90, hi90 = means[int(0.05 * iters)], means[int(0.95 * iters) - 1]
    t1 = (mean - lo90) >= -bound if lo90 != mean else True
    t2 = (hi90 - mean) <= bound if hi90 != mean else True
    return {"mean": mean, "ci90": [lo90, hi90], "within_3pp": bool(-bound <= lo90 and hi90 <= bound)}

# ---------------- per-model expansion analysis ----------------
R = {"set": "expand_v1", "n_questions": len(questions), "models": {}}
for alias in MODELS:
    path = f"{RES}/{alias}.jsonl"
    if not os.path.exists(path):
        continue
    complete, stats = load_model(alias)
    if not complete:
        print(f"{alias}: no complete questions yet, skipped")
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
            "entropy": norm_entropy(sv + pv),
            "sc6_tie": max(s_counts.values()) == 3,
            "comb12_tie": mode_share(sv + pv) == 0.5,
            "off_mode": g not in winners,
            "greedy_ct": gr["usage"].get("ct") if gr.get("usage") else None,
            "greedy_truncated": ((gr.get("usage") or {}).get("ct") or 0) >= 1000,
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
        sv_ok = [majority([cm[(0, str(s))]["answer"] for s in range(1, k + 1)]) ==
                 gold_of(questions[qid]) for qid, cm in complete.items()]
        m[f"acc_sc{k}"] = sum(sv_ok) / len(sv_ok)
        pv_ok = [majority([cm[(p, "1")]["answer"] for p in range(1, k + 1)]) ==
                 gold_of(questions[qid]) for qid, cm in complete.items()]
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
    # CIs
    for cond in ("greedy_ok", "k1_acc", "sc6_ok", "pe6_ok", "hb6_ok", "comb12_ok"):
        m[f"ci_{cond}"] = boot_ci([per_q[q][cond] for q in qids])
    for name, fa, fb in [("sc_vs_greedy", "sc6_ok", "greedy_ok"),
                         ("pe_vs_greedy", "pe6_ok", "greedy_ok")]:
        b = sum(1 for q in qids if per_q[q][fa] and not per_q[q][fb])
        c = sum(1 for q in qids if not per_q[q][fa] and per_q[q][fb])
        m[name + "_p"] = mcnemar(b, c)
    for cond in ("sc6", "pe6", "comb12"):
        mean, lo, hi = boot_ci([per_q[q][f"{cond}_ok"] - per_q[q]["k1_acc"] for q in qids])
        m[f"ci_{cond}_minus_s1"] = [lo, hi]
    # SC vs PE discordance + CI of the gap
    b_sc = sum(1 for q in qids if per_q[q]["sc6_ok"] and not per_q[q]["pe6_ok"])
    c_sc = sum(1 for q in qids if not per_q[q]["sc6_ok"] and per_q[q]["pe6_ok"])
    m["sc_pe_discordant"] = {"sc_only": b_sc, "pe_only": c_sc, "n": n}
    mean, lo, hi = boot_ci([per_q[q]["sc6_ok"] - per_q[q]["pe6_ok"] for q in qids])
    m["ci_sc_minus_pe"] = [lo, hi]
    m["tost3_sc_pe"] = tost([per_q[q]["sc6_ok"] - per_q[q]["pe6_ok"] for q in qids], 0.03)
    m["tost3_questions"] = round(0.03 * n, 1)
    # mode-share strata
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
    # early stopping + adaptive (identical rules to main suite)
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
    ad = m["adaptive_alloc"]
    ad["budget_pct_of_6"] = ad["mean_budget"] / 6
    ad["gap_vs_sc6_q"] = int(round((m["acc"]["sc6_ok"] - ad["acc"]) * n))
    ad["gap_vs_pe6_q"] = int(round((m["acc"]["pe6_ok"] - ad["acc"]) * n))
    ad["gap_vs_hb6_q"] = int(round((m["acc"]["hb6_ok"] - ad["acc"]) * n))
    ad["gap_vs_best_q"] = int(round((max(m["acc"]["sc6_ok"], m["acc"]["pe6_ok"]) - ad["acc"]) * n))
    # adaptive per-question strategy distribution
    def adaptive_detail():
        cnt = Counter()
        for qid, cm in complete.items():
            s2 = [cm[(0, str(s))]["answer"] for s in (1, 2)]
            p2 = [cm[(p, "1")]["answer"] for p in (1, 2)]
            if len(set(s2)) == 1 and len(set(p2)) == 1 and s2[0] == p2[0]:
                cnt["agree4"] += 1
            elif len(set(s2)) == 1 and len(set(p2)) > 1:
                cnt["sc6"] += 1
            elif len(set(p2)) == 1:
                cnt["pe6"] += 1
            else:
                cnt["hb6"] += 1
        return dict(cnt)
    ad["strategy_counts"] = adaptive_detail()
    R["models"][alias] = m
    print(f"{alias}: n={n}/{len(questions)} greedy={m['acc']['greedy_ok']:.3f} S1={m['acc']['k1_acc']:.3f} "
          f"sc6={m['acc']['sc6_ok']:.3f} pe6={m['acc']['pe6_ok']:.3f} hb6={m['acc']['hb6_ok']:.3f} "
          f"comb12={m['acc']['comb12_ok']:.3f}")
    print(f"   gains vs S1: sc6={m['gain_vs_s1_sc6']:+.3f} pe6={m['gain_vs_s1_pe6']:+.3f} "
          f"comb12={m['gain_vs_s1_comb12']:+.3f} | s1-greedy={m['s1_minus_greedy']:+.3f} "
          f"offmode={m['off_mode_n']}/{n} unan={m['unanimous_rate']:.3f}")
    print(f"   sc-pe: gap CI={m['ci_sc_minus_pe']} disc={m['sc_pe_discordant']} "
          f"tost3={m['tost3_sc_pe']['within_3pp']}")
    print(f"   adaptive: acc={ad['acc']:.3f}@{ad['mean_budget']:.2f} calls "
          f"({ad['budget_pct_of_6']*100:.0f}% of 6) gaps: sc6={ad['gap_vs_sc6_q']}q "
          f"pe6={ad['gap_vs_pe6_q']}q best={ad['gap_vs_best_q']}q strategies={ad['strategy_counts']}")

# ---------------- pooled analysis (all models with full 119-question coverage) ----------------
# v1.4.0 hardcoded the two agnes models; v1.5.0 generalizes to every model
# whose complete-question count reaches the full set (currently the two agnes
# flashes plus the apinex deepseek-v4.1-flash rerun).
POOL = [a for a in MODELS
        if a in R["models"] and R["models"][a]["n"] >= 100]
if len(POOL) >= 2:
    common = sorted(set.intersection(*[set(R["models"][a]["per_q"].keys()) for a in POOL]))
    rows = []
    for a in POOL:
        for qid in common:
            v = R["models"][a]["per_q"][qid]
            rows.append({
                "model": a, "qid": qid, "dataset": v["dataset"],
                "greedy_ok": 1 if v["greedy_ok"] else 0, "k1": v["k1_acc"],
                "sc6_ok": 1 if v["sc6_ok"] else 0, "pe6_ok": 1 if v["pe6_ok"] else 0,
                "hb6_ok": 1 if v["hb6_ok"] else 0, "comb12_ok": 1 if v["comb12_ok"] else 0,
            })
    def pooled_ci(field, iters=10000, seed=42):
        # cluster bootstrap on questions (each question carries all pooled models)
        by_q = {}
        for r in rows:
            by_q.setdefault(r["qid"], []).append(r)
        qids = sorted(by_q)
        vals = {qid: sum(r[field] for r in by_q[qid]) / len(by_q[qid]) for qid in qids}
        base = sum(vals.values()) / len(qids)
        rng = random.Random(seed)
        means = []
        for _ in range(iters):
            means.append(sum(vals[qids[rng.randrange(len(qids))]] for _ in range(len(qids))) / len(qids))
        means.sort()
        return base, means[int(0.025 * iters)], means[int(0.975 * iters) - 1]
    pooled = {"n_questions": len(common), "n_pairs": len(rows), "models": POOL}
    for f in ("greedy_ok", "k1", "sc6_ok", "pe6_ok", "hb6_ok", "comb12_ok"):
        base, lo, hi = pooled_ci(f)
        pooled[f] = {"mean": base, "ci95": [lo, hi]}
    for cond in ("sc6", "pe6", "comb12"):
        base, lo, hi = pooled_ci(f"{cond}_ok" if cond != "comb12" else "comb12_ok")
        k1b, _, _ = pooled_ci("k1")
        # CI of the gap via paired cluster bootstrap
        by_q = {}
        for r in rows:
            by_q.setdefault(r["qid"], []).append(r)
        qids = sorted(by_q)
        gaps = {qid: sum(r[f"{cond}_ok"] - r["k1"] for r in by_q[qid]) / len(by_q[qid]) for qid in qids}
        rng = random.Random(43)
        gm = []
        for _ in range(10000):
            gm.append(sum(gaps[qids[rng.randrange(len(qids))]] for _ in range(len(qids))) / len(qids))
        gm.sort()
        pooled[f"gain_vs_s1_{cond}"] = {"mean": sum(gaps.values()) / len(qids),
                                         "ci95": [gm[int(0.025 * 10000)], gm[int(0.975 * 10000) - 1]]}
    R["pooled"] = pooled
    print("\npooled (%s, %d questions, %d pairs):" % (", ".join(POOL), len(common), len(rows)))
    for f in ("greedy_ok", "k1", "sc6_ok", "pe6_ok", "hb6_ok", "comb12_ok"):
        v = pooled[f]
        print(f"  {f:10s} {100*v['mean']:.1f} [{100*v['ci95'][0]:.1f},{100*v['ci95'][1]:.1f}]")
    for cond in ("sc6", "pe6", "comb12"):
        v = pooled[f"gain_vs_s1_{cond}"]
        print(f"  {cond}-S1     {100*v['mean']:+.1f} [{100*v['ci95'][0]:+.1f},{100*v['ci95'][1]:+.1f}]")

# ---------------- cross-model agreement on common questions ----------------
avail = [a for a in MODELS if a in R["models"]]
if len(avail) >= 2:
    common = set.intersection(*[set(R["models"][a]["per_q"].keys()) for a in avail])
    R["common_qids"] = sorted(common)
    R["n_common"] = len(common)
    print(f"\ncommon complete questions across {len(avail)} models: {len(common)}")
    # unanimous (COMB) agreement matrix: how often do all models land on the same answer?
    same_ans = same_ok = 0
    for qid in common:
        answers = [R["models"][a]["per_q"][qid]["comb12"] for a in avail]
        if len(set(answers)) == 1:
            same_ans += 1
    R["comb_agreement_all"] = {"n": len(common), "same_answer": same_ans,
                               "rate": same_ans / len(common)}
    print(f"all-model COMB answer agreement: {same_ans}/{len(common)}")

json.dump(R, open(f"{OUT}/expand_v1.json", "w"), indent=1)
print(f"\nwrote {OUT}/expand_v1.json")
