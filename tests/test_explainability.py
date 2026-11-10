"""Diagnostic tests for src/explainability/explain.py on TINY SYNTHETIC inputs. They check that the API runs and returns the documented
shapes/schemas. Nothing here is a scientific result and no synthetic output is saved."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.explainability.explain import (feature_names, hetero_khop_subset, morgan_bit_substructures, top_features, tree_shap,  # noqa: E402
                                        unwrap_estimator)


def _xy(n=200, f=12, seed=0):
    r = np.random.default_rng(seed)
    X = r.random((n, f)).astype("float32")
    return X, (X[:, 0] + X[:, 3] > 1).astype(int)


def test_tree_shap_random_forest_positive_class_2d():
    from sklearn.ensemble import RandomForestClassifier
    X, y = _xy()
    rf = RandomForestClassifier(n_estimators=10, max_depth=3, random_state=0).fit(X, y)
    idx, sv, base = tree_shap(rf, X, max_rows=50)
    assert sv.shape == (50, X.shape[1]) and len(idx) == 50 and np.isfinite(sv).all()
    t = top_features(sv, [f"f{i}" for i in range(X.shape[1])], top=5)
    assert list(t.columns) == ["feature", "mean_abs_shap", "mean_shap", "n_rows"] and t.feature.iloc[0] in ("f0", "f3")


def test_tree_shap_xgboost_native_contributions():
    xgb = pytest.importorskip("xgboost")
    X, y = _xy()
    m = xgb.XGBClassifier(n_estimators=10, max_depth=3, random_state=0).fit(X, y)
    idx, sv, base = tree_shap(m, X, max_rows=40)
    assert sv.shape == (40, X.shape[1]) and np.isfinite(sv).all()


def test_unwrap_calibrated_estimator():
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.ensemble import RandomForestClassifier
    X, y = _xy()
    cal = CalibratedClassifierCV(RandomForestClassifier(n_estimators=5, random_state=0), cv=3).fit(X, y)
    assert unwrap_estimator(cal).__class__.__name__ == "RandomForestClassifier"
    assert feature_names(4)[:4] == ["morgan_0", "morgan_1", "morgan_2", "morgan_3"] and len(feature_names(2048)) == 2051


def test_morgan_bit_substructures_returns_environments():
    from rdkit import Chem
    from rdkit.Chem import rdFingerprintGenerator
    mol = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    on = list(gen.GetFingerprint(mol).GetOnBits())
    envs = morgan_bit_substructures("CC(=O)Oc1ccccc1C(=O)O", on[0])
    assert len(envs) >= 1 and all(isinstance(e, str) and e for e in envs)
    assert morgan_bit_substructures("not a smiles", 5) == []


def _tiny_hetero(seed=0):
    import torch
    from torch_geometric.data import HeteroData
    torch.manual_seed(seed)
    d = HeteroData()
    d["drug"].x, d["disease"].x, d["gene"].x = torch.rand(30, 16), torch.rand(20, 3), torch.ones(15, 1)
    e = lambda a, b, k: torch.stack([torch.randint(0, a, (k,)), torch.randint(0, b, (k,))])
    d["drug", "binds", "gene"].edge_index = e(30, 15, 60)
    d["gene", "rev_binds", "drug"].edge_index = d["drug", "binds", "gene"].edge_index.flip(0)
    d["disease", "associates", "gene"].edge_index = e(20, 15, 50)
    d["gene", "rev_associates", "disease"].edge_index = d["disease", "associates", "gene"].edge_index.flip(0)
    d["gene", "interacts", "gene"].edge_index = e(15, 15, 40)
    return d


def test_hetero_khop_subset_contains_seeds_and_neighbours():
    pytest.importorskip("torch_geometric")
    d = _tiny_hetero()
    s = hetero_khop_subset(d, {"drug": [3], "disease": [4]}, k=2)
    assert 3 in s["drug"].tolist() and 4 in s["disease"].tolist() and len(s["gene"]) > 0


def test_gnn_explainer_link_runs_on_tiny_graph():
    pytest.importorskip("torch_geometric")
    import torch
    from src.explainability.explain import explain_link_gnn
    from src.models.gnn.base import GNNLinkPredictionModel
    from src.models.gnn.gcn import create_gcn_model
    d = _tiny_hetero()
    m = GNNLinkPredictionModel(create_gcn_model(d.metadata(), hidden_channels=16, out_channels=16), in_channels=16, hidden_channels=8).eval()
    with torch.no_grad():
        m(d.x_dict, d.edge_index_dict, torch.tensor([[0], [0]]))        # initialise lazy layers (the training script does this too)
    prob, edges, rel = explain_link_gnn(m, d, drug_idx=2, disease_idx=5, hops=2, epochs=10)
    assert 0.0 <= prob <= 1.0
    assert {"src_type", "relation", "dst_type", "src_node_id", "dst_node_id", "edge_mask"} <= set(edges.columns) and len(edges) > 0
    assert {"relation", "mean_edge_mask", "n_edges"} <= set(rel.columns) and len(rel) > 0
