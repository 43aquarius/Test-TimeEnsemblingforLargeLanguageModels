#!/usr/bin/env python3
"""Diversity probe: 6x temp-0.7 samples on logiqa/lsat + gsm8k math check."""
import json, re, sys, time
sys.path.insert(0, "/home/z/my-project/scripts")
from collections import Counter

DATA = "/home/z/my-project/data"
questions = {q["id"]: q for q in json.load(open(f"{DATA}/questions_expand.json"))}
pdata = json.load(open(f"{DATA}/paraphrases_expand.json"))
PARA, INSTR = pdata["paraphrases"], pdata["instructions"]
_orig = json.load(open(f"{DATA}/paraphrases.json"))
PARA.update(_orig.get("paraphrases", {}))
INSTR = {**_orig["instructions"], **INSTR}

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

def chat(model, prompt, temp, mt):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "temperature": temp, "max_tokens": mt}).encode()
    req = urllib.request.Request(f"{BASE}/chat/completions", data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                 "User-Agent": UA, "Accept": "application/json"})
    t0 = time.time()
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=170).read())
        msg = d["choices"][0]["message"]
        return {"ok": True, "dt": time.time()-t0, "content": msg.get("content") or "",
                "rlen": len(msg.get("reasoning_content") or ""),
                "ct": (d.get("usage") or {}).get("completion_tokens")}
    except Exception as e:
        return {"ok": False, "dt": time.time()-t0, "err": f"{type(e).__name__}:{str(e)[:100]}"}

# pick probes
logiqa_q = next(q for q in questions.values() if q["dataset"] == "logiqa")
lsat_q = next((q for q in questions.values() if q["dataset"] == "lsat_lr"), None)
gsm_q = next(q for q in questions.values() if q["dataset"] == "gsm8k")

def parse_mcq(c, n=4):
    for pat in [r"Answer:?\s*\**\s*\(?([A-J])\)?", r"\*\*([A-J])\*\*"]:
        m = re.findall(pat, c)
        if m: return m[-1]
    return None

print("=== A) logiqa diversity: 6 samples temp0.7 P0 on free/deepseek-v4.1-flash ===", flush=True)
p = build_prompt(logiqa_q, 0)
gold = "ABCDE"[logiqa_q["answer_idx"]]
answers = []
for i in range(6):
    r = chat("free/deepseek-v4.1-flash", p, 0.7, 2500)
    if r["ok"]:
        a = parse_mcq(r["content"])
        answers.append(a)
        print(f"  s{i+1} {r['dt']:5.1f}s rlen={r['rlen']:5d} ct={r['ct']:4d} ans={a} tail={r['content'][-30:]!r}", flush=True)
    else:
        print(f"  s{i+1} FAIL {r['err']}", flush=True)
    if i < 5: time.sleep(12.5)
print(f"  => distinct={len(set(answers))}/6 gold={gold} answers={answers}", flush=True)

print("\n=== B) gsm8k math: 3 samples temp0.7 on free/deepseek-v4.1-flash ===", flush=True)
p = build_prompt(gsm_q, 0)
print(f"  qid={gsm_q['id']} gold={gsm_q['answer']}")
for i in range(3):
    r = chat("free/deepseek-v4.1-flash", p, 0.7, 3500)
    if r["ok"]:
        m = re.findall(r"Answer:\s*\$?\s*(-?[\d,]+(?:\.\d+)?)", r["content"])
        print(f"  s{i+1} {r['dt']:5.1f}s rlen={r['rlen']:5d} ct={r['ct']:4d} parsed={m[-1] if m else None} tail={r['content'][-40:]!r}", flush=True)
    else:
        print(f"  s{i+1} FAIL {r['err']}", flush=True)
    if i < 2: time.sleep(12.5)

if lsat_q:
    print("\n=== C) lsat_lr: 3 samples temp0.7 P0 on free/deepseek-v4-flash-0731 ===", flush=True)
    p = build_prompt(lsat_q, 0)
    gold = "ABCDE"[lsat_q["answer_idx"]]
    for i in range(3):
        r = chat("free/deepseek-v4-flash-0731", p, 0.7, 2500)
        if r["ok"]:
            a = parse_mcq(r["content"])
            print(f"  s{i+1} {r['dt']:5.1f}s rlen={r['rlen']:5d} ct={r['ct']:4d} ans={a} gold={gold}", flush=True)
        else:
            print(f"  s{i+1} FAIL {r['err']}", flush=True)
        if i < 2: time.sleep(12.5)
