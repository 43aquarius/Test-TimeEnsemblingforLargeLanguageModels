#!/usr/bin/env python3
"""Test apinex endpoint: chat format, usage reporting, latency, burst rate."""
import urllib.request, json, time, statistics

BASE = "https://api.apinex.bond/v1"
KEY = "sk-apxe8e3bc610bd556066ca665074a4ba0c722a9cce84fbe1cf"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

def chat(model, prompt="What is 2+2? Answer with just the number.", max_tokens=512, temperature=0.7):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "temperature": temperature, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(f"{BASE}/chat/completions", data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                 "User-Agent": UA, "Accept": "application/json"})
    t0 = time.time()
    try:
        r = urllib.request.urlopen(req, timeout=120)
        dt = time.time() - t0
        d = json.loads(r.read())
        msg = d["choices"][0]["message"]
        return {"ok": True, "dt": dt, "content": (msg.get("content") or "")[:80],
                "reasoning_len": len(msg.get("reasoning_content") or ""),
                "usage": d.get("usage"), "finish": d["choices"][0].get("finish_reason"),
                "model_returned": d.get("model")}
    except Exception as e:
        msg = ""
        if hasattr(e, "read"):
            try: msg = e.read().decode()[:250]
            except: pass
        return {"ok": False, "dt": time.time() - t0, "err": f"{type(e).__name__}: {str(e)[:100]} {msg}"}

# 1) single-call format check on both target models
for m in ["free/deepseek-v4-flash-0731", "free/deepseek-v4.1-flash"]:
    r = chat(m)
    if r["ok"]:
        print(f"[{m}] OK {r['dt']:.1f}s | usage={r['usage']} | finish={r['finish']} | "
              f"rlen={r['reasoning_len']} | ret_model={r['model_returned']}")
        print(f"   content: {r['content']!r}")
    else:
        print(f"[{m}] FAIL {r['dt']:.1f}s: {r['err']}")

print()
# 2) burst test: 8 rapid sequential calls to free/deepseek-v4-flash-0731
print("burst x8 on free/deepseek-v4-flash-0731:")
dts, oks = [], 0
for i in range(8):
    r = chat("free/deepseek-v4-flash-0731", prompt=f"Reply with the single word OK{i}.", max_tokens=300)
    dts.append(r["dt"])
    oks += r["ok"]
    print(f"  #{i+1} {'ok' if r['ok'] else 'FAIL ' + str(r.get('err'))[:80]} {r['dt']:.1f}s")
print(f"  => {oks}/8 ok, mean={statistics.mean(dts):.1f}s")
