"""
scripts/evaluate_primekg.py - Track B evaluation on the SAVED test split, all models on identical pairs.

    python scripts/evaluate_primekg.py --config configs/primekg_morgan.yaml

Reads every prediction CSV that train_baselines.py / train_gnn.py wrote under outputs/<exp>/ (columns
drug_id, disease_id, label, probability), keeps only rows that are exactly the saved test pairs, and reports:
  ROC-AUC, PR-AUC, MCC (threshold 0.5), Precision@K / Recall@K / MRR / NDCG@K (per disease, macro-average)
for subsets: all test pairs, NTD diseases only, fully-mapped diseases only, and by negative type
(curated vs sampled; PrimeKG has no curated negatives, so only 'sampled').
Writes outputs/<exp>/ranking_report.csv and .md. A model that does not cover every test pair is flagged.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import average_precision_score, matthews_corrcoef, roc_auc_score

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from src.utils.ranking import ranking_metrics  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/primekg_morgan.yaml")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(REPO / a.config))
    exp, ds = cfg["experiment"]["name"], cfg.get("dataset", {})
    proc, out = REPO / "data" / "processed" / exp, REPO / "outputs" / exp
    z = np.load(REPO / ds["presplit"])
    dis = pd.read_csv(proc / "diseases.csv", low_memory=False)
    e, y, cur = z["edges_test"], z["y_test"], z["curated_test"]
    test = pd.DataFrame({"drug_id": e[0], "disease_id": e[1], "label": y, "curated": cur})
    test["is_ntd"] = dis.is_ntd.values[test.disease_id].astype(int)
    test["mapped"] = (dis.mapping_status.values[test.disease_id] == "mapped")
    # structure coverage: a drug has a usable structure iff it has a SMILES AND a non-zero fingerprint.
    # Zero-fingerprint drugs are more common among sampled negatives than positives, so a model could
    # exploit "no structure => negative"; the with/no_structure subsets expose that.
    drugs = pd.read_csv(proc / "drugs.csv", low_memory=False)
    fp_nonzero = np.load(proc / "drug_features.npy", mmap_mode="r").any(axis=1)
    has_struct = (drugs.has_smiles.values == 1) & fp_nonzero
    test["has_structure"] = has_struct[test.drug_id.values]
    n_test = len(test)

    # GNN predictions carry ids; baseline cold-start predictions are in test-split order (y_true, probability).
    # CV-fold predictions (anything else) are NOT drug-disjoint and are ignored on purpose.
    files = sorted(list((out / "predictions").glob("gnn_*_predictions.csv")) + list(out.glob("baseline_*_coldstart_predictions.csv")))
    if not files:
        sys.exit(f"no prediction files under {out}. Run train_baselines.py / train_gnn.py first.")
    rows = []
    for f in files:
        p = pd.read_csv(f)
        name = f.stem.replace("_predictions", "")
        if {"drug_id", "disease_id", "probability"} <= set(p.columns):
            m = test.merge(p[["drug_id", "disease_id", "probability"]].drop_duplicates(["drug_id", "disease_id"]),
                           on=["drug_id", "disease_id"], how="left")
        elif {"y_true", "probability"} <= set(p.columns) and len(p) == n_test and (p.y_true.values == test.label.values).all():
            m = test.copy()
            m["probability"] = p.probability.values          # positional: identical test order
        else:
            print(f"  [SKIP] {f.name}: cannot be aligned to the saved test split")
            continue
        covered = int(m.probability.notna().sum())
        if covered < n_test:
            print(f"  [WARN] {name}: covers {covered}/{n_test} test pairs - scored on the covered subset only")
        m = m.dropna(subset=["probability"])
        subsets = {"all": m, "ntd_only": m[m.is_ntd == 1], "mapped_only": m[m["mapped"]],
                   "sampled_negatives": m[(m.label == 1) | (~m.curated)],
                   "with_structure": m[m.has_structure],      # sensitivity: drop zero-fingerprint drugs
                   "no_structure": m[~m.has_structure]}
        if m.curated.any():
            subsets["curated_negatives"] = m[(m.label == 1) | m.curated]
        for sub, d in subsets.items():
            r = {"model": name, "subset": sub, "pairs": len(d), "positives": int(d.label.sum()),
                 "coverage_of_test": round(covered / n_test, 4)}
            if d.label.nunique() == 2:
                r["roc_auc"] = roc_auc_score(d.label, d.probability)
                r["pr_auc"] = average_precision_score(d.label, d.probability)
                r["mcc"] = matthews_corrcoef(d.label, (d.probability >= 0.5).astype(int))
            r.update(ranking_metrics(d))
            rows.append(r)
    rep = pd.DataFrame(rows)
    rep.to_csv(out / "ranking_report.csv", index=False)
    cols = [c for c in ("model", "subset", "pairs", "positives", "roc_auc", "pr_auc", "mcc", "precision@5",
                        "recall@5", "mrr", "ndcg@10", "n_groups") if c in rep.columns]
    try:
        table = rep[cols].round(4).to_markdown(index=False)
    except ImportError:                                   # tabulate not installed
        table = "\n".join(["```", rep[cols].round(4).to_string(index=False), "```"])
    cov = test.groupby("has_structure").label.agg(pairs="size", positives="sum")
    cov["negatives"] = cov.pairs - cov.positives
    cov_txt = cov.reset_index().to_string(index=False)
    print("\nTest-split structure coverage (has_structure = SMILES and non-zero fingerprint):\n" + cov_txt)
    md = ["# Track B evaluation (saved test split)", "",
          "Structure coverage of the test pairs (`with_structure` / `no_structure` rows below are the sensitivity "
          "analysis; the primary result is the `all` row):", "", "```", cov_txt, "```", "",
          "Ranking metrics are per-disease over the split's candidate pairs (positives + sampled negatives); "
          "compare models relatively, not as absolute retrieval over all drugs.", "",
          "NTD subset is small - report counts and treat as an exploratory analysis.", "",
          table]
    (out / "ranking_report.md").write_text("\n".join(md), encoding="utf-8")
    print(rep[cols].round(4).to_string(index=False))
    print(f"\nsaved {out / 'ranking_report.csv'}")


if __name__ == "__main__":
    main()
