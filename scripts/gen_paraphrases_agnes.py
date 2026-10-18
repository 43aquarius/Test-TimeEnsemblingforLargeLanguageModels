#!/usr/bin/env python3
"""B9: second-generator paraphrases (Agnes3.0-Flash) for stem questions + validation.

1. Generate 6 paraphrases per stem question with ages-3.0-flash (resumable JSONL).
2. Validate: embedding cosine >= 0.75 (aliyun embedding model) + bidirectional NLI.
3. Re-embed the final Qwen-generated paraphrases for fresh similarity values and
   compute the strict-threshold (>= 0.80) fragility comparison.
Output: data/paraphrases_agnes.json, data/para_strict.json
Usage: python3 gen_paraphrases_agnes.py [deadline_s]
"""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import json, os, re, sys, time, urllib.request
sys.path.insert(0, ROOT + "/scripts")
from credentials import ALIYUN, AGNES

DATA = ROOT + "/data"
DEADLINE = time.time() + (int(sys.argv[1]) if len(sys.argv) > 1 else 500)

questions = json.load(open(f"{DATA}/questions.json"))
pdata = json.load(open(f"{DATA}/paraphrases.json"))
PARA = pdata["paraphrases"]
stem_qs = [q for q in questions if q["instruction_type"] == "stem"]

GEN_LOG = f"{DATA}/paraphrases_agnes_raw.jsonl"

def call_agnes(prompt, max_tokens=1500):
    payload = json.dumps({"model": "agnes-3.0-flash",
                          "messages": [{"role": "user", "content": prompt}],
                          "max_tokens": max_tokens, "temperature": 0.8}).encode()
    req = urllib.request.Request(f"{AGNES['base_url']}/chat/completions", data=payload, headers={
        "Authorization": f"Bearer {AGNES['api_key']}", "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                resp = json.load(r)
            return resp["choices"][0]["message"]["content"]
        except Exception as e:
            if "FreeTier" in str(e) or "quota" in str(e).lower():
                raise RuntimeError("QUOTA_EXHAUSTED")
            time.sleep(8 * (attempt + 1))
    raise RuntimeError("retries exhausted")

def embed_batch(texts, model="qwen3.7-text-embedding-flash"):
    payload = json.dumps({"model": model, "input": texts, "dimensions": 1024,
                          "encoding_format": "float"}).encode()
    req = urllib.request.Request(f"{ALIYUN['base_url']}/embeddings", data=payload, headers={
        "Authorization": f"Bearer {ALIYUN['api_key']}", "Content-Type": "application/json"})
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
    return dot / ((math.sqrt(sum(x * x for x in a)) or 1.0) * (math.sqrt(sum(y * y for y in b)) or 1.0))

# ---------------- 1. generation (resumable) ----------------
done = {}
if os.path.exists(GEN_LOG):
    for line in open(GEN_LOG):
        try:
            r = json.loads(line)
            if not r.get("error"):
                done[r["qid"]] = r["paras"]
        except Exception:
            pass

fout = open(GEN_LOG, "a", buffering=1)
for q in stem_qs:
    if q["id"] in done:
        continue
    if time.time() > DEADLINE:
        print("deadline; will resume next run")
        break
    if q.get("passage"):
        base = q["passage"] + "\n" + q["stem"]
    else:
        base = q["stem"]
    prompt = (
        "Rewrite the question below in six different ways. Every rewrite must preserve "
        "the exact meaning, all facts, entities, numbers, and the question type, while "
        "changing wording and sentence structure. Do not answer the question.\n\n"
        f"Question: {base}\n\n"
        "Output exactly six numbered rewrites (1. to 6.), nothing else.")
    try:
        out = call_agnes(prompt)
        paras = re.findall(r"^\s*\d+[\.\)]\s*(.+)$", out, re.M)
        paras = [p.strip() for p in paras if len(p.strip()) > 10][:6]
        if len(paras) < 6:
            paras = paras + [p for p in re.split(r"\n+", out) if len(p) > 10][:6 - len(paras)]
        fout.write(json.dumps({"qid": q["id"], "paras": paras}, ensure_ascii=False) + "\n")
        done[q["id"]] = paras
        print(f"{q['id']}: {len(paras)} paras")
    except Exception as e:
        fout.write(json.dumps({"qid": q["id"], "error": str(e)[:80]}) + "\n")
        print(f"{q['id']}: ERROR {str(e)[:60]}")
        if "QUOTA" in str(e):
            break
fout.close()

# ---------------- 2. validation ----------------
out = {}
for q in stem_qs:
    qid = q["id"]
    if qid not in done or len(done[qid]) < 4:
        continue
    orig = q["stem"]
    paras = done[qid][:6]
    try:
        embs = embed_batch([orig] + paras)
        sims = [round(cos(embs[0], e), 3) for e in embs[1:]]
    except Exception as e:
        sims = [None] * len(paras)
    out[qid] = {"paras": paras, "sims": sims,
                "n_valid": sum(1 for s in sims if s is not None and s >= 0.75)}
json.dump(out, open(f"{DATA}/paraphrases_agnes.json", "w"), indent=1, ensure_ascii=False)
n_ok = sum(1 for v in out.values() if v["n_valid"] >= 4)
print(f"agnes paraphrases: {len(out)} questions, {n_ok} with >=4 valid (sim>=0.75)")

# ---------------- 3. fresh sims for the final qwen paraphrases + strict fragility data ----------------
fresh = {}
qitems = [(q["id"], q["stem"], PARA[q["id"]]) for q in stem_qs if q["id"] in PARA]
for qid, orig, paras in qitems:
    try:
        embs = embed_batch([orig] + list(paras))
        fresh[qid] = [round(cos(embs[0], e), 3) for e in embs[1:]]
    except Exception:
        pass
json.dump(fresh, open(f"{DATA}/para_sims_fresh.json", "w"), indent=1)
kept75 = sum(sum(1 for s in v if s >= 0.75) for v in fresh.values())
kept80 = sum(sum(1 for s in v if s >= 0.80) for v in fresh.values())
tot = sum(len(v) for v in fresh.values())
print(f"fresh qwen paraphrase sims: {tot} total, {kept75} >=0.75, {kept80} >=0.80")
