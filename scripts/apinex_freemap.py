#!/usr/bin/env python3
"""Map which free/* models still work vs subscription-gated (3 tries each)."""
import urllib.request, json, time

KEY = "sk-apxe8e3bc610bd556066ca665074a4ba0c722a9cce84fbe1cf"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

def chat(model):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": "Say OK only."}],
                       "max_tokens": 10}).encode()
    req = urllib.request.Request("https://api.apinex.bond/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json", "User-Agent": UA})
    try:
        r = urllib.request.urlopen(req, timeout=45)
        d = json.loads(r.read())
        return "OK: " + (d["choices"][0]["message"]["content"] or "").strip()[:20]
    except urllib.error.HTTPError as e:
        try: b = e.read().decode()
        except: b = ""
        if "subscription" in b: return "GATED(subscription)"
        if "Insufficient balance" in b: return "PAID(balance)"
        if "Daily check-in" in b: return "NEED_CHECKIN"
        return f"HTTP{e.code}:{b[:60]}"
    except Exception as e:
        return f"{type(e).__name__}"

models = [
    "free/deepseek-v4-flash-0731", "free/deepseek-v4-pro-0813", "free/deepseek-v4.1-flash",
    "free/qwen-3.8-max", "free/kimi-k3", "free/kimi-k2.8",
    "free/glm-5.3-flash", "free/glm-5.3", "free/glm-5.3-flashx",
    "free/gemini-3.8-flash", "free/gemini-3.1-pro",
    "free/gpt-6-luna", "free/hy4", "free/jev-1.13",
    "free/mimo-v2.6-flash", "free/minimax-m3.1-flash", "free/muse-spark-1.3",
    "free/claude-sonnet-4.6",
]
verdicts = {}
for m in models:
    results = []
    for attempt in range(3):
        v = chat(m)
        results.append(v)
        if v.startswith("OK"):
            break
        time.sleep(4)
    verdicts[m] = results[-1]
    print(f"{m:32s} -> {results[-1]}")
    time.sleep(2)

print("\n=== SUMMARY ===")
ok_list = [m for m, v in verdicts.items() if v.startswith("OK")]
print(f"still free & working: {ok_list}")
print(f"gated: {[m for m,v in verdicts.items() if 'GATED' in v]}")
