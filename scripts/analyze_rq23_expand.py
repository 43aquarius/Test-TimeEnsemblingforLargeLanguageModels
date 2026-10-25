#!/usr/bin/env python3
"""v1.8.1: recompute on the HELD-OUT suite, directly from the raw logs, the
analyses that the revision previously ran only on the development suite:

  (1) the greedy-versus-S1 divergence for all ten model-endpoint configs;
  (2) RQ2  -- paraphrase fragility (overall / per-dataset / by locus);
  (3) RQ3  -- agreement scores as error signals (AUROC with question-level
              bootstrap CIs, tie-randomized AURC, flagged-error overlap,
              pooled cluster-bootstrap AUROC, non-degenerate stratum);
  (4) the SAT-Math (and other instruction-locus) instruction-variant control:
      single-call accuracy per handcrafted instruction variant against the
      canonical instruction and against the paraphrase ensemble.

Self-contained and deterministic. Outputs results/analysis/rq23_expand.json
plus a printed summary. Methodology mirrors recompute_all.py / analyze_v3.py.
"""
import json, math, os, random
from collections import defaultdict, Counter

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
STEM_DS = {"truthfulqa", "lsat_lr", "logiqa"}
INST_DS = {"piqa", "sat_math", "gsm8k"}


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
    cells = defaultdict(dict)
    for line in open(path):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("FAILED"):
            continue
        cells[r["qid"]][(r["para"], str(r["sample"]))] = r
    complete = {}
    for qid, cm in cells.items():
        if all(k in cm and cm[k]["answer"] is not None for k in NEED):
            complete[qid] = {k: cm[k] for k in NEED}
    return complete


def per_q_stats(complete, questions):
    out = {}
    for qid, cm in complete.items():
        q = questions[qid]
        gold = gold_of(q)
        sv = [cm[(0, str(s))]["answer"] for s in range(1, 7)]
        pv = [cm[(p, "1")]["answer"] for p in range(1, 7)]
        out[qid] = {
            "dataset": q["dataset"], "gold": gold,
            "greedy_ok": cm[(0, "g")]["answer"] == gold,
            "k1_acc": sum(v == gold for v in sv) / 6.0,
            "pe1_acc": sum(v == gold for v in pv) / 6.0,
            "sc6_ok": majority(sv) == gold,
            "pe6_ok": majority(pv) == gold,
            "comb12_ok": majority(sv + pv) == gold,
            "c_s": mode_share(sv), "c_p": mode_share(pv),
            "mode_share": mode_share(sv + pv),
            "fragile": majority(sv) != majority(pv),
        }
    return out


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
            if p > n:
                wins += 1
            elif p == n:
                ties += 1
    return (wins + 0.5 * ties) / (len(pos) * len(neg))


def auroc_boot_ci(pq, score_fn, label_fn, iters=10000, seed=42, alpha=0.05):
    """Question-level bootstrap CI for AUROC. Returns (auroc, lo, hi, ok_rate)."""
    qids = sorted(pq)
    base = auroc([score_fn(pq[q]) for q in qids], [label_fn(pq[q]) for q in qids])
    if base is None:
        return None, None, None, None
    rng = random.Random(seed)
    vals, bad = [], 0
    for _ in range(iters):
        qs = [qids[rng.randrange(len(qids))] for _ in range(len(qids))]
        a = auroc([score_fn(pq[q]) for q in qs], [label_fn(pq[q]) for q in qs])
        if a is None:
            bad += 1
            continue
        vals.append(a)
    if not vals:
        return base, None, None, 0.0
    vals.sort()
    lo = vals[int(alpha / 2 * len(vals))]
    hi = vals[int((1 - alpha / 2) * len(vals)) - 1]
    return base, lo, hi, len(vals) / iters


def aurc_random(scores, errors, perms=1000, seed=42):
    idx = [i for i, s in enumerate(scores) if s is not None]
    n = len(idx)
    if n == 0:
        return None
    rng = random.Random(seed)
    vals = []
    for _ in range(perms):
        order = sorted(idx, key=lambda i: (-scores[i], rng.random()))
        cum = tot = 0
        a = 0.0
        for i in order:
            cum += errors[i]
            tot += 1
            a += cum / tot
        vals.append(a / n)
    return sum(vals) / len(vals)


def pooled_auroc_cluster_ci(by_q, score_fn, label_fn, iters=10000, seed=42, alpha=0.05):
    """by_q: {qid: [per-model rows]}. Cluster bootstrap over questions."""
    qids = sorted(by_q)
    rows = [r for q in qids for r in by_q[q]]
    base = auroc([score_fn(r) for r in rows], [label_fn(r) for r in rows])
    if base is None:
        return None, None, None
    rng = random.Random(seed)
    vals, bad = [], 0
    for _ in range(iters):
        qs = [qids[rng.randrange(len(qids))] for _ in range(len(qids))]
        rs = [r for q in qs for r in by_q[q]]
        a = auroc([score_fn(r) for r in rs], [label_fn(r) for r in rs])
        if a is None:
            bad += 1
            continue
        vals.append(a)
    if not vals:
        return base, None, None
    vals.sort()
    return base, vals[int(alpha / 2 * len(vals))], vals[int((1 - alpha / 2) * len(vals)) - 1]


# ============ load question sets ============
Q = {q["id"]: q for q in json.load(open(f"{DATA}/questions.json"))}
QE = {q["id"]: q for q in json.load(open(f"{DATA}/questions_expand.json"))}

OUT = {"set": "held-out (expand) RQ2/RQ3 recomputation + greedy divergence + instruction control"}

# ============ (1) greedy vs S1 over all ten configs ============
print("=" * 78)
print("(1) GREEDY vs S1 -- all ten model-endpoint configurations")
print("=" * 78)
greedy_div = {}
for m in MAIN_MODELS:
    pq = per_q_stats(load(f"{RES}/{m}.jsonl"), Q)
    n = len(pq)
    g = 100 * sum(pq[q]["greedy_ok"] for q in pq) / n
    s1 = 100 * sum(pq[q]["k1_acc"] for q in pq) / n
    greedy_div[m] = {"suite": "dev", "n": n, "greedy": round(g, 1), "s1": round(s1, 1),
                     "s1_minus_greedy": round(s1 - g, 1)}
for m in EXP_MODELS:
    pq = per_q_stats(load(f"{EXP}/{m}.jsonl"), QE)
    n = len(pq)
    g = 100 * sum(pq[q]["greedy_ok"] for q in pq) / n
    s1 = 100 * sum(pq[q]["k1_acc"] for q in pq) / n
    greedy_div[m + "@expand"] = {"suite": "held-out", "n": n, "greedy": round(g, 1),
                                 "s1": round(s1, 1), "s1_minus_greedy": round(s1 - g, 1)}
OUT["greedy_divergence"] = greedy_div
big = {k: v for k, v in greedy_div.items() if abs(v["s1_minus_greedy"]) >= 4.0}
for k, v in greedy_div.items():
    flag = "  <== >=4pp" if abs(v["s1_minus_greedy"]) >= 4.0 else ""
    print(f"  {k:34s} n={v['n']:3d}  greedy={v['greedy']:5.1f}  S1={v['s1']:5.1f}  "
          f"S1-greedy={v['s1_minus_greedy']:+5.1f}{flag}")
above = [k for k, v in big.items() if v["s1_minus_greedy"] > 0]
below = [k for k, v in big.items() if v["s1_minus_greedy"] < 0]
print(f"  --> |gap| >= 4pp on {len(big)}/10 configs: {sorted(big)}")
print(f"      greedy BELOW S1 on {sorted(above)}; greedy ABOVE S1 on {sorted(below)}")
OUT["greedy_divergence_summary"] = {
    "n_configs": 10, "n_gap_ge4": len(big), "configs_ge4": sorted(big),
    "greedy_below_s1": sorted(above), "greedy_above_s1": sorted(below)}

# ============ (2) RQ2: fragility on the held-out suite ============
print()
print("=" * 78)
print("(2) RQ2 -- FRAGILITY (SC-6 majority != PE-6 majority), held-out suite")
print("=" * 78)
frag = {}
for m in FULL4 + ["qwen3.7-flash"]:
    pq = per_q_stats(load(f"{EXP}/{m}.jsonl"), QE)
    qids = sorted(pq)
    row = {"n": len(qids), "overall": 100 * sum(pq[q]["fragile"] for q in qids) / len(qids)}
    for ds in sorted({pq[q]["dataset"] for q in qids}):
        dq = [q for q in qids if pq[q]["dataset"] == ds]
        row[ds] = (round(100 * sum(pq[q]["fragile"] for q in dq) / len(dq), 1), len(dq))
    stem = [q for q in qids if pq[q]["dataset"] in STEM_DS]
    inst = [q for q in qids if pq[q]["dataset"] in INST_DS]
    row["stem_locus"] = (round(100 * sum(pq[q]["fragile"] for q in stem) / len(stem), 1), len(stem))
    row["inst_locus"] = (round(100 * sum(pq[q]["fragile"] for q in inst) / len(inst), 1), len(inst))
    row["_pq"] = pq
    frag[m] = row
# pooled over FULL4, questions weighted equally (mean over models per question)
byq = {q: [frag[m]["_pq"][q] for m in FULL4 if q in frag[m]["_pq"]] for q in
       set.intersection(*[set(frag[m]["_pq"]) for m in FULL4])}
pooled_stem = pooled_inst = pooled_all = 0.0
ns = ni = na = 0
for q, rows in byq.items():
    f = sum(r["fragile"] for r in rows) / len(rows)
    pooled_all += f; na += 1
    ds = rows[0]["dataset"]
    if ds in STEM_DS:
        pooled_stem += f; ns += 1
    else:
        pooled_inst += f; ni += 1
frag_pooled = {"stem_locus": round(100 * pooled_stem / ns, 1), "stem_n": ns,
               "inst_locus": round(100 * pooled_inst / ni, 1), "inst_n": ni,
               "overall": round(100 * pooled_all / na, 1), "n_pairs": 4 * na,
               "stem_flips": sum(1 for q, rows in byq.items() if rows[0]["dataset"] in STEM_DS
                                 for r in rows if r["fragile"]),
               "inst_flips": sum(1 for q, rows in byq.items() if rows[0]["dataset"] in INST_DS
                                 for r in rows if r["fragile"])}
OUT["fragility_heldout"] = {m: {k: v for k, v in row.items() if k != "_pq"}
                            for m, row in frag.items()}
OUT["fragility_heldout"]["POOLED_FULL4"] = frag_pooled
for m in FULL4 + ["qwen3.7-flash"]:
    r = frag[m]
    print(f"  {m:24s} n={r['n']:3d} overall={r['overall']:5.1f}%  "
          f"stem={r['stem_locus'][0]:5.1f}% (n={r['stem_locus'][1]})  "
          f"inst={r['inst_locus'][0]:5.1f}% (n={r['inst_locus'][1]})")
    print(f"      per-dataset: " + "  ".join(f"{ds}={v[0]}%(n={v[1]})" for ds, v in r.items()
                                             if ds not in ("n", "overall", "stem_locus", "inst_locus", "_pq")))
print(f"  POOLED FULL4: stem={frag_pooled['stem_locus']}% ({frag_pooled['stem_flips']} flips / "
      f"{frag_pooled['stem_n']}q x4), inst={frag_pooled['inst_locus']}% "
      f"({frag_pooled['inst_flips']} flips / {frag_pooled['inst_n']}q x4), "
      f"overall={frag_pooled['overall']}%")

# ============ (3) RQ3: error signals on the held-out suite ============
print()
print("=" * 78)
print("(3) RQ3 -- AGREEMENT AS ERROR SIGNAL (reference: COMB-12), held-out suite")
print("=" * 78)
sig = {}
sc = lambda r: 1 - r["c_s"]          # sample disagreement (reversed agreement)
pc = lambda r: 1 - r["c_p"]          # paraphrase disagreement
bc = lambda r: 2 - r["c_s"] - r["c_p"]
err = lambda r: 0 if r["comb12_ok"] else 1
for m in FULL4 + ["qwen3.7-flash"]:
    pq = frag[m]["_pq"]
    qids = sorted(pq)
    n_err = sum(err(pq[q]) for q in qids)
    row = {"n": len(qids), "n_errors": n_err,
           "error_rate": round(100 * n_err / len(qids), 1)}
    for name, fn in (("cs", sc), ("cp", pc), ("both", bc)):
        a, lo, hi, okr = auroc_boot_ci(pq, fn, err, seed=42)
        row[f"auroc_{name}"] = None if a is None else round(a, 3)
        row[f"auroc_{name}_ci"] = None if lo is None else [round(lo, 3), round(hi, 3)]
    # non-degenerate stratum (mode share over 12 votes < 1)
    nd = {q: r for q, r in pq.items() if r["mode_share"] < 1}
    row["n_nondegen"] = len(nd)
    row["n_errors_nondegen"] = sum(err(r) for r in nd.values())
    for name, fn in (("cs", sc), ("cp", pc), ("both", bc)):
        a = auroc([fn(r) for r in nd.values()], [err(r) for r in nd.values()])
        row[f"auroc_nd_{name}"] = None if a is None else round(a, 3)
    # AURC (tie-randomized)
    errs_list = [err(pq[q]) for q in qids]
    row["aurc_cs"] = round(aurc_random([sc(pq[q]) for q in qids], errs_list), 3)
    row["aurc_cp"] = round(aurc_random([pc(pq[q]) for q in qids], errs_list), 3)
    # flagged-error overlap: an error is flagged when the source shows any dissent
    flagged_s = sum(1 for q in qids if err(pq[q]) and pq[q]["c_s"] < 1)
    flagged_p = sum(1 for q in qids if err(pq[q]) and pq[q]["c_p"] < 1)
    flagged_both = sum(1 for q in qids if err(pq[q]) and (pq[q]["c_s"] < 1 or pq[q]["c_p"] < 1))
    only_s = sum(1 for q in qids if err(pq[q]) and pq[q]["c_s"] < 1 and pq[q]["c_p"] == 1)
    only_p = sum(1 for q in qids if err(pq[q]) and pq[q]["c_p"] < 1 and pq[q]["c_s"] == 1)
    row.update({"err_flagged_cs": flagged_s, "err_flagged_cp": flagged_p,
                "err_flagged_any": flagged_both, "err_only_cs": only_s, "err_only_cp": only_p})
    sig[m] = row
    print(f"  {m:24s} n={row['n']:3d} errors={n_err:2d} ({row['error_rate']:4.1f}%)  "
          f"AUROC cs={row['auroc_cs']} {row['auroc_cs_ci']}  cp={row['auroc_cp']} "
          f"{row['auroc_cp_ci']}  both={row['auroc_both']} {row['auroc_both_ci']}")
    print(f"      non-degenerate: n={row['n_nondegen']} errors={row['n_errors_nondegen']}  "
          f"AUROC cs={row['auroc_nd_cs']} cp={row['auroc_nd_cp']} both={row['auroc_nd_both']}  "
          f"AURC cs={row['aurc_cs']} cp={row['aurc_cp']}")
    print(f"      errors flagged: cs={flagged_s}/{n_err} cp={flagged_p}/{n_err} any={flagged_both}/{n_err} "
          f"(only-cs={only_s}, only-cp={only_p})")
# pooled over FULL4 (cluster bootstrap over questions)
byq_err = {q: [frag[m]["_pq"][q] for m in FULL4] for q in byq}
pooled_sig = {}
for name, fn in (("cs", sc), ("cp", pc), ("both", bc)):
    a, lo, hi = pooled_auroc_cluster_ci(byq_err, fn, err, seed=42)
    pooled_sig[f"auroc_{name}"] = round(a, 3)
    pooled_sig[f"auroc_{name}_ci"] = [round(lo, 3), round(hi, 3)]
pooled_sig["n_pairs"] = 4 * len(byq_err)
pooled_sig["n_errors"] = sum(err(r) for rs in byq_err.values() for r in rs)
tot = pooled_sig["n_errors"]
pooled_sig["err_flagged_cs"] = sum(1 for rs in byq_err.values() for r in rs if err(r) and r["c_s"] < 1)
pooled_sig["err_flagged_cp"] = sum(1 for rs in byq_err.values() for r in rs if err(r) and r["c_p"] < 1)
pooled_sig["err_only_cs"] = sum(1 for rs in byq_err.values() for r in rs if err(r) and r["c_s"] < 1 and r["c_p"] == 1)
pooled_sig["err_only_cp"] = sum(1 for rs in byq_err.values() for r in rs if err(r) and r["c_p"] < 1 and r["c_s"] == 1)
OUT["error_signals_heldout"] = sig
OUT["error_signals_heldout"]["POOLED_FULL4"] = pooled_sig
print(f"  POOLED FULL4: {pooled_sig['n_pairs']} pairs, {tot} errors")
for name in ("cs", "cp", "both"):
    print(f"      AUROC {name}={pooled_sig[f'auroc_{name}']} {pooled_sig[f'auroc_{name}_ci']}")
print(f"      flagged: cs={pooled_sig['err_flagged_cs']}/{tot} cp={pooled_sig['err_flagged_cp']}/{tot} "
      f"(only-cs={pooled_sig['err_only_cs']}, only-cp={pooled_sig['err_only_cp']})")

# ============ (4) instruction-variant control (SAT-Math / PIQA / GSM8K) ============
print()
print("=" * 78)
print("(4) INSTRUCTION-VARIANT CONTROL -- single-call accuracy per variant (P0=canonical)")
print("=" * 78)
inst_ctl = {}
for ds in sorted(INST_DS):
    ds_rows = {}
    for m in FULL4:
        pq = frag[m]["_pq"]
        qds = [q for q in sorted(pq) if pq[q]["dataset"] == ds]
        if not qds:
            continue
        canon = 100 * sum(pq[q]["k1_acc"] for q in qds) / len(qds)
        variants = []
        for k in range(1, 7):
            acc = 100 * sum(pq[q]["pe1_acc"] if False else 0 for q in qds)  # placeholder
            # per-variant accuracy: recompute from raw votes via pe1 per-paraphrase
            variants.append(None)
        ds_rows[m] = {"n": len(qds), "canonical_S1": round(canon, 1), "variants": variants}
    ds_rows["_note"] = "filled below from raw per-paraphrase answers"
    inst_ctl[ds] = ds_rows

# per-variant accuracy needs per-paraphrase answers: recompute from complete matrices
for ds in sorted(INST_DS):
    for m in FULL4:
        complete = load(f"{EXP}/{m}.jsonl")
        pq = frag[m]["_pq"]
        qds = [q for q in sorted(pq) if pq[q]["dataset"] == ds]
        if not qds:
            continue
        variants = []
        for k in range(1, 7):
            ok = 0
            for q in qds:
                cm = complete[q]
                gold = gold_of(QE[q])
                ok += cm[(k, "1")]["answer"] == gold
            variants.append(round(100 * ok / len(qds), 1))
        pe6 = 100 * sum(pq[q]["pe6_ok"] for q in qds) / len(qds)
        best = max(variants)
        inst_ctl[ds][m] = {"n": len(qds),
                           "canonical_S1": round(100 * sum(pq[q]["k1_acc"] for q in qds) / len(qds), 1),
                           "variants_P1_P6": variants, "best_variant": best,
                           "best_minus_canonical": round(best - 100 * sum(pq[q]["k1_acc"] for q in qds) / len(qds), 1),
                           "PE6": round(pe6, 1),
                           "PE6_minus_best": round(pe6 - best, 1),
                           "canonical_rank": sorted([100 * sum(pq[q]['k1_acc'] for q in qds) / len(qds)] + variants,
                                                     reverse=True).index(100 * sum(pq[q]["k1_acc"] for q in qds) / len(qds)) + 1}
    # pooled over FULL4 (equal model weight)
    if all(m in inst_ctl[ds] for m in FULL4):
        pv = [round(sum(inst_ctl[ds][m]["variants_P1_P6"][k] for m in FULL4) / 4, 1) for k in range(6)]
        canon = round(sum(inst_ctl[ds][m]["canonical_S1"] for m in FULL4) / 4, 1)
        pe6 = round(sum(inst_ctl[ds][m]["PE6"] for m in FULL4) / 4, 1)
        inst_ctl[ds]["POOLED_FULL4"] = {"variants_P1_P6": pv, "canonical_S1": canon,
                                        "best_variant": max(pv), "best_minus_canonical": round(max(pv) - canon, 1),
                                        "PE6": pe6, "PE6_minus_best": round(pe6 - max(pv), 1)}
    print(f"  --- {ds} ---")
    for m in FULL4:
        if m not in inst_ctl[ds]:
            continue
        r = inst_ctl[ds][m]
        print(f"    {m:24s} n={r['n']:2d}  canonical={r['canonical_S1']:5.1f}  "
              f"variants={r['variants_P1_P6']}  best={r['best_variant']:5.1f} "
              f"(+{r['best_minus_canonical']} vs canon, rank {r['canonical_rank']}/7)  "
              f"PE-6={r['PE6']:5.1f} ({r['PE6_minus_best']:+} vs best)")
    if "POOLED_FULL4" in inst_ctl[ds]:
        r = inst_ctl[ds]["POOLED_FULL4"]
        print(f"    {'POOLED FULL4':24s}     canonical={r['canonical_S1']:5.1f}  variants={r['variants_P1_P6']}  "
              f"best={r['best_variant']:5.1f} (+{r['best_minus_canonical']} vs canon)  "
              f"PE-6={r['PE6']:5.1f} ({r['PE6_minus_best']:+} vs best)")
OUT["instruction_control"] = inst_ctl

json.dump(OUT, open(f"{RES}/analysis/rq23_expand.json", "w"), indent=1)
print()
print(f"saved -> {RES}/analysis/rq23_expand.json")
