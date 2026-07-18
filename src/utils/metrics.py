"""
src/utils/metrics.py - Unified Evaluation Metrics

All models (baselines + GNNs) are evaluated using the same metrics
for a fair comparison in the research paper.
"""

from typing import Optional

import numpy as np

try:
    from sklearn.metrics import (
        roc_auc_score,
        average_precision_score,
        f1_score,
        precision_score,
        recall_score,
        matthews_corrcoef,
        confusion_matrix,
        classification_report,
    )
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


def compute_all_metrics(y_true: np.ndarray, y_pred_proba: np.ndarray,
                         threshold: float = 0.5) -> dict:
    """Compute all evaluation metrics for a binary classifier.

    Args:
        y_true: Ground truth labels (0 or 1).
        y_pred_proba: Predicted probabilities [0, 1].
        threshold: Decision threshold for converting probabilities to labels.

    Returns:
        Dictionary with: roc_auc, pr_auc, f1, precision, recall, mcc, accuracy.
    """
    if not SKLEARN_AVAILABLE:
        raise ImportError("scikit-learn required for metrics computation.")

    y_pred = (y_pred_proba >= threshold).astype(int)

    metrics = {}

    # ROC-AUC (requires both classes present)
    try:
        metrics["roc_auc"] = round(roc_auc_score(y_true, y_pred_proba), 4)
    except ValueError:
        metrics["roc_auc"] = 0.0

    # PR-AUC (Average Precision)
    try:
        metrics["pr_auc"] = round(average_precision_score(y_true, y_pred_proba), 4)
    except ValueError:
        metrics["pr_auc"] = 0.0

    # Classification metrics
    metrics["f1"] = round(f1_score(y_true, y_pred, zero_division=0), 4)
    metrics["precision"] = round(precision_score(y_true, y_pred, zero_division=0), 4)
    metrics["recall"] = round(recall_score(y_true, y_pred, zero_division=0), 4)
    metrics["mcc"] = round(matthews_corrcoef(y_true, y_pred), 4)
    metrics["accuracy"] = round(np.mean(y_true == y_pred), 4)

    return metrics


def format_metrics_table(model_results: list[dict]) -> str:
    """Format a list of model results into a readable comparison table.

    Args:
        model_results: List of dicts with keys: name, type, roc_auc, pr_auc, f1, mcc.

    Returns:
        Formatted string table.
    """
    header = f"{'Model':<25} {'Type':<8} {'ROC-AUC':>15} {'PR-AUC':>15} {'F1':>13} {'MCC':>13}"
    sep = "-" * len(header)

    lines = [sep, header, sep]
    for r in model_results:
        roc_str = f"{r.get('roc_auc', 0):.4f}"
        if "roc_auc_std" in r: roc_str += f" ± {r['roc_auc_std']:.4f}"
        
        pr_str = f"{r.get('pr_auc', 0):.4f}"
        if "pr_auc_std" in r: pr_str += f" ± {r['pr_auc_std']:.4f}"
        
        f1_str = f"{r.get('f1', 0):.4f}"
        if "f1_std" in r: f1_str += f" ± {r['f1_std']:.4f}"
        
        mcc_str = f"{r.get('mcc', 0):.4f}"
        if "mcc_std" in r: mcc_str += f" ± {r['mcc_std']:.4f}"
        
        line = (
            f"{r['name']:<25} "
            f"{r.get('type', 'base'):<8} "
            f"{roc_str:>15}  "
            f"{pr_str:>15}  "
            f"{f1_str:>13}  "
            f"{mcc_str:>13}"
        )
        lines.append(line)
    lines.append(sep)

    return "\n".join(lines)


def print_metrics(model_name: str, metrics: dict, model_type: str = "base"):
    """Pretty-print metrics for a single model."""
    print(f"\n  {'-' * 40}")
    print(f"  {model_name} ({model_type})")
    print(f"  {'-' * 40}")
    for key, val in metrics.items():
        if key not in ("name", "type"):
            print(f"    {key:<12}: {val:.4f}")
