#!/usr/bin/env python3
"""Precise gap count (analysis-grade) + real-question parse test on apinex."""
import json, os, re, sys, time
from collections import defaultdict

DATA = "/home/z/my-project/data"
RES = "/home/z/my-project/results/expand"
sys.path.insert(0, "/home/z/my-project/scripts")

questions = {q["id"]: q for q in json.load(open(f"{DATA}/questions_expand.json"))}
pdata = json.load(open(f"{DATA}/paraphrases_expand.json"))
PARA, INSTR = pdata["paraphrases"], pdata["instructions"]
_orig = json.load(open(f"{DATA}/paraphrases.json"))
PARA.update(_orig.get("paraphrases", {}))
INSTR = {**_orig["instructions"], **INSTR}

MAIN_NEED = [(0, "g")] + [(0, str(s)) for s in range(1, 7)] + \
            [(p, str(s)) for p in (1, 2, 3) for s in (1, 2)] + [(p, "1") for p in (4, 5, 6)]

# ---- 1) gap count per model (cells with parsed answer)
for alias in ["deepseek-v4.1-flash", "deepseek-v4-flash-0731", "qwen3.7-flash"]:
    cells = defaultdict(set)
    for line in open(f"{RES}/{alias}.jsonl"):
        try: r = json.loads(line)
        except Exception: continue
        if r.get("FAILED") or r.get("answer") is None: continue
        cells[r["qid"]].add((r["para"], str(r["sample"])))
    full = sum(1 for q in questions if all(c in cells[q] for c in MAIN_NEED))
    total_cells = sum(len(cells[q]) for q in questions)
    missing_cells = 119 * 16 - sum(1 for q in questions for c in MAIN_NEED if c in cells[q])
    done_qids = sorted([q for q in questions if all(c in cells[q] for c in MAIN_NEED)],
                       key=lambda x: int(x[1:]))
    print(f"{alias}: complete_q={full}/119 valid_cells={total_cells} missing_cells={missing_cells}")
    print(f"   first/last complete: {done_qids[:3]} ... {done_qids[-3:] if done_qids else '-'}")

# ---- 2) real-question test on apinex
print("\n=== real-question parse test ===")
import urllib.request
BASE = "https://api.apinex.bond/v1"
KEY = "sk-apxe8e3bc610bd556066ca665074a4ba0c722a9cce84fbe1cf"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

def build_prompt(q, para_idx):
    ds = q["dataset"]
    if q["instruction_type"] == "instruction":
        stem, instr = q["stem"], INSTR[ds][f"P{para_idx}"]
    else:
        stem = q["stem"] if para_idx == 0 else PARA[q["id"]][para_idx - 1]
        instr = INSTR[ds]["P0"]
    parts = []
    if q.get("passage"): parts.append(q["passage"])
    parts.append(stem)
    if q["options"]:
        letters = "ABCDEFGHIJ"
        parts.append("Options:\n" + "\n".join(f"({letters[i]}) {o}" for i, o in enumerate(q["options"])))
    parts.append(instr)
    return "\n\n".join(parts)

# pick one MCQ (non-gsm8k) question
test_q = None
for q in questions.values():
    if q["dataset"] not in ("gsm8k",) and len(q["options"]) >= 4:
        test_q = q; break
prompt = build_prompt(test_q, 1)
print(f"test qid={test_q['id']} ds={test_q['dataset']} gold={'ABCDEFGHIJ'[test_q['answer_idx']]}")

for model in ["free/deepseek-v4.1-flash", "free/deepseek-v4-flash-0731"]:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0.7, "max_tokens": 2500}).encode()
    req = urllib.request.Request(f"{BASE}/chat/completions", data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                 "User-Agent": UA, "Accept": "application/json"})
    t0 = time.time()
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=180).read())
        msg = d["choices"][0]["message"]
        content = msg.get("content") or ""
        rlen = len(msg.get("reasoning_content") or "")
        u = d.get("usage", {})
        m = re.findall(r"Answer:?\s*\**\s*\(?([A-J])\)?", content)
        print(f"[{model}] {time.time()-t0:.1f}s rlen={rlen} ct={u.get('completion_tokens')} "
              f"parsed={'Y:'+m[-1] if m else 'NONE'} content_tail={content[-80:]!r}")
    except Exception as e:
        print(f"[{model}] FAIL {time.time()-t0:.1f}s {type(e).__name__}: {str(e)[:150]}")
    time.sleep(13)
