"""
scripts/make_results_package.py - turn trained-model outputs into the full paper results package (tables, figures, JSON).

    python scripts/make_results_package.py --config configs/primekg_morgan.yaml
    python scripts/make_results_package.py --config configs/primekg_morgan_structcov.yaml

Reads  outputs/<exp>/ : predictions (gnn_*_predictions.csv, baseline_*_coldstart_predictions.csv), models/*_metrics.json,
                        gnn_*_history.csv, gnn_comparison.csv, baseline_comparison.csv, ranking_report.csv (optional),
                        models/gnn_*_{drug,disease}_embeddings.npy (optional)
Writes outputs/<exp>/paper_package/ :
   tables/  model_comparison.csv|md, subset_metrics.csv|md, structure_sensitivity.csv, ntd_breakdown.csv
   figures/ fig_roc_pr_*.png|pdf, fig_confusion_*.png|pdf, fig_calibration_*.png|pdf, fig_model_comparison.png|pdf,
            fig_ntd_breakdown.png|pdf, fig_structure_sensitivity.png|pdf, fig_training_curves.png|pdf, fig_embeddings.png|pdf
   results_metrics.json   (every number plotted/tabulated, with seed, split id and file provenance)
Every figure is generated ONLY from this run's prediction files; a model without a usable prediction file is listed as
missing, never filled in. Figures that need absent inputs are skipped and listed in results_metrics.json["skipped"].
Models are drawn per family (<= 6 series per chart, fixed colour order) so identity never relies on a 9th+ hue.
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
import yaml  # noqa: E402
from sklearn.calibration import calibration_curve  # noqa: E402
from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix, f1_score, matthews_corrcoef,  # noqa: E402
                             precision_recall_curve, roc_auc_score, roc_curve)

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]   # validated categorical order
INK, MUTED = "#0b0b0b", "#52514e"
plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 300,
                     "axes.edgecolor": MUTED, "axes.linewidth": 0.6})
FAMILY = {"classical": ["logistic", "nb", "rf", "xgb", "mlp"], "graph": ["node2vec", "GCN", "GraphSAGE", "GAT", "RGCN", "HGT"]}
LABEL = {"logistic": "Logistic Reg.", "nb": "Naive Bayes", "rf": "Random Forest", "xgb": "XGBoost", "mlp": "MLP", "node2vec": "Node2Vec + LR"}
skipped = []


def save(fig, d, name):
    fig.savefig(d / f"{name}.png", bbox_inches="tight")
    fig.savefig(d / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def load_models(out, test):
    """-> {key: DataFrame(probability aligned to test rows)}, {key: provenance}"""
    n = len(test)
    preds, prov = {}, {}
    for f in sorted((out / "predictions").glob("gnn_*_predictions.csv")) if (out / "predictions").exists() else []:
        key = f.stem[len("gnn_"):-len("_predictions")]
        p = pd.read_csv(f)
        m = test.merge(p[["drug_id", "disease_id", "probability"]].drop_duplicates(["drug_id", "disease_id"]), on=["drug_id", "disease_id"], how="left")
        if m.probability.notna().all():
            preds[key], prov[key] = m.probability.values, f.name
        else:
            skipped.append(f"{f.name}: covers {int(m.probability.notna().sum())}/{n} test pairs - excluded")
    for f in sorted(out.glob("baseline_*_coldstart_predictions.csv")):
        key = f.stem[len("baseline_"):-len("_coldstart_predictions")]
        p = pd.read_csv(f)
        if len(p) == n and (p.y_true.values == test.label.values).all():
            preds[key], prov[key] = p.probability.values, f.name
        else:
            skipped.append(f"{f.name}: cannot be aligned to the saved test split - excluded")
    return preds, prov


def threshold_of(out, key):
    cands = [out / "models" / f"gnn_{key}_metrics.json", out / "models" / f"baseline_{key}_metrics.json"]
    for c in cands:
        if c.exists():
            m = json.loads(c.read_text())
            for k in ("threshold", "coldstart_threshold"):
                if k in m:
                    return float(m[k])
    return None


def metrics(y, p, thr=None):
    r = {"n": int(len(y)), "positives": int(y.sum())}
    if len(np.unique(y)) == 2:
        r.update(roc_auc=float(roc_auc_score(y, p)), pr_auc=float(average_precision_score(y, p)), brier=float(brier_score_loss(y, p)))
        if thr is not None:
            yh = (p >= thr).astype(int)
            r.update(f1=float(f1_score(y, yh, zero_division=0)), mcc=float(matthews_corrcoef(y, yh)), threshold=thr)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/primekg_morgan.yaml")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(REPO / a.config))
    exp, ds = cfg["experiment"]["name"], cfg["dataset"]
    proc, out = REPO / "data" / "processed" / exp, REPO / "outputs" / exp
    pk = out / "paper_package"
    (pk / "tables").mkdir(parents=True, exist_ok=True)
    (pk / "figures").mkdir(parents=True, exist_ok=True)
    z = np.load(REPO / ds["presplit"])
    dis = pd.read_csv(proc / "diseases.csv", low_memory=False)
    drugs = pd.read_csv(proc / "drugs.csv", low_memory=False)
    fp = np.load(proc / "drug_features.npy", mmap_mode="r").any(axis=1)
    e, y = z["edges_test"], z["y_test"]
    test = pd.DataFrame({"drug_id": e[0], "disease_id": e[1], "label": y})
    test["is_ntd"] = dis.is_ntd.values[test.disease_id].astype(int)
    test["mapped"] = dis.mapping_status.values[test.disease_id] == "mapped"
    test["has_structure"] = ((drugs.has_smiles.values == 1) & fp)[test.drug_id.values]
    preds, prov = load_models(out, test)
    if not preds:
        sys.exit(f"no usable prediction files under {out}")
    M = {"experiment": exp, "config": a.config, "split_file": ds["presplit"], "seed": ds.get("random_seed"),
         "test_pairs": int(len(test)), "test_positives": int(y.sum()), "models_found": sorted(preds), "provenance": prov, "per_model": {}}
    thr = {k: threshold_of(out, k) for k in preds}

    # ---------- tables ----------
    rows, sub_rows = [], []
    for k, p in preds.items():
        full = metrics(y, p, thr[k])
        M["per_model"][k] = {"all": full}
        rows.append({"model": LABEL.get(k, k), "key": k, **full})
        for sname, mask in (("all", np.ones(len(y), bool)), ("ntd_only", test.is_ntd.values == 1), ("mapped_only", test["mapped"].values),
                            ("with_structure", test.has_structure.values), ("no_structure", ~test.has_structure.values)):
            r = metrics(y[mask], p[mask], thr[k])
            M["per_model"][k][sname] = r
            sub_rows.append({"model": LABEL.get(k, k), "subset": sname, **r})
    comp = pd.DataFrame(rows)
    comp.to_csv(pk / "tables" / "model_comparison.csv", index=False)
    subs = pd.DataFrame(sub_rows)
    subs.to_csv(pk / "tables" / "subset_metrics.csv", index=False)
    try:
        md_table = comp.round(4).to_markdown(index=False)
    except ImportError:                                   # tabulate not installed
        md_table = "```\n" + comp.round(4).to_string(index=False) + "\n```"
    (pk / "tables" / "model_comparison.md").write_text(md_table, encoding="utf-8")
    sens = subs[subs.subset.isin(["all", "with_structure", "no_structure"])].pivot(index="model", columns="subset", values="roc_auc").reset_index()
    sens.to_csv(pk / "tables" / "structure_sensitivity.csv", index=False)
    subs[subs.subset.isin(["all", "ntd_only"])].to_csv(pk / "tables" / "ntd_breakdown.csv", index=False)
    rr = out / "ranking_report.csv"
    if rr.exists():
        shutil_copy = pd.read_csv(rr)
        shutil_copy.to_csv(pk / "tables" / "ranking_report.csv", index=False)
        M["ranking_report"] = "tables/ranking_report.csv (from evaluate_primekg.py)"
    else:
        skipped.append("ranking_report.csv missing: run scripts/evaluate_primekg.py first (P@K, Recall@K, MRR, NDCG)")

    # ---------- figures: ROC/PR, calibration, confusion (per family) ----------
    for fam, keys in FAMILY.items():
        ks = [k for k in keys if k in preds]
        if not ks:
            continue
        fig, ax = plt.subplots(1, 2, figsize=(7.16, 3.0))
        for i, k in enumerate(ks):
            fpr, tpr, _ = roc_curve(y, preds[k])
            pr, rc, _ = precision_recall_curve(y, preds[k])
            auc, ap_ = roc_auc_score(y, preds[k]), average_precision_score(y, preds[k])
            ax[0].plot(fpr, tpr, color=PAL[i], lw=1.4, label=f"{LABEL.get(k, k)} (AUC {auc:.3f})")
            ax[1].plot(rc, pr, color=PAL[i], lw=1.4, label=f"{LABEL.get(k, k)} (AP {ap_:.3f})")
        ax[0].plot([0, 1], [0, 1], color="#b9b8b2", lw=0.8, ls="--")
        ax[1].axhline(y.mean(), color="#b9b8b2", lw=0.8, ls="--", label=f"chance ({y.mean():.2f})")
        ax[0].set(xlabel="false positive rate", ylabel="true positive rate", title="ROC (test, drug-disjoint)")
        ax[1].set(xlabel="recall", ylabel="precision", title="Precision-recall (test)")
        for x_ in ax:
            x_.legend(frameon=False, fontsize=6.5, loc="lower right" if x_ is ax[0] else "upper right")
        save(fig, pk / "figures", f"fig_roc_pr_{fam}")
        fig, ax = plt.subplots(figsize=(3.5, 3.0))
        for i, k in enumerate(ks):
            fr, mp_ = calibration_curve(y, preds[k], n_bins=10, strategy="quantile")
            ax.plot(mp_, fr, marker="o", ms=3, color=PAL[i], lw=1.2, label=f"{LABEL.get(k, k)} (Brier {brier_score_loss(y, preds[k]):.3f})")
        ax.plot([0, 1], [0, 1], color="#b9b8b2", ls="--", lw=0.8)
        ax.set(xlabel="mean predicted probability", ylabel="observed positive fraction", title="Calibration (test)")
        ax.legend(frameon=False, fontsize=6.5)
        save(fig, pk / "figures", f"fig_calibration_{fam}")
        has_thr = [k for k in ks if thr[k] is not None]
        if has_thr:
            fig, axs = plt.subplots(1, len(has_thr), figsize=(1.9 * len(has_thr) + 0.4, 2.2), squeeze=False)
            for ax, k in zip(axs[0], has_thr):
                cm = confusion_matrix(y, (preds[k] >= thr[k]).astype(int), labels=[0, 1])
                ax.imshow(cm, cmap="Blues")
                for (i, j), v in np.ndenumerate(cm):
                    ax.text(j, i, f"{v:,}", ha="center", va="center", color="white" if v > cm.max() / 2 else INK, fontsize=7)
                ax.set(xticks=[0, 1], yticks=[0, 1], xticklabels=["pred 0", "pred 1"], yticklabels=["true 0", "true 1"], title=LABEL.get(k, k))
                ax.spines[:].set_visible(False)
            save(fig, pk / "figures", f"fig_confusion_{fam}")
            M.setdefault("confusion", {}).update({k: confusion_matrix(y, (preds[k] >= thr[k]).astype(int), labels=[0, 1]).ravel().tolist() for k in has_thr})
        else:
            skipped.append(f"confusion matrices ({fam}): no stored validation threshold found")

    # ---------- model comparison bars (ROC-AUC and PR-AUC, two panels, one colour per metric slot) ----------
    c2 = comp.sort_values("roc_auc", ascending=False)
    fig, ax = plt.subplots(1, 2, figsize=(7.16, 2.6), sharey=True)
    for a_, col, c_ in zip(ax, ("roc_auc", "pr_auc"), (PAL[0], PAL[1])):
        yy = np.arange(len(c2))[::-1]
        a_.barh(yy, c2[col], color=c_, height=0.6)
        for yi, v in zip(yy, c2[col]):
            a_.text(v + 0.005, yi, f"{v:.3f}", va="center", fontsize=7)
        a_.set_xlim(0, 1)
        a_.set_xlabel(col.replace("_", "-").upper())
    ax[0].set_yticks(np.arange(len(c2))[::-1], c2.model)
    save(fig, pk / "figures", "fig_model_comparison")

    # ---------- NTD + structure sensitivity (all vs subset, grouped bars) ----------
    def grouped(sub_a, sub_b, name, la, lb):
        t = subs[subs.subset.isin([sub_a, sub_b])].pivot(index="model", columns="subset", values="roc_auc").dropna(how="all")
        if sub_a not in t or sub_b not in t:
            skipped.append(f"{name}: subset missing")
            return
        fig, ax = plt.subplots(figsize=(7.16, 2.6))
        x = np.arange(len(t))
        ax.bar(x - 0.2, t[sub_a], 0.38, color=PAL[0], label=la)
        ax.bar(x + 0.2, t[sub_b], 0.38, color=PAL[1], label=lb)
        for xi, (va, vb) in zip(x, zip(t[sub_a], t[sub_b])):
            ax.text(xi - 0.2, va + 0.01, f"{va:.2f}", ha="center", fontsize=6.5)
            ax.text(xi + 0.2, vb + 0.01, f"{vb:.2f}", ha="center", fontsize=6.5)
        ax.set_xticks(x, t.index, rotation=20, ha="right")
        ax.set_ylabel("ROC-AUC")
        ax.set_ylim(0, 1.05)
        ax.axhline(0.5, color="#b9b8b2", lw=0.8, ls="--")
        ax.legend(frameon=False, fontsize=7)
        save(fig, pk / "figures", name)
    grouped("all", "ntd_only", "fig_ntd_breakdown", f"all test pairs (n={len(test):,})", f"NTD diseases only (n={int(test.is_ntd.sum())}, {int(y[test.is_ntd.values == 1].sum())} positives: exploratory)")
    grouped("with_structure", "no_structure", "fig_structure_sensitivity", "drug has structure", "drug has no structure")

    # ---------- GNN training curves ----------
    hist = {f.stem[len("gnn_"):-len("_history")]: pd.read_csv(f) for f in sorted(out.glob("gnn_*_history.csv"))}
    if hist:
        fig, ax = plt.subplots(1, 2, figsize=(7.16, 2.8))
        for i, (k, h) in enumerate(hist.items()):
            cols = [c for c in h.columns if "loss" in c.lower()]
            vcols = [c for c in h.columns if "val" in c.lower() and "auc" in c.lower()]
            if cols:
                ax[0].plot(h.index + 1, h[cols[0]], color=PAL[i % 8], lw=1.2, label=k)
            if vcols:
                ax[1].plot(h.index + 1, h[vcols[0]], color=PAL[i % 8], lw=1.2, label=k)
        ax[0].set(xlabel="epoch", ylabel="training loss")
        ax[1].set(xlabel="epoch", ylabel="validation ROC-AUC")
        ax[0].legend(frameon=False, fontsize=6.5)
        save(fig, pk / "figures", "fig_training_curves")
    else:
        skipped.append("training curves: no gnn_*_history.csv")

    # ---------- embeddings (PCA, no extra dependency) ----------
    embs = sorted((out / "models").glob("gnn_*_disease_embeddings.npy")) if (out / "models").exists() else []
    if embs:
        from sklearn.decomposition import PCA
        pick = next((p for p in embs if "HGT" in p.name), embs[0])
        E = np.load(pick)
        xy = PCA(n_components=2, random_state=0).fit_transform(E)
        isn = dis.is_ntd.values.astype(bool)
        fig, ax = plt.subplots(figsize=(3.5, 3.2))
        ax.scatter(xy[~isn, 0], xy[~isn, 1], s=2, color="#b9b8b2", label=f"other diseases ({int((~isn).sum()):,})", rasterized=True)
        ax.scatter(xy[isn, 0], xy[isn, 1], s=12, color=PAL[1], label=f"NTD diseases ({int(isn.sum())})", edgecolor="white", linewidth=0.3)
        ax.set(xlabel="PC1", ylabel="PC2", title=f"Disease embeddings ({pick.stem.split('_')[1]}), PCA")
        ax.legend(frameon=False, fontsize=7)
        save(fig, pk / "figures", "fig_embeddings")
    else:
        skipped.append("embeddings figure: no gnn_*_disease_embeddings.npy")

    M["skipped"] = skipped
    (pk / "results_metrics.json").write_text(json.dumps(M, indent=2, default=float), encoding="utf-8")
    print(f"models: {sorted(preds)}\nwrote {pk}\nskipped: {skipped}")


if __name__ == "__main__":
    main()
