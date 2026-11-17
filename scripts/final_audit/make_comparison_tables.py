"""
scripts/final_audit/make_comparison_tables.py - assemble the published-baseline comparison from saved artifacts (no training).

    python scripts/final_audit/make_comparison_tables.py

Reads
  outputs/final_audit_20261117/kge/<model>/<split>/seed<seed>/metrics.json          (TransE / DistMult / ComplEx / RotatE)
  outputs/final_audit_20261117/disease_protocol/<model>/disease_split/seed*/        (VectorDrugMatch + feature baselines, disease protocol)
  reports/final_audit_20261117/{DEV_CV_SUMMARY.csv, final_holdout/HOLDOUT_RESULTS.json, final_holdout/HOLDOUT_PREDICTIONS.csv}
Writes
  reports/final_audit_20261117/COMPARISON_BASELINES.csv and comparison/{paired_vs_kge_holdout.csv, disease_protocol_metrics.csv}
Paired hierarchical bootstrap (same pairs, B = 2,000, seed 20261117) for the deployed model against each KGE baseline on the locked holdout.
Everything here is POST-HOC: the deployed model was frozen first and nothing is selected on these numbers.
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from src.utils.final_metrics import all_metrics, hierarchical_paired_bootstrap, holm  # noqa: E402

R = REPO / "reports/final_audit_20261117"
O = REPO / "outputs/final_audit_20261117"
KGE = ("TransE", "DistMult", "ComplEx", "RotatE")
BOOT = 20261117


def kge_rows():
    rows = []
    for f in sorted(glob.glob(str(O / "kge/*/*/seed*/metrics.json"))):
        m = json.loads(Path(f).read_text())
        for k, v in m.items():
            if isinstance(v, dict) and "roc_auc" in v:
                rows.append({"model": m["model"], "split": m["split"], "seed": m["seed"], "eval_set": k, "roc_auc": v["roc_auc"],
                             "pr_auc_ap": v["pr_auc_ap"], "precision_at_100": v.get("precision_at_100"), "steps_run": m.get("steps_run"),
                             "best_step": m.get("best_step"), "train_seconds": m.get("train_seconds"), "n_params": m.get("n_params")})
    return pd.DataFrame(rows)


def rank_avg(a, b):
    from scipy.stats import rankdata
    return (rankdata(a) + rankdata(b)) / (2 * len(a))


def main():
    out_dir = R / "comparison"
    out_dir.mkdir(exist_ok=True)
    kg = kge_rows()
    if kg.empty:
        sys.exit("no KGE runs found - run notebooks/colab_comparison_20261118.ipynb first")
    kg.to_csv(out_dir / "kge_raw_metrics.csv", index=False)
    rows = []

    # ---- development CV (5 folds): VectorDrugMatch candidates vs KGE ----
    dev = pd.read_csv(R / "DEV_CV_SUMMARY.csv")
    for r in dev.itertuples():
        if r.model in ("rankavg[L3_combo+deg_conn_fp_gbm]", "L3_combo", "deg_conn_fp_gbm", "rf_disease_profile", "max_tanimoto"):
            rows.append({"protocol": "drug_disjoint", "stage": "dev_cv_val", "method": r.model, "family": "VectorDrugMatch",
                         "n_runs": r.n_runs, "roc_auc": r.val_auc, "roc_auc_sd": r.val_auc_sd, "pr_auc_ap": r.val_ap, "ap_sd": r.val_ap_sd,
                         "popmatch_ap": r.popmatch_ap})
    d = kg[(kg.split.str.startswith("cv_fold")) & (kg.eval_set == "val")]
    dpm = kg[(kg.split.str.startswith("cv_fold")) & (kg.eval_set == "val_popmatch")]
    for m, g in d.groupby("model"):
        rows.append({"protocol": "drug_disjoint", "stage": "dev_cv_val", "method": m, "family": "KG embedding", "n_runs": len(g),
                     "roc_auc": g.roc_auc.mean(), "roc_auc_sd": g.roc_auc.std(ddof=1), "pr_auc_ap": g.pr_auc_ap.mean(),
                     "ap_sd": g.pr_auc_ap.std(ddof=1), "popmatch_ap": dpm[dpm.model == m].pr_auc_ap.mean()})

    # ---- locked holdout: deployed model vs KGE (paired bootstrap on identical pairs) ----
    hold = json.loads((R / "final_holdout/HOLDOUT_RESULTS.json").read_text())
    for st in ("hard", "popmatch"):
        S = hold["sets"][st]["models"]
        for k in (list(S)[0], "gcn_component_per_seed", "deg_conn_fp_gbm", "rf_disease_profile"):
            if k in S:
                rows.append({"protocol": "drug_disjoint", "stage": f"holdout_{st}", "method": k, "family": "VectorDrugMatch",
                             "n_runs": len(S[k]["per_seed"]), "roc_auc": S[k]["mean"]["roc_auc"], "pr_auc_ap": S[k]["mean"]["pr_auc_ap"],
                             "precision_at_100": S[k]["mean"]["precision_at_100"],
                             "roc_auc_ci_low": S[k]["roc_auc_ci"][0], "roc_auc_ci_high": S[k]["roc_auc_ci"][1],
                             "ap_ci_low": S[k]["ap_ci"][0], "ap_ci_high": S[k]["ap_ci"][1]})
    pr = pd.read_csv(R / "final_holdout/HOLDOUT_PREDICTIONS.csv", dtype={"drug_id": str, "disease_id": str})
    paired = []
    for st, ev in (("hard", "holdout"), ("popmatch", "holdout_popmatch")):
        ours = pr[pr.set == st]
        for m in KGE:
            f = O / f"kge/{m}/final_train/seed42/{ev}_predictions.csv"
            if not f.exists():
                continue
            kp = pd.read_csv(f, dtype={"drug_id": str, "disease_id": str})
            assert (kp.drug_id.values == ours.drug_id.values).all() and (kp.label.values == ours.label.values).all(), f"pair mismatch {m} {st}"
            met = all_metrics(kp.label.values, kp.probability.values)
            rows.append({"protocol": "drug_disjoint", "stage": f"holdout_{st}", "method": m, "family": "KG embedding", "n_runs": 1,
                         "roc_auc": met["roc_auc"], "pr_auc_ap": met["pr_auc_ap"], "precision_at_100": met["precision_at_100"]})
            b = hierarchical_paired_bootstrap(ours.label.values, ours.ranking_score.values[None, :], kp.probability.values[None, :], B=2000, seed=BOOT)
            b.update({"candidate_set": st, "model_1": "VectorDrugMatch vdm-1.0.0", "model_2": m})
            paired.append(b)
    if paired:
        pdf = pd.DataFrame(paired)
        for c in ("roc_auc_p", "ap_p"):
            pdf[c + "_holm"] = holm(pdf[c].values)
        pdf.to_csv(out_dir / "paired_vs_kge_holdout.csv", index=False)

    # ---- zero-shot-disease protocol ----
    dp = O / "disease_protocol"
    dis_rows = []
    gcn_test, gbm_test = {}, None
    for f in sorted(glob.glob(str(dp / "*/disease_split/seed*/metrics.json"))):
        m = json.loads(Path(f).read_text())
        nm = m.get("name") or m.get("model")
        for ek in ("test", "test_popmatch"):
            if ek in m:
                dis_rows.append({"method": nm, "seed": m.get("seed"), "eval_set": ek, **{k: m[ek][k] for k in ("roc_auc", "pr_auc_ap", "precision_at_100")}})
        tf = Path(f).parent / "test_predictions.csv"
        if tf.exists():
            t = pd.read_csv(tf, dtype={"drug_id": str, "disease_id": str})
            if nm == "L3_combo":
                gcn_test[m.get("seed")] = t
            elif nm == "deg_conn_fp_gbm":
                gbm_test = t
    for m in KGE:
        f = O / f"kge/{m}/disease_split/seed42/test_predictions.csv"
        if f.exists():
            t = pd.read_csv(f)
            dis_rows.append({"method": m, "seed": 42, "eval_set": "test", **{k: all_metrics(t.label.values, t.probability.values)[k]
                                                                             for k in ("roc_auc", "pr_auc_ap", "precision_at_100")}})
    if gcn_test and gbm_test is not None:
        for sd, t in gcn_test.items():
            assert (t.drug_id.values == gbm_test.drug_id.values).all()
            ens = rank_avg(t.probability.values, gbm_test.probability.values)
            dis_rows.append({"method": "rankavg[L3_combo+deg_conn_fp_gbm]", "seed": sd, "eval_set": "test",
                             **{k: all_metrics(t.label.values, ens)[k] for k in ("roc_auc", "pr_auc_ap", "precision_at_100")}})
    if dis_rows:
        ddf = pd.DataFrame(dis_rows)
        ddf.to_csv(out_dir / "disease_protocol_metrics.csv", index=False)
        for (m, ek), g in ddf.groupby(["method", "eval_set"]):
            fam = "KG embedding" if m in KGE else ("VectorDrugMatch" if m.startswith(("L3", "rankavg")) else "feature baseline")
            rows.append({"protocol": "disease_disjoint", "stage": f"disease_{ek}", "method": m, "family": fam, "n_runs": len(g),
                         "roc_auc": g.roc_auc.mean(), "roc_auc_sd": g.roc_auc.std(ddof=1) if len(g) > 1 else None,
                         "pr_auc_ap": g.pr_auc_ap.mean(), "ap_sd": g.pr_auc_ap.std(ddof=1) if len(g) > 1 else None,
                         "precision_at_100": g.precision_at_100.mean()})
    df = pd.DataFrame(rows)
    df.to_csv(R / "COMPARISON_BASELINES.csv", index=False)
    for stage, g in df.groupby("stage"):
        print(f"\n=== {stage}")
        print(g.sort_values("pr_auc_ap", ascending=False)[["method", "family", "n_runs", "roc_auc", "pr_auc_ap"]].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
