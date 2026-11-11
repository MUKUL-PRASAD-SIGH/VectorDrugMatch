"""Tests for src/data/treats_edges.py on a tiny synthetic split (no real data, no training)."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from src.data.treats_edges import (REV, TARGET, build_variant_edges, leakage_audit, make_folds, supervision_view, train_positive_pairs)  # noqa: E402

ND, NS = 6, 8                       # drugs, diseases


class FakeGraph:
    """Minimal stand-in for HeteroData: edge_types + __getitem__(et).edge_index."""
    def __init__(self, ed):
        self._ed = ed
        self.edge_types = list(ed)

    def __getitem__(self, et):
        class _E:
            pass
        e = _E()
        e.edge_index = self._ed[et]
        return e


def _split():
    # train drugs 0,1,2 ; val drug 3 ; test drugs 4,5
    tr = np.array([[0, 0, 1, 1, 2, 2, 0, 1], [0, 1, 1, 2, 3, 4, 5, 6]])
    y_tr = np.array([1, 1, 1, 1, 1, 0, 0, 0])
    va = np.array([[3, 3], [0, 7]])
    y_va = np.array([1, 0])
    te = np.array([[4, 5, 4], [2, 3, 7]])
    y_te = np.array([1, 1, 0])
    held = np.array([[3, 4, 5], [0, 2, 3]])
    return {"edges_train": tr, "y_train": y_tr, "edges_val": va, "y_val": y_va, "edges_test": te, "y_test": y_te,
            "drugs_train": np.array([0, 1, 2]), "drugs_val": np.array([3]), "drugs_test": np.array([4, 5]), "heldout_indication_pairs": held}


def _graph(split):
    """Full graph: all positives as treats; a contraindication on a train pair; reverse edges present."""
    pos = np.concatenate([split["edges_train"][:, split["y_train"] == 1], split["edges_val"][:, split["y_val"] == 1], split["edges_test"][:, split["y_test"] == 1]], axis=1)
    contra = np.array([[2, 1], [7, 7]])
    full = {TARGET: torch.as_tensor(pos), REV: torch.as_tensor(pos).flip(0),
            ("drug", "contraindicated_for", "disease"): torch.as_tensor(contra), ("disease", "rev_contraindicated_for", "drug"): torch.as_tensor(contra).flip(0),
            ("drug", "offlabel_for", "disease"): torch.empty((2, 0), dtype=torch.long), ("disease", "rev_offlabel_for", "drug"): torch.empty((2, 0), dtype=torch.long)}
    base = dict(full)
    base[TARGET] = torch.empty((2, 0), dtype=torch.long)
    base[REV] = torch.empty((2, 0), dtype=torch.long)
    return FakeGraph(full), FakeGraph(base)


def test_variants_edge_counts_and_audit_pass():
    s = _split()
    full, base = _graph(s)
    for variant, n_treats in (("original", 0), ("train_treats", 5), ("mechanism", 0)):
        ed = build_variant_edges(base, s, variant)
        assert ed[TARGET].shape[1] == n_treats
        a = leakage_audit(ed, s, full, ND, NS, variant)
        assert a["all_pass"], {k: v for k, v in a.items() if isinstance(v, dict) and not v.get("pass", True)}
    assert build_variant_edges(base, s, "mechanism")[("drug", "contraindicated_for", "disease")].shape[1] == 0


def test_audit_detects_a_planted_heldout_leak():
    s = _split()
    full, base = _graph(s)
    ed = build_variant_edges(base, s, "train_treats")
    ed[TARGET] = torch.cat([ed[TARGET], torch.tensor([[4], [2]])], dim=1)        # a TEST positive pair added to the message-passing graph
    ed[REV] = ed[TARGET].flip(0)
    a = leakage_audit(ed, s, full, ND, NS, "train_treats")
    assert not a["all_pass"] and not a["val_test_positives_absent_from_treats"]["pass"]


def test_audit_detects_a_held_out_pair_leaking_through_the_reverse_edge_only():
    s = _split()
    full, base = _graph(s)
    ed = build_variant_edges(base, s, "original")
    ed[REV] = torch.tensor([[3], [0]])                                           # disease 3 -> drug 0 ... pair (0,3)? use the held-out pair (drug 3, disease 0)
    ed[REV] = torch.tensor([[0], [3]])                                           # (disease 0, drug 3) = reverse of held-out pair (3, 0)
    a = leakage_audit(ed, s, full, ND, NS, "original")
    assert not a["all_pass"]


def test_supervision_view_removes_supervised_positives_and_their_reverse():
    s = _split()
    pos = torch.as_tensor(train_positive_pairs(s))
    ed = {TARGET: pos, REV: pos.flip(0)}
    v = supervision_view(ed, pos, torch.tensor([0, 3]))
    assert v[TARGET].shape[1] == pos.shape[1] - 2 and v[REV].shape[1] == pos.shape[1] - 2
    removed = {tuple(pos[:, i].tolist()) for i in (0, 3)}
    kept = {tuple(c) for c in v[TARGET].t().tolist()}
    assert not (removed & kept)
    assert {tuple(c) for c in v[REV].flip(0).t().tolist()} == kept


def test_folds_partition_the_train_pairs_stratified():
    s = _split()
    folds = make_folds(5, s["y_train"], 2, np.random.default_rng(0))
    allidx = np.concatenate(folds)
    assert sorted(allidx.tolist()) == list(range(len(s["y_train"])))
    assert all(set(a).isdisjoint(set(b)) for i, a in enumerate(folds) for b in folds[i + 1:])
