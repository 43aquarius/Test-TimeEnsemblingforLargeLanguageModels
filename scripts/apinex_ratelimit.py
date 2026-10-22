#!/usr/bin/env python3
"""Probe apinex rate limit: full 429 body + headers, then paced tests."""
import urllib.request, json, time

BASE = "https://api.apinex.bond/v1"
KEY = "sk-apxe8e3bc610bd556066ca665074a4ba0c722a9cce84fbe1cf"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

def chat(model, max_tokens=300):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": "Reply OK"}],
                       "temperature": 0.7, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(f"{BASE}/chat/completions", data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                 "User-Agent": UA, "Accept": "application/json"})
    t0 = time.time()
    try:
        r = urllib.request.urlopen(req, timeout=120)
        r.read()
        return {"ok": True, "dt": time.time() - t0}
    except urllib.error.HTTPError as e:
        body_txt = ""
        try: body_txt = e.read().decode()
        except: pass
        hdrs = {k: v for k, v in e.headers.items() if any(s in k.lower() for s in ("rate", "retry", "limit", "remaining"))}
        return {"ok": False, "code": e.code, "body": body_txt[:400], "hdrs": hdrs, "dt": time.time() - t0}
    except Exception as e:
        return {"ok": False, "code": -1, "body": f"{type(e).__name__}: {str(e)[:150]}", "hdrs": {}, "dt": time.time() - t0}

print("=== 1) get full 429 body ===")
time.sleep(20)
for i in range(6):
    r = chat("free/deepseek-v4-flash-0731")
    if not r["ok"]:
        print(f"code={r['code']}\nbody={r['body']}\nheaders={r['hdrs']}")
        break
    print(f"#{i+1} ok {r['dt']:.1f}s")

print("\n=== 2) paced test: 1 call / 12s x 10 (after 60s cooldown) ===")
time.sleep(60)
okc, tot = 0, 10
for i in range(tot):
    r = chat("free/deepseek-v4-flash-0731")
    okc += r["ok"]
    print(f"  #{i+1} {'ok' if r['ok'] else 'FAIL ' + str(r.get('body'))[:120]} {r['dt']:.1f}s", flush=True)
    if i < tot - 1: time.sleep(12)
print(f"=> {okc}/{tot} ok at 12s spacing")
