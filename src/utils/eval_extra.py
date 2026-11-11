"""
src/utils/eval_extra.py - metrics used by the treats-edge ablation (all computed from a label vector and a probability vector).

Definitions (stated because the same words are used loosely in the literature):
* ROC-AUC          sklearn.metrics.roc_auc_score.
* PR-AUC / AP      sklearn.metrics.average_precision_score: the step-wise (non-interpolated) average precision. This is NOT the trapezoidal area under the
                   precision-recall curve (sklearn.metrics.auc(recall, precision)), which can be optimistic; the trapezoidal value is reported separately as pr_auc_trapz.
* Precision@K / Recall@K / NDCG@K   GLOBAL over the sampled test pairs: sort all pairs by score (ties broken by stable order), take the top K;
                   Precision@K = positives in top K / K; Recall@K = positives in top K / all positives; NDCG@K with binary gains and log2(rank+1) discount,
                   normalised by the ideal ordering. They describe the sampled candidate set, not a prospective search.
* Brier score      mean squared error of the probability.
* Log loss         natural-log cross-entropy (probabilities clipped to [1e-7, 1-1e-7]).
* ECE              expected calibration error, 10 equal-width bins on the predicted probability, weighted by bin size.
* Errors           false positives / false negatives at a stated threshold; "high-confidence mistakes" are errors with probability >= 0.9 (FP) or <= 0.1 (FN).
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import auc, average_precision_score, precision_recall_curve, roc_auc_score

KS = (10, 50, 100, 500)


def _order(p):
    return np.argsort(-np.asarray(p), kind="stable")


def precision_recall_ndcg_at_k(y, p, ks=KS):
    y = np.asarray(y).astype(float)
    o = _order(p)
    ys = y[o]
    n_pos = y.sum()
    out = {}
    cum = np.cumsum(ys)
    disc = 1.0 / np.log2(np.arange(2, len(ys) + 2))
    for k in ks:
        k = min(k, len(ys))
        out[f"precision_at_{k}"] = float(cum[k - 1] / k)
        out[f"recall_at_{k}"] = float(cum[k - 1] / n_pos) if n_pos else float("nan")
        dcg = float((ys[:k] * disc[:k]).sum())
        ideal = float(disc[: int(min(n_pos, k))].sum())
        out[f"ndcg_at_{k}"] = dcg / ideal if ideal else float("nan")
    return out


def ece(y, p, bins=10):
    y, p = np.asarray(y).astype(float), np.asarray(p).astype(float)
    idx = np.minimum((p * bins).astype(int), bins - 1)
    total = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            total += m.mean() * abs(y[m].mean() - p[m].mean())
    return float(total)


def classification_calibration(y, p):
    y, p = np.asarray(y).astype(float), np.asarray(p).astype(float)
    pc = np.clip(p, 1e-7, 1 - 1e-7)
    prec, rec, _ = precision_recall_curve(y, p)
    return {"roc_auc": float(roc_auc_score(y, p)), "pr_auc_ap": float(average_precision_score(y, p)), "pr_auc_trapz": float(auc(rec, prec)),
            "brier": float(np.mean((p - y) ** 2)), "log_loss": float(-np.mean(y * np.log(pc) + (1 - y) * np.log(1 - pc))), "ece10": ece(y, p)}


def errors_at(y, p, threshold, conf=0.9, top=10):
    y, p = np.asarray(y).astype(int), np.asarray(p).astype(float)
    pred = p >= threshold
    fp, fn = int(((pred) & (y == 0)).sum()), int(((~pred) & (y == 1)).sum())
    hc_fp = np.where(pred & (y == 0) & (p >= conf))[0]
    hc_fn = np.where((~pred) & (y == 1) & (p <= 1 - conf))[0]
    worst_fp = hc_fp[np.argsort(-p[hc_fp])][:top]
    worst_fn = hc_fn[np.argsort(p[hc_fn])][:top]
    return {"threshold": float(threshold), "false_positives": fp, "false_negatives": fn, "error_rate": float((fp + fn) / len(y)),
            "high_conf_false_positives": int(len(hc_fp)), "high_conf_false_negatives": int(len(hc_fn))}, worst_fp, worst_fn


def bootstrap_ci(y, p, n=3000, seed=0, alpha=0.05):
    """Percentile bootstrap over test pairs for ROC-AUC and AP. Resamples that contain one class only are skipped (counted)."""
    rng = np.random.default_rng(seed)
    y, p = np.asarray(y), np.asarray(p)
    r, a, skipped = [], [], 0
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() == y[i].max():
            skipped += 1
            continue
        r.append(roc_auc_score(y[i], p[i]))
        a.append(average_precision_score(y[i], p[i]))
    q = [100 * alpha / 2, 100 * (1 - alpha / 2)]
    return {"roc_auc_ci": [float(x) for x in np.percentile(r, q)], "pr_auc_ap_ci": [float(x) for x in np.percentile(a, q)], "n_resamples": n, "skipped": skipped}


def paired_bootstrap_diff(y, p1, p2, n=5000, seed=0, alpha=0.05):
    """Paired percentile bootstrap of (model 1 minus model 2) on the same test pairs."""
    rng = np.random.default_rng(seed)
    y, p1, p2 = np.asarray(y), np.asarray(p1), np.asarray(p2)
    dr, da = [], []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() == y[i].max():
            continue
        dr.append(roc_auc_score(y[i], p1[i]) - roc_auc_score(y[i], p2[i]))
        da.append(average_precision_score(y[i], p1[i]) - average_precision_score(y[i], p2[i]))
    q = [100 * alpha / 2, 100 * (1 - alpha / 2)]
    return {"roc_auc_diff": float(roc_auc_score(y, p1) - roc_auc_score(y, p2)), "roc_auc_diff_ci": [float(x) for x in np.percentile(dr, q)],
            "pr_auc_ap_diff": float(average_precision_score(y, p1) - average_precision_score(y, p2)), "pr_auc_ap_diff_ci": [float(x) for x in np.percentile(da, q)]}
