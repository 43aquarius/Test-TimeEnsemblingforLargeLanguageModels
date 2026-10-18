#!/usr/bin/env python3
"""Data quality check + preliminary analysis on completed models.
Validates: parse rate, sample diversity, SC/PE/HB condition derivation."""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import json, sys
from collections import Counter, defaultdict

RES = ROOT + "/results"

def load(model):
    recs = [json.loads(l) for l in open(f"{RES}/{model}.jsonl")]
    return [r for r in recs if not r.get("FAILED")]

def majority(votes):
    """Majority vote; tie-break by first occurrence in votes."""
    if not votes: return None
    c = Counter(votes)
    top = c.most_common()
    best_n = top[0][1]
    winners = [v for v, n in top if n == best_n]
    for v in votes:
        if v in winners: return v
    return votes[0]

def analyze(model, verbose=True):
    recs = load(model)
    by_q = defaultdict(dict)
    for r in recs:
        by_q[r["qid"]][(r["para"], str(r["sample"]))] = r
    stats = {"total": len(recs), "parsed": sum(1 for r in recs if r["answer"] is not None)}
    # complete questions: all 16 cells
    complete, partial = [], 0
    for qid, cells in by_q.items():
        need = [(0, str(s)) for s in range(1, 7)] + [(p, str(s)) for p in (1, 2, 3) for s in (1, 2)] + \
               [(p, "1") for p in (4, 5, 6)] + [(0, "g")]
        if all(k in cells and cells[k]["answer"] is not None for k in need):
            complete.append(qid)
        else:
            partial += 1
    stats["complete_questions"] = len(complete)
    stats["partial"] = partial

    if complete:
        qs = {q["id"]: q for q in json.load(open(ROOT + "/data/questions.json"))}
        accs = defaultdict(list)
        frag = 0
        for qid in complete:
            q = qs[qid]
            cells = by_q[qid]
            gold = ("ABCDEFGHIJ"[q["answer_idx"]] if q["options"] and q["dataset"] != "piqa"
                    else (str(q["answer_idx"] + 1) if q["dataset"] == "piqa" else q["answer"]))
            # greedy
            g = cells[(0, "g")]["answer"]
            # SC-6: P0 samples 1-6
            sc_votes = [cells[(0, str(s))]["answer"] for s in range(1, 7)]
            sc = majority([v for v in sc_votes if v])
            # PE-6: P1-P6 first sample
            pe_votes = [cells[(p, "1")]["answer"] for p in range(1, 7)]
            pe = majority([v for v in pe_votes if v])
            # HB-6: P1-P3 x 2 samples
            hb_votes = [cells[(p, str(s))]["answer"] for p in (1, 2, 3) for s in (1, 2)]
            hb = majority([v for v in hb_votes if v])
            # COMB-12: P0x6 + P1-P6x1
            comb_votes = sc_votes + pe_votes
            comb = majority([v for v in comb_votes if v])
            for name, pred in [("greedy", g), ("SC-6", sc), ("PE-6", pe), ("HB-6", hb), ("COMB-12", comb)]:
                if pred is not None:
                    accs[name].append(pred == gold)
            # fragility: paraphrase majority != P0-majority answer
            p0_maj = majority([v for v in sc_votes if v])
            pe_maj = majority([v for v in pe_votes if v])
            if p0_maj and pe_maj and p0_maj != pe_maj:
                frag += 1
        if verbose:
            print(f"\n=== {model}: {stats['total']} calls, parse rate {100*stats['parsed']/stats['total']:.1f}%, "
                  f"{stats['complete_questions']} complete questions ===")
            for name in ["greedy", "SC-6", "PE-6", "HB-6", "COMB-12"]:
                if accs[name]:
                    print(f"  {name:8s}: acc = {100*sum(accs[name])/len(accs[name]):.1f}%  (n={len(accs[name])})")
            print(f"  Fragile questions (P0-maj != PE-maj): {frag}/{len(complete)}")
    return stats, accs

if __name__ == "__main__":
    models = sys.argv[1:] or ["qwen3.8-max"]
    for m in models:
        analyze(m)
