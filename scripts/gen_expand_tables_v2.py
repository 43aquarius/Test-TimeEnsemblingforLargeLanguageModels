#!/usr/bin/env python3
"""Regenerate tab_expand.tex and tab_expand_ds.tex with both agnes models + pooled.
Numbers are recomputed directly from the expand JSONL files (single source of truth)."""
import json, collections
from collections import defaultdict

RES = "/home/z/my-project/results/expand"
DATA = "/home/z/my-project/data"
questions = {q["id"]: q for q in json.load(open(f"{DATA}/questions_expand.json"))}

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
    c = collections.Counter(vs)
    top = max(c.values())
    winners = set(v for v, n in c.items() if n == top)
    for v in vs:
        if v in winners:
            return v

def load(alias):
    cells = defaultdict(dict)
    for line in open(f"{RES}/{alias}.jsonl"):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("FAILED"):
            continue
        cells[r["qid"]][(r["para"], str(r["sample"]))] = r
    NEED = [(0, "g")] + [(0, str(s)) for s in range(1, 7)] + \
           [(p, str(s)) for p in (1, 2, 3) for s in (1, 2)] + [(p, "1") for p in (4, 5, 6)]
    complete = {}
    for qid, cm in cells.items():
        if all(k in cm and cm[k]["answer"] is not None for k in NEED):
            complete[qid] = {k: cm[k] for k in NEED}
    return complete

def metrics(complete):
    per_q = {}
    for qid, cm in complete.items():
        q = questions[qid]
        gold = gold_of(q)
        sv = [cm[(0, str(s))]["answer"] for s in range(1, 7)]
        pv = [cm[(p, "1")]["answer"] for p in range(1, 7)]
        per_q[qid] = {
            "ds": q["dataset"], "gold": gold,
            "greedy": cm[(0, "g")]["answer"] == gold,
            "s1": sum(v == gold for v in sv) / 6.0,
            "pe1": sum(v == gold for v in pv) / 6.0,
            "sc6": majority(sv) == gold,
            "pe6": majority(pv) == gold,
            "hb6": majority([cm[(p, str(s))]["answer"] for p in (1, 2, 3) for s in (1, 2)]) == gold,
            "comb12": majority(sv + pv) == gold,
            "unanimous": len(set(v for v in sv + pv if v is not None)) == 1,
        }
    return per_q

def acc(per_q, f):
    return 100 * sum(v[f] for v in per_q.values()) / len(per_q)

def unan_rule(complete):
    accs, ks = [], []
    for qid, cm in complete.items():
        gold = gold_of(questions[qid])
        votes = [cm[(0, str(s))]["answer"] for s in range(1, 7)]
        stop = 6
        for s in range(2, 7):
            if len(set(votes[:s])) == 1:
                stop = s
                break
        accs.append(majority(votes[:stop]) == gold)
        ks.append(stop)
    return 100 * sum(accs) / len(accs), sum(ks) / len(ks)

def adaptive(complete):
    accs, ks = [], []
    for qid, cm in complete.items():
        gold = gold_of(questions[qid])
        s2 = [cm[(0, str(s))]["answer"] for s in (1, 2)]
        p2 = [cm[(p, "1")]["answer"] for p in (1, 2)]
        if len(set(s2)) == 1 and len(set(p2)) == 1 and s2[0] == p2[0]:
            ans, used = s2[0], 4
        elif len(set(s2)) == 1 and len(set(p2)) > 1:
            ans, used = majority([cm[(0, str(s))]["answer"] for s in range(1, 7)]), 8
        elif len(set(p2)) == 1:
            ans, used = majority([cm[(p, "1")]["answer"] for p in range(1, 7)]), 8
        else:
            ans, used = majority([cm[(p, str(s))]["answer"] for p in (1, 2, 3) for s in (1, 2)]), 8
        accs.append(ans == gold)
        ks.append(used)
    return 100 * sum(accs) / len(accs), sum(ks) / len(ks)

M = {}
for alias, disp in [("agnes-3.0-flash", "Agnes3.0-Flash"),
                    ("agnes-2.5-flash", "Agnes2.5-Flash"),
                    ("qwen3.7-flash", "Qwen3.7-Flash")]:
    comp = load(alias)
    if len(comp) < 50:
        continue
    pq = metrics(comp)
    ua, uk = unan_rule(comp)
    aa, ak = adaptive(comp)
    M[disp] = {"n": len(comp), "pq": pq,
               "acc": {f: acc(pq, f) for f in ("greedy", "s1", "pe1", "sc6", "pe6", "hb6", "comb12", "unanimous")},
               "ua": ua, "uk": uk, "aa": aa, "ak": ak}
    print(f"{disp}: n={len(comp)} pe1={acc(pq,'pe1'):.1f} unan_rule={ua:.1f}@{uk:.1f} adaptive={aa:.1f}@{ak:.2f}")

# ---------------- tab_expand.tex ----------------
rows = []
for disp, m in M.items():
    a = m["acc"]
    star = "$^{\\S}$" if disp == "Qwen3.7-Flash" else ""
    rows.append(f"{disp}{star} & {m['n']} & {a['greedy']:.1f} & {a['s1']:.1f} & {a['sc6']:.1f} & "
                f"{a['pe6']:.1f} & {a['hb6']:.1f} & {a['comb12']:.1f} & {a['unanimous']:.0f} & "
                f"{m['ua']:.1f} & {m['uk']:.1f} & {m['aa']:.1f} & {m['ak']:.1f} & {100*m['ak']/6:.0f}\\% \\\\")
POOL = ["Agnes3.0-Flash", "Agnes2.5-Flash"]
pool_pq = {}
for disp in POOL:
    for qid, v in M[disp]["pq"].items():
        pool_pq.setdefault(qid, []).append(v)
n_pairs = sum(len(v) for v in pool_pq.values())
def pacc(f):
    return 100 * sum(v[f] for vs in pool_pq.values() for v in vs) / n_pairs
p_greedy, p_s1, p_sc6, p_pe6, p_hb6, p_c12, p_unan = (
    pacc(f) for f in ("greedy", "s1", "sc6", "pe6", "hb6", "comb12", "unanimous"))
pu_a = sum(M[d]["ua"] for d in POOL) / 2
pu_k = sum(M[d]["uk"] for d in POOL) / 2
pa_a = sum(M[d]["aa"] for d in POOL) / 2
pa_k = sum(M[d]["ak"] for d in POOL) / 2
rows.append("\\midrule")
rows.append(f"Pooled & {n_pairs} & {p_greedy:.1f} & {p_s1:.1f} & {p_sc6:.1f} & {p_pe6:.1f} & "
            f"{p_hb6:.1f} & {p_c12:.1f} & {p_unan:.0f} & {pu_a:.1f} & {pu_k:.1f} & "
            f"{pa_a:.1f} & {pa_k:.1f} & {100*pa_k/6:.0f}\\% \\\\")

tab = """\\scriptsize
\\begin{tabular*}{\\columnwidth}{@{\\extracolsep{\\fill}} l c c c c c c c c c c c c c}
\\toprule
 & & \\multicolumn{6}{c}{Accuracy (\\%)} & & \\multicolumn{2}{c}{Unanimity rule} & \\multicolumn{3}{c}{Adaptive rule} \\\\
\\cmidrule(lr){3-8}\\cmidrule(lr){10-11}\\cmidrule(lr){12-14}
Model & $n$ & Greedy & S1 & SC-6 & PE-6 & HB-6 & COMB & Unan.\\% & Acc & $\\bar{k}$ & Acc & $\\bar{k}$ & Bud. \\\\
\\midrule
""" + "\n".join(rows) + """
\\bottomrule
\\end{tabular*}"""
open("/home/z/my-project/paper/tables/tab_expand.tex", "w").write(tab + "\n")
print("\n--- tab_expand.tex written ---")
print(tab)

# ---------------- tab_expand_ds.tex ----------------
ds_order = ["gsm8k", "logiqa", "lsat_lr", "piqa", "sat_math", "truthfulqa"]
lines = []
for disp in POOL:
    pq = M[disp]["pq"]
    for ds in ds_order:
        dq = {q: v for q, v in pq.items() if v["ds"] == ds}
        if not dq:
            continue
        n = len(dq)
        s1 = 100 * sum(v["s1"] for v in dq.values()) / n
        pe1 = 100 * sum(v["pe1"] for v in dq.values()) / n
        sc6 = 100 * sum(v["sc6"] for v in dq.values()) / n
        pe6 = 100 * sum(v["pe6"] for v in dq.values()) / n
        lines.append(f"{disp} & {ds} & {n} & {s1:.1f} & {pe1:.1f} & {sc6:.1f} & {pe6:.1f} & "
                     f"{sc6-s1:+.1f} & {pe6-pe1:+.1f} \\\\")
    n = len(pq)
    s1 = 100 * sum(v["s1"] for v in pq.values()) / n
    pe1 = 100 * sum(v["pe1"] for v in pq.values()) / n
    sc6 = 100 * sum(v["sc6"] for v in pq.values()) / n
    pe6 = 100 * sum(v["pe6"] for v in pq.values()) / n
    lines.append(f" & pooled & {n} & {s1:.1f} & {pe1:.1f} & {sc6:.1f} & {pe6:.1f} & "
                 f"{sc6-s1:+.1f} & {pe6-pe1:+.1f} \\\\")
    lines.append("\\midrule")
lines.pop()  # drop trailing midrule
lines.append("\\midrule")
for ds in ds_order:
    dq = [v for disp in POOL for v in M[disp]["pq"].values() if v["ds"] == ds]
    n = len(dq)
    s1 = 100 * sum(v["s1"] for v in dq) / n
    pe1 = 100 * sum(v["pe1"] for v in dq) / n
    sc6 = 100 * sum(v["sc6"] for v in dq) / n
    pe6 = 100 * sum(v["pe6"] for v in dq) / n
    lines.append(f"Pooled & {ds} & {n} & {s1:.1f} & {pe1:.1f} & {sc6:.1f} & {pe6:.1f} & "
                 f"{sc6-s1:+.1f} & {pe6-pe1:+.1f} \\\\")
dq_all = [v for disp in POOL for v in M[disp]["pq"].values()]
n = len(dq_all)
s1 = 100 * sum(v["s1"] for v in dq_all) / n
pe1 = 100 * sum(v["pe1"] for v in dq_all) / n
sc6 = 100 * sum(v["sc6"] for v in dq_all) / n
pe6 = 100 * sum(v["pe6"] for v in dq_all) / n
lines.append(f"Pooled & pooled & {n} & {s1:.1f} & {pe1:.1f} & {sc6:.1f} & {pe6:.1f} & "
             f"{sc6-s1:+.1f} & {pe6-pe1:+.1f} \\\\")

tab2 = """\\scriptsize
\\begin{tabular*}{\\columnwidth}{@{\\extracolsep{\\fill}} l l c c c c c c c c}
\\toprule
 & & & \\multicolumn{2}{c}{Single call (\\%)} & & \\multicolumn{2}{c}{6-vote (\\%)} & \\multicolumn{2}{c}{Ensembling gain (pp)} \\\\
\\cmidrule(lr){4-5}\\cmidrule(lr){6-7}\\cmidrule(lr){8-9}
Model & Dataset & $n$ & S1 & PE-1 & SC-6 & PE-6 & $\\Delta$SC & $\\Delta$PE \\\\
\\midrule
""" + "\n".join(lines) + """
\\bottomrule
\\end{tabular*}"""
open("/home/z/my-project/paper/tables/tab_expand_ds.tex", "w").write(tab2 + "\n")
print("\n--- tab_expand_ds.tex written ---")
print(tab2)
