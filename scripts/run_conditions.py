#!/usr/bin/env python3
"""Runner for the three revision conditions (resumable, all providers concurrent).

Conditions:
  greedypara : tau=0 decode of each paraphrase P1..P6 on each model's completed
               question set  -> results/cond_greedypara/{alias}.jsonl
  mmlupro    : greedy + 6 samples on the MMLU-Pro 30-question probe (no paraphrases)
               -> results/cond_mmlupro/{alias}.jsonl
  cot        : prompt-level chain-of-thought on MCQ questions: greedy + 6 SC
               samples; stem-locus questions additionally get 6 paraphrase votes
               -> results/cond_cot/{alias}.jsonl

Usage: python3 run_conditions.py [deadline_seconds] (default 520; 0 = run to end)
Each invocation appends to per-model JSONL and skips already-recorded calls, so
repeated invocations make progress across process restarts.
"""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import asyncio, aiohttp, json, os, re, time, sys, random
sys.path.insert(0, ROOT + "/scripts")
from credentials import APINEX, AGNES, ALIYUN

DATA = ROOT + "/data"
RES = ROOT + "/results"
DEADLINE = time.time() + (int(sys.argv[1]) if len(sys.argv) > 1 else 520)

questions = {q["id"]: q for q in json.load(open(f"{DATA}/questions.json"))}
mmlupro = {q["id"]: q for q in json.load(open(f"{DATA}/mmlupro30.json"))}
pdata = json.load(open(f"{DATA}/paraphrases.json"))
PARA, INSTR = pdata["paraphrases"], pdata["instructions"]
ANALYSIS = json.load(open(f"{RES}/analysis/results.json"))  # completed question sets

COT_INSTR = ('Think step by step to solve the problem. Then end your response with '
             '"Answer: <letter>", where <letter> is the correct option.')
COT_PIQA_INSTR = ('Think step by step to solve the problem. Then end your response with '
                  '"Answer: 1" or "Answer: 2" for the better solution.')

# ---------------- prompts ----------------
def build_prompt_base(q, para_idx, cot=False):
    """Original-suite prompt; cot=True swaps in a CoT instruction."""
    ds = q["dataset"]
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
    if cot:
        parts.append(COT_PIQA_INSTR if ds == "piqa" else COT_INSTR)
    else:
        instr = INSTR[ds][f"P{para_idx}"] if para_idx > 0 and q["instruction_type"] == "instruction" \
            else INSTR[ds]["P0"]
        parts.append(instr)
    return "\n\n".join(parts)

def build_prompt_mmlupro(q):
    parts = [q["stem"], "Options:\n" + "\n".join(f"({'ABCDEFGHIJ'[i]}) {o}" for i, o in enumerate(q["options"])),
             'Answer with the letter of the correct option. End your response with "Answer: <letter>".']
    return "\n\n".join(parts)

# ---------------- answer parsing (same as main runner) ----------------
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

# ---------------- model configs ----------------
MODELS = {
    "qwen3.8-max":      ("aliyun", "qwen3.8-max", 1, 120, 2000),
    "qwen3.8-omni":     ("aliyun", "qwen3.8-omni-flash", 2, 120, 2000),
    "agnes-3.0-flash":  ("agnes", "agnes-3.0-flash", 3, 200, 1200),
    "agnes-2.5-flash":  ("agnes", "agnes-2.5-flash", 4, 1400, 2500),
    "gpt-6-luna":       ("apinex", "free/gpt-6-luna", 5, 900, 1500),
    "gemini-3.8-flash": ("apinex", "free/gemini-3.8-flash", 6, 900, 1500),
}
ENDPOINTS = {
    "aliyun": {"base": ALIYUN["base_url"], "key": ALIYUN["api_key"],
               "rate": 5.0, "max_rate": 8.0, "min_rate": 1.0, "conc": 10},
    "agnes":  {"base": AGNES["base_url"], "key": AGNES["api_key"],
               "rate": 0.13, "max_rate": 0.13, "min_rate": 0.10, "conc": 6},
    "apinex": {"base": APINEX["base_url"], "key": APINEX["api_key"],
               "rate": 0.083, "max_rate": 0.083, "min_rate": 0.06, "conc": 5},
}
COT_MAX_TOKENS = {"qwen3.8-max": 2000, "qwen3.8-omni": 2000, "agnes-3.0-flash": 2000,
                  "agnes-2.5-flash": 2500, "gpt-6-luna": 2000, "gemini-3.8-flash": 2000}

def cot_questions(alias):
    """MCQ questions of the model's completed set (gsm8k excluded: already CoT)."""
    per_q = ANALYSIS["models"][alias]["per_q"]
    mcq = [qid for qid, v in per_q.items() if v["dataset"] != "gsm8k"]
    mcq.sort()
    rng = random.Random(42)
    if alias == "qwen3.8-max":
        # stratified 12: logiqa 5, sat_math 3, lsat 2, truthfulqa 2
        by_ds = {}
        for qid in mcq:
            by_ds.setdefault(questions[qid]["dataset"], []).append(qid)
        take = {"logiqa": 5, "sat_math": 3, "lsat_lr": 2, "truthfulqa": 2}
        sel = []
        for ds, k in take.items():
            pool = sorted(by_ds.get(ds, []))
            rng.shuffle(pool)
            sel += pool[:k]
        return sorted(sel)
    if alias == "qwen3.8-omni":
        by_ds = {}
        for qid in mcq:
            by_ds.setdefault(questions[qid]["dataset"], []).append(qid)
        take = {"logiqa": 6, "sat_math": 1, "lsat_lr": 3, "truthfulqa": 3, "piqa": 2}
        sel = []
        for ds, k in take.items():
            pool = sorted(by_ds.get(ds, []))
            rng.shuffle(pool)
            sel += pool[:k]
        return sorted(sel)
    return mcq  # agnes-3.0, agnes-2.5, gpt-6-luna: full MCQ sets

def mmlupro_questions(alias):
    ids = sorted(mmlupro.keys())
    if alias == "qwen3.8-max":
        return ids[:20]
    if alias == "gpt-6-luna":
        return ids[:15]
    if alias in ("gemini-3.8-flash", "agnes-2.5-flash"):
        return ids[:15]
    return ids

# ---------------- task lists ----------------
def tasks_for(alias):
    """Return list of (cond, qid, para, sample, temp, max_tokens, prompt, qref)."""
    ep, mid, _, mcq_tok, gsm_tok = MODELS[alias]
    out = []
    # 1. greedypara: on completed question set
    for qid in sorted(ANALYSIS["models"][alias]["per_q"]):
        q = questions[qid]
        mt = gsm_tok if q["dataset"] == "gsm8k" else mcq_tok
        for p in range(1, 7):
            out.append(("greedypara", qid, p, "g", 0.0, mt, build_prompt_base(q, p), q))
    # 2. mmlupro: greedy + 6 samples
    for qid in mmlupro_questions(alias):
        q = mmlupro[qid]
        out.append(("mmlupro", qid, 0, "g", 0.0, mcq_tok, build_prompt_mmlupro(q), q))
        for s in range(1, 7):
            out.append(("mmlupro", qid, 0, s, 0.7, mcq_tok, build_prompt_mmlupro(q), q))
    # 3. cot: MCQ questions; stem-locus get paraphrase votes too
    if alias != "gemini-3.8-flash":  # gemini excluded (coverage/queue budget)
        for qid in cot_questions(alias):
            q = questions[qid]
            mt = COT_MAX_TOKENS[alias]
            out.append(("cot", qid, 0, "g", 0.0, mt, build_prompt_base(q, 0, cot=True), q))
            for s in range(1, 7):
                out.append(("cot", qid, 0, s, 0.7, mt, build_prompt_base(q, 0, cot=True), q))
            if q["instruction_type"] == "stem":
                for p in range(1, 7):
                    out.append(("cot", qid, p, 1, 0.7, mt, build_prompt_base(q, p, cot=True), q))
    # priority: greedypara first, then mmlupro, then cot
    prio = {"greedypara": 0, "mmlupro": 1, "cot": 2}
    out.sort(key=lambda t: (prio[t[0]], t[1], t[2], str(t[3])))
    return out

def result_path(cond, alias):
    return f"{RES}/cond_{cond}/{alias}.jsonl"

def load_done():
    done = set()
    for cond in ("greedypara", "mmlupro", "cot"):
        d = f"{RES}/cond_{cond}"
        if os.path.exists(d):
            for fn in os.listdir(d):
                for line in open(os.path.join(d, fn)):
                    try:
                        r = json.loads(line)
                        if r.get("FAILED"):
                            continue
                        done.add((cond, r["model"], r["qid"], r["para"], str(r["sample"])))
                    except Exception:
                        pass
    return done

# ---------------- rate limiter + api (same as main runner) ----------------
class RateLimiter:
    def __init__(self, name, cfg):
        self.name = name
        self.rate, self.max_rate, self.min_rate = cfg["rate"], cfg["max_rate"], cfg["min_rate"]
        self.sem = asyncio.Semaphore(cfg["conc"])
        self.next_slot = 0.0
        self.lock = asyncio.Lock()
        self.success_streak = 0
        self.cooldown_until = 0.0
        self.total_ok = 0
        self.total_err = 0

    async def acquire(self):
        while True:
            async with self.lock:
                now = time.monotonic()
                if now < self.cooldown_until:
                    cd = self.cooldown_until - now
                else:
                    cd = 0.0
                    if self.next_slot < now:
                        self.next_slot = now
                    slot = self.next_slot
                    self.next_slot += 1.0 / self.rate
            if cd > 0:
                await asyncio.sleep(cd)
                continue
            if slot > now:
                await asyncio.sleep(slot - now)
            await self.sem.acquire()
            return

    def release(self):
        self.sem.release()

    def report_ok(self):
        self.total_ok += 1
        self.success_streak += 1
        if self.success_streak >= 40 and self.rate < self.max_rate:
            self.rate = min(self.max_rate, self.rate * 1.1)
            self.success_streak = 0

    def report_err(self, retryable):
        self.total_err += 1
        self.success_streak = 0
        if retryable:
            self.rate = max(self.min_rate, self.rate * 0.5)
            self.cooldown_until = time.monotonic() + 45

async def call_api(session, ep_cfg, model_id, prompt, temperature, max_tokens, thinking=None):
    body = {"model": model_id, "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature, "max_tokens": max_tokens}
    if thinking is not None:
        body["enable_thinking"] = thinking
    headers = {"Authorization": f"Bearer {ep_cfg['key']}", "Content-Type": "application/json"}
    try:
        async with session.post(f"{ep_cfg['base']}/chat/completions", json=body, headers=headers,
                                timeout=aiohttp.ClientTimeout(total=150)) as resp:
            text = await resp.text()
            if resp.status == 200:
                try:
                    r = json.loads(text)
                    msg = r["choices"][0]["message"]
                    usage = r.get("usage", {})
                    return {"ok": True, "content": msg.get("content") or "",
                            "reasoning_len": len(msg.get("reasoning_content") or ""),
                            "usage": {"pt": usage.get("prompt_tokens"), "ct": usage.get("completion_tokens")}}
                except Exception as e:
                    return {"ok": False, "err": f"parse:{str(e)[:60]}", "retry": True}
            if resp.status == 403 and ("FreeTier" in text or "AllocationQuota" in text):
                return {"ok": False, "err": "QUOTA_EXHAUSTED", "retry": False, "fatal_model": True}
            if resp.status in (402, 403) and ("quota" in text.lower() or "payment" in text.lower() or "unavailable" in text.lower()):
                return {"ok": False, "err": f"MODEL_QUOTA:{text[:80]}", "retry": False, "fatal_model": True}
            retryable = resp.status in (429, 500, 502, 503, 504)
            return {"ok": False, "err": f"HTTP{resp.status}:{text[:100]}", "retry": retryable}
    except asyncio.TimeoutError:
        return {"ok": False, "err": "TIMEOUT", "retry": True}
    except Exception as e:
        return {"ok": False, "err": f"EXC:{str(e)[:80]}", "retry": True}

# ---------------- worker ----------------
async def worker(alias, session, limiters, status, done, fouts):
    ep, mid, prio, _, _ = MODELS[alias]
    ep_cfg, limiter = ENDPOINTS[ep], limiters[ep]
    tasks = tasks_for(alias)
    todo = [t for t in tasks if (t[0], alias, t[1], t[2], str(t[3])) not in done]
    status[alias] = {"total": len(tasks), "done": len(tasks) - len(todo), "errors": 0,
                     "dead": False, "last_msg": "running"}
    if not todo:
        status[alias]["last_msg"] = "COMPLETE"
        return
    consec_err = 0
    for (cond, qid, para, sample, temp, mt, prompt, q) in todo:
        if status[alias]["dead"]:
            break
        if time.time() > DEADLINE:
            status[alias]["last_msg"] = "DEADLINE"
            break
        # qwen thinking config: same as main run for greedypara; off for mmlupro/cot
        thinking = None
        if ep == "aliyun":
            thinking = (q["dataset"] == "gsm8k") if cond == "greedypara" else False
        success = False
        for attempt in range(4):
            if time.time() > DEADLINE + 60:
                break
            await limiter.acquire()
            try:
                res = await call_api(session, ep_cfg, mid, prompt, temp, mt, thinking)
            finally:
                limiter.release()
            if res.get("ok"):
                limiter.report_ok()
                consec_err = 0
                ans = extract_answer(res["content"], q)
                c = res["content"]
                snippet = (c[:60] + " ... " + c[-640:]) if len(c) > 720 else c
                fouts[(cond, alias)].write(json.dumps({
                    "model": alias, "qid": qid, "dataset": q["dataset"], "para": para,
                    "sample": sample, "temp": temp, "answer": ans,
                    "correct": answer_to_int(ans, q) if ans is not None else None,
                    "content_len": len(c), "reasoning_len": res["reasoning_len"],
                    "snippet": snippet,
                    "usage": res["usage"], "t": round(time.time(), 1)}, ensure_ascii=False) + "\n")
                status[alias]["done"] += 1
                success = True
                break
            else:
                limiter.report_err(res.get("retry", False))
                status[alias]["errors"] += 1
                status[alias]["last_msg"] = res.get("err", "")[:70]
                if res.get("fatal_model"):
                    status[alias]["dead"] = True
                    status[alias]["last_msg"] = "QUOTA_EXHAUSTED"
                    break
                consec_err += 1
                if consec_err >= 8:
                    status[alias]["dead"] = True
                    status[alias]["last_msg"] = "8 consecutive errors"
                    break
                await asyncio.sleep(min(60, 5 * (2 ** attempt)) + random.uniform(0, 3))
        if not success and not status[alias]["dead"] and time.time() <= DEADLINE + 60:
            fouts[(cond, alias)].write(json.dumps({"model": alias, "qid": qid, "para": para,
                                          "sample": sample, "FAILED": True,
                                          "err": status[alias]["last_msg"],
                                          "t": round(time.time(), 1)}, ensure_ascii=False) + "\n")
    if status[alias]["done"] >= status[alias]["total"]:
        status[alias]["last_msg"] = "COMPLETE"

async def main():
    aliases = sys.argv[2].split(",") if len(sys.argv) > 2 else list(MODELS.keys())
    limiters = {name: RateLimiter(name, cfg) for name, cfg in ENDPOINTS.items()}
    done = load_done()
    status = {}
    for cond in ("greedypara", "mmlupro", "cot"):
        os.makedirs(f"{RES}/cond_{cond}", exist_ok=True)
    fouts = {(cond, a): open(f"{RES}/cond_{cond}/{a}.jsonl", "a", buffering=1)
             for cond in ("greedypara", "mmlupro", "cot") for a in aliases}
    conn = aiohttp.TCPConnector(limit=40)
    async with aiohttp.ClientSession(connector=conn) as session:
        tasks = [asyncio.create_task(worker(a, session, limiters, status, done, fouts))
                 for a in aliases]
        start = time.time()
        while not all(t.done() for t in tasks):
            if time.time() - start > 30:
                lines = [time.strftime("%H:%M:%S")]
                for ep_name, lim in limiters.items():
                    lines.append(f"  [{ep_name:6s}] rate={lim.rate:.2f}/s ok={lim.total_ok} err={lim.total_err}")
                for a in sorted(status, key=lambda x: MODELS[x][2]):
                    s = status[a]
                    lines.append(f"  {a:18s} {s['done']:4d}/{s['total']:4d} err={s['errors']:3d} "
                                 f"{'DEAD' if s['dead'] else '    '} {s['last_msg'][:50]}")
                open(f"{RES}/cond_status.txt", "w").write("\n".join(lines) + "\n")
                start = time.time()
            await asyncio.sleep(5)
    open(f"{RES}/cond_status.txt", "a").write("\nALL WORKERS FINISHED\n")
    for f in fouts.values():
        f.close()

if __name__ == "__main__":
    asyncio.run(main())
