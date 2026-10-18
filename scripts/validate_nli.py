#!/usr/bin/env python3
"""B9: bidirectional NLI entailment validation of stem paraphrases + stricter-threshold
embedding revalidation. Uses qwen3.7-flash (separate quota bucket, not in eval pool).
Output: data/nli_validation.json"""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import json, os, re, sys, time, urllib.request
sys.path.insert(0, ROOT + "/scripts")
from credentials import ALIYUN

BASE, KEY = ALIYUN["base_url"], ALIYUN["api_key"]
DATA = ROOT + "/data"

questions = {q["id"]: q for q in json.load(open(f"{DATA}/questions.json"))}
pdata = json.load(open(f"{DATA}/paraphrases.json"))
PARA = pdata["paraphrases"]

def call_flash(prompt, max_tokens=400):
    payload = json.dumps({"model": "qwen3.7-flash",
                          "messages": [{"role": "user", "content": prompt}],
                          "max_tokens": max_tokens, "temperature": 0.0,
                          "enable_thinking": False}).encode()
    req = urllib.request.Request(f"{BASE}/chat/completions", data=payload, headers={
        "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                resp = json.load(r)
            return resp["choices"][0]["message"]["content"]
        except Exception as e:
            if "FreeTier" in str(e):
                raise RuntimeError("QUOTA_EXHAUSTED")
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("retries exhausted")

def nli_pair(orig, para):
    prompt = (
        "You are checking whether two versions of a question are semantically equivalent.\n"
        f"Text A (original): {orig}\n"
        f"Text B (paraphrase): {para}\n\n"
        "Answer two questions, each with only yes or no:\n"
        "1. Does Text A convey the same meaning and ask the same thing as Text B (A entails B)?\n"
        "2. Does Text B convey the same meaning and ask the same thing as Text A (B entails A)?\n"
        "Reply in exactly this format: '1: yes/no 2: yes/no'")
    out = call_flash(prompt).strip().lower()
    m1 = re.search(r"1:\s*(yes|no)", out)
    m2 = re.search(r"2:\s*(yes|no)", out)
    a2b = m1.group(1) if m1 else None
    b2a = m2.group(1) if m2 else None
    return a2b, b2a, out[:80]

def embed_batch(texts, model="qwen3.7-text-embedding-flash"):
    payload = json.dumps({"model": model, "input": texts, "dimensions": 1024,
                          "encoding_format": "float"}).encode()
    req = urllib.request.Request(f"{BASE}/embeddings", data=payload, headers={
        "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                resp = json.load(r)
            return [d["embedding"] for d in resp["data"]]
        except Exception:
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("embed failed")

def cos(a, b):
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)

# ---------------- NLI over all stem paraphrases ----------------
results = {}
stem_qs = [q for q in questions.values() if q["instruction_type"] == "stem" and q["id"] in PARA]
pairs = []
for q in stem_qs:
    for i, p in enumerate(PARA[q["id"]], 1):
        pairs.append((q["id"], i, q["stem"], p))
print(f"{len(pairs)} paraphrase pairs to check (NLI)")

# resume support
if os.path.exists(f"{DATA}/nli_validation.json"):
    results = json.load(open(f"{DATA}/nli_validation.json"))
    print(f"resuming with {len(results)} done")

import asyncio
async def run():
    sem = asyncio.Semaphore(6)
    lock = asyncio.Lock()
    next_slot = 0.0
    async def one(qid, i, orig, para):
        nonlocal next_slot
        key = f"{qid}_P{i}"
        if key in results:
            return
        async with sem:
            async with lock:
                now = time.monotonic()
                if next_slot < now:
                    next_slot = now
                slot = next_slot
                next_slot += 0.2   # 5/s
        if slot > time.monotonic():
            await asyncio.sleep(slot - time.monotonic())
        try:
            a2b, b2a, raw = await asyncio.to_thread(nli_pair, orig, para)
            results[key] = {"a_entails_b": a2b, "b_entails_a": b2a, "raw": raw,
                            "qid": qid, "para_idx": i}
        except Exception as e:
            results[key] = {"error": str(e)[:60], "qid": qid, "para_idx": i}
        if len(results) % 40 == 0:
            json.dump(results, open(f"{DATA}/nli_validation.json", "w"), indent=1)
            print(f"  {len(results)}/{len(pairs)}")

    await asyncio.gather(*[one(qid, i, o, p) for qid, i, o, p in pairs])
    json.dump(results, open(f"{DATA}/nli_validation.json", "w"), indent=1)

asyncio.run(run())

ok = [k for k, v in results.items() if v.get("a_entails_b") == "yes" and v.get("b_entails_a") == "yes"]
fail = [k for k, v in results.items() if v.get("a_entails_b") == "no" or v.get("b_entails_a") == "no"]
err = [k for k, v in results.items() if "error" in v]
print(f"NLI bidirectional entailment: {len(ok)}/{len(results)} pass, {len(fail)} fail, {len(err)} errors")

# ---------------- stricter-threshold embedding revalidation ----------------
para_val = json.load(open(f"{DATA}/para_validation.json"))
sims = [row[2] for row in para_val.get("report", []) if len(row) > 2]
for thr in (0.75, 0.80, 0.85):
    kept = sum(1 for s in sims if s >= thr)
    print(f"embedding threshold {thr}: {kept}/{len(sims)} paraphrases kept")
json.dump({"nli_pass": len(ok), "nli_total": len(results),
           "nli_fail_keys": fail[:50],
           "emb_thresholds": {str(t): sum(1 for s in sims if s >= t)
                              for t in (0.75, 0.80, 0.85)},
           "n_sims": len(sims)},
          open(f"{DATA}/nli_summary.json", "w"), indent=1)
print("saved data/nli_summary.json")
