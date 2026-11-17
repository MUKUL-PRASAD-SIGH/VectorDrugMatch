"""Integrity of the final evaluation protocol (data/processed/primekg/splits_final_20261117). Skipped when the protocol files are absent."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
D = REPO / "data/processed/primekg/splits_final_20261117"
pytestmark = pytest.mark.skipif(not (D / "protocol_manifest.json").exists(), reason="final protocol not generated")


def _k(e, n=17080):
    return np.asarray(e[0], np.int64) * n + np.asarray(e[1], np.int64)


def test_hashes_match_committed_manifest():
    committed = json.loads((REPO / "reports/final_audit_20261117/protocol_manifest_committed.json").read_text())
    for name, info in committed["files"].items():
        assert hashlib.sha256((D / name).read_bytes()).hexdigest() == info["sha256"], name
    assert hashlib.sha256((D / "holdout_LOCKED.npz").read_bytes()).hexdigest() == committed["holdout"]["sha256"]


def test_drug_disjoint_and_holdout_excluded_everywhere():
    h = np.load(D / "holdout_LOCKED.npz")
    hold = set(h["drugs_holdout"].tolist())
    hk = _k(h["holdout_indication_pairs"])
    val_drugs = []
    for f in [f"cv_fold{i}" for i in range(5)] + ["final_train"]:
        z = np.load(D / f"{f}.npz")
        tr, va = set(z["drugs_train"].tolist()), set(z["drugs_val"].tolist())
        assert not tr & va and not tr & hold and not va & hold
        for nm in ("train", "val", "val_popmatch"):
            assert not set(z[f"edges_{nm}"][0].tolist()) & hold
        ex = _k(z["exclude_from_graph_pairs"])
        assert np.isin(hk, ex).all()                                            # holdout positives always removed from the graph
        vpos = z["edges_val"][:, z["y_val"] == 1]
        assert np.isin(_k(vpos), ex).all()
        assert not np.isin(_k(z["edges_train"][:, z["y_train"] == 1]), ex).any()   # training positives are not excluded
        if f.startswith("cv"):
            val_drugs.append(va)
    allv = set().union(*val_drugs)
    assert sum(len(v) for v in val_drugs) == len(allv)                          # CV folds partition the development drugs


def test_popmatch_negatives_have_matched_marginals():
    z = np.load(D / "cv_fold0.npz")
    e, y = z["edges_val_popmatch"], z["y_val_popmatch"]
    pos_d, neg_d = np.bincount(e[0, y == 1], minlength=7957), np.bincount(e[0, y == 0], minlength=7957)
    m = pos_d > 0
    assert np.corrcoef(pos_d[m], neg_d[m] / 5)[0, 1] > 0.8                      # drug frequency of negatives tracks that of positives
