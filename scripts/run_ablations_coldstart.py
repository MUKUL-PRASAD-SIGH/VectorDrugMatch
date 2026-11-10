"""
scripts/run_ablations_coldstart.py - feature-group ablation on the SAVED drug-disjoint split (replaces the pooled 5-fold CV of
scripts/run_ablations.py, which is NOT drug-disjoint and must not be used for the PrimeKG paper).

    python scripts/run_ablations_coldstart.py --config configs/primekg_morgan.yaml          # Colab (trains Random Forests)

Protocol: fit on the train split, choose the decision threshold on the validation split (Youden), score the test split once.
Arms (all use the same pairs / labels / negatives):
    full                 drug fingerprint + disease features
    drug_only            drug fingerprint only
    disease_only         disease features only (no chemistry)
    shuffled_labels      full features, TRAIN labels permuted  -> must give ROC-AUC ~ 0.5 (leakage / pipeline sanity control)
    zero_drug_features   fingerprint replaced by zeros -> what the model can learn without any chemistry
Reported on: all test pairs, drugs with structure, drugs without structure, NTD diseases (counts always shown).
Output: outputs/<exp>/ablation_coldstart.csv and .json  (+ seed and split file).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from src.data.dataset import build_tabular_dataset  # noqa: E402
from src.data.graph_builder import build_hetero_data  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/primekg_morgan.yaml")
    ap.add_argument("--n-estimators", type=int, default=None)
    a = ap.parse_args()
    cfg = yaml.safe_load(open(REPO / a.config))
    exp, ds = cfg["experiment"]["name"], cfg["dataset"]
    seed = ds.get("random_seed", 42)
    proc, out = REPO / "data" / "processed" / exp, REPO / "outputs" / exp
    out.mkdir(parents=True, exist_ok=True)
    data = build_hetero_data(proc, include_features=True)
    sp = build_tabular_dataset(data, presplit=ds["presplit"], random_state=seed)
    d_dim = data["drug"].x.shape[1]
    drugs = pd.read_csv(proc / "drugs.csv", low_memory=False)
    dis = pd.read_csv(proc / "diseases.csv", low_memory=False)
    has_struct = (drugs.has_smiles.values == 1) & np.load(proc / "drug_features.npy", mmap_mode="r").any(axis=1)
    et = sp["edges_test"]
    masks = {"all": np.ones(len(et[0]), bool), "with_structure": has_struct[et[0]], "no_structure": ~has_struct[et[0]],
             "ntd_only": dis.is_ntd.values[et[1]] == 1}
    rf_kw = dict(cfg.get("models", {}).get("rf", {}))
    if a.n_estimators:
        rf_kw["n_estimators"] = a.n_estimators
    rng = np.random.default_rng(seed)
    arms = {
        "full": (lambda X: X, False), "drug_only": (lambda X: X[:, :d_dim], False), "disease_only": (lambda X: X[:, d_dim:], False),
        "shuffled_labels": (lambda X: X, True),
        "zero_drug_features": (lambda X: np.hstack([np.zeros((len(X), d_dim), X.dtype), X[:, d_dim:]]), False),
    }
    rows = []
    for name, (tf, shuffle) in arms.items():
        ytr = rng.permutation(sp["y_train"]) if shuffle else sp["y_train"]
        clf = RandomForestClassifier(random_state=seed, n_jobs=-1, class_weight="balanced", **rf_kw).fit(tf(sp["X_train"]), ytr)
        pv, pt = clf.predict_proba(tf(sp["X_val"]))[:, 1], clf.predict_proba(tf(sp["X_test"]))[:, 1]
        fpr, tpr, thr = roc_curve(sp["y_val"], pv)
        t = float(thr[np.argmax(tpr - fpr)])
        for sub, m in masks.items():
            yy, pp = sp["y_test"][m], pt[m]
            r = {"arm": name, "subset": sub, "n": int(m.sum()), "positives": int(yy.sum()), "threshold": t, "seed": seed}
            if len(np.unique(yy)) == 2:
                r.update(roc_auc=float(roc_auc_score(yy, pp)), pr_auc=float(average_precision_score(yy, pp)))
            rows.append(r)
        print(name, {r["subset"]: round(r.get("roc_auc", float("nan")), 4) for r in rows if r["arm"] == name})
    df = pd.DataFrame(rows)
    df.to_csv(out / "ablation_coldstart.csv", index=False)
    (out / "ablation_coldstart.json").write_text(json.dumps({"config": a.config, "split": ds["presplit"], "rf": rf_kw, "rows": rows}, indent=2), encoding="utf-8")
    print("saved", out / "ablation_coldstart.csv")


if __name__ == "__main__":
    main()
