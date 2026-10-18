#!/usr/bin/env python3
"""Generate COMPLETE LaTeX table environments (float body) from analysis results.
Each file contains \\begin{tabular*}...\\end{tabular*} so the main tex only does \\input.
Usage: python3 gen_tables.py"""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import json, os

R = json.load(open(ROOT + "/results/analysis/results.json"))
OUT = ROOT + "/paper/tables"
os.makedirs(OUT, exist_ok=True)

LABEL = {"qwen3.8-max": "Qwen3.8-Max", "qwen3.8-omni": "Qwen3.8-Omni", "agnes-3.0-flash": "Agnes3.0-Flash",
         "agnes-2.5-flash": "Agnes2.5-Flash", "gpt-6-luna": "GPT-6-Luna", "gemini-3.8-flash": "Gemini3.8-Flash"}
FAM = {"qwen3.8-max": "Qwen", "qwen3.8-omni": "Qwen", "agnes-3.0-flash": "Agnes",
       "agnes-2.5-flash": "Agnes", "gpt-6-luna": "GPT", "gemini-3.8-flash": "Gemini"}
TIER = {"qwen3.8-max": "flagship", "qwen3.8-omni": "multimodal", "agnes-3.0-flash": "fast",
        "agnes-2.5-flash": "reasoning", "gpt-6-luna": "reasoning", "gemini-3.8-flash": "fast"}
ORDER = [m for m in ["qwen3.8-max", "qwen3.8-omni", "agnes-3.0-flash", "agnes-2.5-flash",
                     "gpt-6-luna", "gemini-3.8-flash"] if m in R["models"]]
MODELS = ORDER
DS_ORDER = ["gsm8k", "sat_math", "piqa", "truthfulqa", "lsat_lr", "logiqa"]
DS_LABEL = {"gsm8k": "GSM8K", "logiqa": "LogiQA", "lsat_lr": "LSAT-LR", "sat_math": "SAT-Math",
            "piqa": "PIQA", "truthfulqa": "TruthfulQA"}

def pct(x, d=1):
    return f"{100*x:.{d}f}" if x is not None else "--"

def env(spec, header, rows):
    return ("\\begin{tabular*}{\\columnwidth}{@{\\extracolsep{\\fill}} " + spec + "}\n"
            "\\toprule\n" + header + " \\\\\n\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular*}")

# ---------- Table: models ----------
rows = []
for m in MODELS:
    p2 = f"{ROOT}/results/{m}.jsonl"
    recs = [json.loads(l) for l in open(p2)]
    ok = [r for r in recs if not r.get("FAILED")]
    parse_rate = 100 * len([r for r in ok if r["answer"] is not None]) / max(1, len(ok))
    d = R["models"][m]
    rows.append(f"{LABEL[m]} & {FAM[m]} & {TIER[m]} & {parse_rate:.1f}\\% & {d['n']} \\\\")
open(f"{OUT}/tab_models.tex", "w").write(
    env("l l l c c", "Model & Family & Tier & Parse rate & $n$", rows))

# ---------- Table: main results ----------
rows = []
for m in MODELS:
    d = R["models"][m]
    a = d["acc"]
    rows.append(f"{LABEL[m]} & {d['n']} & {pct(a['greedy'])} & {pct(a['sc6'])} & {pct(a['pe6'])} & "
                f"{pct(a['hb6'])} & {pct(a['comb12'])} & {pct(d['fragile_rate'])} & {pct(d['degenerate_rate'])} \\\\")
open(f"{OUT}/tab_main.tex", "w").write("\\footnotesize\n" + env("l c c c c c c c c", "Model & $n$ & Greedy & SC-6 & PE-6 & HB-6 & COMB-12 & Fragile & Degen.", rows))

# ---------- Table: regime ----------
rows = []
for m in MODELS:
    d = R["models"][m]
    by_ds = sorted(d["by_ds"].items(), key=lambda kv: DS_ORDER.index(kv[0]))
    for i, (ds, dd) in enumerate(by_ds):
        gain = dd["comb12"] - dd["greedy"]
        ml = "\\midrule\n" if (i == 0 and rows) else ""
        rows.append(ml + f"{LABEL[m]} & {DS_LABEL[ds]} & {dd['n']} & {pct(dd['greedy'])} & {pct(dd['comb12'])} & "
                     f"{gain*100:+.1f} & {pct(dd['entropy'])} & {pct(dd['degenerate'])} \\\\")
open(f"{OUT}/tab_regime.tex", "w").write("\\footnotesize\n" + env("l l c c c c c c", "Model & Dataset & $n$ & Greedy & COMB & $\\Delta$ & Entropy & Degen.", rows))

# ---------- Table: uncertainty ----------
rows = []
for m in MODELS:
    d = R["models"][m]
    def f3(x):
        return f"{x:.3f}" if x is not None else "--"
    rows.append(f"{LABEL[m]} & {pct(d.get('err_rate'))} & {f3(d.get('auroc_cs'))} & {f3(d.get('auroc_cp'))} & "
                f"{f3(d.get('auroc_both'))} & {f3(d.get('aurc_cs'))} & {f3(d.get('aurc_cp'))} & {f3(d.get('aurc_both'))} \\\\")
uncert_body = ("\\begin{tabular*}{\\columnwidth}{@{\\extracolsep{\\fill}} l c c c c c c c}\n"
    "\\toprule\n & & \\multicolumn{3}{c}{AUROC} & \\multicolumn{3}{c}{AURC} \\\\\n"
    "\\cmidrule(lr){3-5}\\cmidrule(lr){6-8}\n"
    "Model & Err. & $c_S$ & $c_P$ & Both & $c_S$ & $c_P$ & Both \\\\\n"
    "\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular*}")
open(f"{OUT}/tab_uncert_full.tex", "w").write(uncert_body)

# ---------- Table: paired tests ----------
rows = []
for m in MODELS:
    d = R["models"][m]
    t = d["sc_vs_pe"]
    p = t["p"]
    pstr = f"{p:.3f}" if p >= 0.001 else "<0.001"
    ci = t["ci"]
    rows.append(f"{LABEL[m]} & {d['n']} & {t['b']} & {t['c']} & {pstr} & {100*t['diff']:+.1f} & "
                f"[{100*ci[0]:+.1f}, {100*ci[1]:+.1f}] \\\\")
open(f"{OUT}/tab_tests.tex", "w").write(
    env("l c c c c c c", "Model & $n$ & $b$ & $c$ & $p$ & Diff. & 95\\% CI", rows))

# ---------- Numbers dict ----------
N = {}
for m in MODELS:
    d = R["models"][m]
    N[m] = {"n": d["n"], "greedy": d["acc"]["greedy"], "sc6": d["acc"]["sc6"], "pe6": d["acc"]["pe6"],
            "hb6": d["acc"]["hb6"], "comb12": d["acc"]["comb12"],
            "sc_vs_greedy_p": d["sc_vs_greedy"]["p"], "pe_vs_greedy_p": d["pe_vs_greedy"]["p"],
            "frag": d["fragile_rate"], "degen": d["degenerate_rate"], "ent": d["mean_entropy"]}
json.dump(N, open(f"{OUT}/numbers.json", "w"), indent=1)
print("Tables written (full environments):", sorted(os.listdir(OUT)))
