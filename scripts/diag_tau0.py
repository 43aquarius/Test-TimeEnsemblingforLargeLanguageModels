#!/usr/bin/env python3
"""Diagnose the tau=0 (greedy) anomaly flagged by the reviewer.

R1: For each model, compare greedy answer vs the mode of the 6 tau=0.7 P0
samples.  Inspect every question where greedy is NOT the modal answer:
response snippet, content_len, completion tokens (truncation / format failure
evidence).  Quantify how much of SC-6-minus-greedy is explained by greedy
being off-mode.

R3: Recompute AURC with ties broken uniformly at random (averaged over many
permutations) and compare against the v2 (stable-sort) numbers, esp. omni and
agnes-3.0 cP.

Also: mode-share distribution preview for the entropy-metric redesign.
"""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import json, math, random
from collections import defaultdict, Counter, OrderedDict

DATA = ROOT + "/data"
RES = ROOT + "/results"
MODELS = ["qwen3.8-max", "qwen3.8-omni", "agnes-3.0-flash",
          "agnes-2.5-flash", "gpt-6-luna", "gemini-3.8-flash"]

questions = {q["id"]: q for q in json.load(open(f"{DATA}/questions.json"))}

def gold_of(q):
    if q["dataset"] == "gsm8k":
        return str(q["answer"])
    if q["dataset"] == "piqa":
        return str(q["answer_idx"] + 1)
    return "ABCDEFGHIJ"[q["answer_idx"]]

MAIN_NEED = [("0", str(s)) for s in range(1, 7)] + [(str(p), "1") for p in range(1, 7)] + [("0", "g")]

def load(path):
    cells = defaultdict(dict)
    for line in open(path):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("FAILED"):
            continue
        cells[r["qid"]][(str(r["para"]), str(r["sample"]))] = r
    complete = {}
    for qid, cm in cells.items():
        cm = {k: cm[k] for k in MAIN_NEED if k in cm}
        if len(cm) == len(MAIN_NEED) and all(cm[k]["answer"] is not None for k in MAIN_NEED):
            complete[qid] = cm
    return complete

def mode_count(votes):
    c = Counter(votes)
    top = max(c.values())
    winners = [v for v, n in c.items() if n == top]
    return winners, top, len(votes)

print("=" * 100)
print("PART 1: greedy vs mode-of-samples (tau=0 anomaly)")
print("=" * 100)
summary = {}
for alias in MODELS:
    complete = load(f"{RES}/{alias}.jsonl")
    n = len(complete)
    g_ok = s1_sum = sc6_ok = pe6_ok = 0
    off_mode = []          # greedy not in modal winners
    off_mode_detail = []
    for qid, cm in complete.items():
        gold = gold_of(questions[qid])
        g = cm[("0", "g")]["answer"]
        sv = [cm[("0", str(s))]["answer"] for s in range(1, 7)]
        pv = [cm[(str(p), "1")]["answer"] for p in range(1, 7)]
        winners, top, tot = mode_count(sv)
        k1 = sum(v == gold for v in sv) / 6.0
        g_ok += g == gold
        s1_sum += k1
        # SC-6 majority = mode of sv (first-appearing winner, same as analyze_v2)
        c = Counter(sv)
        sc_ans = None
        for v in sv:
            if c[v] == top:
                sc_ans = v
                break
        sc6_ok += sc_ans == gold
        pc = Counter(pv)
        ptop = max(pc.values())
        pe_ans = None
        for v in pv:
            if pc[v] == ptop:
                pe_ans = v
                break
        pe6_ok += pe_ans == gold
        if g not in winners:
            gr = cm[("0", "g")]
            off_mode.append(qid)
            off_mode_detail.append({
                "qid": qid, "ds": questions[qid]["dataset"],
                "gold": gold, "greedy": g, "sample_counts": dict(c),
                "greedy_ok": g == gold, "mode_ok": winners[0] == gold,
                "sc6_ok": sc_ans == gold,
                "snippet": (gr.get("snippet") or "")[:90],
                "ct": gr["usage"].get("ct"), "clen": gr.get("content_len"),
                "temp": gr.get("temp"),
            })
    summary[alias] = {
        "n": n, "greedy": g_ok / n, "s1": s1_sum / n,
        "sc6": sc6_ok / n, "pe6": pe6_ok / n,
        "n_off_mode": len(off_mode),
        "off_mode_but_mode_right": sum(1 for d in off_mode_detail if d["mode_ok"] and not d["greedy_ok"]),
        "off_mode_detail": off_mode_detail,
    }
    s = summary[alias]
    print(f"\n{alias}: n={n} greedy={s['greedy']:.3f} S1={s['s1']:.3f} "
          f"SC-6={s['sc6']:.3f} PE-6={s['pe6']:.3f} | off-mode greedy: {s['n_off_mode']}")
    print(f"  SC-6 - greedy = {(s['sc6']-s['greedy'])*100:+.1f}pp ; "
          f"SC-6 - S1 = {(s['sc6']-s['s1'])*100:+.1f}pp ; "
          f"PE-6 - S1 = {(s['pe6']-s['s1'])*100:+.1f}pp ; "
          f"S1 - greedy = {(s['s1']-s['greedy'])*100:+.1f}pp")
    print(f"  off-mode questions where mode is RIGHT but greedy WRONG: {s['off_mode_but_mode_right']}")
    for d in off_mode_detail:
        print(f"    {d['qid']} [{d['ds']}] gold={d['gold']} greedy={d['greedy']} "
              f"({'OK' if d['greedy_ok'] else 'WRONG'}) samples={d['sample_counts']} "
              f"ct={d['ct']} clen={d['clen']} temp={d['temp']} snippet={d['snippet']!r}")

print()
print("=" * 100)
print("PART 2: greedy response-format audit (all models, all questions)")
print("=" * 100)
for alias in MODELS:
    complete = load(f"{RES}/{alias}.jsonl")
    cts = [cm[("0", "g")]["usage"].get("ct") or 0 for cm in complete.values()]
    clens = [cm[("0", "g")].get("content_len") or 0 for cm in complete.values()]
    empty = sum(1 for cm in complete.values() if not (cm[("0", "g")].get("snippet") or "").strip())
    print(f"{alias}: n={len(complete)} greedy ct min/med/max={min(cts)}/{sorted(cts)[len(cts)//2]}/{max(cts)} "
          f"clen min/max={min(clens)}/{max(clens)} empty_snippet={empty}")

print()
print("=" * 100)
print("PART 3: AURC with random tie-breaking (1000 perms) vs v2 stable sort")
print("=" * 100)
def aurc_stable(scores, errors):
    pairs = sorted([(s, e) for s, e in zip(scores, errors) if s is not None],
                   key=lambda x: -x[0])
    n = len(pairs); cum = 0; tot = 0; a = 0.0
    for s, e in pairs:
        cum += e; tot += 1; a += cum / tot
    return a / n

def aurc_random(scores, errors, perms=1000, seed=42):
    """Average AURC over random orderings within tied-score groups."""
    rng = random.Random(seed)
    idx = [i for i, s in enumerate(scores) if s is not None]
    n = len(idx)
    if n == 0:
        return None
    vals = []
    for _ in range(perms):
        order = sorted(idx, key=lambda i: (-scores[i], rng.random()))
        cum = 0; tot = 0; a = 0.0
        for i in order:
            cum += errors[i]; tot += 1; a += cum / tot
        vals.append(a / n)
    return sum(vals) / len(vals)

def aurc_random_exact(scores, errors):
    """Closed-form: AURC with ties = average over all tie orders equals
    grouping by score, treating within-group errors in expectation.
    Equivalent to computing AURC on score groups where each group's internal
    order is random: E[AURC] = same as evaluating with expected cumulative
    error at each within-group prefix.  Implemented via the permutation-free
    formula: sort by score desc; within a tied block of size m with e errors,
    the expected cumulative-error contribution is e*(k+1/2 terms)...
    Simpler and exact: average the two extreme orders (all-errors-first and
    all-errors-last) -> equals midrank AURC.  We use the permutation average
    from aurc_random as the estimate and report its Monte-Carlo s.d."""
    return None

for alias in MODELS:
    complete = load(f"{RES}/{alias}.jsonl")
    rows = []
    for qid, cm in complete.items():
        gold = gold_of(questions[qid])
        sv = [cm[("0", str(s))]["answer"] for s in range(1, 7)]
        pv = [cm[(str(p), "1")]["answer"] for p in range(1, 7)]
        comb = sv + pv
        c = Counter(comb)
        # comb12 correctness (same majority rule as analyze_v2: first-appearing winner)
        top = max(c.values())
        ans = None
        for v in comb:
            if c[v] == top:
                ans = v
                break
        rows.append({
            "err": 0 if ans == gold else 1,
            "cs": Counter(sv).most_common(1)[0][1] / 6,
            "cp": Counter(pv).most_common(1)[0][1] / 6,
        })
    errs = [r["err"] for r in rows]
    for sig in ("cs", "cp"):
        sc = [r[sig] for r in rows]
        a_st = aurc_stable(sc, errs)
        a_rd = aurc_random(sc, errs)
        rand_baseline = sum(errs) / len(errs)  # AURC of random ordering
        print(f"{alias:16s} {sig}: stable={a_st:.4f} tie-random={a_rd:.4f} "
              f"err_rate={rand_baseline:.4f} n_err={sum(errs)}")

print()
print("=" * 100)
print("PART 4: mode-share distribution (COMB-12), all models pooled + per model")
print("=" * 100)
all_shares = []
for alias in MODELS:
    complete = load(f"{RES}/{alias}.jsonl")
    shares = []
    for qid, cm in complete.items():
        sv = [cm[("0", str(s))]["answer"] for s in range(1, 7)]
        pv = [cm[(str(p), "1")]["answer"] for p in range(1, 7)]
        comb = sv + pv
        shares.append(max(Counter(comb).values()) / len(comb))
    all_shares += shares
    hist = Counter(round(s, 2) for s in shares)
    print(f"{alias}: n={len(shares)} share=1.0: {sum(1 for s in shares if s==1.0)}, "
          f"0.917 (11/12): {sum(1 for s in shares if abs(s-11/12)<1e-9)}, "
          f"0.833 (10/12): {sum(1 for s in shares if abs(s-10/12)<1e-9)}, "
          f"<0.833: {sum(1 for s in shares if s<10/12-1e-9)}")
print(f"pooled: n={len(all_shares)} unanimous={sum(1 for s in all_shares if s==1.0)/len(all_shares):.3f} "
      f"mean={sum(all_shares)/len(all_shares):.3f}")

# save machine-readable summary
out = {m: {k: v for k, v in s.items() if k != "off_mode_detail"} for m, s in summary.items()}
for m in out:
    out[m]["off_mode_qids"] = [d["qid"] for d in summary[m]["off_mode_detail"]]
json.dump(out, open(f"{RES}/analysis/diag_tau0.json", "w"), indent=1)
print("\nsaved -> results/analysis/diag_tau0.json")
