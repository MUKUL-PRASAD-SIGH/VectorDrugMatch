"""
scripts/summarize_treats_ablation.py - aggregate the runs of scripts/run_treats_edge_ablation.py into seed-wise and five-seed tables.

    python scripts/summarize_treats_ablation.py [--root outputs/treats_edge_ablation_20261111] [--reference A_orig]

Reads  <root>/<config>/seed<seed>/{metrics.json, predictions.csv}
Writes <root>/seed_wise_metrics.csv, five_seed_summary.csv, paired_vs_<reference>.csv, README_results.md
Mean +- SAMPLE standard deviation (ddof=1) over the seeds present; the number of seeds is shown. Nothing is selected by test score: validation ROC-AUC is
shown next to test ROC-AUC. Paired differences use the SAME test pairs and the same seed. No claim of superiority is generated.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from_root = Path(__file__).resolve().parents[1]
import sys  # noqa: E402

sys.path.insert(0, str(from_root))
from src.utils.eval_extra import paired_bootstrap_diff  # noqa: E402

COLS = [("val.roc_auc", "val ROC-AUC"), ("test.roc_auc", "ROC-AUC"), ("test.pr_auc_ap", "PR-AUC (AP)"), ("test.pr_auc_trapz", "PR-AUC (trapz)"), ("test.brier", "Brier"),
        ("test.log_loss", "log loss"), ("test.ece10", "ECE10"), ("test.precision_at_10", "P@10"), ("test.precision_at_50", "P@50"), ("test.precision_at_100", "P@100"),
        ("test.precision_at_500", "P@500"), ("test.recall_at_500", "R@500"), ("test.ndcg_at_500", "NDCG@500"), ("test_errors.false_positives", "FP"),
        ("test_errors.false_negatives", "FN"), ("test_errors.error_rate", "error rate"), ("test_errors.high_conf_false_positives", "HC-FP"),
        ("test_errors.high_conf_false_negatives", "HC-FN"), ("n_params", "params"), ("train_seconds", "train s"), ("inference_seconds_val_plus_test", "inference s"), ("best_epoch", "best epoch")]


def get(d, path):
    for k in path.split("."):
        d = d[k]
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="outputs/treats_edge_ablation_20261111")
    ap.add_argument("--reference", default="A_orig")
    a = ap.parse_args()
    root = from_root / a.root
    rows = []
    for mj in sorted(root.glob("*/seed*/metrics.json")):
        if "smoke" in mj.parts:
            continue
        m = json.loads(mj.read_text(encoding="utf-8"))
        r = {"config": m["config"], "seed": m["seed"], "arch": m["arch"], "variant": m["variant"], "k": m["k"], "masked": m["mask_supervised_edges"]}
        for path, name in COLS:
            r[name] = get(m, path)
        rows.append(r)
    if not rows:
        raise SystemExit(f"no completed runs under {root}")
    sw = pd.DataFrame(rows).sort_values(["config", "seed"])
    sw.to_csv(root / "seed_wise_metrics.csv", index=False)
    num = [n for _, n in COLS]
    g = sw.groupby("config")
    summ = pd.concat({"n_seeds": g.size()}, axis=1)
    for n in num:
        summ[n] = [f"{g[n].mean()[c]:.4f} ± {g[n].std(ddof=1)[c]:.4f}" if g.size()[c] > 1 else f"{g[n].mean()[c]:.4f} (1 seed)" for c in summ.index]
    summ.to_csv(root / "five_seed_summary.csv")
    # paired differences against the reference configuration, same seed, same test pairs
    prow = []
    for cfg in sorted(set(sw.config) - {a.reference}):
        for s in sorted(set(sw[sw.config == cfg].seed) & set(sw[sw.config == a.reference].seed)):
            p1 = pd.read_csv(root / cfg / f"seed{s}" / "predictions.csv")
            p0 = pd.read_csv(root / a.reference / f"seed{s}" / "predictions.csv")
            assert (p1.drug_id.values == p0.drug_id.values).all() and (p1.disease_id.values == p0.disease_id.values).all() and (p1.label.values == p0.label.values).all(), "different test pairs"
            d = paired_bootstrap_diff(p1.label.values, p1.probability.values, p0.probability.values, n=2000, seed=s)
            prow.append({"config": cfg, "reference": a.reference, "seed": s, **{k: (v if not isinstance(v, list) else f"[{v[0]:.4f}, {v[1]:.4f}]") for k, v in d.items()}})
    pd.DataFrame(prow).to_csv(root / f"paired_vs_{a.reference}.csv", index=False)
    show = ["n_seeds", "val ROC-AUC", "ROC-AUC", "PR-AUC (AP)", "Brier", "ECE10", "P@100", "P@500", "NDCG@500", "error rate", "params"]
    md = ["# Treats-edge ablation: five-seed summary (auto-generated)\n",
          "Mean ± sample SD over the seeds listed in `n_seeds`; the split is the fixed saved seed-42 split for every row; see `README.md` for the design and `Docs/` for caveats.\n",
          summ[show].to_markdown(), "\n",
          f"Paired differences versus `{a.reference}` (same seed, same test pairs; 2,000-resample percentile bootstrap per seed) are in `paired_vs_{a.reference}.csv`.\n",
          "Reference results of the unchanged feature-based models on the same split (from `reports/research_validation_20261111/five_seed_performance.csv`, five seeds): "
          "RF + disease profile ROC-AUC 0.8049 ± 0.0020, PR-AUC 0.6113 ± 0.0078 (PrimeKG); XGBoost + disease profile 0.8433 ± 0.0000 / 0.6979 ± 0.0000 (structure-covered subset, not directly comparable with the PrimeKG rows).\n"]
    (root / "README_results.md").write_text("\n".join(md), encoding="utf-8")
    print(summ[show].to_string())


if __name__ == "__main__":
    main()
