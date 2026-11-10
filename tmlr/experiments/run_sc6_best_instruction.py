#!/usr/bin/env python3
"""D3b -- SC-6 under the pre-registered best instruction, on a fresh SAT-Math draw.

Steps:
  1. draw a fresh set of SAT-Math items from the AGIEval source pool with a
     fixed seed, excluding every item already consumed by the development or
     held-out suites (matched on stem text);
  2. for each model configured in --config, run per item:
       canonical  : 6 stochastic samples at tau=0.7 under P0 (S1 + SC-6)
                    plus one greedy call (reference),
       best variant: 6 stochastic samples at tau=0.7 under the pre-registered
                    variant (single-call expectation + SC-6);
  3. write logs in the release format plus a summary JSON:
       S1, SC-6 (canonical) vs best-variant single-call, SC-6 (best variant),
       with paired bootstrap CIs for the two SC-6-vs-SC-6 and
       best-SC-6-vs-canonical-SC-6 differences.

The pre-registration file from D3a is consumed read-only; its SHA-256 is
echoed into the summary so the selection cannot be changed after the fact.

Usage:
  python3 run_sc6_best_instruction.py --repo /path/to/repo \
      --prereg experiments/prereg_best_instruction.json \
      --source /path/to/agieval/sat-math.jsonl --n 40 --seed 20261110 \
      --config experiments/endpoints.json --out experiments/d3_results.json
"""
import argparse, hashlib, json, os, random, re, time

def gold_of_q(q):
    if q["dataset"] == "gsm8k":
        return str(q["answer"])
    if q["dataset"] == "piqa":
        return str(q["answer_idx"] + 1)
    return "ABCDEFGHIJ"[q["answer_idx"]]


def extract_answer(content, q):
    c = content.strip()
    if not c:
        return None
    letters = "ABCDEFGHIJ"[:len(q["options"])] if q["options"] else "ABCDEFGHIJ"
    for p in (r"Answer:?\s*\**\s*\(?([A-J])\)?", r"\*\*([A-J])\*\*"):
        m = re.findall(p, c)
        if m and m[-1] in letters:
            return m[-1]
    for line in reversed(c.split("\n")):
        s = line.strip()
        if len(s) == 1 and s in letters:
            return s
    return None


def load_instr(repo):
    """Instruction bank = development store merged with the expansion store."""
    a = json.load(open(os.path.join(repo, "data/paraphrases.json")))["instructions"]
    b = json.load(open(os.path.join(repo, "data/paraphrases_expand.json")))["instructions"]
    return {**a, **b}



def read_source(path):
    """Read AGIEval-style SAT-Math items: expects {question, options, answer}."""
    ext = os.path.splitext(path)[1]
    items = []
    if ext == ".jsonl":
        for line in open(path):
            items.append(json.loads(line))
    else:
        items = json.load(open(path))
    out = []
    for it in items:
        stem = it.get("question") or it.get("stem")
        opts = it.get("options") or []
        gold_idx = it.get("answer")
        if gold_idx is None and isinstance(it.get("label"), str):
            gold_idx = "ABCDE".find(it["label"])
        if stem and opts and gold_idx is not None:
            out.append({"stem": stem, "options": opts, "answer_idx": int(gold_idx)})
    return out


def build_prompt(q, instruction):
    letters = "ABCDEFGHIJ"
    parts = [q["stem"],
             "Options:\n" + "\n".join(f"({letters[i]}) {o}" for i, o in enumerate(q["options"])),
             instruction]
    return "\n\n".join(parts)


def call_endpoint(cfg, prompt, temp, seed, max_tokens=512):
    from openai import OpenAI
    client = OpenAI(base_url=cfg["base_url"], api_key=os.environ.get(cfg.get("key_env", "OPENAI_API_KEY")))
    r = client.chat.completions.create(model=cfg["model_id"],
                                       messages=[{"role": "user", "content": prompt}],
                                       temperature=temp, max_tokens=max_tokens, seed=seed)
    text = r.choices[0].message.content or ""
    usage = {"pt": getattr(getattr(r, "usage", None), "prompt_tokens", 0) or 0,
             "ct": getattr(getattr(r, "usage", None), "completion_tokens", 0) or 0}
    return text, usage


def boot_ci(vals, iters=10000, seed=42, alpha=0.05):
    rng = random.Random(seed)
    n = len(vals)
    means = sorted(sum(vals[rng.randrange(n)] for _ in range(n)) / n for _ in range(iters))
    return sum(vals) / n, means[int(alpha / 2 * iters)], means[int((1 - alpha / 2) * iters) - 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="/home/z/my-project/repo")
    ap.add_argument("--prereg", required=True)
    ap.add_argument("--source", required=True, help="AGIEval SAT-Math raw items")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=20261110)
    ap.add_argument("--config", required=True, help="JSON {alias:{model_id,base_url,key_env}}")
    ap.add_argument("--out", default="d3_results.json")
    ap.add_argument("--logdir", default="results/d3_best_instruction")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    prereg = json.load(open(args.prereg))
    best_instr = prereg["wording"]
    instr = load_instr(args.repo)
    canonical = instr["sat_math"]["P0"]

    dev = json.load(open(os.path.join(args.repo, "data/questions.json")))
    held = json.load(open(os.path.join(args.repo, "data/questions_expand.json")))
    consumed = {q["stem"].strip().lower() for q in dev + held if q["dataset"] == "sat_math"}

    pool = [it for it in read_source(args.source)
            if it["stem"].strip().lower() not in consumed]
    rng = random.Random(args.seed)
    draw = rng.sample(pool, min(args.n, len(pool)))
    items = [{"id": f"d3_{i:03d}", "dataset": "sat_math", "instruction_type": "instruction",
              "stem": it["stem"], "options": it["options"], "answer_idx": it["answer_idx"]}
             for i, it in enumerate(draw)]
    print(f"fresh draw: {len(items)} SAT-Math items (pool {len(pool)}, "
          f"consumed {len(consumed)}, seed {args.seed})")
    if args.dry_run:
        for q in items[:2]:
            print("--- canonical ---"); print(build_prompt(q, canonical))
            print("--- best variant ---"); print(build_prompt(q, best_instr))
        return

    cfgs = json.load(open(args.config))
    os.makedirs(args.logdir, exist_ok=True)
    summary = {"prereg_sha256": prereg.get("sha256"), "selected_variant": prereg["selected_variant"],
               "n_items": len(items), "seed": args.seed, "models": {}}
    for alias, cfg in cfgs.items():
        rows = []
        out = os.path.join(args.logdir, f"{alias}.jsonl")
        for q in items:
            gold = "ABCD"[q["answer_idx"]]
            # canonical side: 6 samples + greedy
            canon = []
            for s in range(1, 7):
                text, usage = call_endpoint(cfg, build_prompt(q, canonical), 0.7, seed=1000 + s)
                a = extract_answer(text, q)
                canon.append(a)
                rows.append(_rec(alias, q, 0, s, 0.7, a, gold, text, usage))
            text, usage = call_endpoint(cfg, build_prompt(q, canonical), 0.0, seed=0)
            rows.append(_rec(alias, q, 0, "g", 0.0, extract_answer(text, q), gold, text, usage))
            # best-variant side: 6 samples
            bests = []
            for s in range(1, 7):
                text, usage = call_endpoint(cfg, build_prompt(q, best_instr), 0.7, seed=2000 + s)
                a = extract_answer(text, q)
                bests.append(a)
                rows.append(_rec(alias, q, 1, s, 0.7, a, gold, text, usage, para_tag="best"))
        with open(out, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        # summary statistics
        def acc(votes_fn):
            return 100 * sum(votes_fn(q) for q in items) / len(items)
        def mode(v):
            from collections import Counter
            vs = [x for x in v if x is not None]
            if not vs:
                return None
            c = Counter(vs); top = max(c.values())
            return next(x for x in vs if c[x] == top)
        canon_rows = {(r["qid"], r["sample"]): r for r in rows if r.get("para_tag") is None and r["para"] == 0}
        best_rows = {(r["qid"], r["sample"]): r for r in rows if r.get("para_tag") == "best"}
        s1 = acc(lambda q: sum(canon_rows[(q["id"], s)]["answer"] == "ABCD"[q["answer_idx"]] for s in range(1, 7)) / 6)
        sc6_c = acc(lambda q: 1 if mode([canon_rows[(q["id"], s)]["answer"] for s in range(1, 7)]) == "ABCD"[q["answer_idx"]] else 0)
        b1 = acc(lambda q: sum(best_rows[(q["id"], s)]["answer"] == "ABCD"[q["answer_idx"]] for s in range(1, 7)) / 6)
        sc6_b = acc(lambda q: 1 if mode([best_rows[(q["id"], s)]["answer"] for s in range(1, 7)]) == "ABCD"[q["answer_idx"]] else 0)
        diffs = [(1 if mode([best_rows[(q["id"], s)]["answer"] for s in range(1, 7)]) == "ABCD"[q["answer_idx"]] else 0)
                 - (1 if mode([canon_rows[(q["id"], s)]["answer"] for s in range(1, 7)]) == "ABCD"[q["answer_idx"]] else 0)
                 for q in items]
        m, lo, hi = boot_ci(diffs, seed=42)
        summary["models"][alias] = {"S1_canonical": round(s1, 1), "SC6_canonical": round(sc6_c, 1),
                                    "single_best": round(b1, 1), "SC6_best": round(sc6_b, 1),
                                    "SC6best_minus_SC6canonical": {"mean": round(100 * m, 1),
                                                                   "ci95": [round(100 * lo, 1), round(100 * hi, 1)]}}
        print(alias, summary["models"][alias])
    json.dump(summary, open(args.out, "w"), indent=1)
    print(f"summary -> {args.out}; import into the paper's Section 5.3 and "
          f"re-run audit_paper_numbers.py")


def _rec(alias, q, para, sample, temp, answer, gold, text, usage, para_tag=None):
    return {"model": alias, "qid": q["id"], "dataset": q["dataset"], "para": para,
            "sample": "g" if sample == "g" else sample, "temp": temp,
            "answer": answer, "correct": (answer == gold) if answer else False,
            "content_len": len(text), "reasoning_len": 0, "snippet": text[:120],
            "usage": usage, "t": round(time.time(), 1), "para_tag": para_tag}


if __name__ == "__main__":
    main()
