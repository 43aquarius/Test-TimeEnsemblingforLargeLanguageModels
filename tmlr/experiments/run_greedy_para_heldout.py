#!/usr/bin/env python3
"""D2 -- held-out greedy-paraphrase control (PE-g-6).

Re-decodes each of the six paraphrases of every held-out question at tau=0 on
the four fully covered models, yielding the noise-free paraphrase ensemble
PEg-6 that the paper currently lacks out of sample.  Prompt construction,
parsing, and log format follow the release's run_conditions.py; calls go
through the same OpenAI-compatible endpoint configuration the user supplies.

Design decisions to keep the control comparable:
  * same paraphrases as the main matrix (para 1-6, first-decode slots);
  * greedy decoding (temperature 0, seed fixed to 0 -- deterministic);
  * the canonical side is NOT re-collected: SC-6/greedy rows already exist in
    the held-out logs, so PEg-6 pairs with them directly;
  * output jsonl: results/cond_greedypara_heldout/<model>.jsonl with the same
    field layout as cond_greedypara/*.jsonl (para as int, sample "g").

Result placeholder: until this run completes, the paper's held-out paraphrase
margins keep the "sampling noise mixed in" caveat (Sections 5.2 and B).

Usage:
  python3 run_greedy_para_heldout.py --models agnes-3.0-flash,agnes-2.5-flash \\
      --repo /path/to/repo --config experiments/endpoints.json
"""
import argparse, json, os, re, time

def gold_of(q):
    if q["dataset"] == "gsm8k":
        return str(q["answer"])
    if q["dataset"] == "piqa":
        return str(q["answer_idx"] + 1)
    return "ABCDEFGHIJ"[q["answer_idx"]]


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


def load_instr(repo):
    """Instruction bank = development store merged with the expansion store."""
    a = json.load(open(os.path.join(repo, "data/paraphrases.json")))["instructions"]
    b = json.load(open(os.path.join(repo, "data/paraphrases_expand.json")))["instructions"]
    return {**a, **b}



def call_endpoint(cfg, model_id, prompt, temp, max_tokens=512):
    """OpenAI-compatible chat call. cfg keys: base_url, api_key (from env)."""
    from openai import OpenAI
    client = OpenAI(base_url=cfg["base_url"], api_key=os.environ.get(cfg.get("key_env", "OPENAI_API_KEY")))
    r = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": prompt}],
        temperature=temp,
        max_tokens=max_tokens,
        seed=0)
    text = r.choices[0].message.content or ""
    usage = {"pt": getattr(getattr(r, "usage", None), "prompt_tokens", 0) or 0,
             "ct": getattr(getattr(r, "usage", None), "completion_tokens", 0) or 0}
    return text, usage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True, help="comma-separated aliases, e.g. agnes-3.0-flash,...")
    ap.add_argument("--repo", default="/home/z/my-project/repo")
    ap.add_argument("--config", required=True,
                    help="JSON: {alias: {model_id, base_url, key_env}}")
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfgs = json.load(open(args.config))
    questions = json.load(open(os.path.join(args.repo, "data/questions_expand.json")))
    para_bank = json.load(open(os.path.join(args.repo, "data/paraphrases_expand.json")))["paraphrases"]
    instr = load_instr(args.repo)
    outdir = args.outdir or os.path.join(args.repo, "results/cond_greedypara_heldout")
    os.makedirs(outdir, exist_ok=True)

    for alias in args.models.split(","):
        alias = alias.strip()
        cfg = cfgs[alias]
        out = os.path.join(outdir, f"{alias}.jsonl")
        n = 0
        for q in questions:
            for para in range(1, 7):           # paraphrases 1-6, greedy
                prompt = build_prompt(q, para, para_bank, instr)
                if args.dry_run:
                    print(f"[dry] {alias} {q['id']} para={para}")
                    continue
                text, usage = call_endpoint(cfg, cfg["model_id"], prompt, 0.0, args.max_tokens)
                answer = extract_answer(text, q)
                gold = gold_of(q)
                rec = {"model": alias, "qid": q["id"], "dataset": q["dataset"],
                       "para": para, "sample": "g", "temp": 0.0,
                       "answer": answer, "correct": (answer == gold) if answer else False,
                       "content_len": len(text), "reasoning_len": 0,
                       "snippet": text[:120], "usage": usage, "t": round(time.time(), 1)}
                with open(out, "a") as f:
                    f.write(json.dumps(rec) + "\n")
                n += 1
        if not args.dry_run:
            print(f"{alias}: {n} greedy paraphrase calls -> {out}")


if __name__ == "__main__":
    main()
