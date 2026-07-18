"""
src/utils/experiment_logger.py - Experiment Tracking

Records experiment runs, including model configuration, 
feature ablation flags, Git commit hashes, and final metrics.
Appends results to outputs/experiment_log.jsonl.
"""

import json
import time
import subprocess
from pathlib import Path
from typing import Dict, Any

def get_git_hash() -> str:
    """Attempt to get the current Git commit hash."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], 
            stderr=subprocess.DEVNULL
        ).decode("ascii").strip()
        return commit
    except Exception:
        return "unknown"

def log_experiment(metrics: Dict[str, Any], config: Dict[str, Any], model_name: str, output_dir: Path, feature_dim: int = None):
    """
    Appends an experiment record to the experiment_log.jsonl.
    
    Args:
        metrics: Dictionary of evaluation metrics.
        config: The full configuration dictionary (loaded from config.yaml).
        model_name: The name of the model being evaluated (e.g., 'RandomForest', 'GraphSAGE').
        output_dir: Path to the outputs directory.
        feature_dim: The dimensionality of the features used.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "experiment_log.jsonl"
    
    record = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "experiment_name": config.get("experiment", {}).get("name", "unnamed"),
        "model_name": model_name,
        "git_commit": get_git_hash(),
        "feature_dim": feature_dim,
        "config": config,
        "metrics": metrics
    }
    
    with open(log_path, "a") as f:
        f.write(json.dumps(record) + "\n")
    
    print(f"  [Experiment Logger] Saved run record to {log_path.name}")
