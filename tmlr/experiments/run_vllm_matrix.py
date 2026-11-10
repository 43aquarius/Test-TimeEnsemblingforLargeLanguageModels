#!/usr/bin/env python3
"""D1 -- local open-weight replication of the 16-call matrix on the held-out suite.

Protocol (identical to the released pipeline):
  questions  : data/questions_expand.json (119 held-out items, ids e000--e119)
  prompts    : build_prompt() with the same instruction bank and paraphrase
               set as run_expand.py (canonical P0 at para=0; paraphrase k-1 at
               para=k; handcrafted variants on instruction-locus datasets)
  decoding   : temperature 0.7, top_p 1.0 for the 15 stochastic calls;
               temperature 0.0 for the greedy call; one deterministic seed per
               call (stable hash of qid/para/sample)
  matrix     : 1 greedy + 6 canonical samples + 6 paraphrase first-decodes
               + 3 paraphrase second-decodes (paraphrases 1-3)
  parsing    : the release's extract_answer() (Answer:<letter/number> first,
               fallback scan of final output lines)
  log format : the release's per-call JSON fields

The paper carries this control as a TODO; when the run completes, add the row
to tab_expand and re-run audit_paper_numbers.py.

Usage:
  python3 run_vllm_matrix.py --model Qwen/Qwen3-8B \\
      --repo /path/to/repo --out results/expand_vllm/qwen3-8b.jsonl
  python3 run_vllm_matrix.py ... --dry-run   # show the call plan, no engine
"""
import argparse, hashlib, json, os, re, sys, time

NEED = ([(0, "g", 0.0)]                                    # 1 greedy call
        + [(0, s, 0.7) for s in range(1, 7)]               # 6 canonical samples
        + [(p, s, 0.7) for p in (1, 2, 3) for s in (1, 2)]  # 3x2 paraphrases
        + [(p, 1, 0.7) for p in (4, 5, 6)])                # 3x1 paraphrases


def load_instruction_bank(repo, explicit=None):
    """Instruction bank = development store merged with the expansion store."""
    if explicit:
        return json.load(open(explicit))
    a = json.load(open(os.path.join(repo, "data/paraphrases.json")))["instructions"]
    b = json.load(open(os.path.join(repo, "data/paraphrases_expand.json")))["instructions"]
    return {**a, **b}


def build_prompt(q, para_idx, para_bank, instr):
    ds = q["dataset"]
    if q["instruction_type"] == "instruction":
        stem, ivar = q["stem"], instr[ds][f"P{para_idx}"]
    else:
        stem = q["stem"] if para_idx == 0 else para_bank[q["id"]][para_idx - 1]
        ivar = instr[ds]["P0"]
    parts = []
    if q.get("passage"):
        parts.append(q["passage"])
    parts.append(stem)
    if q["options"]:
        letters = "ABCDEFGHIJ"
        parts.append("Options:\n" + "\n".join(f"({letters[i]}) {o}" for i, o in enumerate(q["options"])))
    parts.append(ivar)
    return "\n\n".join(parts)


def extract_answer(content, q):
    c = content.strip()
    if not c:
        return None
    n_opt = len(q["options"]) if q["options"] else None
    letters = "ABCDEFGHIJ"[:n_opt] if n_opt else "ABCDEFGHIJ"
    if q["dataset"] == "gsm8k":
        m = re.findall(r"Answer:\s*\$?\s*(-?[\d,]+(?:\.\d+)?)", c)
        if m:
            return m[-1].replace(",", "")
        for line in reversed(c.split("\n")):
            nums = re.findall(r"-?[\d,]+(?:\.\d+)?", line)
            if nums:
                return nums[-1].replace(",", "")
        return None
    if q["dataset"] == "piqa":
        m = re.findall(r"Answer:?\s*\**\s*([12])", c)
        if m:
            return m[-1]
        for line in reversed(c.split("\n")):
            if line.strip() in ("1", "2"):
                return line.strip()
        return None
    for p in (r"Answer:?\s*\**\s*\(?([A-J])\)?", r"\*\*([A-J])\*\*"):
        m = re.findall(p, c)
        if m and m[-1] in letters:
            return m[-1]
    for line in reversed(c.split("\n")):
        s = line.strip()
        if len(s) == 1 and s in letters:
            return s
    return None


def gold_of(q):
    if q["dataset"] == "gsm8k":
        return str(q["answer"])
    if q["dataset"] == "piqa":
        return str(q["answer_idx"] + 1)
    return "ABCDEFGHIJ"[q["answer_idx"]]


def seed_for(qid, para, sample):
    h = hashlib.sha256(f"{qid}|{para}|{sample}".encode()).digest()
    return int.from_bytes(h[:4], "little") % (2**31 - 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--repo", default="/home/z/my-project/repo")
    ap.add_argument("--questions", default=None)
    ap.add_argument("--paraphrases", default=None)
    ap.add_argument("--instr-bank", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    qpath = args.questions or os.path.join(args.repo, "data/questions_expand.json")
    ppath = args.paraphrases or os.path.join(args.repo, "data/paraphrases_expand.json")
    questions = json.load(open(qpath))
    para_bank = json.load(open(ppath))["paraphrases"]
    instr = load_instruction_bank(args.repo)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    model_alias = os.path.basename(args.out).replace(".jsonl", "")

    if args.dry_run:
        n = sum(len(NEED) for _ in questions)
        print(f"plan: {n} calls over {len(questions)} questions")
        q0 = questions[0]
        print("--- canonical prompt (para=0) ---")
        print(build_prompt(q0, 0, para_bank, instr))
        print("--- paraphrase prompt (para=1) ---")
        print(build_prompt(q0, 1, para_bank, instr))
        return

    from vllm import LLM, SamplingParams
    llm = LLM(model=args.model)
    n_written = 0
    for q in questions:
        for para, sample, temp in NEED:
            sp = SamplingParams(temperature=temp, top_p=1.0,
                                max_tokens=args.max_tokens,
                                seed=seed_for(q["id"], para, sample))
            resp = llm.generate([build_prompt(q, para, para_bank, instr)], sp)[0]
            text = resp.outputs[0].text
            answer = extract_answer(text, q)
            gold = gold_of(q)
            rec = {"model": model_alias, "qid": q["id"], "dataset": q["dataset"],
                   "para": para,
                   "sample": "g" if sample == "g" else sample,
                   "temp": temp,
                   "answer": answer, "correct": (answer == gold) if answer else False,
                   "content_len": len(text), "reasoning_len": 0,
                   "snippet": text[:120],
                   "usage": {"pt": len(text.split()), "ct": 0},
                   "t": round(time.time(), 1)}
            with open(args.out, "a") as f:
                f.write(json.dumps(rec) + "\n")
            n_written += 1
    print(f"wrote {n_written} calls to {args.out}; "
          f"recompute with audit_paper_numbers.py --root {args.repo}")


if __name__ == "__main__":
    main()
