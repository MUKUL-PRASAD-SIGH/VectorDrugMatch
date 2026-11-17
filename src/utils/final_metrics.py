"""
src/utils/final_metrics.py - metrics and paired statistics used by the final audit (reports/final_audit_*).

Point metrics reuse src/utils/eval_extra.py definitions exactly (AP = step-wise average precision; trapezoidal PR-AUC reported separately; ECE with 10
equal-width bins; P/R/NDCG@K global over the sampled candidate pairs).

Resampling statistics
---------------------
`weighted_auc_ap(y, s, W)` evaluates ROC-AUC and AP for MANY bootstrap replicates at once, where each replicate is a vector of non-negative integer
weights (multinomial counts) over the test pairs. Ties are handled exactly as sklearn does (ROC-AUC: half credit for tied pos/neg; AP: one step per
distinct score). Verified against sklearn with sample_weight in tests/test_final_metrics.py.

`hierarchical_paired_bootstrap(y, S1, S2, ...)`: S1, S2 are (n_seeds, n_pairs) score matrices of two models on the SAME ordered test pairs; row j of S1
and S2 come from the same training seed (identical initial weights for the GCN configurations, see scripts/run_treats_edge_ablation.py::make_model).
Each replicate (a) resamples training seeds with replacement (level 1: seed variability) and (b) resamples test pairs with replacement, stratified by
class (level 2: test-pair sampling; positives and negatives resampled separately so every replicate has the original class counts). The statistic is
the mean over the resampled seeds of metric(S1_seed) - metric(S2_seed), computed on the resampled pairs. The SAME pair resample is applied to both
models (paired). Five seeds are therefore NOT treated as five independent test populations. Percentile 95% CI; two-sided bootstrap p-value
p = min(1, 2 * min(P(d <= 0), P(d >= 0))) (with the +1 correction). A single-seed model (e.g. a deterministic baseline) is passed as a 1-row matrix and
is broadcast against every resampled seed of the other model.

These intervals describe uncertainty over training seeds and over test pairs drawn like the fixed test set; they are NOT evidence about other drug
populations or other splits (all runs share one split).
"""
from __future__ import annotations

import numpy as np

from src.utils.eval_extra import classification_calibration, precision_recall_ndcg_at_k

KS = (10, 50, 100, 500)


def all_metrics(y, p, ks=KS):
    out = classification_calibration(y, p)
    out.update(precision_recall_ndcg_at_k(y, p, ks))
    return out


def _groups(s):
    """Descending order and distinct-score group ids (0 = highest score)."""
    o = np.argsort(-s, kind="stable")
    ss = s[o]
    g = np.concatenate([[0], np.cumsum(ss[1:] != ss[:-1])])
    return o, g, int(g[-1]) + 1


def weighted_auc_ap(y, s, W):
    """y (n,), s (n,), W (B, n) non-negative weights -> (auc (B,), ap (B,))."""
    y = np.asarray(y).astype(bool)
    s = np.asarray(s, dtype=np.float64)
    W = np.atleast_2d(np.asarray(W, dtype=np.float64))
    o, g, G = _groups(s)
    yo, Wo = y[o], W[:, o]
    B = W.shape[0]
    pos_g = np.zeros((B, G))
    neg_g = np.zeros((B, G))
    for arr, mask in ((pos_g, yo), (neg_g, ~yo)):
        idx = g[mask]
        # sum weights per group: use np.add.at on transposed view for each replicate (vectorised via bincount with offsets)
        flat = (np.arange(B)[:, None] * G + idx[None, :]).ravel()
        arr += np.bincount(flat, weights=Wo[:, mask].ravel(), minlength=B * G).reshape(B, G)
    P = pos_g.sum(1)
    N = neg_g.sum(1)
    # groups are in DESCENDING score order: negatives strictly below group k are those in groups > k
    neg_above_incl = np.cumsum(neg_g, axis=1)
    neg_below = N[:, None] - neg_above_incl
    auc = (pos_g * (neg_below + 0.5 * neg_g)).sum(1) / (P * N)
    tp = np.cumsum(pos_g, axis=1)
    fp = np.cumsum(neg_g, axis=1)
    prec = np.divide(tp, tp + fp, out=np.zeros_like(tp), where=(tp + fp) > 0)
    ap = (pos_g / P[:, None] * prec).sum(1)
    return auc, ap


def stratified_weights(y, B, rng):
    """(B, n) multinomial counts: positives and negatives resampled separately with replacement."""
    y = np.asarray(y).astype(bool)
    n = len(y)
    W = np.zeros((B, n))
    for mask in (y, ~y):
        idx = np.where(mask)[0]
        draws = rng.integers(0, len(idx), size=(B, len(idx)))
        rows = np.repeat(np.arange(B), len(idx))
        np.add.at(W, (rows, idx[draws].ravel()), 1.0)
    return W


def _boot_p(d):
    d = np.asarray(d)
    lo = (np.sum(d <= 0) + 1) / (len(d) + 1)
    hi = (np.sum(d >= 0) + 1) / (len(d) + 1)
    return float(min(1.0, 2 * min(lo, hi)))


def hierarchical_paired_bootstrap(y, S1, S2, B=2000, seed=20261117, chunk=250, pair_seeds=True):
    """See module docstring. Returns dict with point estimates, per-seed differences, CI and p-values for ROC-AUC and AP."""
    from sklearn.metrics import average_precision_score, roc_auc_score
    y = np.asarray(y).astype(int)
    S1, S2 = np.atleast_2d(S1), np.atleast_2d(S2)
    n1, n2 = S1.shape[0], S2.shape[0]
    rng = np.random.default_rng(seed)
    pt1 = np.array([[roc_auc_score(y, s), average_precision_score(y, s)] for s in S1])
    pt2 = np.array([[roc_auc_score(y, s), average_precision_score(y, s)] for s in S2])
    paired = pair_seeds and n1 == n2 and n1 > 1
    if paired:
        per_seed = pt1 - pt2
    else:
        per_seed = pt1 - pt2.mean(0) if n2 == 1 else pt1.mean(0, keepdims=True) - pt2 if n1 == 1 else None
    d_auc, d_ap = [], []
    done = 0
    while done < B:
        b = min(chunk, B - done)
        W = stratified_weights(y, b, rng)
        if paired:
            sidx = rng.integers(0, n1, size=(b, n1))
            sidx2 = sidx
        else:
            sidx = rng.integers(0, n1, size=(b, n1)) if n1 > 1 else np.zeros((b, 1), int)
            sidx2 = rng.integers(0, n2, size=(b, n2)) if n2 > 1 else np.zeros((b, 1), int)
        # evaluate each distinct seed once per chunk, then average over the resampled seed indices
        r1 = np.stack([np.stack(weighted_auc_ap(y, S1[j], W), axis=1) for j in range(n1)])   # (n1, b, 2)
        r2 = np.stack([np.stack(weighted_auc_ap(y, S2[j], W), axis=1) for j in range(n2)])   # (n2, b, 2)
        ar = np.arange(b)[:, None]
        m1 = r1[sidx, ar].mean(1)
        m2 = r2[sidx2, ar].mean(1)
        d = m1 - m2
        d_auc.append(d[:, 0])
        d_ap.append(d[:, 1])
        done += b
    d_auc, d_ap = np.concatenate(d_auc), np.concatenate(d_ap)
    q = [2.5, 97.5]
    out = {
        "n_pairs": int(len(y)), "n_pos": int(y.sum()), "n_neg": int((1 - y).sum()), "n_seeds_1": n1, "n_seeds_2": n2, "seed_paired": bool(paired),
        "B": int(B), "rng_seed": int(seed),
        "roc_auc_1_mean": float(pt1[:, 0].mean()), "roc_auc_2_mean": float(pt2[:, 0].mean()),
        "ap_1_mean": float(pt1[:, 1].mean()), "ap_2_mean": float(pt2[:, 1].mean()),
        "roc_auc_diff": float(pt1[:, 0].mean() - pt2[:, 0].mean()), "roc_auc_diff_ci": [float(x) for x in np.percentile(d_auc, q)], "roc_auc_p": _boot_p(d_auc),
        "ap_diff": float(pt1[:, 1].mean() - pt2[:, 1].mean()), "ap_diff_ci": [float(x) for x in np.percentile(d_ap, q)], "ap_p": _boot_p(d_ap),
    }
    if per_seed is not None:
        out["per_seed_roc_auc_diff"] = [float(x) for x in per_seed[:, 0]]
        out["per_seed_ap_diff"] = [float(x) for x in per_seed[:, 1]]
        out["per_seed_roc_auc_diff_sd"] = float(np.std(per_seed[:, 0], ddof=1)) if len(per_seed) > 1 else None
        out["per_seed_ap_diff_sd"] = float(np.std(per_seed[:, 1], ddof=1)) if len(per_seed) > 1 else None
        out["n_seeds_favouring_1_roc_auc"] = int((per_seed[:, 0] > 0).sum())
        out["n_seeds_favouring_1_ap"] = int((per_seed[:, 1] > 0).sum())
    return out


def holm(pvals):
    """Holm-Bonferroni adjusted p-values (same order as input)."""
    p = np.asarray(pvals, dtype=float)
    o = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    run = 0.0
    for r, i in enumerate(o):
        run = max(run, (m - r) * p[i])
        adj[i] = min(1.0, run)
    return adj.tolist()
