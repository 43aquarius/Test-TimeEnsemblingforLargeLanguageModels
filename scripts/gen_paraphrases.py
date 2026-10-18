#!/usr/bin/env python3
"""Generate 6 paraphrases per stem-type question (truthfulqa/lsat_lr/logiqa) via qwen3.7-flash.
Instruction-type datasets (gsm8k/piqa/sat_math) use fixed handcrafted instruction variants.
Output: data/paraphrases.json  {qid: [p1..p6]}
Also embeds canonical instruction definitions per dataset in data/instructions.json
"""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import json, re, time, urllib.request, sys
sys.path.insert(0, ROOT + "/scripts")
from credentials import ALIYUN

BASE, KEY = ALIYUN["base_url"], ALIYUN["api_key"]

questions = json.load(open(ROOT + "/data/questions.json"))

# ---------- Fixed instruction sets for instruction-type datasets ----------
INSTR = {
    "gsm8k": {
        "P0": "Solve the problem step by step. End your response with \"Answer: <number>\".",
        "P1": "Work through the problem one step at a time, then conclude with \"Answer: <number>\".",
        "P2": "Reason carefully about the problem and compute the result. The last line must be \"Answer: <number>\".",
        "P3": "Please solve this math problem. Show your reasoning, and finish with \"Answer: <number>\".",
        "P4": "Figure out the solution by working through the calculations. End with \"Answer: <number>\".",
        "P5": "Approach the problem methodically and determine the final value. Terminate your reply with \"Answer: <number>\".",
        "P6": "Think the problem through and calculate the answer. Your response must end with \"Answer: <number>\".",
    },
    "piqa": {
        "P0": "Consider the goal and the two proposed solutions. Decide which solution is more sensible and appropriate. End your response with \"Answer: 1\" if Solution 1 is better, or \"Answer: 2\" if Solution 2 is better.",
        "P1": "Evaluate both solutions against the goal and pick the more practical one. Conclude with \"Answer: 1\" or \"Answer: 2\".",
        "P2": "Which of the two solutions better achieves the goal? Decide and end with \"Answer: 1\" or \"Answer: 2\".",
        "P3": "Judge which solution makes more sense for the stated goal. Finish with \"Answer: 1\" or \"Answer: 2\".",
        "P4": "Compare the two solutions and select the more appropriate one. The final line must read \"Answer: 1\" or \"Answer: 2\".",
        "P5": "Determine which proposed solution is the better fit for the goal. End with \"Answer: 1\" or \"Answer: 2\".",
        "P6": "Assess both solutions and identify the better approach. Close with \"Answer: 1\" or \"Answer: 2\".",
    },
    "sat_math": {
        "P0": "Answer with the letter of the correct option. End your response with \"Answer: <letter>\".",
        "P1": "Select the correct option and conclude with \"Answer: <letter>\".",
        "P2": "Choose the right answer from the options above. Finish with \"Answer: <letter>\".",
        "P3": "Pick the best option. The last line of your reply must be \"Answer: <letter>\".",
        "P4": "Identify the correct choice, then end with \"Answer: <letter>\".",
        "P5": "Decide which option is right. Terminate your reply with \"Answer: <letter>\".",
        "P6": "Work out the answer and give the final letter, formatted as \"Answer: <letter>\".",
    },
    # stem-type datasets: instruction FIXED, stem varies
    "truthfulqa": {"P0": "Answer with the letter of the correct option. End your response with \"Answer: <letter>\"."},
    "lsat_lr": {"P0": "Answer with the letter of the correct option. End your response with \"Answer: <letter>\"."},
    "logiqa": {"P0": "Answer with the letter of the correct option. End your response with \"Answer: <letter>\"."},
}

def call_qwen(prompt, max_tokens=1500, temperature=0.8):
    payload = json.dumps({
        "model": "qwen3.7-flash",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens, "temperature": temperature,
        "enable_thinking": False,
    }).encode()
    req = urllib.request.Request(f"{BASE}/chat/completions", data=payload, headers={
        "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                resp = json.load(r)
            return resp["choices"][0]["message"]["content"]
        except Exception as e:
            err = str(e)
            if "FreeTier" in err or "free" in err.lower():
                raise RuntimeError(f"QUOTA_EXHAUSTED: {err[:100]}")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("retries exhausted")

GEN_PROMPT = """Rewrite the following question in {n} different ways while keeping its meaning exactly the same. Keep all facts, entities, numbers, and what is being asked strictly unchanged. Do not answer the question. Only rephrase the wording and sentence structure.

Question: {stem}

{extra}Output ONLY a JSON array of exactly {n} strings, each being one full rewritten question."""

LSAT_EXTRA = "The question belongs to a logical reasoning test and refers to a passage that is provided separately; just rewrite the question itself, do not mention or invent passage content.\n\n"

stem_qs = [q for q in questions if q["instruction_type"] == "stem"]
print(f"Generating paraphrases for {len(stem_qs)} stem-type questions...")

paraphrases = {}
for i, q in enumerate(stem_qs):
    extra = LSAT_EXTRA if q["dataset"] in ("lsat_lr", "logiqa") else ""
    prompt = GEN_PROMPT.format(n=8, stem=q["stem"], extra=extra)
    try:
        raw = call_qwen(prompt)
    except RuntimeError as e:
        print(f"  {q['id']}: FAILED - {e}")
        continue
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        print(f"  {q['id']}: no JSON array found")
        continue
    try:
        cands = json.loads(m.group())
        cands = [c.strip() for c in cands if isinstance(c, str) and c.strip()]
    except json.JSONDecodeError:
        print(f"  {q['id']}: JSON parse error")
        continue
    # Basic validity: not identical to original, reasonable length
    valid = [c for c in cands if c.lower() != q["stem"].lower()
             and 0.4 < len(c) / max(1, len(q["stem"])) < 2.5
             and len(c) > 10]
    paraphrases[q["id"]] = valid[:6]
    n_ok = len(paraphrases[q["id"]])
    print(f"  [{i+1}/{len(stem_qs)}] {q['id']} ({q['dataset']}): {n_ok}/6 valid candidates")
    time.sleep(0.3)

# Second pass: top up questions with < 6 valid
for qid, plist in list(paraphrases.items()):
    if len(plist) < 6:
        q = next(x for x in questions if x["id"] == qid)
        extra = LSAT_EXTRA if q["dataset"] in ("lsat_lr", "logiqa") else ""
        try:
            raw = call_qwen(GEN_PROMPT.format(n=10, stem=q["stem"], extra=extra), temperature=0.9)
            m = re.search(r"\[.*\]", raw, re.DOTALL)
            if m:
                cands = json.loads(m.group())
                existing = set(p.lower() for p in plist)
                for c in cands:
                    if isinstance(c, str) and len(plist) < 6 and c.strip().lower() not in existing \
                       and 0.4 < len(c.strip()) / max(1, len(q["stem"])) < 2.5 and len(c.strip()) > 10:
                        plist.append(c.strip())
            print(f"  topup {qid}: now {len(plist)}")
        except Exception as e:
            print(f"  topup {qid} failed: {e}")
        time.sleep(0.3)

# Report
n_complete = sum(1 for p in paraphrases.values() if len(p) >= 6)
print(f"\nComplete (>=6 paraphrases): {n_complete}/{len(stem_qs)}")
json.dump({"paraphrases": paraphrases, "instructions": INSTR},
          open(ROOT + "/data/paraphrases.json", "w"), indent=1, ensure_ascii=False)
print("Saved to data/paraphrases.json")
