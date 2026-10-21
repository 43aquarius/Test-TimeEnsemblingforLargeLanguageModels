#!/usr/bin/env python3
"""Greedy-bias audit for the EXPANSION set: for every (model, qid) where the
greedy answer sits off the six-sample mode, dump the raw greedy record
(snippet, token usage), the six canonical sample answers, the modal answer,
mode share, gold answer, and dataset. Writes JSON + markdown to
supplementary_data/greedy_bias_audit_expand/.

Usage: python3 export_audit_expand.py
"""
import json, os
from collections import Counter, defaultdict

RES = "/home/z/my-project/results/expand"
OUT = "/home/z/my-project/supplementary_data/greedy_bias_audit_expand"
os.makedirs(OUT, exist_ok=True)
questions = {q["id"]: q for q in json.load(open("/home/z/my-project/data/questions_expand.json"))}

def gold_of(q):
    if q["dataset"] == "gsm8k":
        return str(q["answer"])
    if q["dataset"] == "piqa":
        return str(q["answer_idx"] + 1)
    return "ABCDEFGHIJ"[q["answer_idx"]]

MAIN_NEED = [(0, "g")] + [(0, str(s)) for s in range(1, 7)] + \
            [(p, str(s)) for p in (1, 2, 3) for s in (1, 2)] + [(p, "1") for p in (4, 5, 6)]

MODELS = [m for m in ("agnes-3.0-flash", "agnes-2.5-flash", "qwen3.7-flash")
          if os.path.exists(f"{RES}/{m}.jsonl")]

summary = {}
for alias in MODELS:
    cells = defaultdict(dict)
    for line in open(f"{RES}/{alias}.jsonl"):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("FAILED") or r.get("answer") is None:
            continue
        cells[r["qid"]][(r["para"], str(r["sample"]))] = r
    complete = {qid: cm for qid, cm in cells.items() if all(k in cm for k in MAIN_NEED)}
    ev = []
    for qid, cm in sorted(complete.items()):
        q = questions[qid]
        gold = gold_of(q)
        g = cm[(0, "g")]
        sv = [cm[(0, str(s))]["answer"] for s in range(1, 7)]
        cnt = Counter(sv)
        top = max(cnt.values())
        winners = set(v for v, n in cnt.items() if n == top)
        if g["answer"] in winners:
            continue
        # off-mode: record evidence
        s_acc = sum(v == gold for v in sv) / 6
        ev.append({
            "qid": qid, "dataset": q["dataset"],
            "gold": gold,
            "greedy_answer": g["answer"],
            "greedy_correct": g["answer"] == gold,
            "greedy_usage": g.get("usage"),
            "greedy_content_len": g.get("content_len"),
            "greedy_snippet": g.get("snippet"),
            "six_sample_answers": sv,
            "sample_answers_correct": [v == gold for v in sv],
            "sample_acc": round(s_acc, 3),
            "modal_answer": sorted(winners)[0],
            "mode_share": round(top / 6, 3),
            "mode_is_gold": (sorted(winners)[0] == gold) if len(winners) == 1 else None,
        })
    n = len(complete)
    cost = sum(1 for e in ev if not e["greedy_correct"]) - sum(
        1 for e in ev if not e["greedy_correct"] and e["sample_acc"] < 0.5)
    summary[alias] = {
        "n_complete": n, "n_off_mode": len(ev),
        "off_mode_rate": round(len(ev) / max(1, n), 4),
        "off_mode_but_greedy_correct": sum(1 for e in ev if e["greedy_correct"]),
        "evidence": ev,
    }
    # per-model JSON dump
    json.dump(summary[alias], open(f"{OUT}/{alias}_offmode.json", "w"),
              indent=1, ensure_ascii=False)
    print(f"{alias}: {len(ev)}/{n} off-mode "
          f"({100*len(ev)/max(1,n):.1f}%), greedy-right on {sum(1 for e in ev if e['greedy_correct'])} of them")

# combined markdown index
md = ["# Expansion set: greedy off-mode audit", "",
      "Greedy answer falls outside the six-sample modal set. "
      "Raw evidence per model in `<model>_offmode.json`.", ""]
for alias, s in summary.items():
    md.append(f"## {alias}")
    md.append("")
    md.append(f"- complete questions: {s['n_complete']}")
    md.append(f"- off-mode greedy: {s['n_off_mode']} ({100*s['off_mode_rate']:.1f}%)")
    md.append(f"- off-mode but greedy correct: {s['off_mode_but_greedy_correct']}")
    md.append("")
    md.append("| qid | dataset | gold | greedy | greedy ok | mode | share | S-acc |")
    md.append("|---|---|---|---|---|---|---|---|")
    for e in s["evidence"]:
        md.append(f"| {e['qid']} | {e['dataset']} | {e['gold']} | {e['greedy_answer']} | "
                  f"{'Y' if e['greedy_correct'] else 'N'} | {e['modal_answer']} | "
                  f"{e['mode_share']:.2f} | {e['sample_acc']:.2f} |")
    md.append("")
open(f"{OUT}/README.md", "w").write("\n".join(md))
json.dump({k: {kk: vv for kk, vv in v.items() if kk != "evidence"} for k, v in summary.items()},
          open(f"{OUT}/summary.json", "w"), indent=1)
print(f"\nwrote {OUT}/ (README.md, summary.json, per-model JSON)")
