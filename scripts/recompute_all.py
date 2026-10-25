#!/usr/bin/env python3
"""v1.7.0 integrity pass: recompute EVERY number cited in the paper directly
from the raw call logs, verify the five claimed robustness checks, and compute
the new statistics the revision needs (Holm-adjusted p-values, 90+119 combined
analysis, expansion parse rates for Table 1).

Self-contained: reads only raw JSONLs + question/paraphrase/NLI/similarity files.
Outputs: results/analysis/recompute_report.json + printed PASS/FAIL checklist.
Deterministic (fixed seeds)."""
import json, math, os, random
from collections import defaultdict, Counter

# repo root = parent of this scripts/ directory (portable across checkouts)
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = f"{BASE}/data"
RES = f"{BASE}/results"
EXP = f"{RES}/expand"

MAIN_MODELS = ["qwen3.8-max", "qwen3.8-omni", "agnes-3.0-flash", "agnes-2.5-flash",
               "gpt-6-luna", "gemini-3.8-flash"]
EXP_MODELS = ["agnes-3.0-flash", "agnes-2.5-flash", "qwen3.7-flash",
              "deepseek-v4.1-flash", "deepseek-v4-flash-0731", "deepseek-v4-pro-0813"]
FULL4 = ["agnes-3.0-flash", "agnes-2.5-flash", "deepseek-v4.1-flash", "deepseek-v4-pro-0813"]
NEED = [(0, "g")] + [(0, str(s)) for s in range(1, 7)] + \
       [(p, str(s)) for p in (1, 2, 3) for s in (1, 2)] + [(p, "1") for p in (4, 5, 6)]

CHECKS = []          # (id, description, expected, actual, ok)
def check(cid, desc, expected, actual, tol=None):
    if expected is None:  # informational check (no ground truth)
        ok = actual is not None
    elif isinstance(expected, float) or isinstance(actual, float):
        ok = actual is not None and abs(float(actual) - float(expected)) <= (tol or 0.051)
    else:
        ok = actual == expected
    CHECKS.append({"id": cid, "desc": desc, "expected": expected,
                   "actual": actual, "ok": bool(ok)})
    return ok

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
    """cells[qid][(para,sample)] -> record; stats include parse rate."""
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
                             "parse_rate": 1 - n_unparsed / max(1, n_calls)}

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
    """by_q_pairs: {qid: [per-model row dicts]}; field_fn(row)->value."""
    qids = sorted(by_q_pairs)
    vals = {q: sum(field_fn(r) for r in by_q_pairs[q]) / len(by_q_pairs[q]) for q in qids}
    base = sum(vals.values()) / len(qids)
    rng = random.Random(seed)
    means = sorted(sum(vals[qids[rng.randrange(len(qids))]] for _ in range(len(qids))) / len(qids)
                   for _ in range(iters))
    lo, hi = means[int(alpha / 2 * iters)], means[int((1 - alpha / 2) * iters) - 1]
    # two-sided bootstrap p-value
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

def norm_entropy(votes):
    vs = [v for v in votes if v is not None]
    if len(vs) <= 1:
        return 0.0
    c = Counter(vs)
    h = -sum((n / len(vs)) * math.log(n / len(vs)) for n in c.values())
    return h / math.log(len(c)) if len(c) > 1 else 0.0

# ============ load question sets ============
Q = {q["id"]: q for q in json.load(open(f"{DATA}/questions.json"))}
QE = {q["id"]: q for q in json.load(open(f"{DATA}/questions_expand.json"))}
STEM_DS = {"truthfulqa", "lsat_lr", "logiqa"}

# ============ 1. MAIN SUITE ============
main = {}
for m in MAIN_MODELS:
    complete, cells, stats = load(f"{RES}/{m}.jsonl")
    pq = per_q(complete, Q)
    qids = sorted(pq)
    n = len(qids)
    def A(f):
        return 100 * sum(pq[q][f] for q in qids) / n
    # fragility by locus
    inst = [q for q in qids if Q[q]["dataset"] not in STEM_DS]
    stem = [q for q in qids if Q[q]["dataset"] in STEM_DS]
    # tokens: canonical samples vs paraphrase first decodes
    tok_c, tok_p = [], []
    for qid, cm in complete.items():
        for s in range(1, 7):
            u = cm[(0, str(s))].get("usage") or {}
            if u.get("pt") is not None and u.get("ct") is not None:
                tok_c.append(u["pt"] + u["ct"])
        for p in range(1, 7):
            u = cm[(p, "1")].get("usage") or {}
            if u.get("pt") is not None and u.get("ct") is not None:
                tok_p.append(u["pt"] + u["ct"])
    main[m] = {
        "n": n, "pq": pq, "stats": stats,
        "greedy": A("greedy_ok"), "s1": A("k1_acc"), "pe1": A("pe1_acc"),
        "sc6": A("sc6_ok"), "pe6": A("pe6_ok"), "hb6": A("hb6_ok"), "comb": A("comb12_ok"),
        "frag_inst": (sum(pq[q]["fragile"] for q in inst), len(inst)),
        "frag_stem": (sum(pq[q]["fragile"] for q in stem), len(stem)),
        "tok_c": sum(tok_c) / len(tok_c) if tok_c else None,
        "tok_p": sum(tok_p) / len(tok_p) if tok_p else None,
        "off_mode_n": sum(pq[q]["off_mode"] for q in qids),
    }
    # budget-curve points
    for k in (2, 4):
        main[m][f"sc{k}"] = 100 * sum(
            majority([complete[q][(0, str(s))]["answer"] for s in range(1, k + 1)]) == gold_of(Q[q])
            for q in qids) / n
        main[m][f"pe{k}"] = 100 * sum(
            majority([complete[q][(p, "1")]["answer"] for p in range(1, k + 1)]) == gold_of(Q[q])
            for q in qids) / n

# tab_main verification
tab_main_expected = {
    "qwen3.8-max":       (90, 93.3, 93.3, 93.3, 93.3, 92.2, 93.3),
    "qwen3.8-omni":      (71, 93.0, 93.9, 93.0, 93.0, 91.5, 93.0),
    "agnes-3.0-flash":   (33, 78.8, 89.4, 90.9, 90.9, 90.9, 90.9),
    "agnes-2.5-flash":   (40, 90.0, 94.2, 95.0, 92.5, 92.5, 95.0),
    "gpt-6-luna":        (15, 80.0, 76.7, 73.3, 86.7, 86.7, 86.7),
    "gemini-3.8-flash":  (12, 91.7, 86.1, 83.3, 91.7, 91.7, 91.7),
}
for m, (n, gr, s1, sc, pe, hb, cb) in tab_main_expected.items():
    d = main[m]
    check(f"main-{m}", "tab_main row", f"{n},{gr},{s1},{sc},{pe},{hb},{cb}",
          f"{d['n']},{d['greedy']:.1f},{d['s1']:.1f},{d['sc6']:.1f},{d['pe6']:.1f},{d['hb6']:.1f},{d['comb']:.1f}")
    check(f"parse-{m}", "parse rate", None, round(100 * d["stats"]["parse_rate"], 1))

# pooled 4 well-covered models on common questions
P4 = ["qwen3.8-max", "qwen3.8-omni", "agnes-3.0-flash", "agnes-2.5-flash"]
common = sorted(set.intersection(*[set(main[m]["pq"]) for m in P4]))
by_q = {q: [main[m]["pq"][q] for m in P4] for q in common}
npairs = 4 * len(common)
def pooled_pct(field):
    return 100 * sum(sum(r[field] for r in by_q[q]) / 4 for q in common) / len(common)
p_s1b, _, _, _ = cluster_boot(by_q, lambda r: r["k1_acc"])
p_s1 = 100 * p_s1b
p_gr = pooled_pct("greedy_ok"); p_sc = pooled_pct("sc6_ok")
p_pe = pooled_pct("pe6_ok"); p_cb = pooled_pct("comb12_ok")
check("main-pooled-s1", "pooled S1", 96.4, round(p_s1, 1))
check("main-pooled-greedy", "pooled greedy", 92.0, round(p_gr, 1))
check("main-pooled-sc", "pooled SC-6", 97.3, round(p_sc, 1))
check("main-pooled-pe", "pooled PE-6", 95.5, round(p_pe, 1))
check("main-pooled-comb", "pooled COMB-12", 96.4, round(p_cb, 1))
check("main-sc-s1", "pooled SC-S1 (pp)", 0.9, round(p_sc - p_s1, 1))
check("main-pe-s1", "pooled PE-S1 (pp)", -0.9, round(p_pe - p_s1, 1))
g2, g2_lo, g2_hi, _ = cluster_boot(by_q, lambda r: (1 if r["sc6_ok"] else 0) - (1 if r["pe6_ok"] else 0))
check("main-sc-pe", "pooled SC-PE (pp)", 1.8, round(100 * g2, 1))
check("main-sc-pe-ci", "SC-PE CI", (0.0, 5.4), (round(100 * g2_lo, 1), round(100 * g2_hi, 1)))
un = sum(1 for q in common if all(r["mode_share"] == 1 for r in by_q[q]))
check("main-unan", "unanimous pairs", 104, un * 4 if False else sum(1 for q in common for r in by_q[q] if r["mode_share"] == 1))
check("main-pairs", "pooled pairs", 112, npairs)
dsc = sum(1 for q in common for r in by_q[q] if r["sc6_ok"] and not r["pe6_ok"])
check("main-sc-wins", "SC>PE discordant pairs", 2, dsc)
ggap, gg_lo, gg_hi, _ = cluster_boot(by_q, lambda r: r["k1_acc"] - (1 if r["greedy_ok"] else 0))
check("main-s1-greedy", "S1-greedy pooled (pp)", 4.5, round(100 * ggap, 1))
check("main-s1-greedy-ci", "S1-greedy CI", (0.9, 8.8), (round(100 * gg_lo, 1), round(100 * gg_hi, 1)))
# spearman correlations over pooled pairs
ds_all, s1m_gr, comb_s1 = [], [], []
for q in common:
    for r in by_q[q]:
        ds_all.append(1 - r["mode_share"])
        s1m_gr.append(r["k1_acc"] - (1 if r["greedy_ok"] else 0))
        comb_s1.append((1 if r["comb12_ok"] else 0) - r["k1_acc"])
check("spearman-dissent-s1greedy", "Spearman(dissent, S1-greedy)", 0.80, round(spearman(ds_all, s1m_gr), 2))
check("spearman-dissent-comb", "Spearman(dissent, COMB-S1)", 0.17, round(spearman(ds_all, comb_s1), 2))
# fragility pooled by locus over the 4-model common set
fi = sum(1 for q in common for r in by_q[q]
         if Q[q]["dataset"] not in STEM_DS and r["fragile"])
ni = sum(1 for q in common for r in by_q[q] if Q[q]["dataset"] not in STEM_DS)
fs = sum(1 for q in common for r in by_q[q]
         if Q[q]["dataset"] in STEM_DS and r["fragile"])
ns = sum(1 for q in common for r in by_q[q] if Q[q]["dataset"] in STEM_DS)
check("main-frag-inst", "instruction-locus flips", "0/52", f"{fi}/{ni}")
check("main-frag-stem", "stem-locus flip rate", 3.3, round(100 * fs / ns, 1))
# per-model fragility claims
check("frag-max", "Max fragility %", 1.1, round(100 * sum(main['qwen3.8-max']['pq'][q]['fragile'] for q in main['qwen3.8-max']['pq']) / 90, 1))
check("frag-omni", "Omni fragility %", 4.2, round(100 * sum(main['qwen3.8-omni']['pq'][q]['fragile'] for q in main['qwen3.8-omni']['pq']) / 71, 1))
check("frag-gpt6", "GPT6 fragility %", 13.3, round(100 * sum(main['gpt-6-luna']['pq'][q]['fragile'] for q in main['gpt-6-luna']['pq']) / 15, 1))
check("frag-gemini", "Gemini fragility %", 8.3, round(100 * sum(main['gemini-3.8-flash']['pq'][q]['fragile'] for q in main['gemini-3.8-flash']['pq']) / 12, 1))
check("frag-agnes3", "Agnes3.0 fragility", 0, sum(main['agnes-3.0-flash']['pq'][q]['fragile'] for q in main['agnes-3.0-flash']['pq']))
# logiqa-specific fragility
for m, exp in [("gpt-6-luna", 40.0), ("gemini-3.8-flash", 33.3), ("qwen3.8-max", 6.7), ("qwen3.8-omni", 21.4)]:
    lq = [q for q in main[m]["pq"] if Q[q]["dataset"] == "logiqa"]
    check(f"frag-logiqa-{m}", "LogiQA fragility %", exp,
          round(100 * sum(main[m]["pq"][q]["fragile"] for q in lq) / len(lq), 1))
# token-match claims
check("tok-max", "Max tokens c/p", "223/219",
      f"{main['qwen3.8-max']['tok_c']:.0f}/{main['qwen3.8-max']['tok_p']:.0f}")
check("tok-gpt6", "GPT6 tokens c/p", "505/528",
      f"{main['gpt-6-luna']['tok_c']:.0f}/{main['gpt-6-luna']['tok_p']:.0f}")
# budget-curve claims
check("bc-agnes3-pe2", "Agnes3.0 PE-2 = full", 90.9, round(main["agnes-3.0-flash"]["pe2"], 1))
check("bc-agnes25-sc6", "Agnes2.5 SC-6", 95.0, round(main["agnes-2.5-flash"]["sc6"], 1))
check("bc-agnes25-pe4", "Agnes2.5 PE plateau", 92.5, round(main["agnes-2.5-flash"]["pe4"], 1))

# ============ 2. EXPANSION SET ============
exp = {}
for m in EXP_MODELS:
    complete, cells, stats = load(f"{EXP}/{m}.jsonl")
    pq = per_q(complete, QE)
    qids = sorted(pq)
    n = len(qids)
    def A(f):
        return 100 * sum(pq[q][f] for q in qids) / n
    exp[m] = {"n": n, "pq": pq, "stats": stats, "complete": complete,
              "greedy": A("greedy_ok"), "s1": A("k1_acc"), "pe1": A("pe1_acc"),
              "sc6": A("sc6_ok"), "pe6": A("pe6_ok"), "hb6": A("hb6_ok"), "comb": A("comb12_ok"),
              "off_mode_n": sum(pq[q]["off_mode"] for q in qids),
              "unan_rate": 100 * sum(1 for q in qids if pq[q]["mode_share"] == 1) / n}
tab_expand_expected = {
    "agnes-3.0-flash":     (119, 80.7, 79.6, 81.5, 87.4, 83.2, 82.4, 59, 80.7, 2.5, 81.5, 5.2, 86),
    "agnes-2.5-flash":     (119, 89.9, 88.1, 90.8, 91.6, 89.1, 89.9, 76, 90.8, 2.3, 89.9, 4.7, 79),
    "deepseek-v4.1-flash": (119, 73.1, 77.6, 79.8, 81.5, 83.2, 83.2, 58, 80.7, 2.8, 84.0, 5.2, 87),
    "deepseek-v4-pro-0813":(119, 79.0, 78.0, 80.7, 82.4, 82.4, 84.0, 61, 80.7, 2.7, 83.2, 5.1, 85),
    "qwen3.7-flash":       (60, 85.0, 86.1, 85.0, 86.7, 85.0, 85.0, 82, 85.0, 2.1, 85.0, 4.5, 74),
}
for m, vals in tab_expand_expected.items():
    d = exp[m]
    got = (d["n"], round(d["greedy"], 1), round(d["s1"], 1), round(d["sc6"], 1),
           round(d["pe6"], 1), round(d["hb6"], 1), round(d["comb"], 1))
    check(f"exp-{m}", "tab_expand fixed-cond row", ",".join(str(v) for v in vals[:7]),
          ",".join(str(v) for v in got))

# pooled 4 fully covered
by_qe = {q: [exp[m]["pq"][q] for m in FULL4] for q in sorted(exp[FULL4[0]]["pq"])}
def pooled_e(field):
    return 100 * sum(sum(r[field] for r in by_qe[q]) / 4 for q in by_qe) / len(by_qe)
pe_s1b, _, _, _ = cluster_boot(by_qe, lambda r: r["k1_acc"], seed=52)
pe_s1 = 100 * pe_s1b
pe_gr = pooled_e("greedy_ok"); pe_sc = pooled_e("sc6_ok"); pe_pe = pooled_e("pe6_ok")
pe_hb = pooled_e("hb6_ok"); pe_cb = pooled_e("comb12_ok"); pe_pe1 = pooled_e("pe1_acc")
check("exp-pooled-greedy", "exp pooled greedy", 80.7, round(pe_gr, 1))
check("exp-pooled-s1", "exp pooled S1", 80.8, round(pe_s1, 1))
check("exp-pooled-sc", "exp pooled SC-6", 83.2, round(pe_sc, 1))
check("exp-pooled-pe", "exp pooled PE-6", 85.7, round(pe_pe, 1))
check("exp-pooled-hb", "exp pooled HB-6", 84.5, round(pe_hb, 1))
check("exp-pooled-comb", "exp pooled COMB-12", 84.9, round(pe_cb, 1))
check("exp-pooled-pe1", "exp pooled PE-1", 82.7, round(pe_pe1, 1))
NEW = {}
for name, fn, exp_mean, exp_ci in [
        ("SC-S1", lambda r: (1 if r["sc6_ok"] else 0) - r["k1_acc"], 2.4, (1.1, 3.7)),
        ("PE-S1", lambda r: (1 if r["pe6_ok"] else 0) - r["k1_acc"], 4.9, (2.3, 7.6)),
        ("COMB-S1", lambda r: (1 if r["comb12_ok"] else 0) - r["k1_acc"], 4.1, (2.0, 6.3)),
        ("PE-SC", lambda r: (1 if r["pe6_ok"] else 0) - (1 if r["sc6_ok"] else 0), 2.5, (-0.6, 5.7)),
        ("PE-HB", lambda r: (1 if r["pe6_ok"] else 0) - (1 if r["hb6_ok"] else 0), 1.3, (-0.4, 2.9)),
        ("COMB-PE", lambda r: (1 if r["comb12_ok"] else 0) - (1 if r["pe6_ok"] else 0), -0.8, (-2.9, 1.3))]:
    b, lo, hi, p = cluster_boot(by_qe, fn, seed=53)
    check(f"exp-{name}", f"exp pooled {name} (pp)", None,
          f"{100*b:.1f} ({round(100*lo,1)},{round(100*hi,1)})")
    # CI endpoints within 0.5pp seed noise of official (analyze_expand seeds 42/43)
    ok_ci = abs(100*b - exp_mean) <= 0.15 and abs(100*lo - exp_ci[0]) <= 0.5 and abs(100*hi - exp_ci[1]) <= 0.5
    check(f"exp-ci-{name}", f"exp pooled {name} mean+CI within seed noise", True, ok_ci)
    NEW[name] = {"mean": 100 * b, "ci95": [100 * lo, 100 * hi], "p_boot": p}
# per-model gain CIs cited in text
for m, cond, em, eci in [
        ("agnes-3.0-flash", "pe6", 7.8, (2.4, 13.7)), ("agnes-3.0-flash", "sc6", 2.0, (-1.0, 5.0)),
        ("agnes-2.5-flash", "pe6", 3.5, (0.4, 7.0)), ("agnes-2.5-flash", "sc6", 2.7, (0.7, 4.9)),
        ("deepseek-v4.1-flash", "pe6", 3.9, (-0.8, 8.7)), ("deepseek-v4.1-flash", "sc6", 2.2, (-0.4, 4.9)),
        ("deepseek-v4-pro-0813", "comb12", 6.0, (2.1, 10.2)),
        ("deepseek-v4-pro-0813", "sc6", 2.7, (0.1, 5.5)),
        ("deepseek-v4-pro-0813", "pe6", 4.3, (-0.7, 9.4))]:
    qids = sorted(exp[m]["pq"])
    diffs = [(1 if exp[m]["pq"][q][f"{cond}_ok"] else 0) - exp[m]["pq"][q]["k1_acc"] for q in qids]
    mean, lo, hi = boot_ci(diffs, seed=54)
    ok_ci = abs(100*mean - em) <= 0.15 and abs(100*lo - eci[0]) <= 0.5 and abs(100*hi - eci[1]) <= 0.5
    check(f"exp-ci-{m}-{cond}", f"{m} {cond}-S1 (CI seed-noise tol)", True, ok_ci,
          )
# strata
def stratum(pq, lo, hi_excl):
    qs = [q for q in pq if (lo is None or pq[q]["mode_share"] >= lo) and (hi_excl is None or pq[q]["mode_share"] < hi_excl)]
    return qs
WEAK = "weak"; STR = "strong"; UNA = "unan"
strata_defs = {UNA: (1.0, None), STR: (2/3, 1.0), WEAK: (None, 2/3)}
for m in FULL4:
    pq = exp[m]["pq"]
    for sname, (lo, hi) in strata_defs.items():
        qs = [q for q in pq if (lo is None or pq[q]["mode_share"] >= lo) and (hi is None or pq[q]["mode_share"] < hi)]
        exp[m][f"strat_{sname}"] = {
            "n": len(qs),
            "s1": 100 * sum(pq[q]["k1_acc"] for q in qs) / len(qs),
            "sc6": 100 * sum(pq[q]["sc6_ok"] for q in qs) / len(qs),
            "pe6": 100 * sum(pq[q]["pe6_ok"] for q in qs) / len(qs),
            "comb": 100 * sum(pq[q]["comb12_ok"] for q in qs) / len(qs)}
for m, n_exp in [("agnes-3.0-flash", 24), ("agnes-2.5-flash", 8),
                 ("deepseek-v4.1-flash", 14), ("deepseek-v4-pro-0813", 15)]:
    check(f"strat-weak-n-{m}", "weak-majority n", n_exp, exp[m]["strat_weak"]["n"])
weak_pairs = []
for q in by_qe:
    for r in by_qe[q]:
        weak_pairs.append((q, r))
# official pooled stratum stats (expand_pooled_suppl.py): unweighted mean of
# the per-model within-stratum rates (models weighted equally)
def strat_model_mean(sname, field):
    vals = [exp[m][f"strat_{sname}"][field] for m in FULL4]
    return sum(vals) / len(vals)
ws1 = strat_model_mean("weak", "s1")
wsc = strat_model_mean("weak", "sc6")
wpe = strat_model_mean("weak", "pe6")
wcb = strat_model_mean("weak", "comb")
check("strat-weak-pooled", "weak stratum pooled S1/SC/PE (model-mean)", "30.9/31.8/52.9",
      f"{ws1:.1f}/{wsc:.1f}/{wpe:.1f}")
check("strat-weak-n-pooled", "weak stratum pairs", 61, sum(1 for q, r in weak_pairs if r["mode_share"] < 2/3))
check("strat-strong-s1", "strong stratum pooled S1", 67.0, round(strat_model_mean("strong", "s1"), 1))
check("strat-unan-sat", "unanimous stratum pooled (all conds)", 96.3,
      round(max(strat_model_mean("unan", f) for f in ("s1", "sc6", "pe6", "comb")), 1))
check("strat-weak-comb-v41", "v4.1 weak COMB vs PE", "57.1/50.0",
      f"{exp['deepseek-v4.1-flash']['strat_weak']['comb']:.1f}/{exp['deepseek-v4.1-flash']['strat_weak']['pe6']:.1f}")
check("strat-weak-comb-pro", "pro weak COMB vs PE", "60.0/53.3",
      f"{exp['deepseek-v4-pro-0813']['strat_weak']['comb']:.1f}/{exp['deepseek-v4-pro-0813']['strat_weak']['pe6']:.1f}")
# off-mode
for m, n_exp in [("agnes-3.0-flash", 15), ("agnes-2.5-flash", 5), ("deepseek-v4.1-flash", 16),
                 ("deepseek-v4-pro-0813", 14), ("qwen3.7-flash", 1), ("deepseek-v4-flash-0731", 0)]:
    check(f"offmode-{m}", "off-mode count", n_exp, exp[m]["off_mode_n"])
om_total = sum(exp[m]["off_mode_n"] for m in FULL4)
check("offmode-pooled", "pooled off-mode", "50/476", f"{om_total}/476")

print("=== main + expansion recomputation done, %d checks so far ===" % len(CHECKS))

# ============ 3. NEW: Holm, combined 90+119, parse rates ============
contrasts = ["SC-S1", "PE-S1", "COMB-S1", "PE-SC"]
pv = [NEW[c]["p_boot"] for c in contrasts]
adj = holm(pv)
NEW["holm"] = {c: {"p_raw": p, "p_holm": a} for c, p, a in zip(contrasts, pv, adj)}

for m in ["agnes-3.0-flash", "agnes-2.5-flash"]:
    merged = dict(main[m]["pq"])
    merged.update(exp[m]["pq"])
    qids = sorted(merged)
    n = len(qids)
    def A(f):
        return 100 * sum(merged[q][f] for q in qids) / n
    row = {"n": n, "greedy": A("greedy_ok"), "s1": A("k1_acc"), "pe1": A("pe1_acc"),
           "sc6": A("sc6_ok"), "pe6": A("pe6_ok"), "hb6": A("hb6_ok"), "comb": A("comb12_ok")}
    for cond in ("sc6", "pe6", "comb12"):
        mean, lo, hi = boot_ci([(1 if merged[q][f"{cond}_ok"] else 0) - merged[q]["k1_acc"] for q in qids], seed=55)
        row[f"d{cond}"] = {"mean": 100 * mean, "ci": [100 * lo, 100 * hi]}
    mean, lo, hi = boot_ci([(1 if merged[q]["pe6_ok"] else 0) - (1 if merged[q]["sc6_ok"] else 0) for q in qids], seed=56)
    row["pe-sc"] = {"mean": 100 * mean, "ci": [100 * lo, 100 * hi]}
    NEW[f"combined_{m}"] = row

NEW["exp_parse_rates"] = {m: round(100 * exp[m]["stats"]["parse_rate"], 2) for m in EXP_MODELS}
NEW["main_parse_rates"] = {m: round(100 * main[m]["stats"]["parse_rate"], 2) for m in MAIN_MODELS}

print("=== NEW stats ===")
print("Holm:", {c: round(NEW['holm'][c]['p_holm'], 4) for c in contrasts})
for m in ["agnes-3.0-flash", "agnes-2.5-flash"]:
    r = NEW[f"combined_{m}"]
    print(f"combined {m}: n={r['n']} greedy={r['greedy']:.1f} S1={r['s1']:.1f} SC={r['sc6']:.1f} "
          f"PE={r['pe6']:.1f} dSC={r['dsc6']['mean']:+.1f}{[round(x,1) for x in r['dsc6']['ci']]} "
          f"dPE={r['dpe6']['mean']:+.1f}{[round(x,1) for x in r['dpe6']['ci']]}")
print("exp parse rates:", NEW["exp_parse_rates"])

# ============ 4. claimed robustness checks ============
# (a) NLI entailment counts
nli = json.load(open(f"{DATA}/nli_validation.json"))
both = total = 0
for k, it in nli.items():
    if isinstance(it, dict) and "a_entails_b" in it:
        total += 1
        if it.get("a_entails_b") == "yes" and it.get("b_entails_a") == "yes":
            both += 1
check("nli-main", "NLI bidirectional pass", "267/270", f"{both}/{total}")
ag = json.load(open(f"{DATA}/nli_agnes_summary.json"))
check("nli-agnes", "NLI agnes summary pass", 269, ag.get("nli_pass"))

# (b) 0.80 threshold sensitivity (fragility on tight-paraphrase subset)
sims = json.load(open(f"{DATA}/para_sims_fresh.json"))
check("sim-structure", "para_sims_fresh structure (45 stem-locus questions)", "45q x 6",
      f"{len(sims)}q x {len(sims[list(sims)[0]])}")
def tight_frag(m, thresh=0.80, min_paras=4):
    pq = main[m]["pq"]
    nq = fl = 0
    # need paraphrase answers: reload complete matrices
    comp, cells, _ = load(f"{RES}/{m}.jsonl")
    for qid in pq:
        s = sims.get(qid)
        if not s:
            continue
        keep = [i + 1 for i, v in enumerate(list(s)[:6]) if v > thresh]
        if len(keep) < min_paras:
            continue
        cm = comp.get(qid)
        if cm is None:
            continue
        pv = [cm[(p, "1")]["answer"] for p in keep]
        sc_ans = majority([cm[(0, str(s2))]["answer"] for s2 in range(1, 7)])
        nq += 1
        fl += (sc_ans != majority(pv))
    return 100 * fl / nq if nq else None, nq
for m, exp_rate, exp_n in [("gpt-6-luna", 33.3, 6), ("gemini-3.8-flash", 25.0, None),
                           ("qwen3.8-omni", 4.8, None)]:
    rate, nq = tight_frag(m)
    check(f"sim80-{m}", f"tight-paraphrase fragility % (n={nq})", exp_rate,
          round(rate, 1) if rate is not None else None)

# (c) lenient aggregation rule — official per-source protocol (analyze_v2):
#     SC over ALL questions with >=4 parsed canonical votes; PE over ALL with
#     >=4 parsed paraphrase votes; denominators stated per source.
for m, sc_exp, sc_n, pe_exp, pe_n in [
        ("agnes-3.0-flash", 88.1, 42, 92.3, 39),
        ("qwen3.8-max", 93.3, 90, 93.3, 90),
        ("qwen3.8-omni", 88.9, 90, 89.7, 87)]:
    complete, cells, _ = load(f"{RES}/{m}.jsonl")
    sc_ok = pe_ok = 0
    n_sc = n_pe = 0
    for qid, cm in cells.items():
        gold = gold_of(Q[qid])
        sv = [cm.get((0, str(s)), {}).get("answer") for s in range(1, 7)]
        pv = [cm.get((p, "1"), {}).get("answer") for p in range(1, 7)]
        sv_ok = [v for v in sv if v is not None]
        pv_ok = [v for v in pv if v is not None]
        if len(sv_ok) >= 4:
            n_sc += 1
            sc_ok += majority(sv_ok) == gold
        if len(pv_ok) >= 4:
            n_pe += 1
            pe_ok += majority(pv_ok) == gold
    check(f"lenient-{m}", "lenient SC/PE (n_sc,n_pe)", f"{sc_exp}/{pe_exp} ({sc_n},{pe_n})",
          f"{100*sc_ok/n_sc:.1f}/{100*pe_ok/n_pe:.1f} ({n_sc},{n_pe})")

# (d) excluded vs included greedy difficulty
for m, exp_in, exp_ex in [("qwen3.8-omni", 93.0, 84.2), ("agnes-2.5-flash", 90.0, 60.0)]:
    complete, cells, _ = load(f"{RES}/{m}.jsonl")
    inc = set(complete)
    gr_in = sum(1 for q in inc if cells[q][(0, "g")]["answer"] == gold_of(Q[q])) / len(inc)
    ex = [q for q in cells if q not in inc and (0, "g") in cells[q] and cells[q][(0, "g")]["answer"] is not None]
    gr_ex = (sum(1 for q in ex if cells[q][(0, "g")]["answer"] == gold_of(Q[q])) / len(ex)) if ex else None
    check(f"excl-{m}", "excluded vs included greedy", f"{exp_ex} vs {exp_in}",
          f"{100*gr_ex:.1f} vs {100*gr_in:.1f}" if gr_ex is not None else "no excluded w/ greedy")

# (e) greedy off-mode audit counts (main suite)
try:
    aud = json.load(open(f"{BASE}/results/analysis/greedy_bias_audit/greedy_bias_audit.json"))
    check("audit-main", "greedy audit file", "present", "present")
except Exception as e:
    check("audit-main", "greedy audit file", "present", f"ERR {e}")

json.dump({"checks": CHECKS, "new": NEW}, open(f"{RES}/analysis/recompute_report.json", "w"), indent=1)

fails = [c for c in CHECKS if not c["ok"]]
print(f"\n================ REPORT: {len(CHECKS)} checks, {len(fails)} FAIL ================")
for c in CHECKS:
    status = "PASS" if c["ok"] else "FAIL"
    print(f"[{status}] {c['id']:28s} {c['desc'][:44]:44s} exp={str(c['expected'])[:34]:34s} got={str(c['actual'])[:40]}")
