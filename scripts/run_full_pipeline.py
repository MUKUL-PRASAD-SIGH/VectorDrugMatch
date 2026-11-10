"""
scripts/run_full_pipeline.py - one entry point for the final (Colab) experiment run. NOT executed locally.

    python scripts/run_full_pipeline.py --stage prepare            # core data build + split + validation + structure-covered variant
    python scripts/run_full_pipeline.py --stage external           # NTD mapping, Open Targets, HAI, IHME/EML (if supplied), equity table
    python scripts/run_full_pipeline.py --stage smoke              # torch_cluster check, Node2Vec 1 epoch, 5-epoch GNNs, one baseline
    python scripts/run_full_pipeline.py --stage train --variant full
    python scripts/run_full_pipeline.py --stage train --variant structcov
    python scripts/run_full_pipeline.py --stage report --variant full   # evaluation + paper results package
    python scripts/run_full_pipeline.py --stage explain --variant full  # SHAP (RF, XGBoost) + GNNExplainer (HGT, RGCN) on TEST pairs, after training
    python scripts/run_full_pipeline.py --stage all                # prepare -> external -> train/report(full) -> train/report(structcov)

Add --dry-run to print the commands without running them. Each step is logged to outputs/pipeline_log.jsonl (exit code, wall time).
A failing REQUIRED step stops the run (a validation FAIL stops everything: never train on a failed check). Steps marked optional
(inputs only you can supply: Open Targets parquet files, HAI surveys, IHME export, WHO EML list) log their failure and the run continues;
the equity table then reports those components as missing, never as 0.
Training order: classical baselines (one model per call, each result saved), Node2Vec, the five GNNs, the cold-start ablation.
Seeds and split ids come from the config; nothing here changes them.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable
CFG = {"full": "configs/primekg_morgan.yaml", "structcov": "configs/primekg_morgan_structcov.yaml"}
CFG_DP = {"full": "configs/primekg_morgan_dp.yaml", "structcov": "configs/primekg_morgan_structcov_dp.yaml"}   # baselines + train-side disease profile


def steps(stage, variant, epochs):
    """-> list of (command, optional)"""
    c = CFG[variant]
    R, O = False, True
    if stage == "prepare":
        return [([PY, "scripts/fetch_public_data.py", "--primekg"], R),
                ([PY, "scripts/primekg_dataset.py", "--config", CFG["full"]], R),
                ([PY, "scripts/primekg_split.py", "--config", CFG["full"]], R),
                ([PY, "scripts/validate_primekg_dataset.py", "--config", CFG["full"]], R),
                ([PY, "scripts/make_structure_covered_variant.py"], R),
                ([PY, "scripts/audit_models.py"], R)]
    if stage == "external":
        return [([PY, "scripts/build_ntd_mapping.py"], R),
                ([PY, "scripts/open_targets_indications.py"], O), ([PY, "scripts/validate_open_targets.py"], O),
                ([PY, "scripts/open_targets_source_attribution.py"], O),
                ([PY, "scripts/parse_hai_surveys.py"], O), ([PY, "scripts/audit_hai_parsing.py"], O),
                ([PY, "scripts/process_ihme_daly.py"], O),
                ([PY, "scripts/extract_who_eml_pdf.py"], O), ([PY, "scripts/process_who_eml.py"], O),
                ([PY, "scripts/build_equity_features.py"], R)]
    if stage == "smoke":
        return [([PY, "-c", "import torch,torch_cluster;print('torch',torch.__version__,'cuda',torch.cuda.is_available(),'torch_cluster ok')"], R),
                ([PY, "scripts/train_node2vec.py", "--config", c, "--dry-run"], R),
                ([PY, "scripts/train_node2vec.py", "--config", c, "--epochs", "1"], R),
                ([PY, "scripts/train_gnn.py", "--config", c, "--epochs", "5"], R),
                ([PY, "scripts/train_baselines.py", "--model", "logistic", "--config", c], R)]
    if stage == "train":
        s = [([PY, "scripts/train_baselines.py", "--model", m, "--config", c], R) for m in ("logistic", "nb", "xgb", "rf", "mlp")]
        s += [([PY, "scripts/train_node2vec.py", "--config", c, "--epochs", "10"], R),
              ([PY, "scripts/train_gnn.py", "--config", c, "--epochs", str(epochs)], R),
              ([PY, "scripts/run_ablations_coldstart.py", "--config", c], R)]
        d = CFG_DP[variant]                      # second baseline variant: drug + disease-profile features (same saved split and negatives)
        s += [([PY, "scripts/train_baselines.py", "--model", m, "--config", d], R) for m in ("logistic", "nb", "xgb", "rf", "mlp")]
        return s
    if stage == "report":
        d = CFG_DP[variant]
        return [([PY, "scripts/evaluate_primekg.py", "--config", c], R), ([PY, "scripts/make_results_package.py", "--config", c], R),
                ([PY, "scripts/evaluate_primekg.py", "--config", d], R)]
    if stage == "explain":
        return [([PY, "scripts/explain_models.py", "--config", c, "--models", "rf", "xgb", "--n-shap", "1000"], R),
                ([PY, "scripts/explain_models.py", "--config", c, "--gnn", "HGT", "RGCN", "--n-links", "20"], O)]
    raise ValueError(stage)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["prepare", "external", "smoke", "train", "report", "explain", "all"])
    ap.add_argument("--variant", default="full", choices=list(CFG))
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.stage == "all":
        plan = (steps("prepare", "full", a.epochs) + steps("external", "full", a.epochs) + steps("train", "full", a.epochs)
                + steps("report", "full", a.epochs) + steps("explain", "full", a.epochs) + steps("train", "structcov", a.epochs) + steps("report", "structcov", a.epochs))
    else:
        plan = steps(a.stage, a.variant, a.epochs)
    log = REPO / "outputs" / "pipeline_log.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    skipped_optional = []
    for cmd, optional in plan:
        printable = " ".join(Path(x).name if x == PY else x for x in cmd)
        print(f"\n>>> {printable}" + ("   [optional]" if optional else ""))
        if a.dry_run:
            continue
        t0 = time.time()
        rc = subprocess.run(cmd, cwd=REPO).returncode
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"cmd": printable, "returncode": rc, "optional": optional, "seconds": round(time.time() - t0, 1)}) + "\n")
        if rc != 0:
            if optional:
                skipped_optional.append(printable)
                print(f"   (optional step failed with exit {rc}; continuing: its outputs will be reported as missing)")
                continue
            sys.exit(f"STOPPED: step failed (exit {rc}): {printable}")
    print("\npipeline stage complete" + (" (dry run)" if a.dry_run else ""))
    if skipped_optional:
        print("optional steps that failed (their data is MISSING downstream):\n  " + "\n  ".join(skipped_optional))


if __name__ == "__main__":
    main()
