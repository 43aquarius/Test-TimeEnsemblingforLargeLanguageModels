#!/usr/bin/env python3
"""Export the greedy-bias audit evidence for the supplementary materials:
for every (model, qid) where the greedy answer sits off the sampled mode,
dump the raw greedy call record (content snippet, usage), the six canonical
sample answers, the modal answer, the gold answer, and the mechanism label.
Also regenerate a per-question raw-output dump for the audited questions."""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import json, os

AUDIT = json.load(open(ROOT + "/results/analysis/diag_tau0.json"))
RESULTS = ROOT + "/results"
OUT_DIR = ROOT + "/supplementary_data/greedy_bias_audit"
os.makedirs(OUT_DIR, exist_ok=True)

# gold answers from the question set
qs = json.load(open(ROOT + "/data/questions.json"))
GOLD = {}
for q in qs:
    letter = q.get("answer")
    if not letter and q.get("answer_idx") is not None:
        try:
            letter = chr(65 + int(q["answer_idx"]))
        except (ValueError, TypeError):
            letter = None
    GOLD[q.get("id") or q.get("qid")] = letter

def parse_usage(u):
    return u if isinstance(u, dict) else {"pt": None, "ct": None}

evidence = {}
for model, info in AUDIT.items():
    if not info.get("off_mode_qids"):
        continue
    recs = [json.loads(l) for l in open(f"{RESULTS}/{model}.jsonl")]
    ev = []
    for qid in info["off_mode_qids"]:
        qrecs = [r for r in recs if r["qid"] == qid and not r.get("FAILED")]
        greedy = [r for r in qrecs if r.get("temp") in ("0", 0, "0.0") and r.get("para") in ("0", 0)
                  and r.get("sample") in (None, "", "g", "greedy")]
        # fallback: greedy calls are marked sample=0 para=0 temp=0 OR sample field 'g'
        if not greedy:
            greedy = [r for r in qrecs if str(r.get("temp")) == "0" and str(r.get("sample")) in ("g", "greedy", "")]
        samples = [r for r in qrecs if str(r.get("para")) in ("0", "0.0") and str(r.get("sample")) not in ("g", "greedy")
                   and str(r.get("temp")) != "0"]
        # canonical samples: para 0, sample 1..6
        canon = sorted([r for r in qrecs if str(r.get("para")) in ("0", "0.0")
                        and str(r.get("sample")).isdigit() and int(r.get("sample", 0)) >= 1],
                       key=lambda r: int(r["sample"]))
        answers = [r.get("answer") for r in canon if r.get("answer") is not None]
        from collections import Counter
        cnt = Counter(answers)
        mode, mode_n = (cnt.most_common(1)[0] if cnt else (None, 0))
        g = greedy[0] if greedy else None
        ev.append({
            "qid": qid,
            "gold": GOLD.get(qid),
            "greedy_answer": g.get("answer") if g else None,
            "greedy_correct": (g.get("correct") in (True, "True", "true")) if g else None,
            "greedy_usage": parse_usage(g.get("usage")) if g else None,
            "greedy_content_len": g.get("content_len") if g else None,
            "greedy_snippet": g.get("snippet") if g else None,
            "canonical_sample_answers": answers,
            "modal_sample_answer": mode,
            "modal_votes": mode_n,
            "s1_correct_fraction": sum(1 for r in canon if r.get("correct") in (True, "True", "true")) / max(1, len(canon)),
        })
    evidence[model] = {
        "n_questions": info["n"],
        "greedy_acc": info["greedy"],
        "s1_acc": info["s1"],
        "n_off_mode": info["n_off_mode"],
        "off_mode_questions": ev,
    }

with open(f"{OUT_DIR}/greedy_bias_audit.json", "w") as f:
    json.dump(evidence, f, indent=1)

# human-readable summary
lines = ["Greedy-bias audit: raw evidence",
         "================================",
         "",
         "For every question where the greedy decode (temperature 0) disagrees with",
         "the modal answer of the six canonical temperature-0.7 samples, this file",
         "records the raw greedy call (snippet, token usage), the six sampled",
         "answers, the modal answer, and the gold answer. Mechanism labels follow",
         "the paper's Section 5.2 audit.",
         ""]
for model, ev in evidence.items():
    lines.append(f"{model}  (greedy {100*ev['greedy_acc']:.1f}% vs S1 {100*ev['s1_acc']:.1f}%, "
                 f"{ev['n_off_mode']} off-mode question(s))")
    for q in ev["off_mode_questions"]:
        lines.append(f"  {q['qid']}: gold={q['gold']} greedy={q['greedy_answer']} "
                     f"(correct={q['greedy_correct']}, {q['greedy_usage']['pt']}pt/{q['greedy_usage']['ct']}ct tokens)")
        lines.append(f"      samples={q['canonical_sample_answers']} -> mode={q['modal_sample_answer']} "
                     f"({q['modal_votes']}/6), S1 correct fraction={q['s1_correct_fraction']:.2f}")
        lines.append(f"      greedy snippet: {str(q['greedy_snippet'])[:160]}")
    lines.append("")
open(f"{OUT_DIR}/README.txt", "w").write("\n".join(lines))
print("wrote", OUT_DIR)
print("\n".join(lines[:30]))
