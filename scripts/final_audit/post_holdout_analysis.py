"""
scripts/final_audit/post_holdout_analysis.py - descriptive analyses AFTER the one-time holdout evaluation (nothing here selects or tunes anything).

    python scripts/final_audit/post_holdout_analysis.py --bundle outputs/final_audit_20261117/bundles/vdm-1.0.0

Writes reports/final_audit_20261117/analysis/{*.json,*.csv} and reports/final_audit_20261117/figures/*.png:
  calibration and prevalence dependence, popularity / hub concentration of the top of the ranking, performance by drug sparsity and by disease
  training degree, seed stability of the GCN component, high-confidence errors, repeated-drug inflation, and the candidate list for the
  independent-evidence review (top novel pairs for holdout drugs, with graph-evidence explanations).
"""
import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from src.serving.scoring import Scorer, gcn_head_numpy  # noqa: E402

R = REPO / "reports/final_audit_20261117"
AN, FIG = R / "analysis", R / "figures"
BLUE, ORANGE, AQUA, YELLOW, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def style(ax, title, xlabel=None, ylabel=None):
    ax.set_facecolor(SURF)
    ax.set_title(title, loc="left", fontsize=11, color=INK, pad=10)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    if xlabel:
        ax.set_xlabel(xlabel, color=INK2, fontsize=9)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK2, fontsize=9)


def save(fig, name):
    fig.patch.set_facecolor(SURF)
    fig.tight_layout()
    fig.savefig(FIG / name, dpi=160)
    plt.close(fig)


def auc_or_none(y, p):
    return float(roc_auc_score(y, p)) if len(set(y)) == 2 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    a = ap.parse_args()
    AN.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    sc = Scorer(REPO / a.bundle)
    res = json.loads((R / "final_holdout/HOLDOUT_RESULTS.json").read_text())
    pr = pd.read_csv(R / "final_holdout/HOLDOUT_PREDICTIONS.csv", dtype={"drug_id": str, "disease_id": str})
    out = {}

    # ---------------- figure 1: holdout AP / AUC with CIs (hard set) ----------------
    hm = res["sets"]["hard"]["models"]
    names = {list(hm)[0]: "Selected: rank-avg(GCN, GBM)", "gcn_component_per_seed": "GCN L3_combo (5 seeds)", "deg_conn_fp_gbm": "GBM deg+conn+fp",
             "rf_disease_profile": "RF + disease profile (historical recipe)", "fingerprint_gbm": "GBM fingerprint profile", "max_tanimoto": "Max Tanimoto (unsupervised)",
             "connectivity_gbm": "GBM degree+connectivity", "degree_gbm": "GBM degree only", "disease_popularity": "Disease popularity"}
    for metric, key, ci in (("AP", "pr_auc_ap", "ap_ci"), ("ROC-AUC", "roc_auc", "roc_auc_ci")):
        rows = sorted(((names[k], v["mean"][key], v[ci]) for k, v in hm.items()), key=lambda r: r[1])
        fig, ax = plt.subplots(figsize=(7.5, 4.2))
        y = np.arange(len(rows))
        cols = [BLUE if r[0].startswith("Selected") else "#9ec5f4" for r in rows]
        ax.barh(y, [r[1] for r in rows], color=cols, height=0.6)
        ax.errorbar([r[1] for r in rows], y, xerr=[[r[1] - r[2][0] for r in rows], [r[2][1] - r[1] for r in rows]], fmt="none", ecolor=INK2, elinewidth=1, capsize=2)
        for i, r in enumerate(rows):
            ax.text(r[2][1] + 0.01, i, f"{r[1]:.3f}", va="center", fontsize=8, color=INK)
        ax.set_yticks(y, [r[0] for r in rows])
        ax.set_xlim(0, 1.05)
        style(ax, f"Holdout, 361 unseen drugs: {metric} (95% CI)", metric)
        save(fig, f"fig_holdout_{key}.png")

    # ---------------- calibration and prevalence ----------------
    cal = {}
    fig, axes = plt.subplots(1, 2, figsize=(9, 4), sharey=True)
    for ax, st in zip(axes, ("hard", "popmatch")):
        d = pr[pr.set == st]
        ax.plot([0, 1], [0, 1], color=GRID, linewidth=1.5, linestyle="--")
        for col, colr, lab in (("score_gcn", AQUA, "GCN component"), ("score_gbm", ORANGE, "GBM component")):
            b = np.minimum((d[col].values * 10).astype(int), 9)
            xs = [d[col].values[b == k].mean() for k in range(10) if (b == k).sum() >= 20]
            ys = [d.label.values[b == k].mean() for k in range(10) if (b == k).sum() >= 20]
            ax.plot(xs, ys, color=colr, linewidth=2, marker="o", markersize=5, label=lab)
            cal[f"{st}_{col}"] = {"bins_mean_pred": [float(x) for x in xs], "bins_frac_pos": [float(v) for v in ys]}
        style(ax, f"Reliability, {st} negatives", "mean predicted", "observed fraction positive" if st == "hard" else None)
        ax.legend(frameon=False, fontsize=8, loc="upper left")
    save(fig, "fig_calibration_holdout.png")
    # prevalence dependence: what a 1:5-calibrated probability means at realistic prevalence (Bayes odds shift)
    prior_train = 1 / 6
    realistic = 9388 / (7957 * 17080)
    o_train, o_real = prior_train / (1 - prior_train), realistic / (1 - realistic)
    shift = [{"model_prob_at_1to5": p, "implied_prob_at_all_pairs_prevalence": float(1 / (1 + (1 - p) / p * o_train / o_real))} for p in (0.5, 0.9, 0.99)]
    cal["prevalence_note"] = {"training_and_eval_prevalence": prior_train, "all_pairs_indication_prevalence": realistic, "bayes_shift_examples": shift,
                              "interpretation": "component probabilities are calibrated only at the sampled 1:5 prevalence; at the prevalence of indications among all "
                                                "drug-disease pairs a 0.9 becomes a small number. The API therefore serves a ranking score, not a probability."}
    out["calibration"] = cal

    # ---------------- popularity / hub concentration (hard set) ----------------
    d = pr[pr.set == "hard"].copy()
    dis_deg = pd.Series(sc.dis_train_deg, index=sc.disease_ids)
    d["dis_train_deg"] = d.disease_id.map(dis_deg).values
    drug_gene = pd.Series(sc.drug_gene_deg, index=sc.drug_ids)
    d["drug_gene_deg"] = d.drug_id.map(drug_gene).values
    top = d.sort_values("ranking_score", ascending=False).head(500)
    out["top500_concentration"] = {"unique_drugs": int(top.drug_id.nunique()), "unique_diseases": int(top.disease_id.nunique()),
                                   "max_pairs_one_drug": int(top.drug_id.value_counts().max()), "max_pairs_one_disease": int(top.disease_id.value_counts().max()),
                                   "median_dis_train_deg_top500": float(top.dis_train_deg.median()), "median_dis_train_deg_all": float(d.dis_train_deg.median()),
                                   "precision_top500": float(top.label.mean())}
    out["spearman_score_vs_disease_popularity_negatives"] = float(spearmanr(d.ranking_score[d.label == 0], d.dis_train_deg[d.label == 0])[0])
    # ---------------- performance by sparsity ----------------
    buckets = {"drug_gene_targets": ("drug_gene_deg", [(0, 0), (1, 2), (3, 10), (11, 10 ** 9)]), "disease_training_indications": ("dis_train_deg", [(0, 0), (1, 3), (4, 15), (16, 10 ** 9)])}
    strat = []
    for nm, (col, bks) in buckets.items():
        for lo, hi in bks:
            m = (d[col] >= lo) & (d[col] <= hi)
            strat.append({"stratum": nm, "range": f"{lo}-{hi if hi < 10 ** 9 else 'inf'}", "n": int(m.sum()), "pos": int(d.label[m].sum()),
                          "auc_selected": auc_or_none(d.label[m], d.ranking_score[m]), "auc_gcn": auc_or_none(d.label[m], d.score_gcn[m]),
                          "auc_gbm": auc_or_none(d.label[m], d.score_gbm[m])})
    sdf = pd.DataFrame(strat)
    sdf.to_csv(AN / "performance_by_sparsity.csv", index=False)
    out["performance_by_sparsity"] = strat
    fig, ax = plt.subplots(figsize=(8, 3.8))
    sub = sdf[sdf.stratum == "drug_gene_targets"]
    x = np.arange(len(sub))
    for j, (col, colr, lab) in enumerate((("auc_selected", BLUE, "Selected"), ("auc_gbm", ORANGE, "GBM"), ("auc_gcn", AQUA, "GCN"))):
        ax.bar(x + (j - 1) * 0.26, sub[col], width=0.24, color=colr, label=lab)
    ax.set_xticks(x, [f"{r}\n(n={n}, pos={p})" for r, n, p in zip(sub["range"], sub.n, sub.pos)])
    ax.set_ylim(0.5, 1)
    style(ax, "Holdout ROC-AUC by drug gene-target count", "drug gene targets", "ROC-AUC")
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper left")
    save(fig, "fig_auc_by_drug_sparsity.png")

    # ---------------- seed stability of the GCN component ----------------
    e = np.stack([sc.drug_index[x] for x in d.drug_id]), np.stack([sc.disease_index[x] for x in d.disease_id])
    S = np.stack([gcn_head_numpy(g["emb_drug"], g["emb_disease"], g, e[0], e[1]) for g in sc.gcn])
    st = {}
    for K in (50, 100, 500):
        sets = [set(np.argsort(-s, kind="stable")[:K]) for s in S]
        jac = [len(sets[i] & sets[j]) / len(sets[i] | sets[j]) for i in range(len(S)) for j in range(i + 1, len(S))]
        st[f"top{K}_jaccard_mean"], st[f"top{K}_jaccard_min"] = float(np.mean(jac)), float(np.min(jac))
    sp_ = [spearmanr(S[i], S[j])[0] for i in range(len(S)) for j in range(i + 1, len(S))]
    st["pairwise_spearman_mean"], st["pairwise_spearman_min"] = float(np.mean(sp_)), float(np.min(sp_))
    st["per_seed_auc"] = [float(roc_auc_score(d.label, s)) for s in S]
    st["per_seed_ap"] = [float(average_precision_score(d.label, s)) for s in S]
    st["seed_mean_auc"] = float(roc_auc_score(d.label, S.mean(0)))
    out["gcn_seed_stability_holdout"] = st

    # ---------------- errors ----------------
    thr = float(np.quantile(d.ranking_score, 1 - d.label.mean()))   # score cut that flags as many pairs as there are positives
    pred = d.ranking_score >= thr
    out["confusion_at_prevalence_cut"] = {"threshold_ranking_score": thr, "tp": int((pred & (d.label == 1)).sum()), "fp": int((pred & (d.label == 0)).sum()),
                                          "fn": int((~pred & (d.label == 1)).sum()), "tn": int((~pred & (d.label == 0)).sum()),
                                          "note": "cut chosen so the number of flagged pairs equals the number of positives (no tuning on the holdout)"}
    hcfp = d[(d.label == 0)].sort_values("ranking_score", ascending=False).head(30)
    hcfn = d[(d.label == 1)].sort_values("ranking_score").head(30)
    hcfp.to_csv(AN / "holdout_top30_false_positives.csv", index=False)
    hcfn.to_csv(AN / "holdout_bottom30_false_negatives.csv", index=False)
    out["high_conf_errors"] = {"top30_fp_median_dis_train_deg": float(hcfp.dis_train_deg.median()), "all_neg_median_dis_train_deg": float(d[d.label == 0].dis_train_deg.median()),
                               "top30_fp_drugs": hcfp.drug_name.value_counts().head(8).to_dict(), "bottom30_fn_median_drug_gene_deg": float(hcfn.drug_gene_deg.median()),
                               "bottom30_fn_median_dis_train_deg": float(hcfn.dis_train_deg.median()), "all_pos_median_dis_train_deg": float(d[d.label == 1].dis_train_deg.median())}
    neg = d[d.label == 0].groupby(["drug_id", "drug_name"]).ranking_score.agg(["mean", "count"]).reset_index().sort_values("mean", ascending=False)
    out["drugs_with_highest_mean_negative_score"] = neg.head(10).round(4).to_dict("records")

    # ---------------- per-drug full ranking figure ----------------
    pdr = pd.read_csv(R / "final_holdout/per_drug_full_ranking.csv")
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    ks = ["recall@10", "recall@50", "recall@100"]
    x = np.arange(len(ks))
    for j, (pfx, colr, lab) in enumerate((("selected", BLUE, "Selected"), ("gbm", ORANGE, "GBM"), ("gcn", AQUA, "GCN"))):
        vals = [pdr[f"{pfx}_{k}"].mean() for k in ks]
        ax.bar(x + (j - 1) * 0.26, vals, width=0.24, color=colr, label=lab)
        for xi, v in zip(x + (j - 1) * 0.26, vals):
            ax.text(xi, v + 0.01, f"{v:.2f}", ha="center", fontsize=7, color=INK)
    ax.set_xticks(x, ks)
    ax.set_ylim(0, 0.75)
    style(ax, "Per-drug ranking of ~17k diseases: recall of held-out indications", None, "mean recall")
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper left")
    save(fig, "fig_per_drug_recall.png")

    # ---------------- dev-CV comparison figure ----------------
    dv = pd.read_csv(R / "DEV_CV_SUMMARY.csv")
    dv = dv[~dv.model.str.startswith("rankavg") | (dv.model == "rankavg[L3_combo+deg_conn_fp_gbm]")].sort_values("val_ap")
    fig, ax = plt.subplots(figsize=(7.5, 6))
    y = np.arange(len(dv))
    cols = [BLUE if m.startswith("rankavg") else (ORANGE if k == "baseline" else AQUA) for m, k in zip(dv.model, dv.kind)]
    ax.barh(y, dv.val_ap, xerr=dv.val_ap_sd.fillna(0), color=cols, height=0.6, error_kw={"ecolor": INK2, "elinewidth": 1, "capsize": 2})
    ax.set_yticks(y, [f"{m} ({int(s)} seed{'s' if s > 1 else ''})" for m, s in zip(dv.model, dv.n_seeds)], fontsize=8)
    style(ax, "Dev CV, 5 drug-grouped folds: validation AP (mean ± SD)", "validation AP")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=BLUE, label="selected ensemble"), Patch(color=AQUA, label="GCN configs"), Patch(color=ORANGE, label="feature baselines")],
              frameon=False, fontsize=8, loc="lower right")
    save(fig, "fig_dev_cv_val_ap.png")

    # ---------------- convergence figure ----------------
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    for i, s in enumerate((21, 42, 52, 72, 100)):
        h = pd.read_csv(REPO / f"outputs/final_audit_20261117/convergence/A_k4_L3_e200/historical/seed{s}/history.csv")
        ax.plot(h.epoch, h.val_roc_auc, color=[BLUE, ORANGE, AQUA, YELLOW, MAGENTA][i], linewidth=1.5, label=f"seed {s}")
    ax.axvline(100, color=INK2, linewidth=1, linestyle=":")
    ax.text(101, 0.6, "old 100-epoch budget", fontsize=8, color=INK2)
    style(ax, "A_k4_L3, 200-epoch budget: all seeds stopped by epoch 116", "epoch", "validation ROC-AUC")
    ax.legend(frameon=False, fontsize=8, ncol=5, loc="lower right")
    save(fig, "fig_convergence.png")

    # ---------------- evidence-review candidates ----------------
    hold = np.load(REPO / "data/processed/primekg/splits_final_20261117/holdout_LOCKED.npz")
    known_any = (sc.known["treats"] + sc.known["contraindicated_for"] + sc.known["offlabel_for"]).tocsr()
    cand = []
    for dd in np.unique(hold["drugs_holdout"]):
        s_all = np.arange(sc.n_dis)
        rs, comp, _ = sc.score(np.full(sc.n_dis, dd), s_all)
        mask = np.asarray(known_any[dd].todense()).ravel() == 0
        idx = np.where(mask)[0]
        best = idx[np.argsort(-rs[idx], kind="stable")[:3]]
        order = np.argsort(-rs, kind="stable")
        rank_of = np.empty(len(rs), int)
        rank_of[order] = np.arange(1, len(rs) + 1)
        for b in best:
            cand.append({"drug_id": str(sc.drug_ids[dd]), "drug_name": str(sc.drug_names[dd]), "disease_id": str(sc.disease_ids[b]),
                         "disease_name": str(sc.disease_names[b]), "ranking_score": float(rs[b]), "score_gcn": float(comp["gcn"][b]), "score_gbm": float(comp["gbm"][b]),
                         "rank_within_drug_all_diseases": int(rank_of[b]), "drug_known_indications_in_primekg": int(sc.known["treats"][dd].nnz)})
    cdf = pd.DataFrame(cand).sort_values("ranking_score", ascending=False)
    cdf.to_csv(AN / "novel_candidates_holdout_drugs_top3_each.csv", index=False)
    pick = cdf.drop_duplicates("drug_id").head(20).copy()            # one per drug: diversity
    pick["explanation"] = [json.dumps(sc.explain(sc.drug_index[r.drug_id], sc.disease_index[r.disease_id])) for r in pick.itertuples()]
    pick.to_csv(AN / "evidence_review_candidates.csv", index=False)
    out["evidence_candidates"] = {"rule": "holdout drugs only; for each drug the top-3 diseases by ranking_score among pairs with NO PrimeKG relation "
                                          "(indication, contraindication, off-label); the 20 highest-scoring, one per drug, go to literature review",
                                  "n_candidates_pool": int(len(cdf))}
    (AN / "post_holdout_analysis.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("calibration",)}, indent=1, default=float)[:5000])
    print(pick[["drug_name", "disease_name", "ranking_score", "score_gcn", "score_gbm"]].to_string(index=False))


if __name__ == "__main__":
    main()
