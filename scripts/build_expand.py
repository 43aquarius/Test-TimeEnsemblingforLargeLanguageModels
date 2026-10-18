#!/usr/bin/env python3
"""Build the EXPANSION question set: 20 new questions per benchmark (120 total),
drawn from the same raw pools with the same filters as build_dataset_v2.py,
skipping the items already consumed by the original 90-question set.

IDs use the e-prefix (e000..e119) so they cannot collide with q000..q089.
Saves data/questions_expand.json with the same schema as questions.json.
"""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import csv, json, random, re
from collections import Counter

SEED = 42          # replay the original shuffle to identify used items
N_NEW = 20

orig = json.load(open(ROOT + "/data/questions.json"))
used = set((q["dataset"], q["stem"]) for q in orig)
out = []

# --- GSM8K ---
with open(ROOT + "/data/raw/gsm8k_test.jsonl") as f:
    pool = [json.loads(l) for l in f]
random.seed(SEED)
random.shuffle(pool)
count = 0
for item in pool:
    if count >= N_NEW:
        break
    ans_num = item["answer"].split("####")[-1].strip().replace(",", "")
    m = re.search(r"-?\d[\d,]*\.?\d*", ans_num)
    if not m:
        continue
    if ("gsm8k", item["question"]) in used:
        continue
    out.append({"dataset": "gsm8k", "passage": None, "stem": item["question"],
                "options": None, "answer_idx": None, "answer": m.group().replace(",", ""),
                "instruction_type": "instruction"})
    count += 1

# --- TruthfulQA MC1 ---
with open(ROOT + "/data/raw/truthfulqa.csv", newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
random.seed(SEED)
random.shuffle(rows)
count = 0
for item in rows:
    if count >= N_NEW:
        break
    if item["Type"] != "Adversarial":
        continue
    correct = [a.strip() for a in item["Best Answer"].split(";")]
    incorrect = [a.strip() for a in item["Incorrect Answers"].split(";") if a.strip()]
    if len(correct) < 1 or len(incorrect) < 4:
        continue
    if ("truthfulqa", item["Question"]) in used:
        continue
    correct_ans = correct[0]
    opts = [correct_ans] + incorrect[:4]
    random.shuffle(opts)
    out.append({"dataset": "truthfulqa", "passage": None, "stem": item["Question"],
                "options": opts, "answer_idx": opts.index(correct_ans), "answer": None,
                "instruction_type": "stem"})
    count += 1

# --- PIQA ---
with open(ROOT + "/data/raw/piqa_valid.jsonl") as f:
    piqa = [json.loads(l) for l in f]
with open(ROOT + "/data/raw/piqa_valid_labels.lst") as f:
    labels = [int(l.strip()) for l in f if l.strip() != ""]
pairs = list(zip(piqa, labels))
random.seed(SEED)
random.shuffle(pairs)
count = 0
for item, lab in pairs:
    if count >= N_NEW:
        break
    stem = f"Goal: {item['goal']}\nSolution 1: {item['sol1']}\nSolution 2: {item['sol2']}\n\nWhich solution is more sensible and appropriate for achieving the goal?"
    if ("piqa", stem) in used:
        continue
    out.append({"dataset": "piqa", "passage": None, "stem": stem,
                "options": ["Solution 1", "Solution 2"], "answer_idx": lab, "answer": None,
                "instruction_type": "instruction"})
    count += 1

# --- LSAT-LR / LogiQA / SAT-Math (AGIEval) ---
for name, fname, itype in [("lsat_lr", "lsat_lr.jsonl", "stem"),
                           ("logiqa", "logiqa_en.jsonl", "stem"),
                           ("sat_math", "sat_math.jsonl", "instruction")]:
    with open(f"{ROOT}/data/raw/{fname}") as f:
        pool = [json.loads(l) for l in f]
    random.seed(SEED)
    random.shuffle(pool)
    count = 0
    for item in pool:
        if count >= N_NEW:
            break
        opts = [re.sub(r"^\([A-J]\)\s*", "", o) for o in item["options"]]
        if len(opts) < 3 or len(opts) > 5:
            continue
        lab = item["label"].strip().upper()
        if lab not in "ABCDEFGHIJ" or ord(lab) - 65 >= len(opts):
            continue
        passage = item.get("passage") or None
        stem = item["question"]
        if name == "sat_math" and passage:
            stem = (passage + " " + stem).strip()
            passage = None
        if (name, stem) in used:
            continue
        out.append({"dataset": name, "passage": passage, "stem": stem,
                    "options": opts, "answer_idx": ord(lab) - 65, "answer": None,
                    "instruction_type": itype})
        count += 1

random.seed(20261018)
random.shuffle(out)
for i, item in enumerate(out):
    item["id"] = f"e{i:03d}"

counts = Counter(x["dataset"] for x in out)
print("Dataset counts:", dict(counts))
assert all(v == N_NEW for v in counts.values()), counts
with open(ROOT + "/data/questions_expand.json", "w") as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
print(f"Saved {len(out)} questions to data/questions_expand.json")
print("Locus:", Counter(x["instruction_type"] for x in out))
