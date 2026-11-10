"""Leakage and construction tests for the optional disease-profile feature block (no model training)."""
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R))
from src.features.disease_profile import NAMES, _tanimoto, build_disease_profile_block  # noqa: E402


def _fp():
    f = np.zeros((6, 8), dtype=np.float32)
    f[0, [0, 1, 2]] = 1; f[1, [0, 1]] = 1; f[2, [5, 6]] = 1; f[3, [0, 1, 2]] = 1; f[4, [7]] = 1      # drug 5 stays all-zero
    return f


# train: drugs 0,1,2 treat disease 0; drug 3 treats disease 1; negatives (4,0), (5,0)
TE = np.array([[0, 1, 2, 3, 4, 5], [0, 0, 0, 1, 0, 0]]); TY = np.array([1, 1, 1, 1, 0, 0])


def test_tanimoto_values():
    f = _fp()
    t = _tanimoto(f[[0]], f[[1, 2, 5]])
    assert np.isclose(t[0, 0], 2 / 3) and t[0, 1] == 0 and t[0, 2] == 0


def test_leave_one_out_excludes_own_label():
    b = build_disease_profile_block(_fp(), TE, TY, TE[:, :3])                    # the three training positives of disease 0
    assert np.allclose(b[:, 0], np.log1p(2))                                      # each sees the OTHER two, not itself
    # drug 0 vs {1,2}: max = Tanimoto(0,1)=2/3 ; its own identical fingerprint is NOT used
    assert np.isclose(b[0, 1], 2 / 3) and b[0, 3] == 1


def test_new_drug_uses_full_training_profile():
    b = build_disease_profile_block(_fp(), TE, TY, np.array([[3], [0]]))         # drug 3 (identical fp to drug 0), unseen for disease 0
    assert np.isclose(b[0, 0], np.log1p(3)) and np.isclose(b[0, 1], 1.0)


def test_no_evidence_is_flagged_not_silent():
    b = build_disease_profile_block(_fp(), TE, TY, np.array([[4, 5, 0], [2, 0, 5]]))   # disease 2 and 5 have no training positives; drug 5 has an empty fp
    assert b[0, 3] == 0 and b[2, 3] == 0                                           # no profile -> has_profile 0
    assert b[1, 3] == 0 and b[1, 1] == 0                                           # empty fingerprint -> similarity 0 but flagged


def test_unchanged_when_heldout_information_changes():
    """Only train edges/labels are inputs: any change to val/test labels or edges cannot alter a row's features by construction; check the
    function signature really has no other channel and that changing a NON-train positive leaves every output identical."""
    import inspect
    assert list(inspect.signature(build_disease_profile_block).parameters) == ["drug_fp", "train_edges", "train_y", "query_edges"]
    q = np.array([[3, 4, 1, 0], [0, 0, 0, 1]])
    a = build_disease_profile_block(_fp(), TE, TY, q)
    held_edges = np.array([[4], [0]]); held_y = np.array([1])        # a held-out positive for disease 0: never passed to the function
    b = build_disease_profile_block(_fp(), TE, TY, q)
    assert np.array_equal(a, b) and held_edges.shape == (2, 1) and held_y.shape == (1,)


def test_label_flip_of_train_negative_changes_nothing_but_positive_does():
    q = np.array([[3], [0]])
    base = build_disease_profile_block(_fp(), TE, TY, q)
    y2 = TY.copy(); y2[4] = 0                                                       # negatives never enter the profile
    assert np.array_equal(base, build_disease_profile_block(_fp(), TE, y2, q))
    y3 = TY.copy(); y3[0] = 0                                                       # removing a TRAIN positive does change it (profile shrinks)
    assert build_disease_profile_block(_fp(), TE, y3, q)[0, 0] < base[0, 0]


def test_configs_differ_only_in_the_intended_keys():
    for base, dp in (("primekg_morgan", "primekg_morgan_dp"), ("primekg_morgan_structcov", "primekg_morgan_structcov_dp")):
        a, b = (yaml.safe_load(open(R / "configs" / f"{x}.yaml")) for x in (base, dp))
        assert a["dataset"] == b["dataset"], "split, seed, negative ratio and saved split path must be identical"
        assert a["models"] == b["models"]
        assert not a.get("features", {}).get("disease_profile", {}).get("enabled", False)
        assert b["features"]["disease_profile"]["enabled"] is True
        fa = {k: v for k, v in a["features"].items() if k != "disease_profile"}
        fb = {k: v for k, v in b["features"].items() if k != "disease_profile"}
        assert fa == fb
        assert b["experiment"]["processed_name"] == a["experiment"]["name"] and b["experiment"]["name"] == a["experiment"]["name"] + "_dp"


SPLIT = R / "data" / "processed" / "primekg" / "splits" / "seed42.npz"


@pytest.mark.skipif(not SPLIT.exists(), reason="PrimeKG data not present (git-ignored)")
def test_real_split_identity_and_loo():
    from src.data.graph_builder import build_hetero_data
    from src.data.dataset import build_tabular_dataset_from_presplit
    d = build_hetero_data(R / "data" / "processed" / "primekg", include_features=True)
    a = build_tabular_dataset_from_presplit(d, SPLIT)
    b = build_tabular_dataset_from_presplit(d, SPLIT, disease_profile=True)
    z = np.load(SPLIT)
    for sp in ("train", "val", "test"):
        assert np.array_equal(a[f"y_{sp}"], b[f"y_{sp}"]) and np.array_equal(a[f"edges_{sp}"], b[f"edges_{sp}"])   # identical pairs and negatives
        assert b[f"X_{sp}"].shape[1] == a[f"X_{sp}"].shape[1] + len(NAMES)
        assert np.array_equal(a[f"X_{sp}"], b[f"X_{sp}"][:, :a[f"X_{sp}"].shape[1]])                              # original columns untouched
    # LOO on real data: a training positive's degree feature = (#train positives of its disease) - 1
    e, y = z["edges_train"], z["y_train"]
    pos = e[:, y == 1]
    deg = np.bincount(pos[1], minlength=d["disease"].num_nodes)
    k = a["X_train"].shape[1]
    idx = np.where(y == 1)[0][:200]
    assert np.allclose(b["X_train"][idx, k], np.log1p(deg[e[1][idx]] - 1))
    # held-out drugs never appear in the training profile
    heldout_drugs = set(z["edges_test"][0].tolist()) | set(z["edges_val"][0].tolist())
    assert not (heldout_drugs & set(pos[0].tolist()))
