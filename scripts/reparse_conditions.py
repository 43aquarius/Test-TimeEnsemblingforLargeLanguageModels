#!/usr/bin/env python3
"""Aggressive snippet-based re-parse for unparsed cells in the condition files.
Applies a fixed, uniform fallback pattern list to the stored snippet (first 60 +
last 640 chars). Appends recovered records; analyze_v2's last-record-wins loader
picks them up. Truncated outputs without any answer remain unparsed.
Usage: python3 reparse_conditions.py"""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import json, os, re

RES = ROOT + "/results"
DATA = ROOT + "/data"
questions = {q["id"]: q for q in json.load(open(f"{DATA}/questions.json"))}
mmlupro_q = {q["id"]: q for q in json.load(open(f"{DATA}/mmlupro30.json"))}

EXTRA_PATTERNS = [
    r"the correct answer is \(?([A-J])\)?",
    r"correct answer.{0,20}?\(?([A-J])\)?",
    r"answer\s*(?:is|:)\s*\**\(?\s*\*{0,2}([A-J])\*{0,2}\)?\b",
    r"option\s+([A-J])\b",
    r"choice\s+([A-J])\b",
    r"^\s*\*{0,2}\(?([A-J])\)?\*{0,2}\s*$",
    r"I\s+(?:would|will)\s+(?:choose|select|pick)\s+\(?([A-J])\)?",
    r"\*\*([A-J])\*\*(?!\w)",
]

def aggressive_parse(snippet, q):
    n_opt = len(q["options"]) if q["options"] else None
    letters = "ABCDEFGHIJ"[:n_opt] if n_opt else "ABCDEFGHIJ"
    if q["dataset"] == "piqa":
        for pat in [r"answer\s*(?:is|:)\s*\**\s*([12])", r"option\s+([12])\b", r"solution\s+([12])\b"]:
            m = re.findall(pat, snippet, re.I)
            if m:
                return m[-1]
        m = re.findall(r"\b([12])\b", snippet[-60:])
        return m[-1] if m else None
    if q["dataset"] == "gsm8k":
        m = re.findall(r"answer\s*(?:is|:)\s*\$?\s*(-?[\d,]+(?:\.\d+)?)", snippet, re.I)
        if m:
            return m[-1].replace(",", "")
        lines = [l for l in snippet.split("\n") if l.strip()]
        for line in reversed(lines[-3:]):
            m = re.findall(r"-?[\d,]+(?:\.\d+)?", line)
            if m:
                return m[-1].replace(",", "")
        return None
    # search from the END of the snippet backwards
    tail = snippet[-640:]
    for pat in EXTRA_PATTERNS:
        found = re.findall(pat, tail, re.I | re.M)
        in_range = [f.upper() for f in found if f.upper() in letters]
        if in_range:
            return in_range[-1]
    # last standalone letter in final lines
    for line in reversed(tail.split("\n")[-5:]):
        m = re.findall(r"\(?\b([A-J])\)?\b", line)
        in_range = [x for x in m if x in letters]
        if in_range:
            return in_range[-1]
    return None

def answer_to_int(ans, q):
    if ans is None:
        return None
    try:
        if q["dataset"] == "gsm8k":
            return abs(float(ans) - float(q["answer"])) < 1e-6
        if q["dataset"] == "piqa":
            return int(ans) - 1 == q["answer_idx"]
        return "ABCDEFGHIJ".index(ans) == q["answer_idx"]
    except (ValueError, TypeError):
        return False

recovered = 0
attempted = 0
for cond in ("greedypara", "mmlupro", "cot"):
    d = f"{RES}/cond_{cond}"
    if not os.path.exists(d):
        continue
    for fn in os.listdir(d):
        if not fn.endswith(".jsonl"):
            continue
        alias = fn[:-6]
        path = os.path.join(d, fn)
        recs = [json.loads(l) for l in open(path)]
        # last record per key wins
        cells = {}
        for r in recs:
            if r.get("FAILED"):
                continue
            cells[(r["qid"], r["para"], str(r["sample"]))] = r
        broken = [(k, r) for k, r in cells.items() if r["answer"] is None]
        if not broken:
            continue
        out = open(path, "a", buffering=1)
        for (qid, para, sample), old in broken:
            q = mmlupro_q.get(qid) or questions.get(qid)
            if q is None or not old.get("snippet"):
                continue
            attempted += 1
            ans = aggressive_parse(old["snippet"], q)
            if ans is not None:
                out.write(json.dumps({
                    "model": alias, "qid": qid, "dataset": old["dataset"], "para": old["para"],
                    "sample": old["sample"], "temp": old["temp"], "answer": ans,
                    "correct": answer_to_int(ans, q), "content_len": old["content_len"],
                    "reasoning_len": old.get("reasoning_len", 0),
                    "snippet": old["snippet"], "usage": old.get("usage", {}),
                    "t": old.get("t"), "reparsed": True}, ensure_ascii=False) + "\n")
                recovered += 1
        out.close()
print(f"re-parse: attempted {attempted}, recovered {recovered}")
