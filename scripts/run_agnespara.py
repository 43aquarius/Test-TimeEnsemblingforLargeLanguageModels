#!/usr/bin/env python3
"""B9 eval: run GPT-6-Luna and Gemini3.8-Flash on the Agnes-generated paraphrases
for their completed stem questions (single stochastic decode per paraphrase),
to recompute fragility under the second generator.
Output: results/cond_agnespara/{model}.jsonl
Usage: python3 run_agnespara.py [deadline_s]"""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import asyncio, aiohttp, json, os, re, sys, time
sys.path.insert(0, ROOT + "/scripts")
from credentials import APINEX, ALIYUN

DATA = ROOT + "/data"
RES = ROOT + "/results"
DEADLINE = time.time() + (int(sys.argv[1]) if len(sys.argv) > 1 else 460)

questions = {q["id"]: q for q in json.load(open(f"{DATA}/questions.json"))}
paras_agnes = json.load(open(f"{DATA}/paraphrases_agnes.json"))
pdata = json.load(open(f"{DATA}/paraphrases.json"))
INSTR = pdata["instructions"]
ANALYSIS = json.load(open(f"{RES}/analysis/results.json"))

MODELS = {"gpt-6-luna": ("apinex", "free/gpt-6-luna"), "gemini-3.8-flash": ("apinex", "free/gemini-3.8-flash")}
ENDPOINT = {"base": APINEX["base_url"], "key": APINEX["api_key"]}

def build_prompt(q, para_text):
    parts = []
    if q.get("passage"):
        parts.append(q["passage"])
    parts.append(para_text)
    if q["options"]:
        letters = "ABCDEFGHIJ"
        parts.append("Options:\n" + "\n".join(f"({letters[i]}) {o}" for i, o in enumerate(q["options"])))
    parts.append(INSTR[q["dataset"]]["P0"])
    return "\n\n".join(parts)

def extract_answer(content, q):
    c = content.strip()
    if not c:
        return None
    n_opt = len(q["options"]) if q["options"] else None
    letters = "ABCDEFGHIJ"[:n_opt] if n_opt else "ABCDEFGHIJ"
    for pat in [r"Answer:?\s*\**\s*\(?([A-J])\)?", r"\*\*([A-J])\*\*"]:
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
    if ans is None:
        return None
    try:
        return "ABCDEFGHIJ".index(ans) == q["answer_idx"]
    except (ValueError, TypeError):
        return False

def gold_of(q):
    return "ABCDEFGHIJ"[q["answer_idx"]]

def majority(votes):
    from collections import Counter
    vs = [v for v in votes if v]
    if not vs:
        return None
    c = Counter(vs)
    top = c.most_common()
    best = top[0][1]
    winners = set(v for v, n in top if n == best)
    for v in vs:
        if v in winners:
            return v

async def main():
    os.makedirs(f"{RES}/cond_agnespara", exist_ok=True)
    sem = asyncio.Semaphore(3)
    next_slot = 0.0
    lock = asyncio.Lock()
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=8)) as session:
        for alias, (ep, mid) in MODELS.items():
            per_q = ANALYSIS["models"][alias]["per_q"]
            stem_qids = [qid for qid in per_q
                         if questions[qid]["instruction_type"] == "stem"
                         and qid in paras_agnes
                         and paras_agnes[qid]["n_valid"] >= 4]
            print(f"{alias}: {len(stem_qids)} stem questions with valid agnes paraphrases")
            path = f"{RES}/cond_agnespara/{alias}.jsonl"
            done = set()
            if os.path.exists(path):
                for line in open(path):
                    try:
                        r = json.loads(line)
                        if not r.get("FAILED"):
                            done.add((r["qid"], r["para"]))
                    except Exception:
                        pass
            fout = open(path, "a", buffering=1)
            for qid in sorted(stem_qids):
                q = questions[qid]
                valid_paras = [p for p, s in zip(paras_agnes[qid]["paras"],
                                                  paras_agnes[qid]["sims"])
                               if s is not None and s >= 0.75][:6]
                for pi, ptext in enumerate(valid_paras, 1):
                    if (qid, pi) in done or time.time() > DEADLINE:
                        continue
                    async with sem:
                        await asyncio.sleep(12.5)  # ~4.8/min shared
                        prompt = build_prompt(q, ptext)
                        body = {"model": mid, "messages": [{"role": "user", "content": prompt}],
                                "temperature": 0.7, "max_tokens": 900}
                        try:
                            async with session.post(f"{ENDPOINT['base']}/chat/completions", json=body,
                                                    headers={"Authorization": f"Bearer {ENDPOINT['key']}"},
                                                    timeout=aiohttp.ClientTimeout(total=120)) as resp:
                                text = await resp.text()
                                if resp.status != 200:
                                    print(f"  {qid} p{pi}: HTTP{resp.status}")
                                    continue
                                r = json.loads(text)
                                content = r["choices"][0]["message"].get("content") or ""
                                usage = r.get("usage", {})
                        except Exception as e:
                            print(f"  {qid} p{pi}: {str(e)[:50]}")
                            continue
                        ans = extract_answer(content, q)
                        snippet = (content[:60] + " ... " + content[-640:]) if len(content) > 720 else content
                        fout.write(json.dumps({
                            "model": alias, "qid": qid, "dataset": q["dataset"], "para": pi,
                            "sample": 1, "temp": 0.7, "answer": ans,
                            "correct": answer_to_int(ans, q), "content_len": len(content),
                            "reasoning_len": 0, "snippet": snippet,
                            "usage": {"pt": usage.get("prompt_tokens"), "ct": usage.get("completion_tokens")},
                            "t": round(time.time(), 1)}, ensure_ascii=False) + "\n")
            fout.close()
    # quick summary
    for alias in MODELS:
        path = f"{RES}/cond_agnespara/{alias}.jsonl"
        if not os.path.exists(path):
            continue
        cells = {}
        for line in open(path):
            try:
                r = json.loads(line)
                if not r.get("FAILED"):
                    cells.setdefault(r["qid"], {})[r["para"]] = r["answer"]
            except Exception:
                pass
        per_q = ANALYSIS["models"][alias]["per_q"]
        n = flips = pe_ok = 0
        for qid, cm in cells.items():
            if len([k for k, v in cm.items() if v]) < 4 or qid not in per_q:
                continue
            gold = gold_of(questions[qid])
            pe_a = majority(list(cm.values()))
            sc6 = majority([ANALYSIS["models"][alias]["per_q"][qid]["sc"][6][0]])
            n += 1
            flips += int(pe_a != sc6)
            pe_ok += int(pe_a == gold)
        if n:
            print(f"{alias}: agnes-para fragility {flips}/{n} = {100*flips/n:.1f}%  PE-ag acc {100*pe_ok/n:.1f}%")

if __name__ == "__main__":
    asyncio.run(main())
