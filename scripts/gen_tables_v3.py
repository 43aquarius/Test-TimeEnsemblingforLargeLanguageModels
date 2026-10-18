#!/usr/bin/env python3
"""Generate LaTeX tables (v3) — S1 (single-sample expected accuracy) as the
primary k=1 baseline, tie-randomized AURC, mode-share regime columns,
SC/PE-vs-S1 gain columns, greedy-paraphrase answer-identity column,
adaptive-rule budget percentage.  Conditions (greedypara/mmlupro/cot) and
sensitivity data are unchanged and re-read from the v2 results file.

Usage: python3 gen_tables_v3.py"""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import json, os

R2 = json.load(open(ROOT + "/results/analysis/results.json"))       # conditions/sensitivity
R3 = json.load(open(ROOT + "/results/analysis/results_v3.json"))    # core v3 numbers
OUT = ROOT + "/paper/tables"
os.makedirs(OUT, exist_ok=True)

LABEL = {"qwen3.8-max": "Qwen3.8-Max", "qwen3.8-omni": "Qwen3.8-Omni", "agnes-3.0-flash": "Agnes3.0-Flash",
         "agnes-2.5-flash": "Agnes2.5-Flash", "gpt-6-luna": "GPT-6-Luna", "gemini-3.8-flash": "Gemini3.8-Flash"}
FAM = {"qwen3.8-max": "Qwen", "qwen3.8-omni": "Qwen", "agnes-3.0-flash": "Agnes",
       "agnes-2.5-flash": "Agnes", "gpt-6-luna": "GPT", "gemini-3.8-flash": "Gemini"}
TIER = {"qwen3.8-max": "flagship", "qwen3.8-omni": "multimodal", "agnes-3.0-flash": "fast",
        "agnes-2.5-flash": "reasoning", "gpt-6-luna": "reasoning", "gemini-3.8-flash": "fast"}
ORDER = [m for m in ["qwen3.8-max", "qwen3.8-omni", "agnes-3.0-flash",
                     "agnes-2.5-flash", "gpt-6-luna", "gemini-3.8-flash"] if m in R3["models"]]
MODELS = ORDER
DS_ORDER = ["gsm8k", "sat_math", "piqa", "truthfulqa", "lsat_lr", "logiqa"]
DS_LABEL = {"gsm8k": "GSM8K", "logiqa": "LogiQA", "lsat_lr": "LSAT-LR", "sat_math": "SAT-Math",
            "piqa": "PIQA", "truthfulqa": "TruthfulQA"}

def pct(x, d=1):
    return f"{100*x:.{d}f}" if x is not None else "--"

def f3(x):
    return f"{x:.3f}" if x is not None else "--"

def env(spec, header, rows):
    return ("\\begin{tabular*}{\\columnwidth}{@{\\extracolsep{\\fill}} " + spec + "}\n"
            "\\toprule\n" + header + " \\\\\n\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular*}")

# ---------- Table: models (unchanged data) ----------
rows = []
for m in MODELS:
    p2 = f"{ROOT}/results/{m}.jsonl"
    recs = [json.loads(l) for l in open(p2)]
    ok = [r for r in recs if not r.get("FAILED")]
    parse_rate = 100 * len([r for r in ok if r["answer"] is not None]) / max(1, len(ok))
    d = R3["models"][m]
    rows.append(f"{LABEL[m]} & {FAM[m]} & {TIER[m]} & {parse_rate:.1f}\\% & {d['n']} \\\\")
open(f"{OUT}/tab_models.tex", "w").write(
    env("l l l c c", "Model & Family & Tier & Parse rate & $n$", rows))

# ---------- Table: main results — S1 primary baseline + gains vs S1 ----------
rows = []
for m in MODELS:
    d = R3["models"][m]
    a = d["acc"]
    rows.append(f"{LABEL[m]} & {d['n']} & {pct(a['greedy_ok'])} & {pct(a['k1_acc'])} & {pct(a['sc6_ok'])} & "
                f"{pct(a['pe6_ok'])} & {pct(a['hb6_ok'])} & {pct(a['comb12_ok'])} & "
                f"{100*d['gain_vs_s1_sc6']:+.1f} & {100*d['gain_vs_s1_pe6']:+.1f} \\\\")
open(f"{OUT}/tab_main.tex", "w").write("\\scriptsize\n" + env(
    "l c c c c c c c c c",
    "Model & $n$ & Greedy & S1 & SC-6 & PE-6 & HB-6 & COMB-12 & $\\Delta$SC & $\\Delta$PE", rows))

# ---------- Table: regime — mode share replaces entropy, gains vs S1 ----------
rows = []
for m in MODELS:
    d = R3["models"][m]
    by_ds = sorted(d["by_ds"].items(), key=lambda kv: DS_ORDER.index(kv[0]))
    for i, (ds, dd) in enumerate(by_ds):
        gain = dd["comb12"] - dd["k1"]
        ml = "\\midrule\n" if (i == 0 and rows) else ""
        rows.append(ml + f"{LABEL[m]} & {DS_LABEL[ds]} & {dd['n']} & {pct(dd['greedy'])} & {pct(dd['k1'])} & "
                     f"{pct(dd['comb12'])} & {gain*100:+.1f} & {pct(dd['mode_share'])} & {pct(100*(1-dd['mode_share']),0)} \\\\")
open(f"{OUT}/tab_regime.tex", "w").write("\\scriptsize\n" + env(
    "l l c c c c c c c", "Model & Dataset & $n$ & Greedy & S1 & COMB & $\\Delta_C$ & Share & Diss.\\%", rows))

# ---------- Table: uncertainty — tie-randomized AURC + random baseline ----------
rows = []
for m in MODELS:
    d = R3["models"][m]
    dag = "" if not d.get("descriptive_only") else r"$^\dagger$"
    both_auroc = R2["models"][m].get("auroc_both")
    rows.append(f"{LABEL[m]}{dag} & {pct(d.get('err_rate'))} & {f3(d.get('auroc_cs'))} & {f3(d.get('auroc_cp'))} & "
                f"{f3(both_auroc)} & {f3(d.get('aurc_cs'))} & {f3(d.get('aurc_cp'))} \\\\")
uncert_body = ("\\footnotesize\n\\begin{tabular*}{\\columnwidth}{@{\\extracolsep{\\fill}} l c c c c c c}\n"
    "\\toprule\n & & \\multicolumn{3}{c}{AUROC} & \\multicolumn{2}{c}{AURC$^{\\ddagger}$} \\\\\n"
    "\\cmidrule(lr){3-5}\\cmidrule(lr){6-7}\n"
    "Model & Err. & $c_S$ & $c_P$ & Both & $c_S$ & $c_P$ \\\\\n"
    "\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular*}")
open(f"{OUT}/tab_uncert_full.tex", "w").write(uncert_body)

# ---------- Table: paired tests — gains vs S1 (bootstrap) + SC vs PE (McNemar/TOST) ----------
rows = []
for m in MODELS:
    d = R3["models"][m]
    n = d["n"]
    first = [True]
    def lab():
        if first[0]:
            first[0] = False
            return LABEL[m], str(n)
        return "", ""
    # SC-6 - S1
    l, ns = lab()
    ci = d["ci_sc6_minus_s1"]
    rows.append(f"{l} & {ns} & SC-6 $-$ S1 & -- & -- & -- & {100*d['gain_vs_s1_sc6']:+.1f} & "
                f"[{100*ci[0]:.1f},{100*ci[1]:.1f}] & -- \\\\")
    # PE-6 - S1
    l, ns = lab()
    ci = d["ci_pe6_minus_s1"]
    rows.append(f"{l} & {ns} & PE-6 $-$ S1 & -- & -- & -- & {100*d['gain_vs_s1_pe6']:+.1f} & "
                f"[{100*ci[0]:.1f},{100*ci[1]:.1f}] & -- \\\\")
    # SC-6 - greedy (reference: biased baseline)
    t = R2["models"][m]["sc_vs_greedy"]
    l, ns = lab()
    p = t["p"]
    pstr = f"{p:.3f}" if p >= 0.001 else "<0.001"
    ci = t["ci"]
    rows.append(f"{l} & {ns} & SC-6 $-$ Greedy & {t['b']} & {t['c']} & {pstr} & {100*t['diff']:+.1f} & "
                f"[{100*ci[0]:.1f},{100*ci[1]:.1f}] & -- \\\\")
    # SC-6 - PE-6 with TOST
    t = R2["models"][m]["sc_vs_pe"]
    l, ns = lab()
    p = t["p"]
    pstr = f"{p:.3f}" if p >= 0.001 else "<0.001"
    ci = t["ci"]
    tost = t["tost_3pp"]
    teq = "yes" if tost["equivalent"] else "no"
    rows.append(f"{l} & {ns} & SC-6 $-$ PE-6 & {t['b']} & {t['c']} & {pstr} & {100*t['diff']:+.1f} & "
                f"[{100*ci[0]:.1f},{100*ci[1]:.1f}] & {teq} \\\\")
    rows.append("\\addlinespace")
rows = rows[:-1]
open(f"{OUT}/tab_tests.tex", "w").write("\\scriptsize\n" + env(
    "l c l c c c c c c",
    "Model & $n$ & Comparison & $b$ & $c$ & McNemar $p$ & Diff. & 95\\% CI & TOST $\\pm$3", rows))

# ---------- Table: greedy-paraphrase condition + answer identity ----------
gp = R2["conditions"]["greedypara"]
ident = R3.get("greedypara_identity", {})
rows = []
for m in MODELS:
    if m not in gp:
        rows.append(f"{LABEL[m]} & -- & \\multicolumn{{7}}{{c}}{{quota exhausted before the control could be run}} \\\\")
        continue
    d = gp[m]
    a = d["acc"]
    idn = ident.get(m, {})
    idstr = f"{idn.get('answer_identicate', idn.get('answer_identical','--'))}/{idn.get('n','--')}" if idn else "--"
    rows.append(f"{LABEL[m]} & {d['n']} & {pct(a['greedy_ok'])} & {pct(a['sc6_ok'])} & {pct(a['pe6_ok'])} & "
                f"{pct(a['peg6_ok'])} & {idstr} & {pct(d['fragile_greedy_rate'])} & {pct(d['degenerate_pg_rate'])} \\\\")
open(f"{OUT}/tab_greedypara.tex", "w").write("\\footnotesize\n" + env(
    "l c c c c c c c c",
    "Model & $n$ & Greedy & SC-6 & PE-6 & PE$^{g}$-6 & Ident. & Frag.$^{g}$ & Degen.$^{g}$", rows))

# ---------- Table: MMLU-Pro probe (data unchanged; S1 column relabeled) ----------
mp = R2["conditions"]["mmlupro"]
rows = []
for m in MODELS:
    if m not in mp:
        continue
    d = mp[m]
    a = d["acc"]
    main_ent = R2["models"][m]["mean_entropy"]
    rows.append(f"{LABEL[m]} & {d['n']} & {pct(a['greedy_ok'])} & {pct(a['k1_acc'])} & {pct(a['sc6_ok'])} & "
                f"{f3(d['mean_entropy'])} & {pct(d['degenerate_rate'])} & {f3(main_ent)} \\\\")
open(f"{OUT}/tab_mmlupro.tex", "w").write("\\footnotesize\n" + env(
    "l c c c c c c c",
    "Model & $n$ & Greedy & S1 & SC-6 & Entropy & Degen. & Suite entropy", rows))

# ---------- Table: CoT condition (unchanged) ----------
cot = R2["conditions"]["cot"]
rows = []
for m in MODELS:
    if m not in cot:
        continue
    d = cot[m]
    pe_cot = pct(d.get("pe6")) if d.get("pe6") is not None else "--"
    pe_dir = pct(d.get("direct_pe6")) if d.get("direct_pe6") is not None else "--"
    rows.append(f"{LABEL[m]} & {d['n']} & {pct(d['greedy'])} & {pct(d['sc6'])} & {pe_cot} & "
                f"{pct(d['direct_greedy'])} & {pct(d['direct_sc6'])} & {pe_dir} & "
                f"{f3(d['mean_entropy'])} & {f3(d['mean_direct_entropy'])} \\\\")
open(f"{OUT}/tab_cot.tex", "w").write("\\scriptsize\n" + env(
    "l c c c c c c c c c",
    "Model & $n$ & Grd & SC-6 & PE-6 & Grd$_{dir}$ & SC$_{dir}$ & PE$_{dir}$ & H & H$_{dir}$", rows))

# ---------- Table: budget efficiency + budget share ----------
rows = []
for m in MODELS:
    d = R3["models"][m]
    a = d["acc"]
    es = d["early_stop_unanimous"]
    ad = d["adaptive_alloc"]
    rows.append(f"{LABEL[m]} & {pct(a['k1_acc'])} & {pct(a['sc6_ok'])} & {pct(a['pe6_ok'])} & "
                f"{pct(es['acc'])} & {es['mean_budget']:.1f} & {pct(ad['acc'])} & {ad['mean_budget']:.1f} & "
                f"{100*ad['budget_pct_of_6']:.0f}\\% & {pct(a['comb12_ok'])} \\\\")
open(f"{OUT}/tab_efficiency.tex", "w").write("\\scriptsize\n" + env(
    "l c c c c c c c c c",
    "Model & S1 & SC-6 & PE-6 & ES acc & ES $\\bar{k}$ & Ada acc & Ada $\\bar{k}$ & Budget & COMB-12", rows))

# ---------- refresh numbers.json for any downstream consumer ----------
N = json.load(open(ROOT + "/results/analysis/numbers_v3.json"))
json.dump(N, open(f"{OUT}/numbers.json", "w"), indent=1)
print("v3 tables written:", sorted(os.listdir(OUT)))
