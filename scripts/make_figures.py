#!/usr/bin/env python3
"""Generate paper figures from analysis results. Follows chart rules:
no top/right spines, dashed 20% grid or none, no internal titles (LaTeX captions exist),
frameless legends, DejaVu Sans, constrained_layout."""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
for f in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
    try: fm.fontManager.addfont(f)
    except Exception: pass
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.linewidth": 0.6, "axes.edgecolor": "#666666",
    "xtick.color": "#333333", "ytick.color": "#333333",
    "axes.labelcolor": "#111111", "figure.dpi": 200,
})

FIG = ROOT + "/paper/figures"
os.makedirs(FIG, exist_ok=True)
R = json.load(open(ROOT + "/results/analysis/results.json"))

# consistent model order & colors
MODEL_ORDER = [m for m in ["qwen3.8-max", "qwen3.8-omni", "agnes-3.0-flash",
                           "agnes-2.5-flash", "gpt-6-luna", "gemini-3.8-flash"] if m in R["models"]]
LABEL = {"qwen3.8-max": "Qwen3.8-Max", "qwen3.8-omni": "Qwen3.8-Omni", "agnes-3.0-flash": "Agnes3.0-F",
         "agnes-2.5-flash": "Agnes2.5-F", "gpt-6-luna": "GPT-6-Luna", "gemini-3.8-flash": "Gemini3.8-F"}
COLORS = {"qwen3.8-max": "#1f77b4", "qwen3.8-omni": "#4fa3d1", "agnes-3.0-flash": "#2ca02c",
          "agnes-2.5-flash": "#8fbf4d", "gpt-6-luna": "#d62728", "gemini-3.8-flash": "#9467bd"}

def style_ax(ax, grid=True):
    if grid:
        ax.grid(True, linestyle="--", alpha=0.2, linewidth=0.5)
    ax.set_axisbelow(True)

# ---------------- Fig 1: conditions x models (grouped bars) ----------------
def fig_conditions():
    conds = ["greedy", "sc6", "pe6", "hb6", "comb12"]
    cond_labels = ["Greedy", "SC-6", "PE-6", "HB-6", "COMB-12"]
    models = [m for m in MODEL_ORDER if R["models"][m]["n"] >= 20]
    fig, ax = plt.subplots(figsize=(7.0, 3.0), constrained_layout=True)
    n_m = len(models)
    width = 0.16
    shades = ["#c9d6df", "#9fb8c8", "#7497ad", "#4a7591", "#1f4e6e"]
    for i, (cond, lab) in enumerate(zip(conds, cond_labels)):
        xs = [j + (i - 2) * width for j in range(n_m)]
        ys = [100 * R["models"][m]["acc"][cond] for m in models]
        ax.bar(xs, ys, width=width * 0.92, color=shades[i], label=lab, edgecolor="none")
        for x, y in zip(xs, ys):
            ax.text(x, y + 1.0, f"{y:.0f}", ha="center", va="bottom", fontsize=6.2, color="#444444")
    ax.set_xticks(range(n_m))
    ax.set_xticklabels([f"{LABEL[m]}\n(n={R['models'][m]['n']})" for m in models], fontsize=8)
    ax.set_ylabel("Accuracy (%)")
    ax.set_ylim(0, 112)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=5, frameon=False, fontsize=8,
              handlelength=1.2, columnspacing=1.2)
    style_ax(ax, grid=False)
    fig.savefig(f"{FIG}/conditions.pdf")
    plt.close(fig)
    print("fig conditions done")

# ---------------- Fig 2: regime scatter (entropy vs gain) ----------------
def fig_regime():
    fig, ax = plt.subplots(figsize=(4.6, 3.4), constrained_layout=True)
    for m in MODEL_ORDER:
        md = R["models"][m]
        for ds, d in md["by_ds"].items():
            gain = d["comb12"] - d["greedy"]
            x = 100 * d["entropy"]
            y = 100 * gain
            ax.scatter(x, y, s=34, color=COLORS[m], alpha=0.85, edgecolor="white", linewidth=0.5,
                       label=LABEL[m] if ds == sorted(md["by_ds"])[0] else None)
    ax.axhline(0, color="#999999", linewidth=0.7, linestyle="-")
    ax.set_xlabel("Mean normalized answer entropy (%)")
    ax.set_ylabel("COMB-12 accuracy gain over greedy (pp)")
    handles, labels = ax.get_legend_handles_labels()
    seen = {}
    for h, l in zip(handles, labels):
        seen[l] = h
    ax.legend(seen.values(), seen.keys(), loc="lower right", frameon=False, fontsize=7.5,
              handletextpad=0.2, borderaxespad=0.2)
    style_ax(ax)
    fig.savefig(f"{FIG}/regime.pdf")
    plt.close(fig)
    print("fig regime done")

# ---------------- Fig 3: budget curves (small multiples) ----------------
def fig_budget():
    models = [m for m in MODEL_ORDER if R["models"][m]["n"] >= 20]
    n = len(models)
    ncol = 3
    nrow = (n + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(7.0, 2.1 * nrow), constrained_layout=True,
                             sharey=False)
    axes = axes.flatten() if n > 1 else [axes]
    ks = [1, 2, 4, 6]
    for i, m in enumerate(models):
        ax = axes[i]
        md = R["models"][m]
        sc = [100 * md["acc"]["greedy"]] + [100 * md["acc"][f"sc{k}"] for k in (2, 4, 6)]
        pe = [100 * md["acc"]["greedy"]] + [100 * md["acc"][f"pe{k}"] for k in (2, 4, 6)]
        ax.plot(ks, sc, "-o", color="#1f4e6e", linewidth=2.0, markersize=3.5, label="SC-$k$")
        ax.plot(ks, pe, "-s", color="#c25b2e", linewidth=2.0, markersize=3.5, label="PE-$k$")
        ax.set_title(LABEL[m], fontsize=8.5, color="#222222", loc="left", pad=2)
        ax.set_xticks(ks)
        ax.set_xlabel("Budget $k$ (calls)", fontsize=7.5)
        if i % ncol == 0:
            ax.set_ylabel("Accuracy (%)", fontsize=7.5)
        ax.tick_params(labelsize=7)
        if i == 0:
            ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.14), ncol=2, frameon=False, fontsize=7.5)
        style_ax(ax)
    for j in range(n, len(axes)):
        axes[j].set_visible(False)
    fig.savefig(f"{FIG}/budget.pdf")
    plt.close(fig)
    print("fig budget done")

# ---------------- Fig 4: AUROC bars ----------------
def fig_auroc():
    models = [m for m in MODEL_ORDER if R["models"][m].get("auroc_cs") is not None]
    fig, ax = plt.subplots(figsize=(4.8, 3.0), constrained_layout=True)
    xs = range(len(models))
    w = 0.26
    cs = [R["models"][m]["auroc_cs"] for m in models]
    cp = [R["models"][m]["auroc_cp"] for m in models]
    both = [R["models"][m].get("auroc_both") for m in models]
    ax.bar([x - w for x in xs], cs, width=w * 0.9, color="#1f4e6e", label="Sample agr. $c_S$")
    ax.bar(list(xs), cp, width=w * 0.9, color="#c25b2e", label="Paraphrase agr. $c_P$")
    if all(v is not None for v in both):
        ax.bar([x + w for x in xs], both, width=w * 0.9, color="#7aa63a", label="Combined")
    ax.axhline(0.5, color="#999999", linewidth=0.8, linestyle="--")
    ax.text(len(models) - 0.4, 0.505, "chance", fontsize=7, color="#777777", ha="right")
    ax.set_xticks(list(xs))
    ax.set_xticklabels([LABEL[m] for m in models], fontsize=7.5, rotation=20, ha="right")
    ax.set_ylabel("AUROC (error detection)")
    ax.set_ylim(0.3, 1.02)
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.02), ncol=3, frameon=False, fontsize=7.5)
    style_ax(ax)
    fig.savefig(f"{FIG}/auroc.pdf")
    plt.close(fig)
    print("fig auroc done")

if __name__ == "__main__":
    fig_conditions()
    fig_regime()
    fig_budget()
    fig_auroc()
