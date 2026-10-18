#!/usr/bin/env python3
"""Generate + validate paraphrases for the EXPANSION stem questions (e-prefix).
Same generator (qwen3.7-flash), same filters as the original pipeline:
lexical (identity, length ratio 0.4-2.5), embedding cosine >= 0.75.
Checkpointed to data/paras_expand_ckpt.jsonl for resumption.
Output: data/paraphrases_expand.json  {paraphrases: {qid: [p1..p6]}, instructions: {...}}
"""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import json, os, re, time, urllib.request, sys
sys.path.insert(0, ROOT + "/scripts")
from credentials import ALIYUN

BASE, KEY = ALIYUN["base_url"], ALIYUN["api_key"]
CKPT = ROOT + "/data/paras_expand_ckpt.jsonl"
questions = json.load(open(ROOT + "/data/questions_expand.json"))
stem_qs = [q for q in questions if q["instruction_type"] == "stem"]

# reuse the fixed instruction sets verbatim from the original file
INSTR = json.load(open(ROOT + "/data/paraphrases.json"))["instructions"]

done = {}
if os.path.exists(CKPT):
    for line in open(CKPT):
        try:
            r = json.loads(line)
            done[r["qid"]] = r["paras"]
        except Exception:
            pass
print(f"resume: {len(done)} questions already paraphrased")

def call_qwen(prompt, max_tokens=1500, temperature=0.8):
    payload = json.dumps({"model": "qwen3.7-flash",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens, "temperature": temperature,
        "enable_thinking": False}).encode()
    req = urllib.request.Request(f"{BASE}/chat/completions", data=payload, headers={
        "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                resp = json.load(r)
            return resp["choices"][0]["message"]["content"]
        except Exception as e:
            if "FreeTier" in str(e) or "quota" in str(e).lower():
                raise RuntimeError(f"QUOTA_EXHAUSTED: {e}")
            time.sleep(4 * (attempt + 1))
    raise RuntimeError("retries exhausted")

def embed(texts):
    payload = json.dumps({"model": "qwen3.7-text-embedding-flash",
        "input": texts}).encode()
    req = urllib.request.Request(f"{BASE}/embeddings", data=payload, headers={
        "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.load(r)
    return [d["embedding"] for d in resp["data"]]

def cos(a, b):
    num = sum(x * y for x, y in zip(a, b))
    return num / ((sum(x * x for x in a) ** 0.5) * (sum(y * y for y in b) ** 0.5))

GEN = """Rewrite the following question in {n} different ways while keeping its meaning exactly the same. Keep all facts, entities, numbers, and what is being asked strictly unchanged. Do not answer the question. Only rephrase the wording and sentence structure.

Question: {stem}

{extra}Output ONLY a JSON array of exactly {n} strings, each being one full rewritten question."""
LSAT_EXTRA = "The question belongs to a logical reasoning test and refers to a passage that is provided separately; just rewrite the question itself, do not mention or invent passage content.\n\n"

ckpt = open(CKPT, "a")
t0 = time.time()
for i, q in enumerate(stem_qs):
    if q["id"] in done and len(done[q["id"]]) >= 6:
        continue
    if time.time() - t0 > 480:   # leave headroom inside the 570s chunk
        print("time budget reached, stopping for this chunk")
        break
    extra = LSAT_EXTRA if q["dataset"] in ("lsat_lr", "logiqa") else ""
    try:
        raw = call_qwen(GEN.format(n=8, stem=q["stem"], extra=extra))
    except RuntimeError as e:
        print(f"  {q['id']}: {e}")
        break
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        print(f"  {q['id']}: no JSON array")
        continue
    try:
        cands = [c.strip() for c in json.loads(m.group()) if isinstance(c, str) and c.strip()]
    except json.JSONDecodeError:
        continue
    # lexical filter
    lex = [c for c in cands if c.lower() != q["stem"].lower()
           and 0.4 < len(c) / max(1, len(q["stem"])) < 2.5 and len(c) > 10]
    # embedding filter
    paras = []
    try:
        embs = embed([q["stem"]] + lex[:12])
        base = embs[0]
        for c, e in zip(lex[:12], embs[1:]):
            if cos(base, e) >= 0.75:
                paras.append(c)
            if len(paras) >= 6:
                break
    except Exception as e:
        print(f"  {q['id']}: embed failed {str(e)[:60]}")
        paras = lex[:6]          # fall back to lexical-only for this question
    if len(paras) < 6:           # top-up attempt
        try:
            raw2 = call_qwen(GEN.format(n=10, stem=q["stem"], extra=extra), temperature=0.9)
            m2 = re.search(r"\[.*\]", raw2, re.DOTALL)
            if m2:
                more = [c.strip() for c in json.loads(m2.group()) if isinstance(c, str)]
                existing = set(p.lower() for p in paras)
                for c in more:
                    if len(paras) >= 6:
                        break
                    if c.lower() in existing or c.lower() == q["stem"].lower():
                        continue
                    if not (0.4 < len(c) / max(1, len(q["stem"])) < 2.5 and len(c) > 10):
                        continue
                    try:
                        e1, e2 = embed([q["stem"], c])
                        if cos(e1, e2) >= 0.75:
                            paras.append(c)
                            existing.add(c.lower())
                    except Exception:
                        paras.append(c)
        except Exception:
            pass
    ckpt.write(json.dumps({"qid": q["id"], "paras": paras[:6]}, ensure_ascii=False) + "\n")
    ckpt.flush()
    done[q["id"]] = paras[:6]
    print(f"  [{i+1}/{len(stem_qs)}] {q['id']} ({q['dataset']}): {len(paras[:6])}/6 valid")

n_complete = sum(1 for p in done.values() if len(p) >= 6)
print(f"\ncomplete: {n_complete}/{len(stem_qs)}")
json.dump({"paraphrases": done, "instructions": INSTR},
          open(ROOT + "/data/paraphrases_expand.json", "w"), indent=1, ensure_ascii=False)
print("saved data/paraphrases_expand.json")
