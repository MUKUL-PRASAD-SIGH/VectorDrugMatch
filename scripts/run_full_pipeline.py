"""
scripts/run_full_pipeline.py - one entry point for the final (Colab) experiment run. NOT executed locally.

    python scripts/run_full_pipeline.py --stage prepare            # data build + variants + validation (CPU, minutes)
    python scripts/run_full_pipeline.py --stage smoke              # 1-epoch GNNs + one fast baseline (checks the GPU env)
    python scripts/run_full_pipeline.py --stage train --variant full
    python scripts/run_full_pipeline.py --stage train --variant structcov
    python scripts/run_full_pipeline.py --stage report --variant full   # evaluation + paper results package
    python scripts/run_full_pipeline.py --stage all                # prepare -> train(full) -> report(full) -> train/report(structcov)

Add --dry-run to print the commands without running them. Each step is logged to outputs/pipeline_log.jsonl with its exit
code and wall time; the run stops at the first failing step (a validation FAIL stops everything: never train on a failed check).
Training order: classical baselines (one model per call, each result saved), Node2Vec (1-epoch test first), the five GNNs, the
cold-start ablation. Seeds and split ids come from the config; nothing here changes them.
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


def steps(stage, variant, epochs):
    c = CFG[variant]
    if stage == "prepare":
        return [
            [PY, "scripts/fetch_public_data.py", "--primekg"],
            [PY, "scripts/primekg_dataset.py", "--config", CFG["full"]],
            [PY, "scripts/primekg_split.py", "--config", CFG["full"]],
            [PY, "scripts/validate_primekg_dataset.py", "--config", CFG["full"]],
            [PY, "scripts/make_structure_covered_variant.py"],
            [PY, "scripts/build_ntd_mapping.py"],
            [PY, "scripts/open_targets_indications.py"],
            [PY, "scripts/validate_open_targets.py"],
            [PY, "scripts/parse_hai_surveys.py"],
            [PY, "scripts/build_equity_features.py"],
            [PY, "scripts/audit_models.py"],
        ]
    if stage == "smoke":
        return [[PY, "-c", "import torch,torch_cluster;print('torch',torch.__version__,'cuda',torch.cuda.is_available(),'torch_cluster ok')"],
                [PY, "scripts/train_node2vec.py", "--config", c, "--dry-run"],
                [PY, "scripts/train_node2vec.py", "--config", c, "--epochs", "1"],
                [PY, "scripts/train_gnn.py", "--config", c, "--epochs", "5"],
                [PY, "scripts/train_baselines.py", "--model", "logistic", "--config", c]]
    if stage == "train":
        s = [[PY, "scripts/train_baselines.py", "--model", m, "--config", c] for m in ("logistic", "nb", "xgb", "rf", "mlp")]
        s += [[PY, "scripts/train_node2vec.py", "--config", c, "--epochs", "10"],
              [PY, "scripts/train_gnn.py", "--config", c, "--epochs", str(epochs)],
              [PY, "scripts/run_ablations_coldstart.py", "--config", c]]
        return s
    if stage == "report":
        return [[PY, "scripts/evaluate_primekg.py", "--config", c], [PY, "scripts/make_results_package.py", "--config", c]]
    raise ValueError(stage)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["prepare", "smoke", "train", "report", "all"])
    ap.add_argument("--variant", default="full", choices=list(CFG))
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    plan = []
    if a.stage == "all":
        plan = steps("prepare", "full", a.epochs) + steps("train", "full", a.epochs) + steps("report", "full", a.epochs) \
            + steps("train", "structcov", a.epochs) + steps("report", "structcov", a.epochs)
    else:
        plan = steps(a.stage, a.variant, a.epochs)
    log = REPO / "outputs" / "pipeline_log.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    for cmd in plan:
        printable = " ".join(Path(x).name if x == PY else x for x in cmd)
        print(f"\n>>> {printable}")
        if a.dry_run:
            continue
        t0 = time.time()
        rc = subprocess.run(cmd, cwd=REPO).returncode
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"cmd": printable, "returncode": rc, "seconds": round(time.time() - t0, 1)}) + "\n")
        if rc != 0:
            sys.exit(f"STOPPED: step failed (exit {rc}): {printable}")
    print("\npipeline stage complete" + (" (dry run)" if a.dry_run else ""))


if __name__ == "__main__":
    main()
