#!/usr/bin/env python3
"""Probe apinex: 6s pacing, per-model limit isolation, 429 cooldown."""
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
        r = urllib.request.urlopen(req, timeout=90)
        r.read()
        return {"ok": True, "dt": time.time() - t0}
    except urllib.error.HTTPError as e:
        b = ""
        try: b = e.read().decode()
        except: pass
        return {"ok": False, "code": e.code, "body": b[:250], "dt": time.time() - t0}
    except Exception as e:
        return {"ok": False, "code": -1, "body": f"{type(e).__name__}", "dt": time.time() - t0}

A = "free/deepseek-v4-flash-0731"
B = "free/deepseek-v4.1-flash"

print("=== 1) 6s spacing x 12 on A (after 60s cool) ===", flush=True)
time.sleep(60)
okc = 0
for i in range(12):
    r = chat(A)
    okc += r["ok"]
    if not r["ok"]: print(f"  #{i+1} FAIL code={r['code']} {r['body'][:150]}", flush=True)
    if i < 11: time.sleep(6)
print(f"=> {okc}/12 ok at 6s spacing", flush=True)

print("\n=== 2) exhaust A then immediately try B (limit isolation?) ===", flush=True)
time.sleep(45)
n429 = 0
for i in range(12):
    r = chat(A)
    if not r["ok"]:
        n429 += 1
        if n429 == 1:
            print(f"  A first-fail at #{i+1}: code={r['code']} body={r['body'][:200]}", flush=True)
            rb = chat(B)
            print(f"  -> B right after A 429: {'OK' if rb['ok'] else 'FAIL ' + str(rb.get('body'))[:150]}", flush=True)
    if i < 11: time.sleep(1.5)
print(f"  A rapid: {12-n429}/12 ok", flush=True)

print("\n=== 3) 429 cooldown: retry every 20s until ok ===", flush=True)
t0 = time.time()
for attempt in range(10):
    r = chat(A)
    el = time.time() - t0
    if r["ok"]:
        print(f"  recovered after {el:.0f}s (attempt {attempt+1})", flush=True)
        break
    print(f"  attempt {attempt+1} @ {el:.0f}s: code={r['code']} {r['body'][:100]}", flush=True)
    time.sleep(20)
