"""
scripts/final_audit/verify_gpu_ablation.py - independent verification of the treats-edge GPU ablation archive (no training).

    python -I scripts/final_audit/verify_gpu_ablation.py --root <extracted>/treats_edge_ablation_20261112_gpu --out reports/final_audit_20261117

Checks, from the saved files only:
  * the 42 expected main runs exist (8 five-seed configurations + B_k2/B_k8 one seed); smoke runs are kept apart;
  * every run has metrics / predictions / config / history / audit / log; whether model.pth is present (light ZIP excludes weights);
  * commit, torch, GPU metadata per run;
  * every leakage audit has all_pass == true;
  * every predictions.csv holds the SAME ordered (drug, disease, label) rows, equal to the saved split's test pairs;
  * ROC-AUC / AP / trapezoidal PR-AUC / Brier / log loss / ECE / P@K recomputed from predictions agree with metrics.json;
  * best_epoch agrees with argmax of history val ROC-AUC; seeds whose best epoch == the epoch budget are flagged;
  * five_seed_summary.csv / seed_wise_metrics.csv agree with the per-run metrics.json.
Writes <out>/artifact_verification.json and <out>/SEED_WISE_METRICS_recomputed.csv.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from src.utils.final_metrics import all_metrics  # noqa: E402

FIVE = ["A_orig", "A_k4", "A_k4_L3", "B0_naive", "B_k4", "B_k4_L3", "C_k4", "D_rgcn_B"]
ONE = ["B_k2", "B_k8"]
SEEDS = [21, 42, 52, 72, 100]
FILES = ["metrics.json", "predictions.csv", "run_config.json", "history.csv", "leakage_audit.json", "train.log", "high_conf_false_positives.csv",
         "high_conf_false_negatives.csv"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--split", default="data/processed/primekg/splits/seed42.npz")
    ap.add_argument("--tol", type=float, default=1e-6)
    a = ap.parse_args()
    root, out = Path(a.root), REPO / a.out
    out.mkdir(parents=True, exist_ok=True)
    rep = {"root": str(root.name), "problems": []}
    P = rep["problems"]

    expected = [(c, s) for c in FIVE for s in SEEDS] + [(c, 42) for c in ONE]
    found = sorted({(d.parent.name, int(d.name[4:])) for d in root.glob("*/seed*") if d.is_dir() and d.parent.name != "smoke"})
    rep["n_expected_main_runs"], rep["n_found_main_runs"] = len(expected), len(found)
    rep["missing_runs"] = sorted(set(expected) - set(found))
    rep["unexpected_runs"] = sorted(set(found) - set(expected))
    rep["smoke_runs"] = sorted(f"{d.parent.name}/{d.name}" for d in (root / "smoke").glob("*/seed*")) if (root / "smoke").exists() else []
    if rep["missing_runs"] or rep["unexpected_runs"]:
        P.append("run set differs from the 42 expected")

    # saved split: test pairs in their stored order
    z = np.load(REPO / a.split)
    import pandas as _pd
    drugs = _pd.read_csv(REPO / "data/processed/primekg/drugs.csv", usecols=["drug_id"], dtype=str).drug_id.values
    dis = _pd.read_csv(REPO / "data/processed/primekg/diseases.csv", usecols=["disease_id"], dtype=str).disease_id.values
    et, yt = z["edges_test"], z["y_test"].astype(int)
    split_rows = pd.DataFrame({"drug_id": drugs[et[0]], "disease_id": dis[et[1]], "label": yt})
    rep["split_file_sha256"] = sha(REPO / a.split)
    man_copy = json.loads((root / "split_manifest_copy.json").read_text(encoding="utf-8"))
    man_local = json.loads((REPO / "data/processed/primekg/splits/seed42.manifest.json").read_text(encoding="utf-8"))
    rep["split_manifest_matches_local"] = man_copy == man_local
    if not rep["split_manifest_matches_local"]:
        P.append("split manifest copied into the archive differs from the local manifest")

    rows, runs = [], {}
    for c, s in found:
        d = root / c / f"seed{s}"
        info = {"missing_files": [f for f in FILES if not (d / f).exists()], "has_model_pth": (d / "model.pth").exists()}
        if info["missing_files"]:
            P.append(f"{c}/seed{s} missing {info['missing_files']}")
            runs[f"{c}/seed{s}"] = info
            continue
        m = json.loads((d / "metrics.json").read_text(encoding="utf-8"))
        rc = json.loads((d / "run_config.json").read_text(encoding="utf-8"))
        au = json.loads((d / "leakage_audit.json").read_text(encoding="utf-8"))
        pr = pd.read_csv(d / "predictions.csv", dtype={"drug_id": str, "disease_id": str})
        hi = pd.read_csv(d / "history.csv")
        info.update({"git_commit": rc.get("git_commit"), "torch": rc.get("torch"), "gpu": rc.get("gpu"), "python": rc.get("python"), "utc": rc.get("utc"),
                     "leakage_all_pass": bool(au.get("all_pass")), "config_matches_dir": m["config"] == c and m["seed"] == s,
                     "pairs_equal_split_order": bool(len(pr) == len(split_rows) and (pr[["drug_id", "disease_id", "label"]].values == split_rows.values).all()),
                     "predictions_sha256": sha(d / "predictions.csv")})
        if not info["leakage_all_pass"]:
            P.append(f"{c}/seed{s} leakage audit not all_pass")
        if not info["pairs_equal_split_order"]:
            P.append(f"{c}/seed{s} predictions rows differ from the saved split's test pairs")
        rec = all_metrics(pr.label.values, pr.probability.values)
        diffs = {}
        for k_saved, k_rec in [("roc_auc", "roc_auc"), ("pr_auc_ap", "pr_auc_ap"), ("pr_auc_trapz", "pr_auc_trapz"), ("brier", "brier"), ("log_loss", "log_loss"),
                               ("ece10", "ece10"), ("precision_at_10", "precision_at_10"), ("precision_at_50", "precision_at_50"),
                               ("precision_at_100", "precision_at_100"), ("precision_at_500", "precision_at_500"), ("recall_at_500", "recall_at_500"), ("ndcg_at_500", "ndcg_at_500")]:
            if k_saved in m["test"]:
                diffs[k_saved] = abs(float(m["test"][k_saved]) - float(rec[k_rec]))
        info["max_abs_metric_diff"] = max(diffs.values())
        info["metric_diffs_over_tol"] = {k: v for k, v in diffs.items() if v > a.tol}
        if info["metric_diffs_over_tol"]:
            P.append(f"{c}/seed{s} recomputed metrics differ: {info['metric_diffs_over_tol']}")
        best_hist = int(hi.loc[hi.val_roc_auc.idxmax(), "epoch"])
        info.update({"best_epoch": m["best_epoch"], "epochs_run": m["epochs_run"], "best_epoch_matches_history": best_hist == m["best_epoch"],
                     "best_epoch_at_budget": m["best_epoch"] == 100, "val_auc_last5_slope": float(np.polyfit(hi.epoch.values[-5:], hi.val_roc_auc.values[-5:], 1)[0])})
        if not info["best_epoch_matches_history"]:
            P.append(f"{c}/seed{s} best_epoch {m['best_epoch']} != argmax(history) {best_hist}")
        runs[f"{c}/seed{s}"] = info
        rows.append({"config": c, "seed": s, "val_roc_auc": m["val"]["roc_auc"], **{f"test_{k}": v for k, v in rec.items()}, "best_epoch": m["best_epoch"],
                     "epochs_run": m["epochs_run"], "n_params": m["n_params"], "train_seconds": m["train_seconds"], "git_commit": rc.get("git_commit"), "gpu": rc.get("gpu")})
    rep["runs"] = runs
    rep["commits"] = sorted({v.get("git_commit") for v in runs.values() if v.get("git_commit")})
    rep["torch_versions"] = sorted({v.get("torch") for v in runs.values() if v.get("torch")})
    rep["gpus"] = sorted({str(v.get("gpu")) for v in runs.values()})
    rep["n_leakage_all_pass"] = sum(bool(v.get("leakage_all_pass")) for v in runs.values())
    rep["n_with_model_pth"] = sum(bool(v.get("has_model_pth")) for v in runs.values())
    rep["prediction_files_identical_pairs"] = all(v.get("pairs_equal_split_order") for v in runs.values())
    rep["runs_best_epoch_at_budget"] = sorted(k for k, v in runs.items() if v.get("best_epoch_at_budget"))
    sw = pd.DataFrame(rows).sort_values(["config", "seed"])
    sw.to_csv(out / "SEED_WISE_METRICS_historical_recomputed.csv", index=False)

    # summary tables vs per-run metrics
    saved = pd.read_csv(root / "seed_wise_metrics.csv")
    chk = saved.merge(sw[["config", "seed", "test_roc_auc", "test_pr_auc_ap"]], on=["config", "seed"], how="outer", indicator=True)
    rep["seed_wise_csv_rows"] = int(len(saved))
    rep["seed_wise_csv_matches"] = bool((chk._merge == "both").all() and np.allclose(chk["ROC-AUC"], chk.test_roc_auc, atol=a.tol)
                                        and np.allclose(chk["PR-AUC (AP)"], chk.test_pr_auc_ap, atol=a.tol))
    five = pd.read_csv(root / "five_seed_summary.csv").set_index("config")
    agg_ok = True
    for c, g in sw.groupby("config"):
        for col, key in (("ROC-AUC", "test_roc_auc"), ("PR-AUC (AP)", "test_pr_auc_ap")):
            txt = five.loc[c, col]
            mean = float(txt.split()[0])
            sd = float(txt.split("±")[1]) if "±" in txt else None
            ok = abs(mean - g[key].mean()) < 6e-5 and (sd is None or abs(sd - g[key].std(ddof=1)) < 6e-5)
            agg_ok &= ok
            if not ok:
                P.append(f"five_seed_summary {c} {col} '{txt}' != recomputed {g[key].mean():.4f} ± {g[key].std(ddof=1):.4f}")
        if int(five.loc[c, "n_seeds"]) != len(g):
            agg_ok = False
            P.append(f"five_seed_summary {c} n_seeds {five.loc[c, 'n_seeds']} != {len(g)} (smoke mixed in?)")
    rep["five_seed_summary_matches"] = bool(agg_ok)
    rep["all_checks_pass"] = not P
    (out / "artifact_verification.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in rep.items() if k != "runs"}, indent=1, default=str))


if __name__ == "__main__":
    main()
