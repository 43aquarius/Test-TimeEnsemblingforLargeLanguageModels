#!/usr/bin/env python3
"""Generate LaTeX tables (v2) from analysis results — full tabular* environments.
Adds: S1 baseline column, corrected AURC with CIs and descriptive flags,
TOST results, greedy-paraphrase / MMLU-Pro / CoT condition tables,
budget-efficiency table (early stopping + adaptive allocation).
Usage: python3 gen_tables_v2.py"""

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
ORDER = [m for m in ["qwen3.8-max", "qwen3.8-omni", "agnes-3.0-flash",
                     "agnes-2.5-flash", "gpt-6-luna", "gemini-3.8-flash"] if m in R["models"]]
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

# ---------- Table: main results (adds S1 single-sample baseline) ----------
rows = []
for m in MODELS:
    d = R["models"][m]
    a = d["acc"]
    rows.append(f"{LABEL[m]} & {d['n']} & {pct(a['greedy'])} & {pct(a['k1'])} & {pct(a['sc6'])} & "
                f"{pct(a['pe6'])} & {pct(a['hb6'])} & {pct(a['comb12'])} & {pct(d['fragile_rate'])} & {pct(d['degenerate_rate'])} \\\\")
open(f"{OUT}/tab_main.tex", "w").write("\\scriptsize\n" + env(
    "l c c c c c c c c c",
    "Model & $n$ & Greedy & S1 & SC-6 & PE-6 & HB-6 & COMB-12 & Fragile & Degen.", rows))

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
open(f"{OUT}/tab_regime.tex", "w").write("\\footnotesize\n" + env(
    "l l c c c c c c", "Model & Dataset & $n$ & Greedy & COMB & $\\Delta$ & Entropy & Degen.", rows))

# ---------- Table: uncertainty (corrected AURC, CIs, descriptive flags) ----------
rows = []
for m in MODELS:
    d = R["models"][m]
    dag = "" if not d.get("descriptive_only") else r"$^\dagger$"
    rows.append(f"{LABEL[m]}{dag} & {pct(d.get('err_rate'))} & {f3(d.get('auroc_cs'))} & {f3(d.get('auroc_cp'))} & "
                f"{f3(d.get('auroc_both'))} & {f3(d.get('aurc_cs'))} & {f3(d.get('aurc_cp'))} & {f3(d.get('aurc_both'))} \\\\")
uncert_body = ("\\footnotesize\n\\begin{tabular*}{\\columnwidth}{@{\\extracolsep{\\fill}} l c c c c c c c}\n"
    "\\toprule\n & & \\multicolumn{3}{c}{AUROC} & \\multicolumn{3}{c}{AURC} \\\\\n"
    "\\cmidrule(lr){3-5}\\cmidrule(lr){6-8}\n"
    "Model & Err. & $c_S$ & $c_P$ & Both & $c_S$ & $c_P$ & Both \\\\\n"
    "\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular*}")
open(f"{OUT}/tab_uncert_full.tex", "w").write(uncert_body)

# ---------- Table: paired tests + TOST ----------
rows = []
COMPS = [("sc_vs_greedy", "SC-6 $-$ Greedy"), ("pe_vs_greedy", "PE-6 $-$ Greedy"),
         ("sc_vs_pe", "SC-6 $-$ PE-6"), ("hb_vs_greedy", "HB-6 $-$ Greedy")]
for m in MODELS:
    d = R["models"][m]
    first = True
    for key, name in COMPS:
        t = d[key]
        p = t["p"]
        pstr = f"{p:.3f}" if p >= 0.001 else "<0.001"
        ci = t["ci"]
        tost = t["tost_3pp"]
        teq = "yes" if tost["equivalent"] else "no"
        label = LABEL[m] if first else ""
        nstr = d["n"] if first else ""
        first = False
        rows.append(f"{label} & {nstr} & {name} & {t['b']} & {t['c']} & {pstr} & "
                    f"{100*t['diff']:+.1f} & [{100*ci[0]:.1f},{100*ci[1]:.1f}] & {teq} \\\\")
    rows.append("\\addlinespace")
rows = rows[:-1]
open(f"{OUT}/tab_tests.tex", "w").write("\\scriptsize\n" + env(
    "l c l c c c c c c",
    "Model & $n$ & Comparison & $b$ & $c$ & McNemar $p$ & Diff. & 95\\% CI & TOST $\\pm$3", rows))

# ---------- Table: greedy-paraphrase condition ----------
gp = R["conditions"]["greedypara"]
rows = []
for m in MODELS:
    if m not in gp:
        rows.append(f"{LABEL[m]} & -- & \\multicolumn{{6}}{{c}}{{quota exhausted before the control could be run}} \\\\")
        continue
    d = gp[m]
    a = d["acc"]
    rows.append(f"{LABEL[m]} & {d['n']} & {pct(a['greedy_ok'])} & {pct(a['sc6_ok'])} & {pct(a['pe6_ok'])} & "
                f"{pct(a['peg6_ok'])} & {pct(d['fragile_greedy_rate'])} & {pct(d['degenerate_pg_rate'])} \\\\")
open(f"{OUT}/tab_greedypara.tex", "w").write("\\footnotesize\n" + env(
    "l c c c c c c c",
    "Model & $n$ & Greedy & SC-6 & PE-6 & PE$^{g}$-6 & Frag.$^{g}$ & Degen.$^{g}$", rows))

# ---------- Table: MMLU-Pro probe ----------
mp = R["conditions"]["mmlupro"]
rows = []
for m in MODELS:
    if m not in mp:
        continue
    d = mp[m]
    a = d["acc"]
    main_ent = R["models"][m]["mean_entropy"]
    rows.append(f"{LABEL[m]} & {d['n']} & {pct(a['greedy_ok'])} & {pct(a['k1_acc'])} & {pct(a['sc6_ok'])} & "
                f"{f3(d['mean_entropy'])} & {pct(d['degenerate_rate'])} & {f3(main_ent)} \\\\")
open(f"{OUT}/tab_mmlupro.tex", "w").write("\\footnotesize\n" + env(
    "l c c c c c c c",
    "Model & $n$ & Greedy & S1 & SC-6 & Entropy & Degen. & Suite entropy", rows))

# ---------- Table: CoT condition ----------
cot = R["conditions"]["cot"]
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

# ---------- Table: budget efficiency (early stopping + adaptive) ----------
rows = []
for m in MODELS:
    d = R["models"][m]
    a = d["acc"]
    es = d["early_stop_unanimous"]
    ad = d["adaptive_alloc"]
    fs = d["early_stop_fixed6"]
    rows.append(f"{LABEL[m]} & {pct(a['greedy'])} & {pct(a['k1'])} & {pct(a['sc6'])} & "
                f"{pct(es['acc'])} & {es['mean_budget']:.1f} & {pct(ad['acc'])} & {ad['mean_budget']:.1f} & {pct(a['comb12'])} \\\\")
open(f"{OUT}/tab_efficiency.tex", "w").write("\\footnotesize\n" + env(
    "l c c c c c c c c",
    "Model & Greedy & S1 & SC-6 & ES acc & ES $\\bar{k}$ & Ada acc & Ada $\\bar{k}$ & COMB-12", rows))

# ---------- Numbers dict ----------
N = {}
for m in MODELS:
    d = R["models"][m]
    N[m] = {"n": d["n"], "greedy": d["acc"]["greedy"], "k1": d["acc"]["k1"], "sc6": d["acc"]["sc6"],
            "pe6": d["acc"]["pe6"], "hb6": d["acc"]["hb6"], "comb12": d["acc"]["comb12"],
            "sc_vs_greedy_p": d["sc_vs_greedy"]["p"], "pe_vs_greedy_p": d["pe_vs_greedy"]["p"],
            "sc_vs_greedy_ci": d["sc_vs_greedy"]["ci"], "pe_vs_greedy_ci": d["pe_vs_greedy"]["ci"],
            "sc_vs_pe": d["sc_vs_pe"]["diff"], "sc_vs_pe_ci": d["sc_vs_pe"]["ci"],
            "sc_vs_pe_tost3": d["sc_vs_pe"]["tost_3pp"],
            "frag": d["fragile_rate"], "degen": d["degenerate_rate"], "ent": d["mean_entropy"],
            "overlap": d.get("overlap"), "auroc_cs": d.get("auroc_cs"), "auroc_cp": d.get("auroc_cp"),
            "aurc_cs": d.get("aurc_cs"), "aurc_cp": d.get("aurc_cp"), "n_errors": d.get("n_errors"),
            "descriptive": d.get("descriptive_only"),
            "early_stop": d["early_stop_unanimous"], "adaptive": d["adaptive_alloc"],
            "by_locus": d.get("by_locus"), "tokens": d.get("tokens")}
    if m in gp:
        N[m]["greedypara"] = {"n": gp[m]["n"], "acc": gp[m]["acc"],
                              "frag_greedy": gp[m]["fragile_greedy_rate"],
                              "degen_pg": gp[m]["degenerate_pg_rate"]}
    if m in mp:
        N[m]["mmlupro"] = {"n": mp[m]["n"], "acc": mp[m]["acc"],
                           "entropy": mp[m]["mean_entropy"], "degen": mp[m]["degenerate_rate"]}
    if m in cot:
        N[m]["cot"] = {k: cot[m][k] for k in ("n", "n_stem", "greedy", "sc6", "pe6",
                                              "direct_greedy", "direct_sc6", "direct_pe6",
                                              "mean_entropy", "mean_direct_entropy", "degenerate_rate")
                       if k in cot[m]}
N["_pooled"] = R["pooled"]
N["_sensitivity"] = R.get("sensitivity", {})
json.dump(N, open(f"{OUT}/numbers.json", "w"), indent=1)
print("Tables written:", sorted(os.listdir(OUT)))
