#!/usr/bin/env python3
"""Regenerate agnes paraphrases for passage-bearing stem questions using STEM-ONLY
prompts (the original run accidentally rewrote the whole passage)."""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import json, os, re, sys, time, urllib.request
sys.path.insert(0, ROOT + "/scripts")
from credentials import ALIYUN, AGNES

DATA = ROOT + "/data"
DEADLINE = time.time() + (int(sys.argv[1]) if len(sys.argv) > 1 else 460)

questions = json.load(open(f"{DATA}/questions.json"))
stem_qs = [q for q in questions if q["instruction_type"] == "stem"]
targets = [q for q in stem_qs if q.get("passage")]   # lsat_lr + logiqa
print(f"{len(targets)} passage-bearing stem questions to regenerate (stem-only prompt)")

GEN_LOG = f"{DATA}/paraphrases_agnes_raw2.jsonl"

def call_agnes(prompt, max_tokens=1200):
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
            if "quota" in str(e).lower():
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
    return sum(x * y for x, y in zip(a, b)) / ((math.sqrt(sum(x*x for x in a)) or 1.0) * (math.sqrt(sum(y*y for y in b)) or 1.0))

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
for q in targets:
    if q["id"] in done:
        continue
    if time.time() > DEADLINE:
        print("deadline; resume next run")
        break
    prompt = (
        "Below is a question stem from a reading-comprehension problem. The passage it "
        "refers to is NOT shown and must not be rewritten or mentioned. Rewrite only the "
        "question stem itself in six different ways, preserving its exact meaning, all "
        "references, and the question type. Do not answer. Do not restate the passage.\n\n"
        f"Question stem: {q['stem']}\n\n"
        "Output exactly six numbered rewrites (1. to 6.), nothing else.")
    try:
        out = call_agnes(prompt)
        paras = [p.strip() for p in re.findall(r"^\s*\d+[\.\)]\s*(.+)$", out, re.M) if len(p.strip()) > 8][:6]
        if len(paras) < 6:
            paras = paras + [p.strip() for p in re.split(r"\n+", out) if len(p.strip()) > 12][:6 - len(paras)]
        fout.write(json.dumps({"qid": q["id"], "paras": paras}, ensure_ascii=False) + "\n")
        done[q["id"]] = paras
        print(f"{q['id']}: {len(paras)} paras")
    except Exception as e:
        fout.write(json.dumps({"qid": q["id"], "error": str(e)[:80]}) + "\n")
        if "QUOTA" in str(e):
            break
fout.close()

# rebuild combined paraphrases_agnes.json: raw2 (stem-only) for passage ds, raw for others
raw1 = {}
for line in open(f"{DATA}/paraphrases_agnes_raw.jsonl"):
    try:
        r = json.loads(line)
        if not r.get("error"):
            raw1[r["qid"]] = r["paras"]
    except Exception:
        pass
combined = {}
for q in stem_qs:
    qid = q["id"]
    src = done if q.get("passage") else raw1
    if qid not in src or len(src[qid]) < 4:
        continue
    paras = src[qid][:6]
    try:
        embs = embed_batch([q["stem"]] + paras)
        sims = [round(cos(embs[0], e), 3) for e in embs[1:]]
    except Exception:
        sims = [None] * len(paras)
    combined[qid] = {"paras": paras, "sims": sims,
                     "n_valid": sum(1 for s in sims if s is not None and s >= 0.75)}
json.dump(combined, open(f"{DATA}/paraphrases_agnes.json", "w"), indent=1, ensure_ascii=False)
n_ok = sum(1 for v in combined.values() if v["n_valid"] >= 4)
import statistics
allsims = [s for v in combined.values() for s in v["sims"] if s is not None]
print(f"combined: {len(combined)} questions, {n_ok} with >=4 valid; mean sim={statistics.mean(allsims):.3f}")
