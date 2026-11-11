"""
scripts/make_results_figures.py - paper figures 8-11 from the committed aggregate CSVs of the five-seed report.

    python scripts/make_results_figures.py

Reads  reports/research_validation_20261111/{five_seed_performance,five_seed_ranking,five_seed_calibration,five_seed_error_analysis}.csv
Writes Docs/paper/figures/fig8_performance, fig9_ranking, fig10_calibration, fig11_errors (.png and .pdf)

Only columns that exist in the CSVs are drawn. Seed-level data (needed for a per-seed stability plot) and Precision/Recall@K curves are NOT in the repository,
so no such figure is produced here (the older report figures 05 and 06 are not used in the paper). Nothing is computed beyond what the CSVs hold.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

R = Path(__file__).resolve().parents[1]
SRC = R / "reports" / "research_validation_20261111"
OUT = R / "Docs" / "paper" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
ORDER = ["PrimeKG GCN", "PrimeKG RF", "Structure GCN", "Structure XGBoost"]
LABEL = {"PrimeKG GCN": "PrimeKG\nGCN", "PrimeKG RF": "PrimeKG\nRF+profile", "Structure GCN": "Struct.-cov.\nGCN", "Structure XGBoost": "Struct.-cov.\nXGB+profile"}
COL = {"PrimeKG GCN": "#0072B2", "PrimeKG RF": "#E69F00", "Structure GCN": "#56B4E9", "Structure XGBoost": "#D55E00"}   # Okabe-Ito (colour-blind safe), fixed per model
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.25, "axes.axisbelow": True})


def load(name):
    d = pd.read_csv(SRC / name).set_index("model")
    return d.loc[ORDER]


def save(fig, stem):
    fig.savefig(OUT / f"{stem}.png", dpi=200, bbox_inches="tight")
    fig.savefig(OUT / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)


def label_bars(ax, bars, vals, fmt="{:.3f}", pad=None):
    for i, (b, v) in enumerate(zip(bars, vals)):
        y = b.get_height() + (0 if pad is None else float(pad.iloc[i]))
        ax.text(b.get_x() + b.get_width() / 2, y, fmt.format(v), ha="center", va="bottom", fontsize=7)


# Fig. 8: five-seed ROC-AUC and PR-AUC, mean +- sample SD
d = load("five_seed_performance.csv")
fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9), sharey=True)
for ax, m, s, t in ((axes[0], "roc_auc_mean", "roc_auc_sd", "ROC-AUC"), (axes[1], "pr_auc_mean", "pr_auc_sd", "PR-AUC")):
    b = ax.bar(range(4), d[m], yerr=d[s], capsize=3, color=[COL[k] for k in ORDER], width=0.7, error_kw={"lw": 1})
    label_bars(ax, b, d[m], pad=d[s] + 0.005)
    ax.set_xticks(range(4)); ax.set_xticklabels([LABEL[k] for k in ORDER], fontsize=6.5)
    ax.set_title(t); ax.set_ylim(0, 1.0)
axes[0].set_ylabel("mean over 5 seeds (error bar: sample SD)")
save(fig, "fig8_performance")

# Fig. 9: ranking metrics (five-seed means)
d = load("five_seed_ranking.csv")
cols = [("average_precision", "Average precision"), ("precision_at_10", "Precision@10"), ("precision_at_500", "Precision@500"), ("recall_at_500", "Recall@500"), ("ndcg_at_500", "NDCG@500")]
fig, axes = plt.subplots(1, 5, figsize=(7.4, 2.6), sharey=True)
for ax, (c, t) in zip(axes, cols):
    b = ax.bar(range(4), d[c], color=[COL[k] for k in ORDER], width=0.75)
    label_bars(ax, b, d[c], "{:.2f}")
    ax.set_xticks(range(4)); ax.set_xticklabels(["GCN", "RF", "GCN", "XGB"], fontsize=6.5)
    ax.set_title(t, fontsize=8); ax.set_ylim(0, 1.08)
save(fig, "fig9_ranking")

# Fig. 10: calibration (lower is better), mean +- SD
d = load("five_seed_calibration.csv")
fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.7))
for ax, (m, s, t) in zip(axes, (("brier_mean", "brier_sd", "Brier score"), ("log_loss_mean", "log_loss_sd", "Log loss"), ("ece_mean", "ece_sd", "ECE (10 bins)"))):
    b = ax.bar(range(4), d[m], yerr=d[s], capsize=3, color=[COL[k] for k in ORDER], width=0.7, error_kw={"lw": 1})
    label_bars(ax, b, d[m], "{:.3f}", pad=d[s] + 0.002)
    ax.set_xticks(range(4)); ax.set_xticklabels(["GCN", "RF", "GCN", "XGB"], fontsize=6.5)
    ax.set_title(t + " (lower = better)", fontsize=8)
    ax.set_ylim(0, ax.get_ylim()[1] * 1.1)
save(fig, "fig10_calibration")

# Fig. 11: mean false positives / false negatives per model
d = load("five_seed_error_analysis.csv")
fig, ax = plt.subplots(figsize=(4.2, 3.0))
x = np.arange(4)
fp = ax.bar(x, d["fp_mean"], color=[COL[k] for k in ORDER], width=0.6, label="false positives")
fn = ax.bar(x, d["fn_mean"], bottom=d["fp_mean"], color=[COL[k] for k in ORDER], width=0.6, alpha=0.45, hatch="//", edgecolor="white", label="false negatives (hatched)")
for i, k in enumerate(ORDER):
    ax.text(i, d.loc[k, "errors_mean"], f"{d.loc[k, 'error_rate_mean']*100:.1f}%", ha="center", va="bottom", fontsize=7)
ax.set_xticks(x); ax.set_xticklabels([LABEL[k] for k in ORDER], fontsize=6.5)
ax.set_ylabel("mean errors per seed (test pairs)"); ax.set_ylim(0, 1800)
ax.legend(fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)
save(fig, "fig11_errors")
print("wrote fig8-fig11 (png+pdf) to", OUT)
