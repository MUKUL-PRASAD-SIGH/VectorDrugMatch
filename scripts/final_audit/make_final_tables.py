"""
scripts/final_audit/make_final_tables.py - assemble the final-audit tables and manifest from saved artifacts only (no training, no new evaluation).

    python scripts/final_audit/make_final_tables.py --bundle outputs/final_audit_20261117/bundles/vdm-1.0.0

Writes reports/final_audit_20261117/{FINAL_METRICS.csv, SEED_WISE_METRICS.csv, PAIRED_COMPARISONS.csv, PREDICTIONS.csv, EXPERIMENT_MANIFEST.json}.
Every row carries `tier`: historical (seed-42 split, already examined), development (5-fold drug-grouped CV, validation only), final_holdout (evaluated once).
"""
import argparse
import glob
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
R = REPO / "reports/final_audit_20261117"
O = REPO / "outputs/final_audit_20261117"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    a = ap.parse_args()
    hold = json.loads((R / "final_holdout/HOLDOUT_RESULTS.json").read_text())

    # ---------------- FINAL_METRICS ----------------
    rows = []
    for st, S in hold["sets"].items():
        for m, v in S["models"].items():
            rows.append({"tier": "final_holdout", "candidate_set": st, "model": m, "n_seeds": len(v["per_seed"]), "n_pairs": S["n_pairs"], "n_pos": S["n_pos"],
                         **{k: v["mean"][k] for k in ("roc_auc", "pr_auc_ap", "pr_auc_trapz", "brier", "log_loss", "ece10", "precision_at_10", "precision_at_50",
                                                    "precision_at_100", "precision_at_500", "recall_at_500", "ndcg_at_500")},
                         "roc_auc_ci_low": v["roc_auc_ci"][0], "roc_auc_ci_high": v["roc_auc_ci"][1], "ap_ci_low": v["ap_ci"][0], "ap_ci_high": v["ap_ci"][1]})
    pd_means = hold["per_drug_full_ranking"]["means"]
    for comp in ("selected", "gbm", "gcn"):
        rows.append({"tier": "final_holdout", "candidate_set": "per_drug_full_ranking", "model": comp, "n_pairs": None,
                     **{k.replace(f"{comp}_", "per_drug_"): v for k, v in pd_means.items() if k.startswith(comp + "_")}})
    dev = pd.read_csv(R / "DEV_CV_SUMMARY.csv")
    for r in dev.itertuples():
        rows.append({"tier": "development", "candidate_set": "cv_val_hard", "model": r.model, "n_seeds": r.n_seeds, "n_folds": r.n_folds, "roc_auc": r.val_auc,
                     "roc_auc_sd": r.val_auc_sd, "pr_auc_ap": r.val_ap, "ap_sd": r.val_ap_sd, "popmatch_ap": r.popmatch_ap, "popmatch_auc": r.popmatch_auc, "n_params": r.n_params})
    hist = pd.read_csv(R / "phase3_historical/point_metrics_summary.csv")
    for r in hist.itertuples():
        rows.append({"tier": "historical", "candidate_set": "seed42_test", "model": r.model, "n_seeds": r.roc_auc_count, "roc_auc": r.roc_auc_mean, "roc_auc_sd": r.roc_auc_std,
                     "pr_auc_ap": r.pr_auc_ap_mean, "ap_sd": r.pr_auc_ap_std, "brier": r.brier_mean, "ece10": r.ece10_mean, "precision_at_100": r.precision_at_100_mean})
    pd.DataFrame(rows).to_csv(R / "FINAL_METRICS.csv", index=False)

    # ---------------- SEED_WISE_METRICS ----------------
    sw = []
    for st, S in hold["sets"].items():
        for m, v in S["models"].items():
            for i, ps in enumerate(v["per_seed"]):
                sw.append({"tier": "final_holdout", "candidate_set": st, "model": m, "seed_index": i, **ps})
    for f in sorted(glob.glob(str(O / "dev_cv/*/cv_fold*/seed*/metrics.json"))):
        m = json.loads(Path(f).read_text())
        sw.append({"tier": "development", "candidate_set": "cv_val_hard", "model": m["name"], "split": m["split"], "seed": m["seed"], **m["val"],
                   "popmatch_roc_auc": (m.get("val_popmatch") or {}).get("roc_auc"), "popmatch_ap": (m.get("val_popmatch") or {}).get("pr_auc_ap"),
                   "best_epoch": m.get("best_epoch"), "epochs_run": m.get("epochs_run"), "train_seconds": m.get("train_seconds"), "n_params": m.get("n_params")})
    for f in sorted(glob.glob(str(O / "final_model/*/final_train/seed*/metrics.json"))):
        m = json.loads(Path(f).read_text())
        sw.append({"tier": "final_training", "candidate_set": "final_train_internal_val", "model": m["name"], "split": "final_train", "seed": m["seed"], **m["val"],
                   "best_epoch": m["best_epoch"], "epochs_run": m["epochs_run"], "train_seconds": m["train_seconds"], "n_params": m["n_params"]})
    for r in pd.read_csv(R / "phase2_artifacts/SEED_WISE_METRICS_historical_recomputed.csv").to_dict("records"):
        sw.append({"tier": "historical", "candidate_set": "seed42_test", **{k.replace("test_", ""): v for k, v in r.items()}})
    for r in pd.read_csv(R / "convergence/convergence_seedwise.csv").to_dict("records"):
        sw.append({"tier": "historical", "candidate_set": "seed42_test", "model": "A_k4_L3_e200 (convergence rerun)", "seed": r["seed"], "roc_auc": r["test_auc_200"],
                   "pr_auc_ap": r["test_ap_200"], "best_epoch": r["best_epoch_200budget"], "epochs_run": r["epochs_run_200budget"], "train_seconds": r["train_s_200"]})
    pd.DataFrame(sw).to_csv(R / "SEED_WISE_METRICS.csv", index=False)

    # ---------------- PAIRED_COMPARISONS ----------------
    pc = []
    for r in pd.read_csv(R / "phase3_historical/PAIRED_COMPARISONS_historical.csv").to_dict("records"):
        pc.append({"tier": "historical", "candidate_set": "seed42_test", **r})
    for st, S in hold["sets"].items():
        for c in S["paired_vs_selected"]:
            pc.append({"tier": "final_holdout", "candidate_set": st, **{k: (json.dumps(v) if isinstance(v, list) else v) for k, v in c.items()}})
    cv = json.loads((R / "convergence/paired_200_vs_100.json").read_text())
    pc.append({"tier": "historical", "candidate_set": "seed42_test", "model_1": "A_k4_L3 200-epoch budget", "model_2": "A_k4_L3 100-epoch budget",
               **{k: (json.dumps(v) if isinstance(v, list) else v) for k, v in cv.items()}})
    pd.DataFrame(pc).to_csv(R / "PAIRED_COMPARISONS.csv", index=False)

    # ---------------- PREDICTIONS ----------------
    pd.read_csv(R / "final_holdout/HOLDOUT_PREDICTIONS.csv").to_csv(R / "PREDICTIONS.csv", index=False)

    # ---------------- latency of the frozen bundle (CPU) ----------------
    from src.serving.scoring import Scorer
    t0 = time.time()
    sc = Scorer(REPO / a.bundle)
    load_s = time.time() - t0
    rng = np.random.default_rng(0)
    lat = {"bundle_load_seconds": round(load_s, 2)}
    for nm, (d, s) in {"score_1000_pairs": (rng.integers(0, sc.n_drug, 1000), rng.integers(0, sc.n_dis, 1000)),
                       "rank_one_drug_all_diseases": (np.full(sc.n_dis, sc.drug_index["DB00945"]), np.arange(sc.n_dis)),
                       "rank_one_disease_all_drugs": (np.arange(sc.n_drug), np.full(sc.n_drug, sc.disease_index["MONDO:0005044"]))}.items():
        ts = []
        for _ in range(5):
            t = time.time()
            sc.score(d, s)
            ts.append(time.time() - t)
        lat[nm + "_median_seconds"] = round(float(np.median(ts)), 3)

    # ---------------- manifest ----------------
    def runs(pattern):
        out = []
        for f in sorted(glob.glob(str(O / pattern))):
            rc = json.loads(Path(f).read_text())
            out.append({k: rc.get(k) for k in ("name", "split", "seed", "git_commit", "gpu", "torch", "cuda", "python", "utc", "split_sha256", "model_sha256")})
        return out
    bundle = REPO / a.bundle
    bman = json.loads((bundle / "manifest.json").read_text())
    fm = [json.loads(Path(f).read_text()) for f in sorted(glob.glob(str(O / "final_model/*/final_train/seed*/metrics.json")))]
    man = {
        "audit": "final_audit_20261117", "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git": {"branch": "exp/final-audit-20261117", "head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
                "historical_ablation_commit": "fee2401c155e8ed8c50374e3ccf472e0e1ec60c7", "gpu_run_commits": ["3af51fd3a9c0c2bdb53bfcaf5afd2721332c7d38", "0b3d225f176e8733a779b46ae73292b18f9852e5"],
                "note": "the two GPU-run commits differ only in the notebook and the committed protocol files; training code identical (git diff d176908..HEAD on training code is empty)"},
        "data": {"primekg_source": "Harvard Dataverse 10.7910/DVN/IXA7BM (kg.csv sha256 0a5a010f...)",
                 "processed_inputs_sha256": json.loads((R / "protocol_manifest_committed.json").read_text())["inputs_sha256"],
                 "historical_split": {"file": "data/processed/primekg/splits/seed42.npz", "sha256": sha(REPO / "data/processed/primekg/splits/seed42.npz")},
                 "final_protocol": json.loads((R / "protocol_manifest_committed.json").read_text())},
        "predeclared_plan": {"file": "configs/final_audit_20261117_plan.json", "sha256": sha(REPO / "configs/final_audit_20261117_plan.json")},
        "selection": {"file": "reports/final_audit_20261117/FROZEN_SELECTION.json", "sha256": sha(R / "FROZEN_SELECTION.json")},
        "holdout_lock": json.loads((R / "HOLDOUT_EVALUATED.lock").read_text()),
        "final_model": {"bundle": bman["bundle_version"], "status": bman["status"], "kind": bman["kind"], "selected_model": bman["selected_model"],
                        "files_sha256": bman["files_sha256"], "bundle_mb": round(sum(p.stat().st_size for p in bundle.iterdir()) / 1e6, 1),
                        "gcn_params_per_seed": fm[0]["n_params"] if fm else None, "gcn_seeds": [m["seed"] for m in fm],
                        "gcn_hp": fm[0]["hp"] if fm else None, "gbm": "HistGradientBoosting(max_iter=300, lr=0.05, max_leaf_nodes=31, l2=1.0, random_state=0) on deg+conn+label features",
                        "final_gcn_training_seconds": [m["train_seconds"] for m in fm], "final_gcn_best_epochs": [m["best_epoch"] for m in fm]},
        "inference_latency_cpu_local": {**lat, "host": platform.processor(), "note": "numpy/scipy CPU path used by the API; Docker smoke test on the provisional bundle: "
                                                                                   "/rank by drug ~1.7 s, by disease ~0.35 s"},
        "gpu_runs": {"n": len(runs("*/*/*/seed*/run_config.json")) - len(runs("provisional/*/*/seed*/run_config.json")) - len(runs("smoke/*/*/seed*/run_config.json")),
                     "convergence": runs("convergence/*/*/seed*/run_config.json"), "final_model": runs("final_model/*/*/seed*/run_config.json")},
        "historical_gpu_archive": json.loads((R / "phase2_artifacts/artifact_verification.json").read_text()) | {"runs": "see phase2_artifacts/artifact_verification.json"},
        "software": {"local": {"python": platform.python_version(), "platform": platform.platform()}, "colab_gpu": "Tesla T4, torch 2.14.1+cu130, Python 3.13 (run_config.json)",
                     "serving_lock": "requirements-serving.lock"},
        "failed_or_superseded": [
            "phase3 baselines with leave-one-out label features (train/test shift) -> superseded by drug-cross-fitted features (phase3_historical_LOO_superseded/)",
            "Colab regeneration of the final protocol produced different arrays (library versions) -> exact files committed and copied (protocol_files/)",
            "Colab Drive mount outage on the first attempt (no runs lost)",
            "select_dev stage-C planning bug (re-run changed the plan); correct plan fully executed; surplus L4 seeds reported",
            "L3_train_treats, L3_mechanism, RGCN, L3_k1, L2 were all worse than L3_base on dev CV",
            "historical: B_k* (treats edges with masking), D_rgcn_B worse than no-treats controls; B0_naive is a leakage diagnostic"],
    }
    (R / "EXPERIMENT_MANIFEST.json").write_text(json.dumps(man, indent=1, default=str), encoding="utf-8")
    print(json.dumps(lat), json.dumps(man["final_model"], default=str)[:600])


if __name__ == "__main__":
    main()
