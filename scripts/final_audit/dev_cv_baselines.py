"""
scripts/final_audit/dev_cv_baselines.py - feature-based baselines on the final-protocol splits (CPU). Never reads the locked holdout.

    python scripts/final_audit/dev_cv_baselines.py --splits cv_fold0 cv_fold1 cv_fold2 cv_fold3 cv_fold4 final_train --out outputs/final_audit_20261117/dev_cv

Models (fixed hyper-parameters, chosen before any final-protocol result was seen; identical to the historical-split analysis):
  degree_gbm, connectivity_gbm, fingerprint_gbm, deg_conn_fp_gbm   HistGradientBoosting on src/features/simple_baselines.py groups (cross-fitted labels)
  rf_disease_profile    faithful reproduction of the historical RF + disease profile (Morgan 2048 + leave-one-out disease-profile block, RF 100 trees
                        depth 10 balanced, sigmoid-calibrated cv=3), scripts/train_baselines.py
  disease_popularity, max_tanimoto                                  single unsupervised scores
Writes <out>/<model>/<split>/seed0/{val_predictions.csv, val_popmatch_predictions.csv, metrics.json} and, for final_train, model.joblib (+ feature spec).
"""
import argparse
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "final_audit"))
from src.data.graph_builder import build_hetero_data  # noqa: E402
from src.features.disease_profile import build_disease_profile_block  # noqa: E402
from src.features.pair import build_pair_features  # noqa: E402
from src.features.simple_baselines import GROUPS, PairFeaturizer, design, feature_matrices  # noqa: E402
from src.utils.final_metrics import all_metrics  # noqa: E402
from train_gcn_protocol import load_split, mp_graph  # noqa: E402


def gbm(seed=0):
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0, random_state=seed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    data = build_hetero_data(REPO / "data/processed/primekg", include_features=True)
    fp = data["drug"].x.numpy()
    dis_x = data["disease"].x.numpy()
    ids_d, ids_s = np.asarray(data["drug"].node_ids), np.asarray(data["disease"].node_ids)
    for spn in a.splits:
        z, _ = load_split(spn)
        t0 = time.time()
        F = PairFeaturizer(mp_graph(data, z), z["edges_train"], z["y_train"], fp)
        sets = {"train": z["edges_train"], "val": z["edges_val"], "val_popmatch": z["edges_val_popmatch"]}
        feats = feature_matrices(F, sets)
        y = {k: np.asarray(z[f"y_{k}"]).astype(int) for k in sets}
        preds, models = {}, {}
        for name in GROUPS:
            m = gbm().fit(design(feats["train"], name), y["train"])
            preds[name] = {k: m.predict_proba(design(feats[k], name))[:, 1] for k in ("val", "val_popmatch")}
            models[name] = m
        preds["disease_popularity"] = {k: feats[k]["label"][:, 0] for k in ("val", "val_popmatch")}
        preds["max_tanimoto"] = {k: feats[k]["label"][:, 2] for k in ("val", "val_popmatch")}
        Xrf = {k: np.concatenate([build_pair_features(fp, dis_x, e[0], e[1]), build_disease_profile_block(fp, z["edges_train"], z["y_train"], e)], 1) for k, e in sets.items()}
        rf = CalibratedClassifierCV(estimator=RandomForestClassifier(n_estimators=100, max_depth=10, class_weight="balanced", random_state=42, n_jobs=-1),
                                    method="sigmoid", cv=3).fit(Xrf["train"], y["train"])
        preds["rf_disease_profile"] = {k: rf.predict_proba(Xrf[k])[:, 1] for k in ("val", "val_popmatch")}
        models["rf_disease_profile"] = rf
        for name, pr in preds.items():
            d = REPO / a.out / name / spn / "seed0"
            d.mkdir(parents=True, exist_ok=True)
            met = {"name": name, "split": spn, "seed": 0}
            for k, p in pr.items():
                e = sets[k]
                pd.DataFrame({"drug_id": ids_d[e[0]], "disease_id": ids_s[e[1]], "label": y[k], "probability": p}).to_csv(d / f"{k}_predictions.csv", index=False)
                met[k] = all_metrics(y[k], p)
            (d / "metrics.json").write_text(json.dumps(met, indent=1, default=float), encoding="utf-8")
            if spn == "final_train" and name in models:
                joblib.dump(models[name], d / "model.joblib")
        print(f"{spn}: {time.time() - t0:.0f}s | " + " | ".join(f"{n} {all_metrics(y['val'], p['val'])['pr_auc_ap']:.3f}" for n, p in preds.items()))


if __name__ == "__main__":
    main()
