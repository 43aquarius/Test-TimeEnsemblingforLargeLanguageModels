#!/usr/bin/env python3
"""Expansion runner: 16-call matrix on questions_expand.json (119 questions).
Same task structure, prompt builder, extractor, and checkpoint format as
run_experiment.py; only the data source, output directory, model list, and
the (empirically re-measured) Agnes rate differ.  Resumable via JSONL.

Usage: python3 run_expand.py agnes-3.0-flash[,agnes-2.5-flash]
"""
import asyncio, aiohttp, json, os, re, time, sys, random
sys.path.insert(0, "/home/z/my-project/scripts")
from credentials import AGNES, ALIYUN, APINEX

# apinex sits behind Cloudflare: default urllib/aiohttp UA gets 403 (error 1010)
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

DATA = "/home/z/my-project/data"
RES = "/home/z/my-project/results/expand"
os.makedirs(RES, exist_ok=True)

questions = json.load(open(f"{DATA}/questions_expand.json"))
QMAP = {q["id"]: q for q in questions}
pdata = json.load(open(f"{DATA}/paraphrases_expand.json"))
PARA, INSTR = pdata["paraphrases"], pdata["instructions"]
# fall back to the original paraphrase store if an id is somehow missing
_orig = json.load(open(f"{DATA}/paraphrases.json"))
PARA.update(_orig.get("paraphrases", {}))
INSTR = {**_orig["instructions"], **INSTR}

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

MODELS = {
    # mcq budget raised 200 -> 800: sat_math/piqa can trigger content-level
    # chain-of-thought that overruns a 200-token cap before emitting the answer
    "agnes-3.0-flash": ("agnes-3.0-flash", 800, 1200, False),
    "agnes-2.5-flash": ("agnes-2.5-flash", 1400, 2500, False),
    # reasoning model: completion budget must cover reasoning tokens too;
    # 1000 was too small on logiqa (reasoning consumed it before any content)
    "deepseek-v4.1-flash": ("deepseek-v4.1-flash", 2500, 3500, False),
    "deepseek-v4-flash-0731": ("deepseek-v4-flash-0731", 2500, 3500, False),
    # qwen3.7-flash: MCQ answered with enable_thinking=False (direct, ~1 token)
    # EXCEPT sat_math (and GSM8K), where computation happens and thinking mode
    # keeps the content channel short; piqa gets a 400-token content budget
    "qwen3.7-flash": ("qwen3.7-flash", 400, 3000, True),
}
ENDPOINTS = {
    "agnes": {"base": AGNES["base_url"], "key": AGNES["api_key"],
              "rate": 0.35, "max_rate": 0.5, "min_rate": 0.1, "conc": 6, "batch": 1},
    "aliyun": {"base": ALIYUN["base_url"].rstrip("/").rsplit("/compatible-mode", 1)[0] + "/compatible-mode/v1",
               "key": ALIYUN["api_key"],
               "rate": 1.5, "max_rate": 4.0, "min_rate": 0.3, "conc": 16, "batch": 8},
    # apinex free tier: account-wide "Max 5 requests per minute" (shared across
    # models); pace at 0.080/s = 4.8/min to stay safely under the rolling window.
    # 429 bodies carry "Retry in Ns" which run_task honours verbatim.
    "apinex": {"base": APINEX["base_url"], "key": APINEX["api_key"], "ua": BROWSER_UA,
               "rate": 0.080, "max_rate": 0.080, "min_rate": 0.060, "conc": 12, "batch": 8,
               # origin sits behind Cloudflare and can slow down under load;
               # a 240s ceiling lets slow-but-valid responses still land
               "timeout": 240},
}
MODEL_EP = {
    "agnes-3.0-flash": "agnes",
    "agnes-2.5-flash": "agnes",
    "deepseek-v4.1-flash": "apinex",
    "deepseek-v4-flash-0731": "apinex",
    "qwen3.7-flash": "aliyun",
}
# provider-specific model ids (apinex exposes the deepseeks under free/)
EP_MODEL_ID = {
    ("apinex", "deepseek-v4.1-flash"): "free/deepseek-v4.1-flash",
    ("apinex", "deepseek-v4-flash-0731"): "free/deepseek-v4-flash-0731",
}

def tasks_for_model(alias):
    _, mcq_tok, gsm_tok, _ = MODELS[alias]
    tlist = []
    for q in questions:
        mt = gsm_tok if q["dataset"] == "gsm8k" else mcq_tok
        tlist.append((q["id"], 0, "g", 0.0, mt))
        for s in range(1, 7):
            tlist.append((q["id"], 0, s, 0.7, mt))
        for p in (1, 2, 3):
            for s in (1, 2):
                tlist.append((q["id"], p, s, 0.7, mt))
        for p in (4, 5, 6):
            tlist.append((q["id"], p, 1, 0.7, mt))
    return tlist

def result_path(alias):
    return f"{RES}/{alias}.jsonl"

def load_done(alias):
    done = set()
    p = result_path(alias)
    if os.path.exists(p):
        for line in open(p):
            try:
                r = json.loads(line)
                if r.get("FAILED"):
                    continue
                # unparsed cells are re-queued (main-suite protocol: redraw
                # until extraction succeeds, subject to provider quota)
                if r.get("answer") is None:
                    continue
                done.add((r["qid"], r["para"], str(r["sample"])))
            except Exception:
                pass
    return done

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

    def report_err(self, retryable, halve=True):
        self.total_err += 1
        self.success_streak = 0
        if retryable:
            if halve:
                self.rate = max(self.min_rate, self.rate * 0.5)
            self.cooldown_until = time.monotonic() + 30

async def call_api(session, ep_cfg, model_id, prompt, temperature, max_tokens, enable_thinking=None):
    body = {"model": model_id, "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature, "max_tokens": max_tokens}
    if enable_thinking is not None:
        body["enable_thinking"] = enable_thinking
    headers = {"Authorization": f"Bearer {ep_cfg['key']}", "Content-Type": "application/json"}
    if ep_cfg.get("ua"):
        headers["User-Agent"] = ep_cfg["ua"]
        headers["Accept"] = "application/json"
    try:
        async with session.post(f"{ep_cfg['base']}/chat/completions", json=body, headers=headers,
                                timeout=aiohttp.ClientTimeout(total=ep_cfg.get("timeout", 150))) as resp:
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
            if resp.status in (402, 403) and ("quota" in text.lower() or "payment" in text.lower()
                                              or "FreeTier" in text or "unavailable" in text.lower()):
                return {"ok": False, "err": f"MODEL_QUOTA:{text[:80]}", "retry": False, "fatal_model": True}
            retryable = resp.status in (429, 500, 502, 503, 504)
            ra = None
            if resp.status == 429:
                m = re.search(r"Retry in (\d+)s", text)
                if m:
                    ra = min(90, int(m.group(1)) + 2)
            return {"ok": False, "err": f"HTTP{resp.status}:{text[:100]}", "retry": retryable,
                    "retry_after": ra}
    except asyncio.TimeoutError:
        return {"ok": False, "err": "TIMEOUT", "retry": True}
    except Exception as e:
        return {"ok": False, "err": f"EXC:{str(e)[:80]}", "retry": True}

async def run_task(alias, session, ep_cfg, limiter, status, task, fout, state):
    """Execute one (qid, para, sample, temp, mt) task with retries; write result."""
    qid, para, sample, temp, mt = task
    mid = state["mid"]
    nothink_mcq = state["nothink"]
    q = QMAP[qid]
    prompt = build_prompt(q, para)
    eth = (False if nothink_mcq and q["dataset"] not in ("gsm8k", "sat_math") else None)
    for attempt in range(4):
        if status[alias]["dead"]:
            return
        await limiter.acquire()
        try:
            res = await call_api(session, ep_cfg, mid, prompt, temp, mt, enable_thinking=eth)
        finally:
            limiter.release()
        if res.get("ok"):
            limiter.report_ok()
            ans = extract_answer(res["content"], q)
            c = res["content"]
            snippet = (c[:60] + " ... " + c[-640:]) if len(c) > 720 else c
            fout.write(json.dumps({
                "model": alias, "qid": qid, "dataset": q["dataset"], "para": para,
                "sample": sample, "temp": temp, "answer": ans,
                "correct": answer_to_int(ans, q) if ans is not None else None,
                "content_len": len(c), "reasoning_len": res["reasoning_len"],
                "snippet": snippet,
                "usage": res["usage"], "t": round(time.time(), 1)}, ensure_ascii=False) + "\n")
            status[alias]["done"] += 1
            return
        else:
            ra = res.get("retry_after")
            limiter.report_err(res.get("retry", False), halve=ra is None)
            status[alias]["errors"] += 1
            status[alias]["last_msg"] = res.get("err", "")[:70]
            if res.get("fatal_model"):
                status[alias]["dead"] = True
                status[alias]["last_msg"] = "QUOTA_EXHAUSTED"
                return
            if ra:
                await asyncio.sleep(ra)
            else:
                await asyncio.sleep(min(60, 5 * (2 ** attempt)) + random.uniform(0, 3))
    if not status[alias]["dead"]:
        fout.write(json.dumps({"model": alias, "qid": qid, "para": para, "sample": sample,
                               "FAILED": True, "err": status[alias]["last_msg"],
                               "t": round(time.time(), 1)}, ensure_ascii=False) + "\n")

async def worker(alias, session, limiters, status):
    mid, mcq_tok, gsm_tok, nothink_mcq = MODELS[alias]
    ep_name = MODEL_EP[alias]
    mid = EP_MODEL_ID.get((ep_name, alias), mid)
    ep_cfg, limiter = ENDPOINTS[ep_name], limiters[ep_name]
    batch = ENDPOINTS[ep_name].get("batch", 1)
    done = load_done(alias)
    tasks = tasks_for_model(alias)
    todo = [t for t in tasks if (t[0], t[1], str(t[2])) not in done]
    status[alias] = {"total": len(tasks), "done": len(tasks) - len(todo), "errors": 0,
                     "dead": False, "last_msg": "running"}
    if not todo:
        status[alias]["last_msg"] = "COMPLETE"
        return
    # order: complete cheap MCQ questions first, expensive GSM8K last, so that
    # a mid-run quota death still leaves a maximum of complete 16-call questions
    def qnum(t):
        return int(t[0][1:])
    todo.sort(key=lambda t: (1 if QMAP[t[0]]["dataset"] == "gsm8k" else 0, qnum(t), t[1], str(t[2])))
    fout = open(result_path(alias), "a", buffering=1)
    state = {"mid": mid, "nothink": nothink_mcq}
    for i in range(0, len(todo), batch):
        if status[alias]["dead"]:
            break
        chunk = todo[i:i + batch]
        await asyncio.gather(*[run_task(alias, session, ep_cfg, limiter, status, t, fout, state)
                               for t in chunk])
    if status[alias]["done"] >= status[alias]["total"]:
        status[alias]["last_msg"] = "COMPLETE"
    fout.close()

async def monitor(status, limiters, worker_tasks):
    while not all(t.done() for t in worker_tasks):
        lines = [time.strftime("%H:%M:%S")]
        for ep_name, lim in limiters.items():
            lines.append(f"  [{ep_name}] rate={lim.rate:.2f}/s ok={lim.total_ok} err={lim.total_err}")
        for alias, s in status.items():
            pct = 100 * s["done"] / max(1, s["total"])
            lines.append(f"  {alias:18s} {s['done']:4d}/{s['total']:4d} ({pct:4.1f}%) "
                         f"err={s['errors']:3d} {'DEAD' if s['dead'] else ''} {s['last_msg'][:55]}")
        with open(f"{RES}/status.txt", "w") as f:
            f.write("\n".join(lines) + "\n")
        await asyncio.sleep(20)
    open(f"{RES}/status.txt", "a").write("\nALL WORKERS FINISHED\n")

async def main():
    only = sys.argv[1].split(",") if len(sys.argv) > 1 else list(MODELS.keys())
    limiters = {name: RateLimiter(name, cfg) for name, cfg in ENDPOINTS.items()}
    status = {}
    conn = aiohttp.TCPConnector(limit=40)
    async with aiohttp.ClientSession(connector=conn) as session:
        tasks = [asyncio.create_task(worker(alias, session, limiters, status)) for alias in only]
        mon = asyncio.create_task(monitor(status, limiters, tasks))
        await asyncio.gather(*tasks)
        mon.cancel()

if __name__ == "__main__":
    asyncio.run(main())
