#!/usr/bin/env python3
"""Sample 30 MMLU-Pro questions (seed 42, stratified by subject) into our schema.
Output: data/mmlupro30.json with fields compatible with questions.json."""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import duckdb, json, random, re

con = duckdb.connect()
df = con.execute("""
    SELECT question, options, answer_index, answer, src, category
    FROM read_parquet('/home/z/my-project/data/raw2/mmlu_pro_test.parquet')
""").fetchall()
cols = [d[0] for d in con.description]
print("total rows:", len(df))

rows = [dict(zip(cols, r)) for r in df]
# normalize: category is the subject field in this parquet
for r in rows:
    r["subject"] = r.get("category") or r.get("src")
# drop questions that reference figures/images (not answerable text-only)
# and keep only rows with exactly 10 options
clean = [r for r in rows if len(r["options"]) == 10
         and not re.search(r"figure|diagram|as shown|graph below|chart below",
                           r["question"], re.I)]
print("after figure-filter:", len(clean))

random.seed(42)
by_subj = {}
for r in clean:
    by_subj.setdefault(r["subject"], []).append(r)
subjects = sorted(by_subj)
print(f"{len(subjects)} subjects:", subjects)

# 30 questions: 2 per subject for 14 subjects (28) + 2 extra from 2 random subjects
picked = []
for s in subjects:
    pool = sorted(by_subj[s], key=lambda x: x["question"])
    random.shuffle(pool)
    picked += [(s, q) for q in pool[:2]]
# pad to 30 with 2 more from the two largest pools
for s in sorted(subjects, key=lambda s: -len(by_subj[s]))[:2]:
    extra = [q for q in by_subj[s] if (s, q) not in picked]
    if extra:
        picked.append((s, extra[0]))

out = []
for i, (subj, r) in enumerate(picked, 1):
    opts = [re.sub(r"^\(?[A-J]\)?\s*", "", str(o)).strip() for o in r["options"]]
    out.append({
        "id": f"mp{i:03d}",
        "dataset": "mmlu_pro",
        "subject": subj,
        "passage": None,
        "stem": r["question"],
        "options": opts,
        "answer_idx": int(r["answer_index"]),
        "answer": None,
        "answer_text": r["answer"],
    })
random.seed(42)
random.shuffle(out)
for i, q in enumerate(out, 1):
    q["id"] = f"mp{i:03d}"

assert all(len(q["options"]) == 10 for q in out), "MMLU-Pro must have 10 options"
json.dump(out, open(ROOT + "/data/mmlupro30.json", "w"), indent=1, ensure_ascii=False)
print(f"saved {len(out)} questions; subjects:", {q['subject'] for q in out})
print("answer_idx distribution:", sorted(q["answer_idx"] for q in out))
