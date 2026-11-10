"""
src/utils/ranking.py - per-group ranking metrics for drug repurposing.

For each group (a disease), candidates are ranked by predicted probability and we compute
Precision@K, Recall@K, reciprocal rank of the first true drug, and NDCG@K (binary gains); then
average over groups that have at least one positive.

NOTE: candidate lists are the saved split's pairs (positives + sampled negatives), so they are much
shorter than "all 7,957 drugs". Treat these as relative model comparisons, not as absolute retrieval
rates over the whole drug universe.
"""
import numpy as np
import pandas as pd

KS = (1, 5, 10)


def _one_group(y: np.ndarray, p: np.ndarray, ks=KS) -> dict:
    order = np.argsort(-p, kind="mergesort")
    y = y[order]
    n_pos = int(y.sum())
    res = {}
    for k in ks:
        top = y[:k]
        res[f"precision@{k}"] = top.sum() / k
        res[f"recall@{k}"] = top.sum() / n_pos
        disc = 1.0 / np.log2(np.arange(2, len(top) + 2))
        ideal = np.sort(y)[::-1][:k]
        res[f"ndcg@{k}"] = float((top * disc).sum() / (ideal * disc[:len(ideal)]).sum())
    hit = np.flatnonzero(y == 1)
    res["mrr"] = 1.0 / (hit[0] + 1)
    return res


def ranking_metrics(df: pd.DataFrame, group_col="disease_id", label_col="label", score_col="probability",
                    ks=KS) -> dict:
    """df has one row per candidate pair. Returns macro-averaged metrics + number of groups used."""
    rows = []
    for _, g in df.groupby(group_col):
        y = g[label_col].to_numpy().astype(int)
        if y.sum() == 0:
            continue
        rows.append(_one_group(y, g[score_col].to_numpy(), ks))
    if not rows:
        return {"n_groups": 0}
    out = {k: float(np.mean([r[k] for r in rows])) for k in rows[0]}
    out["n_groups"] = len(rows)
    return out
