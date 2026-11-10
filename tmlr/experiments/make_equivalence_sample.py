#!/usr/bin/env python3
"""D4a -- human equivalence spot-check sample for LogiQA stem rewrites.

Draws 100 (original stem, paraphrase) pairs at random (fixed seed) from the
LogiQA stem-locus paraphrases of both suites and emits a fill-in annotation
table:

    qid | suite | para# | original stem | paraphrase | equivalent? | notes

The `equivalent?` column is left blank for the annotator(s); the summary
script (D4b) consumes the filled table.  Two annotators are recommended;
the second set of columns is provided.

Usage:
  python3 make_equivalence_sample.py --repo /path/to/repo \
      --n 100 --seed 20261110 --out equivalence_annotation.csv
"""
import argparse, csv, hashlib, json, os, random

def load_paraphrases(repo):
    """qid -> [six paraphrases] per suite (from the release's stores)."""
    dev = json.load(open(os.path.join(repo, "data/paraphrases.json")))["paraphrases"]
    held = json.load(open(os.path.join(repo, "data/paraphrases_expand.json")))["paraphrases"]
    return {"development": dev, "held-out": held}


def load_questions(repo):
    dev = {q["id"]: q for q in json.load(open(os.path.join(repo, "data/questions.json")))}
    held = {q["id"]: q for q in json.load(open(os.path.join(repo, "data/questions_expand.json")))}
    return {"development": dev, "held-out": held}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="/home/z/my-project/repo")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=20261110)
    ap.add_argument("--dataset", default="logiqa")
    ap.add_argument("--out", default="equivalence_annotation.csv")
    args = ap.parse_args()

    qs = load_questions(args.repo)
    paras = load_paraphrases(args.repo)
    rows = []
    for suite in ("development", "held-out"):
        for qid, plist in paras[suite].items():
            q = qs[suite].get(qid)
            if q is None or q["dataset"] != args.dataset or q["instruction_type"] != "stem":
                continue
            for idx, p in enumerate(plist, start=1):
                rows.append({"suite": suite, "qid": qid, "para": idx,
                             "original": q["stem"], "paraphrase": p})
    rng = random.Random(args.seed)
    sample = rng.sample(rows, min(args.n, len(rows)))
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["#", "suite", "qid", "para#", "original stem", "paraphrase",
                    "equivalent? (Y/N)", "notes (what changed, if anything)"])
        for i, r in enumerate(sample, start=1):
            w.writerow([i, r["suite"], r["qid"], r["para"], r["original"], r["paraphrase"], "", ""])
    digest = hashlib.sha256(json.dumps(sample, sort_keys=True).encode()).hexdigest()
    meta = {"n_pool": len(rows), "n_sample": len(sample), "seed": args.seed,
            "dataset": args.dataset, "sha256": digest}
    json.dump(meta, open(args.out + ".meta.json", "w"), indent=1)
    print(f"annotation table -> {args.out}  ({meta['n_sample']} of {meta['n_pool']} pairs, seed {args.seed})")
    print("protocol: annotate `equivalent?` as Y only if the paraphrase preserves "
          "the full problem statement (premises, question, all numbers/negations); "
          "otherwise N and describe the change in `notes`.")


if __name__ == "__main__":
    main()
