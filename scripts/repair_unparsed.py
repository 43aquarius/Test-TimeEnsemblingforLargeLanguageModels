#!/usr/bin/env python3
"""Retry unparsed calls (answer=None) until extraction succeeds, per reviewer B7.

Appends new records for the same (qid, para, sample); analyze.py's loader takes
the last record per key, so a successful retry overrides the unparsed one.
Usage: python3 repair_unparsed.py <model1,model2,...> [deadline_s]
"""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import asyncio, aiohttp, json, os, re, time, sys, random
sys.path.insert(0, ROOT + "/scripts")
from credentials import APINEX, AGNES, ALIYUN

DATA = ROOT + "/data"
RES = ROOT + "/results"
DEADLINE = time.time() + (int(sys.argv[2]) if len(sys.argv) > 2 else 500)

questions = {q["id"]: q for q in json.load(open(f"{DATA}/questions.json"))}
pdata = json.load(open(f"{DATA}/paraphrases.json"))
PARA, INSTR = pdata["paraphrases"], pdata["instructions"]

MODELS = {
    "qwen3.8-max":      ("aliyun", "qwen3.8-max", 120, 2000),
    "qwen3.8-omni":     ("aliyun", "qwen3.8-omni-flash", 120, 2000),
    "agnes-3.0-flash":  ("agnes", "agnes-3.0-flash", 200, 1200),
    "agnes-2.5-flash":  ("agnes", "agnes-2.5-flash", 1400, 2500),
    "gpt-6-luna":       ("apinex", "free/gpt-6-luna", 900, 1500),
    "gemini-3.8-flash": ("apinex", "free/gemini-3.8-flash", 900, 1500),
}
ENDPOINTS = {
    "aliyun": {"base": ALIYUN["base_url"], "key": ALIYUN["api_key"], "rate": 5.0, "conc": 8},
    "agnes":  {"base": AGNES["base_url"], "key": AGNES["api_key"], "rate": 0.13, "conc": 4},
    "apinex": {"base": APINEX["base_url"], "key": APINEX["api_key"], "rate": 0.083, "conc": 4},
}

def build_prompt(q, para_idx):
    ds = q["dataset"]
    if q["instruction_type"] == "instruction":
        stem, instr = q["stem"], INSTR[ds][f"P{para_idx}"]
    else:
        stem = q["stem"] if para_idx == 0 else PARA[q["id"]][para_idx - 1]
        instr = INSTR[ds]["P0"]
    parts = []
    if q.get("passage"):
        parts.append(q["passage"])
    parts.append(stem)
    if q["options"]:
        letters = "ABCDEFGHIJ"
        parts.append("Options:\n" + "\n".join(f"({letters[i]}) {o}" for i, o in enumerate(q["options"])))
    parts.append(instr)
    return "\n\n".join(parts)

def extract_answer(content, q):
    c = content.strip()
    if not c:
        return None
    n_opt = len(q["options"]) if q["options"] else None
    letters = "ABCDEFGHIJ"[:n_opt] if n_opt else "ABCDEFGHIJ"
    if q["dataset"] == "gsm8k":
        m = re.findall(r"Answer:\s*\$?\s*(-?[\d,]+(?:\.\d+)?)", c)
        if m: return m[-1].replace(",", "")
        for line in reversed(c.split("\n")):
            nums = re.findall(r"-?[\d,]+(?:\.\d+)?", line)
            if nums: return nums[-1].replace(",", "")
        return None
    if q["dataset"] == "piqa":
        m = re.findall(r"Answer:?\s*\**\s*([12])", c)
        if m: return m[-1]
        m = re.findall(r"\b([12])\b", c[-80:])
        if m: return m[-1]
        return None
    pats = [r"Answer:?\s*\**\s*\(?([A-J])\)?", r"\*\*([A-J])\*\*"]
    for pat in pats:
        found = re.findall(pat, c)
        in_range = [f for f in found if f in letters]
        if in_range:
            return in_range[-1]
    for line in reversed(c.split("\n")[-4:]):
        m = re.findall(r"\(?\b([A-J])\)?\b", line)
        in_range = [x for x in m if x in letters]
        if in_range:
            return in_range[-1]
    return None

def answer_to_int(ans, q):
    if ans is None: return None
    try:
        if q["dataset"] == "gsm8k":
            return abs(float(ans) - float(q["answer"])) < 1e-6
        if q["dataset"] == "piqa":
            return int(ans) - 1 == q["answer_idx"]
        return "ABCDEFGHIJ".index(ans) == q["answer_idx"]
    except (ValueError, TypeError):
        return False

async def main():
    aliases = sys.argv[1].split(",")
    sem = {ep: asyncio.Semaphore(cfg["conc"]) for ep, cfg in ENDPOINTS.items()}
    lock = {"aliyun": asyncio.Lock()}
    next_slot = {"aliyun": 0.0}
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=20)) as session:
        for alias in aliases:
            ep, mid, mcq_tok, gsm_tok = MODELS[alias]
            cfg = ENDPOINTS[ep]
            # collect unparsed cells (last record per key wins)
            cells = {}
            for line in open(f"{RES}/{alias}.jsonl"):
                try:
                    r = json.loads(line)
                    if r.get("FAILED"):
                        continue
                    cells[(r["qid"], r["para"], str(r["sample"]))] = r
                except Exception:
                    pass
            broken = [(k, r) for k, r in cells.items() if r["answer"] is None]
            print(f"{alias}: {len(broken)} unparsed cells to retry")
            fout = open(f"{RES}/{alias}.jsonl", "a", buffering=1)
            for (qid, para, sample), old in broken:
                if time.time() > DEADLINE:
                    print("  deadline reached, stopping")
                    break
                q = questions[qid]
                mt = gsm_tok if q["dataset"] == "gsm8k" else mcq_tok
                prompt = build_prompt(q, para)
                temp = old["temp"]
                ok = False
                for attempt in range(5):
                    if ep == "aliyun":
                        async with lock["aliyun"]:
                            now = time.monotonic()
                            if next_slot["aliyun"] < now:
                                next_slot["aliyun"] = now
                            slot = next_slot["aliyun"]
                            next_slot["aliyun"] += 1.0 / cfg["rate"]
                        if slot > time.monotonic():
                            await asyncio.sleep(slot - time.monotonic())
                    else:
                        await asyncio.sleep(12 if ep == "agnes" else 13)  # ~rate limit
                    body = {"model": mid, "messages": [{"role": "user", "content": prompt}],
                            "temperature": temp, "max_tokens": mt}
                    if ep == "aliyun":
                        body["enable_thinking"] = (q["dataset"] == "gsm8k")
                    try:
                        async with sem[ep]:
                            async with session.post(f"{cfg['base']}/chat/completions", json=body,
                                                    headers={"Authorization": f"Bearer {cfg['key']}"},
                                                    timeout=aiohttp.ClientTimeout(total=150)) as resp:
                                text = await resp.text()
                                if resp.status != 200:
                                    print(f"  {qid} p{para} s{sample}: HTTP{resp.status}, retry")
                                    continue
                                r = json.loads(text)
                                msg = r["choices"][0]["message"]
                                content = msg.get("content") or ""
                                usage = r.get("usage", {})
                    except Exception as e:
                        print(f"  {qid} p{para} s{sample}: {str(e)[:60]}, retry")
                        continue
                    ans = extract_answer(content, q)
                    if ans is not None:
                        snippet = (content[:60] + " ... " + content[-640:]) if len(content) > 720 else content
                        fout.write(json.dumps({
                            "model": alias, "qid": qid, "dataset": q["dataset"], "para": para,
                            "sample": old["sample"], "temp": temp, "answer": ans,
                            "correct": answer_to_int(ans, q), "content_len": len(content),
                            "reasoning_len": len(msg.get("reasoning_content") or ""),
                            "snippet": snippet, "usage": {"pt": usage.get("prompt_tokens"),
                                                          "ct": usage.get("completion_tokens")},
                            "t": round(time.time(), 1), "repaired": True}, ensure_ascii=False) + "\n")
                        print(f"  {qid} p{para} s{sample}: repaired -> {ans}")
                        ok = True
                        break
                if not ok:
                    print(f"  {qid} p{para} s{sample}: STILL UNPARSED after retries")
            fout.close()

if __name__ == "__main__":
    asyncio.run(main())
