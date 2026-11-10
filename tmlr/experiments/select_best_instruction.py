#!/usr/bin/env python3
"""D3a -- pre-register the best SAT-Math instruction variant (on development data).

Runs BEFORE the new SAT-Math draw is collected (D3b), so the variant choice
cannot see the evaluation data.  Selection rule (fixed in advance):

  score(variant k) = pooled single-call accuracy of paraphrase-slot-k
                     first decodes over the development-suite SAT-Math items,
                     averaged over the models that completed the main matrix
                     (question-level mean of per-model means, as in the paper);

  selected variant  = argmax_k score(k); ties broken by the lower-variance
                     variant (mean over models of |per-model rank deviation|),
                     then by the smaller variant index.

Outputs a pre-registration JSON (variant index, its wording, scores, date,
and a SHA-256 of the selection inputs) that D3b consumes verbatim.

Usage:
  python3 select_best_instruction.py --repo /path/to/repo \
      --out experiments/prereg_best_instruction.json
"""
import argparse, datetime, hashlib, json, os

def load_logs(repo, model):
    path = os.path.join(repo, "results", f"{model}.jsonl")
    cells = {}
    for line in open(path):
        r = json.loads(line)
        if r.get("FAILED"):
            continue
        cells[(r["qid"], r["para"], str(r["sample"]))] = r
    return cells


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="/home/z/my-project/repo")
    ap.add_argument("--models", default="qwen3.8-max,qwen3.8-omni,agnes-3.0-flash,agnes-2.5-flash")
    ap.add_argument("--out", default="prereg_best_instruction.json")
    args = ap.parse_args()

    questions = json.load(open(os.path.join(args.repo, "data/questions.json")))
    _a = json.load(open(os.path.join(args.repo, "data/paraphrases.json")))["instructions"]
    _b = json.load(open(os.path.join(args.repo, "data/paraphrases_expand.json")))["instructions"]
    instr = {**_a, **_b}["sat_math"]

    global cells_all
    cells_all = {}
    for m in args.models.split(","):
        cells_all[m] = load_logs(args.repo, m.strip())

    # score each variant over development SAT-Math items per model
    scores = {}
    per_model = {}
    for m, cells in cells_all.items():
        sat = [q for q in questions if q["dataset"] == "sat_math" and q["instruction_type"] == "instruction"]
        usable = [q for q in sat
                  if all((q["id"], 0, str(s)) in cells for s in range(1, 7))
                  and all((q["id"], p, "1") in cells for p in range(1, 7))]
        row = {}
        for k in range(0, 7):  # 0 = canonical P0
            hits = []
            for q in usable:
                if k == 0:
                    votes = [cells[(q["id"], 0, str(s))]["answer"] for s in range(1, 7)]
                else:
                    votes = [cells[(q["id"], k, "1")]["answer"]]
                hits.append(sum(1 for v in votes if v is not None and v == gold(q)) / len(votes))
            row[k] = sum(hits) / len(hits) if hits else None
        per_model[m] = {"n_items": len(usable), "scores": row}
    for k in range(0, 7):
        vals = [per_model[m]["scores"][k] for m in cells_all if per_model[m]["scores"][k] is not None]
        if vals:
            scores[k] = sum(vals) / len(vals)

    # selection among variants 1..6 (the canonical P0 is score[0], reference only)
    variants = {k: s for k, s in scores.items() if k >= 1}
    best = max(variants, key=lambda k: (variants[k], -k))
    # tie -> lower spread across models
    ties = [k for k in variants if abs(variants[k] - variants[best]) < 1e-12]
    if len(ties) > 1:
        def spread(k):
            vs = [per_model[m]["scores"][k] for m in cells_all if per_model[m]["scores"][k] is not None]
            mu = sum(vs) / len(vs)
            return sum(abs(v - mu) for v in vs) / len(vs)
        best = sorted(ties, key=lambda k: (spread(k), k))[0]

    payload = {
        "task": "pre-registration of the best SAT-Math instruction variant",
        "rule": "argmax pooled single-call accuracy over development-suite SAT-Math "
                "items; ties broken by lower cross-model spread, then smaller index",
        "selected_variant": f"P{best}",
        "wording": instr[f"P{best}"],
        "canonical_wording": instr["P0"],
        "development_scores_by_variant": {f"P{k}": round(s, 4) for k, s in sorted(scores.items())},
        "per_model": {m: {"n_items": d["n_items"],
                          "scores": {f"P{k}": (round(v, 4) if v is not None else None)
                                     for k, v in sorted(d["scores"].items())}}
                      for m, d in per_model.items()},
        "date": datetime.date.today().isoformat(),
    }
    payload["sha256"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    json.dump(payload, open(args.out, "w"), indent=1)
    print(f"selected {payload['selected_variant']} "
          f"(dev pooled {scores[best]:.3f} vs canonical {scores[0]:.3f}) -> {args.out}")


def gold(q):
    if q["dataset"] == "gsm8k":
        return str(q["answer"])
    if q["dataset"] == "piqa":
        return str(q["answer_idx"] + 1)
    return "ABCDEFGHIJ"[q["answer_idx"]]


if __name__ == "__main__":
    main()
