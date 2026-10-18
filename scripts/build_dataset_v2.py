#!/usr/bin/env python3
"""Build unified question set from raw GitHub-sourced benchmark files.
90 questions: 15 per dataset × 6 datasets. Seed=42.
Structure: {dataset, id, passage, stem, options, answer_idx, answer, instruction_type}
- instruction_type: 'stem' (paraphrase question stem) or 'instruction' (paraphrase instruction only)
"""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import csv, json, random, re

SEED = 42
N_PER = 15
random.seed(SEED)

out = []

# --- GSM8K: free-form math, paraphrase instruction only ---
with open(ROOT + "/data/raw/gsm8k_test.jsonl") as f:
    pool = [json.loads(l) for l in f]
random.shuffle(pool)
for item in pool[:N_PER]:
    ans_num = item["answer"].split("####")[-1].strip().replace(",", "")
    m = re.search(r"-?\d[\d,]*\.?\d*", ans_num)
    if not m:
        continue
    out.append({"dataset": "gsm8k", "passage": None, "stem": item["question"],
                "options": None, "answer_idx": None, "answer": m.group().replace(",", ""),
                "instruction_type": "instruction"})

# --- TruthfulQA MC1: paraphrase stem ---
with open(ROOT + "/data/raw/truthfulqa.csv", newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
random.shuffle(rows)
for item in rows:
    if len(out) >= 15 + sum(1 for x in out if x["dataset"] == "gsm8k"):
        pass
    if item["Type"] != "Adversarial":
        continue
    correct = [a.strip() for a in item["Best Answer"].split(";")]
    incorrect = [a.strip() for a in item["Incorrect Answers"].split(";") if a.strip()]
    if len(correct) < 1 or len(incorrect) < 4:
        continue
    correct_ans = correct[0]
    wrong = incorrect[:4]
    opts = [correct_ans] + wrong
    random.shuffle(opts)
    out.append({"dataset": "truthfulqa", "passage": None, "stem": item["Question"],
                "options": opts, "answer_idx": opts.index(correct_ans), "answer": None,
                "instruction_type": "stem"})
    if sum(1 for x in out if x["dataset"] == "truthfulqa") >= N_PER:
        break

# --- PIQA: 2-choice, paraphrase instruction ---
with open(ROOT + "/data/raw/piqa_valid.jsonl") as f:
    piqa = [json.loads(l) for l in f]
with open(ROOT + "/data/raw/piqa_valid_labels.lst") as f:
    labels = [int(l.strip()) for l in f if l.strip() != ""]
pairs = list(zip(piqa, labels))
random.shuffle(pairs)
for item, lab in pairs[:N_PER]:
    out.append({"dataset": "piqa", "passage": None,
                "stem": f"Goal: {item['goal']}\nSolution 1: {item['sol1']}\nSolution 2: {item['sol2']}\n\nWhich solution is more sensible and appropriate for achieving the goal?",
                "options": ["Solution 1", "Solution 2"], "answer_idx": lab, "answer": None,
                "instruction_type": "instruction"})

# --- LSAT-LR / LogiQA-en / SAT-Math (AGIEval): {passage, question, options [(A)..], label} ---
for name, fname, itype in [("lsat_lr", "lsat_lr.jsonl", "stem"),
                           ("logiqa", "logiqa_en.jsonl", "stem"),
                           ("sat_math", "sat_math.jsonl", "instruction")]:
    with open(f"{ROOT}/data/raw/{fname}") as f:
        pool = [json.loads(l) for l in f]
    random.shuffle(pool)
    count = 0
    for item in pool:
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
        out.append({"dataset": name, "passage": passage, "stem": stem,
                    "options": opts, "answer_idx": ord(lab) - 65, "answer": None,
                    "instruction_type": itype})
        count += 1
        if count >= N_PER:
            break

# Shuffle all, assign IDs
random.shuffle(out)
for i, item in enumerate(out):
    item["id"] = f"q{i:03d}"
    item.pop("instruction_type", None) if False else None

from collections import Counter
counts = Counter(x["dataset"] for x in out)
print("Dataset counts:", dict(counts))
assert len(out) == 90, f"Expected 90, got {len(out)}"

# Save with instruction_type
with open(ROOT + "/data/questions.json", "w") as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
print(f"Saved {len(out)} questions to data/questions.json")
print("Option count distribution:", dict(Counter(len(x["options"]) if x["options"] else 0 for x in out)))
