#!/usr/bin/env python3
"""Re-validate with relaxed criteria, regenerate bad ones, finalize exactly-6 paraphrase sets."""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import json, re, time, urllib.request, sys, math
sys.path.insert(0, ROOT + "/scripts")
from credentials import ALIYUN

BASE, KEY = ALIYUN["base_url"], ALIYUN["api_key"]
questions = {q["id"]: q for q in json.load(open(ROOT + "/data/questions.json"))}
data = json.load(open(ROOT + "/data/paraphrases.json"))
PARA = data["paraphrases"]

WH = ("what", "which", "who", "whom", "whose", "when", "where", "why", "how")
AUX = ("is", "are", "was", "were", "do", "does", "did", "can", "could", "should", "would",
       "will", "shall", "may", "might", "must", "has", "have", "had")

def embed_batch(texts):
    payload = json.dumps({"model": "qwen3.7-text-embedding-flash", "input": texts,
                          "dimensions": 1024, "text_type": "document"}).encode()
    req = urllib.request.Request(f"{BASE}/embeddings", data=payload, headers={
        "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                resp = json.load(r)
            return [d["embedding"] for d in resp["data"]]
        except Exception as e:
            if "FreeTier" in str(e): raise RuntimeError("quota")
            time.sleep(4)
    raise RuntimeError("embed failed")

def cosine(a, b):
    return sum(x*y for x,y in zip(a,b)) / (math.sqrt(sum(x*x for x in a))*math.sqrt(sum(y*y for y in b)) + 1e-9)

def first_word(t):
    m = re.match(r"[a-zA-Z]+", t.lower().strip())
    return m.group(0) if m else ""

def is_valid(q, orig, p, sim):
    if p.lower() == orig.lower(): return False
    if not (0.75 <= sim): return False
    if not (0.4 <= len(p)/max(1,len(orig)) <= 2.5): return False
    if q["dataset"] == "truthfulqa":  # wh vs yes/no must be preserved
        ow, pw = first_word(orig), first_word(p)
        if (ow in WH) != (pw in WH):
            return False
        if ow in WH and pw in AUX: return False
        if ow in AUX and pw in WH: return False
    return True

def call_qwen(prompt, temperature=0.85):
    payload = json.dumps({"model": "qwen3.7-flash", "messages": [{"role": "user", "content": prompt}],
                          "max_tokens": 1500, "temperature": temperature, "enable_thinking": False}).encode()
    req = urllib.request.Request(f"{BASE}/chat/completions", data=payload, headers={
        "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)["choices"][0]["message"]["content"]
        except Exception:
            time.sleep(5)
    return ""

REGEN_PROMPT = """Rewrite the question below in {n} different ways, keeping its meaning exactly the same. Preserve the original question type (if it is a what/which/who/how question, the rewrite must also be that kind of question; if it asks about a passage, keep referring to it abstractly). Keep all facts, entities and numbers unchanged. Do not answer it.

Question: {stem}

Output ONLY a JSON array of exactly {n} rewritten question strings."""

# Pass 1: validate all
stem_ids = list(PARA.keys())
texts, keys = [], []
for qid in stem_ids:
    texts.append(questions[qid]["stem"]); keys.append((qid, "orig"))
    for j, p in enumerate(PARA[qid]):
        texts.append(p); keys.append((qid, j))
embs = {}
for i in range(0, len(texts), 25):
    be = embed_batch(texts[i:i+25])
    for k, e in enumerate(be):
        embs[keys[i+k]] = e
    time.sleep(0.2)

bad = []
sims_all = []
for qid in stem_ids:
    q = questions[qid]
    orig = q["stem"]
    for j, p in enumerate(PARA[qid]):
        sim = cosine(embs[(qid, "orig")], embs[(qid, j)])
        sims_all.append(sim)
        if not is_valid(q, orig, p, sim):
            bad.append((qid, j, round(sim, 3)))

print(f"Pass1: {len(bad)}/{len(sims_all)} invalid | sim mean={sum(sims_all)/len(sims_all):.3f} min={min(sims_all):.3f}")

# Pass 2: regenerate for questions with any bad paraphrase
affected = sorted(set(b[0] for b in bad))
print(f"Regenerating for {len(affected)} questions...")
for qid in affected:
    q = questions[qid]
    orig = q["stem"]
    keep = [p for j, p in enumerate(PARA[qid]) if (qid, j) not in [(b[0], b[1]) for b in bad]]
    raw = call_qwen(REGEN_PROMPT.format(n=10, stem=orig))
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if m:
        try:
            cands = [c.strip() for c in json.loads(m.group()) if isinstance(c, str)]
        except Exception:
            cands = []
    else:
        cands = []
    # embed new candidates together with orig
    new_keep = list(keep)
    cand_texts = [orig] + [c for c in cands if c not in new_keep]
    if cand_texts:
        ce = embed_batch(cand_texts[:20])
        orig_e = ce[0]
        for c, e in zip(cand_texts[1:], ce[1:]):
            if len(new_keep) >= 6: break
            sim = cosine(orig_e, e)
            if is_valid(q, orig, c, sim):
                new_keep.append(c)
    PARA[qid] = new_keep[:6]
    time.sleep(0.3)

# Final check
final_counts = {qid: len(p) for qid, p in PARA.items()}
short = {k: v for k, v in final_counts.items() if v < 6}
print(f"Final: {sum(1 for v in final_counts.values() if v >= 6)}/{len(final_counts)} complete; short: {short}")

# For any still short, duplicate-pad from valid existing (marked) - better: pad with orig itself? No.
# Report them for manual handling
if short:
    for qid in short:
        print(f"  {qid} ({questions[qid]['dataset']}): only {final_counts[qid]} paraphrases")

data["paraphrases"] = PARA
json.dump(data, open(ROOT + "/data/paraphrases.json", "w"), indent=1, ensure_ascii=False)
print("Saved final paraphrases.")
