#!/usr/bin/env python3
"""Repair unparsed CoT cells by re-drawing with a larger max_tokens budget.
Only for models whose provider quota allows it (agnes, apinex).
Usage: python3 repair_cot.py [deadline_s]"""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import asyncio, aiohttp, json, os, re, sys, time, random
sys.path.insert(0, ROOT + "/scripts")
from credentials import APINEX, AGNES

DATA = ROOT + "/data"
RES = ROOT + "/results"
DEADLINE = time.time() + (int(sys.argv[1]) if len(sys.argv) > 1 else 480)

questions = {q["id"]: q for q in json.load(open(f"{DATA}/questions.json"))}
pdata = json.load(open(f"{DATA}/paraphrases.json"))
PARA, INSTR = pdata["paraphrases"], pdata["instructions"]
COT_INSTR = ('Think step by step to solve the problem. Then end your response with '
             '"Answer: <letter>", where <letter> is the correct option.')
COT_PIQA_INSTR = ('Think step by step to solve the problem. Then end your response with '
                  '"Answer: 1" or "Answer: 2" for the better solution.')

MODELS = {
    "agnes-3.0-flash": ("agnes", "agnes-3.0-flash", 3500),
    "agnes-2.5-flash": ("agnes", "agnes-2.5-flash", 3500),
    "gpt-6-luna": ("apinex", "free/gpt-6-luna", 3500),
}
ENDPOINTS = {
    "agnes":  {"base": AGNES["base_url"], "key": AGNES["api_key"], "rate": 0.13, "conc": 4},
    "apinex": {"base": APINEX["base_url"], "key": APINEX["api_key"], "rate": 0.083, "conc": 3},
}

def build_prompt(q, para_idx):
    parts = []
    if para_idx > 0 and q["instruction_type"] == "stem":
        stem = PARA[q["id"]][para_idx - 1]
    else:
        stem = q["stem"]
    if q.get("passage"):
        parts.append(q["passage"])
    parts.append(stem)
    if q["options"]:
        letters = "ABCDEFGHIJ"
        parts.append("Options:\n" + "\n".join(f"({letters[i]}) {o}" for i, o in enumerate(q["options"])))
    parts.append(COT_PIQA_INSTR if q["dataset"] == "piqa" else COT_INSTR)
    return "\n\n".join(parts)

def extract_answer(content, q):
    c = content.strip()
    if not c:
        return None
    n_opt = len(q["options"]) if q["options"] else None
    letters = "ABCDEFGHIJ"[:n_opt] if n_opt else "ABCDEFGHIJ"
    if q["dataset"] == "piqa":
        m = re.findall(r"Answer:?\s*\**\s*([12])", c)
        if m: return m[-1]
        m = re.findall(r"\b([12])\b", c[-80:])
        return m[-1] if m else None
    for pat in [r"Answer:?\s*\**\s*\(?([A-J])\)?", r"\*\*([A-J])\*\*"]:
        found = re.findall(pat, c)
        in_range = [f for f in found if f in letters]
        if in_range: return in_range[-1]
    for line in reversed(c.split("\n")[-4:]):
        m = re.findall(r"\(?\b([A-J])\)?\b", line)
        in_range = [x for x in m if x in letters]
        if in_range: return in_range[-1]
    return None

def answer_to_int(ans, q):
    if ans is None: return None
    try:
        if q["dataset"] == "piqa":
            return int(ans) - 1 == q["answer_idx"]
        return "ABCDEFGHIJ".index(ans) == q["answer_idx"]
    except (ValueError, TypeError):
        return False

async def main():
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=12)) as session:
        for alias, (ep, mid, mt) in MODELS.items():
            cfg = ENDPOINTS[ep]
            path = f"{RES}/cond_cot/{alias}.jsonl"
            if not os.path.exists(path):
                continue
            cells = {}
            for line in open(path):
                try:
                    r = json.loads(line)
                    if r.get("FAILED") or r.get("reparsed"):
                        continue
                    cells[(r["qid"], r["para"], str(r["sample"]))] = r
                except Exception:
                    pass
            broken = [(k, r) for k, r in cells.items() if r["answer"] is None]
            print(f"{alias}: {len(broken)} unparsed CoT cells")
            if not broken:
                continue
            fout = open(path, "a", buffering=1)
            for (qid, para, sample), old in broken:
                if time.time() > DEADLINE:
                    print("  deadline reached")
                    break
                q = questions[qid]
                prompt = build_prompt(q, para)
                ok = False
                for attempt in range(4):
                    await asyncio.sleep(12 if ep == "agnes" else 13)
                    body = {"model": mid, "messages": [{"role": "user", "content": prompt}],
                            "temperature": old["temp"], "max_tokens": mt}
                    try:
                        async with session.post(f"{cfg['base']}/chat/completions", json=body,
                                                headers={"Authorization": f"Bearer {cfg['key']}"},
                                                timeout=aiohttp.ClientTimeout(total=180)) as resp:
                            text = await resp.text()
                            if resp.status != 200:
                                print(f"  {qid} p{para} s{sample}: HTTP{resp.status}")
                                continue
                            r = json.loads(text)
                            msg = r["choices"][0]["message"]
                            content = msg.get("content") or ""
                            usage = r.get("usage", {})
                    except Exception as e:
                        print(f"  {qid} p{para} s{sample}: {str(e)[:50]}")
                        continue
                    ans = extract_answer(content, q)
                    if ans is not None:
                        snippet = (content[:60] + " ... " + content[-640:]) if len(content) > 720 else content
                        fout.write(json.dumps({
                            "model": alias, "qid": qid, "dataset": old["dataset"], "para": old["para"],
                            "sample": old["sample"], "temp": old["temp"], "answer": ans,
                            "correct": answer_to_int(ans, q), "content_len": len(content),
                            "reasoning_len": len(msg.get("reasoning_content") or ""),
                            "snippet": snippet, "usage": {"pt": usage.get("prompt_tokens"),
                                                          "ct": usage.get("completion_tokens")},
                            "t": round(time.time(), 1), "repaired": True}, ensure_ascii=False) + "\n")
                        print(f"  {qid} p{para} s{sample}: repaired -> {ans}")
                        ok = True
                        break
                if not ok and time.time() <= DEADLINE:
                    print(f"  {qid} p{para} s{sample}: still unparsed")
            fout.close()

if __name__ == "__main__":
    asyncio.run(main())
