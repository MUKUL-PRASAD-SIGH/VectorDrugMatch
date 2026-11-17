"""
scripts/final_audit/phase3_historical_stats.py - statistics on the HISTORICAL seed-42 split (already examined; not an untouched holdout).

    python scripts/final_audit/phase3_historical_stats.py --gpu-root <.../treats_edge_ablation_20261112_gpu> --old-root <.../VDM_Outputs/outputs> \
        --out reports/final_audit_20261117/phase3_historical

* Builds simple baselines on the SAME train/test pairs (degree-only, connectivity, fingerprint similarity, popularity) from the leakage-safe graph and
  training labels only, fixed hyper-parameters (no tuning).
* Paired hierarchical bootstrap (src/utils/final_metrics.py) for the predeclared comparisons; Holm correction over the family.
* Reachability / popularity / seed-stability / error analyses of A_k4_L3.
No model is selected here; this is historical evidence only.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from src.data.dataset import build_message_passing_graph  # noqa: E402
from src.data.graph_builder import build_hetero_data  # noqa: E402
from src.features.simple_baselines import CONN_NAMES, GROUPS, LABEL_NAMES, PairFeaturizer, design, feature_matrices  # noqa: E402
from src.utils.final_metrics import all_metrics, hierarchical_paired_bootstrap, holm  # noqa: E402

SEEDS = [21, 42, 52, 72, 100]
SPLIT = "data/processed/primekg/splits/seed42.npz"
BOOT_SEED = 20261117


def gbm(seed=0):
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0, random_state=seed)


def build_baselines(out):
    data = build_hetero_data(REPO / "data/processed/primekg", include_features=True)
    mp = build_message_passing_graph(data, SPLIT)
    z = np.load(REPO / SPLIT)
    fp = data["drug"].x.numpy()
    t0 = time.time()
    F = PairFeaturizer(mp, z["edges_train"], z["y_train"], fp)
    feats = feature_matrices(F, {sp_: z[f"edges_{sp_}"] for sp_ in ("train", "val", "test")})
    print(f"features {time.time() - t0:.0f}s")
    y = {sp_: z[f"y_{sp_}"].astype(int) for sp_ in ("train", "val", "test")}
    preds = {}
    for name in GROUPS:
        X = {sp_: design(feats[sp_], name) for sp_ in feats}
        m = gbm().fit(X["train"], y["train"])
        preds[name] = {sp_: m.predict_proba(X[sp_])[:, 1] for sp_ in ("val", "test")}
    preds["disease_popularity"] = {sp_: feats[sp_]["label"][:, 0] for sp_ in ("val", "test")}
    preds["max_tanimoto"] = {sp_: feats[sp_]["label"][:, 2] for sp_ in ("val", "test")}
    preds["shared_gene_paths"] = {sp_: feats[sp_]["conn"][:, CONN_NAMES.index("log_p_dgs")] for sp_ in ("val", "test")}
    np.savez_compressed(out / "baseline_predictions_seed42split.npz", **{f"{k}__{s}": v[s] for k, v in preds.items() for s in v})
    return preds, feats, y, z


def load_gcn(gpu_root, cfg):
    S = []
    for s in SEEDS:
        p = gpu_root / cfg / f"seed{s}" / "predictions.csv"
        if p.exists():
            S.append(pd.read_csv(p).probability.values)
    return np.stack(S)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu-root", required=True)
    ap.add_argument("--old-root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--B", type=int, default=2000)
    a = ap.parse_args()
    out = REPO / a.out
    out.mkdir(parents=True, exist_ok=True)
    gpu, old = Path(a.gpu_root), Path(a.old_root)
    preds, feats, y, z = build_baselines(out)
    yt = y["test"]
    ref = pd.read_csv(gpu / "A_k4_L3" / "seed42" / "predictions.csv", dtype=str)

    models = {c: load_gcn(gpu, c) for c in ["A_orig", "A_k4", "A_k4_L3", "B_k4", "B_k4_L3", "C_k4", "D_rgcn_B"]}
    rf = []
    for s in SEEDS:
        p = pd.read_csv(old / f"multiseed_primekg_rf_dp_s{s}" / "baseline_pair_level_predictions.csv", dtype={"drug_id": str, "disease_id": str})
        assert (p.drug_id.values == ref.drug_id.values).all() and (p.disease_id.values == ref.disease_id.values).all() and (p.label.values == yt).all(), "RF pairs differ"
        rf.append(p.probability.values)
    models["RF_disease_profile"] = np.stack(rf)
    for k in ("xgb", "logistic", "mlp"):
        p = pd.read_csv(old / "primekg_dp" / f"baseline_{k}_coldstart_predictions.csv")
        assert (p.y_true.values == yt).all()
        models[f"{k.upper()}_disease_profile_1seed"] = p.probability.values[None, :]
    for k, v in preds.items():
        models[k] = v["test"][None, :]

    # point metrics for every model (per seed, then mean/sd)
    rows = []
    for k, S in models.items():
        for j, s in enumerate(S):
            r = all_metrics(yt, s)
            rows.append({"model": k, "seed_index": j, **r})
    pm = pd.DataFrame(rows)
    pm.to_csv(out / "point_metrics_per_seed.csv", index=False)
    summ = pm.groupby("model").agg(["mean", "std", "count"])
    summ.columns = [f"{a_}_{b_}" for a_, b_ in summ.columns]
    summ.to_csv(out / "point_metrics_summary.csv")

    comps = [("A_k4", "B_k4"), ("A_k4_L3", "B_k4_L3"), ("A_k4_L3", "A_k4"), ("A_k4_L3", "A_orig"), ("A_k4_L3", "RF_disease_profile"),
             ("A_k4_L3", "XGB_disease_profile_1seed"), ("A_k4_L3", "LOGISTIC_disease_profile_1seed"), ("A_k4_L3", "MLP_disease_profile_1seed"),
             ("A_k4_L3", "degree_gbm"), ("A_k4_L3", "connectivity_gbm"), ("A_k4_L3", "fingerprint_gbm"), ("A_k4_L3", "deg_conn_fp_gbm"),
             ("A_k4_L3", "C_k4"), ("RF_disease_profile", "deg_conn_fp_gbm")]
    res = []
    for m1, m2 in comps:
        t0 = time.time()
        r = hierarchical_paired_bootstrap(yt, models[m1], models[m2], B=a.B, seed=BOOT_SEED)
        r.update({"model_1": m1, "model_2": m2, "seconds": round(time.time() - t0, 1)})
        res.append(r)
        print(f"{m1} vs {m2}: dAUC {r['roc_auc_diff']:+.4f} {r['roc_auc_diff_ci']} p={r['roc_auc_p']:.4g} | dAP {r['ap_diff']:+.4f} {r['ap_diff_ci']} p={r['ap_p']:.4g}")
    df = pd.DataFrame(res)
    df["roc_auc_p_holm"] = holm(df.roc_auc_p.values)
    df["ap_p_holm"] = holm(df.ap_p.values)
    df.to_csv(out / "PAIRED_COMPARISONS_historical.csv", index=False)

    # ---------- analyses of A_k4_L3 on the historical test set ----------
    S = models["A_k4_L3"]
    mean_s = S.mean(0)
    an = {}
    conn = feats["test"]["conn"]
    deg = feats["test"]["deg"]
    lab = feats["test"]["label"]
    for nm in ("reach2", "reach3"):
        r_ = conn[:, CONN_NAMES.index(nm)] > 0
        an[nm] = {"pos_fraction_reachable": float(r_[yt == 1].mean()), "neg_fraction_reachable": float(r_[yt == 0].mean()),
                  "auc_reachability_flag": float(roc_auc_score(yt, r_)),
                  "gcn_auc_within_reachable": float(np.mean([roc_auc_score(yt[r_], s[r_]) for s in S])) if r_.sum() and len(set(yt[r_])) == 2 else None,
                  "gcn_auc_within_unreachable": float(np.mean([roc_auc_score(yt[~r_], s[~r_]) for s in S])) if (~r_).sum() and len(set(yt[~r_])) == 2 else None,
                  "n_unreachable_pos": int((~r_ & (yt == 1)).sum()), "n_unreachable_neg": int((~r_ & (yt == 0)).sum())}
    pop = lab[:, 0]
    an["disease_popularity"] = {"auc_alone": float(roc_auc_score(yt, pop)), "spearman_gcn_vs_pop_all": float(spearmanr(mean_s, pop)[0]),
                                "spearman_gcn_vs_pop_negatives": float(spearmanr(mean_s[yt == 0], pop[yt == 0])[0]),
                                "pos_mean_pop": float(pop[yt == 1].mean()), "neg_mean_pop": float(pop[yt == 0].mean())}
    # GCN AUC within popularity strata (quintiles of disease training degree): does the GCN rank within equally popular diseases?
    q = pd.qcut(pd.Series(pop).rank(method="first"), 5, labels=False).values
    an["gcn_auc_within_popularity_quintile"] = [{"quintile": int(k), "n": int((q == k).sum()), "pos": int(yt[q == k].sum()),
                                                "gcn_auc": float(np.mean([roc_auc_score(yt[q == k], s[q == k]) for s in S])) if len(set(yt[q == k])) == 2 else None,
                                                "conn_gbm_auc": float(roc_auc_score(yt[q == k], models["deg_conn_fp_gbm"][0][q == k])) if len(set(yt[q == k])) == 2 else None}
                                               for k in range(5)]
    # parameter-free rank-average ensemble (nothing fitted on test): does the GCN add to the strongest simple baseline?
    from scipy.stats import rankdata
    base = models["deg_conn_fp_gbm"][0]
    ens = np.stack([(rankdata(s) + rankdata(base)) / 2 for s in S])
    models["rankavg_A_k4_L3__deg_conn_fp_gbm"] = ens
    r = hierarchical_paired_bootstrap(yt, ens, base[None, :], B=a.B, seed=BOOT_SEED)
    an["rank_average_ensemble_vs_baseline"] = {k: r[k] for k in ("roc_auc_1_mean", "roc_auc_2_mean", "roc_auc_diff", "roc_auc_diff_ci", "roc_auc_p", "ap_1_mean", "ap_2_mean", "ap_diff", "ap_diff_ci", "ap_p")}
    # seed stability of the top of the ranking
    tops = {}
    for K in (50, 100, 500):
        sets = [set(np.argsort(-s, kind="stable")[:K]) for s in S]
        jac = [len(sets[i] & sets[j]) / len(sets[i] | sets[j]) for i in range(5) for j in range(i + 1, 5)]
        tops[f"top{K}_pairwise_jaccard_mean"] = float(np.mean(jac))
        tops[f"top{K}_pairwise_jaccard_min"] = float(np.min(jac))
    sp_ = [spearmanr(S[i], S[j])[0] for i in range(5) for j in range(i + 1, 5)]
    tops["pairwise_spearman_mean"], tops["pairwise_spearman_min"] = float(np.mean(sp_)), float(np.min(sp_))
    an["seed_stability"] = tops
    # drug/disease concentration in the top of the ranking and among high-confidence false positives
    drug = ref.drug_id.values
    disease = ref.disease_id.values
    o = np.argsort(-mean_s, kind="stable")
    top500 = o[:500]
    an["top500_concentration"] = {"unique_drugs": int(len(set(drug[top500]))), "unique_diseases": int(len(set(disease[top500]))),
                                  "max_pairs_one_drug": int(pd.Series(drug[top500]).value_counts().max()),
                                  "max_pairs_one_disease": int(pd.Series(disease[top500]).value_counts().max()),
                                  "test_drugs": int(len(set(drug))), "test_diseases": int(len(set(disease)))}
    fp_mask = (yt == 0) & (mean_s >= 0.9)
    fpd = pd.DataFrame({"drug_id": drug[fp_mask], "disease_id": disease[fp_mask], "mean_prob": mean_s[fp_mask], "dis_train_degree": np.expm1(pop[fp_mask]),
                        "reach2": conn[fp_mask, CONN_NAMES.index("reach2")], "shared_genes": np.expm1(conn[fp_mask, 0]),
                        "contra_via_related": np.expm1(conn[fp_mask, CONN_NAMES.index("log_p_dcs")])}).sort_values("mean_prob", ascending=False)
    fpd.to_csv(out / "high_conf_false_positives_A_k4_L3_seedmean.csv", index=False)
    neg = yt == 0
    an["high_conf_fp_profile"] = {"n": int(fp_mask.sum()), "median_dis_train_degree_hcfp": float(np.median(np.expm1(pop[fp_mask]))) if fp_mask.any() else None,
                                  "median_dis_train_degree_all_neg": float(np.median(np.expm1(pop[neg]))),
                                  "frac_contra_via_related_hcfp": float((conn[fp_mask, CONN_NAMES.index("log_p_dcs")] > 0).mean()) if fp_mask.any() else None,
                                  "frac_contra_via_related_all_neg": float((conn[neg, CONN_NAMES.index("log_p_dcs")] > 0).mean()),
                                  "top_drugs": pd.Series(drug[fp_mask]).value_counts().head(10).to_dict(),
                                  "top_diseases": pd.Series(disease[fp_mask]).value_counts().head(10).to_dict()}
    # same drug inflated across unrelated diseases: per drug, mean score on its negatives
    dneg = pd.DataFrame({"drug": drug[neg], "p": mean_s[neg]}).groupby("drug").p.agg(["mean", "count"]).sort_values("mean", ascending=False)
    an["drugs_with_highest_mean_negative_score"] = dneg.head(10).round(4).reset_index().to_dict("records")
    # sparse drugs: GCN AUC by drug gene-degree bucket
    gdeg = np.expm1(deg[:, 0])
    buckets = [(0, 0), (1, 2), (3, 10), (11, 10 ** 9)]
    an["gcn_auc_by_drug_gene_degree"] = []
    for lo, hi in buckets:
        mk = (gdeg >= lo) & (gdeg <= hi)
        an["gcn_auc_by_drug_gene_degree"].append({"drug_gene_degree": f"{lo}-{hi if hi < 10 ** 9 else 'inf'}", "n": int(mk.sum()), "pos": int(yt[mk].sum()),
                                                   "gcn_auc": float(np.mean([roc_auc_score(yt[mk], s[mk]) for s in S])) if mk.sum() and len(set(yt[mk])) == 2 else None})
    (out / "analysis_A_k4_L3_historical.json").write_text(json.dumps(an, indent=1, default=str), encoding="utf-8")
    print(json.dumps(an, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
