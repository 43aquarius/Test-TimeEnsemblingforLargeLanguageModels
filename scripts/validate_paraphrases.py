#!/usr/bin/env python3
"""Validate paraphrases: embedding cosine similarity + question-form preservation.
Replace invalid ones by regenerating with explicit constraints. Final: exactly 6 per question."""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import json, re, time, urllib.request, sys, math
sys.path.insert(0, ROOT + "/scripts")
from credentials import ALIYUN

BASE, KEY = ALIYUN["base_url"], ALIYUN["api_key"]
questions = {q["id"]: q for q in json.load(open(ROOT + "/data/questions.json"))}
data = json.load(open(ROOT + "/data/paraphrases.json"))
PARA, INSTR = data["paraphrases"], data["instructions"]

QN_WORDS = ["what", "which", "who", "whom", "whose", "when", "where", "why", "how", "whose",
            "is", "are", "was", "were", "do", "does", "did", "can", "could", "should", "would",
            "will", "shall", "may", "might", "must", "has", "have", "had", "if", "in what way",
            "based on", "according to", "from", "determine", "identify", "select", "choose",
            "judge", "evaluate", "decide", "pick", "work", "figure", "consider"]

def qform(text):
    t = text.lower().strip()
    m = re.match(r"([a-z]+)", t)
    return m.group(1) if m else ""

def embed_batch(texts, model="qwen3.7-text-embedding-flash"):
    payload = json.dumps({"model": model, "input": texts, "dimensions": 1024,
                          "text_type": "query" if len(texts) == 1 else "document"}).encode()
    req = urllib.request.Request(f"{BASE}/embeddings", data=payload, headers={
        "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                resp = json.load(r)
            return [d["embedding"] for d in resp["data"]]
        except Exception as e:
            if "FreeTier" in str(e):
                raise RuntimeError("quota exhausted")
            time.sleep(4)
    raise RuntimeError("embed failed")

def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb + 1e-9)

# Embed all originals and paraphrases
stem_ids = list(PARA.keys())
all_texts, mapping = [], []
for qid in stem_ids:
    all_texts.append(questions[qid]["stem"]); mapping.append((qid, -1))
    for j, p in enumerate(PARA[qid]):
        all_texts.append(p); mapping.append((qid, j))

print(f"Embedding {len(all_texts)} texts...")
embs = {}
for i in range(0, len(all_texts), 25):
    batch = all_texts[i:i+25]
    be = embed_batch(batch)
    for t, e in zip(batch, be):
        embs.setdefault(id(t), e)
    # map by position
    for k, t in enumerate(batch):
        qid, j = mapping[i+k]
        if j == -1:
            embs[qid + "|orig"] = be[k]
        else:
            embs[f"{qid}|{j}"] = be[k]
    time.sleep(0.3)

# Validate
report, invalid = [], []
for qid in stem_ids:
    orig = questions[qid]["stem"]
    orig_e = embs[qid + "|orig"]
    oform = qform(orig)
    for j, p in enumerate(PARA[qid]):
        sim = cosine(orig_e, embs[f"{qid}|{j}"])
        pform = qform(p)
        form_ok = (pform == oform) or (oform in ("which", "what") and pform in ("which", "what")) \
                  or (oform in ("is","are","was","were","do","does","did","can","could","has","have","had") and
                      pform in ("is","are","was","were","do","does","did","can","could","has","have","had")) \
                  or (oform in ("determine","identify","select","choose","judge","evaluate","decide","pick","which","what") and
                      pform in ("determine","identify","select","choose","judge","evaluate","decide","pick","which","what"))
        ratio = len(p) / max(1, len(orig))
        ok = sim >= 0.80 and form_ok and 0.4 <= ratio <= 2.5 and p.lower() != orig.lower()
        report.append((qid, j, round(sim, 3), pform, oform, round(ratio, 2), ok))
        if not ok:
            invalid.append((qid, j, round(sim, 3), pform, oform))

sims = [r[2] for r in report]
print(f"\nSimilarity: min={min(sims)}, mean={sum(sims)/len(sims):.3f}, max={max(sims)}")
print(f"Invalid: {len(invalid)}/{len(report)}")
for qid, j, sim, pf, of in invalid[:15]:
    print(f"  {qid} P{j+1}: sim={sim} form {pf} vs {of}")

# Show similarity distribution buckets
buckets = {}
for s in sims:
    b = round(s, 1)
    buckets[b] = buckets.get(b, 0) + 1
print("Distribution:", dict(sorted(buckets.items())))

json.dump({"report": report, "invalid": invalid},
          open(ROOT + "/data/para_validation.json", "w"), indent=1)
