"""Weighted (bootstrap) ROC-AUC / AP must equal sklearn with sample_weight, including ties; hierarchical bootstrap sanity."""
import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

from src.utils.final_metrics import hierarchical_paired_bootstrap, holm, stratified_weights, weighted_auc_ap


def test_weighted_auc_ap_matches_sklearn_with_ties():
    rng = np.random.default_rng(0)
    y = rng.random(400) < 0.2
    s = np.round(rng.random(400) + 0.4 * y, 2)          # rounding creates ties
    W = stratified_weights(y, 20, rng)
    auc, ap = weighted_auc_ap(y, s, W)
    for b in range(20):
        assert abs(auc[b] - roc_auc_score(y, s, sample_weight=W[b])) < 1e-10
        assert abs(ap[b] - average_precision_score(y, s, sample_weight=W[b])) < 1e-10


def test_unit_weights_equal_point_estimate():
    rng = np.random.default_rng(1)
    y = rng.random(300) < 0.3
    s = rng.random(300) + 0.5 * y
    auc, ap = weighted_auc_ap(y, s, np.ones((1, 300)))
    assert abs(auc[0] - roc_auc_score(y, s)) < 1e-12 and abs(ap[0] - average_precision_score(y, s)) < 1e-12


def test_stratified_weights_keep_class_counts():
    y = np.array([1] * 30 + [0] * 70, bool)
    W = stratified_weights(y, 50, np.random.default_rng(2))
    assert (W[:, y].sum(1) == 30).all() and (W[:, ~y].sum(1) == 70).all()


def test_hierarchical_bootstrap_detects_and_rejects_difference():
    rng = np.random.default_rng(3)
    y = (rng.random(1500) < 0.17).astype(int)
    good = np.stack([y * 1.0 + rng.normal(0, 0.8, len(y)) for _ in range(5)])
    bad = np.stack([y * 0.4 + rng.normal(0, 0.8, len(y)) for _ in range(5)])
    r = hierarchical_paired_bootstrap(y, good, bad, B=300, seed=1)
    assert r["roc_auc_diff"] > 0 and r["roc_auc_diff_ci"][0] > 0 and r["roc_auc_p"] < 0.05
    same = hierarchical_paired_bootstrap(y, good, good, B=100, seed=1)
    assert same["roc_auc_diff"] == 0 and same["roc_auc_p"] == 1.0
    one = hierarchical_paired_bootstrap(y, good, bad[:1], B=100, seed=1)      # single-seed reference is broadcast
    assert one["n_seeds_2"] == 1 and len(one["per_seed_roc_auc_diff"]) == 5


def test_holm():
    assert holm([0.01, 0.04, 0.03]) == [0.03, 0.06, 0.06]
