"""
src/explainability/explain.py - explainability utilities (no training happens here).

Which method is appropriate for which model (decision record):
  * Random Forest, XGBoost  -> SHAP TreeExplainer (exact, fast). Appropriate. Explains the UNCALIBRATED base estimator: sigmoid calibration is a monotone
    map of the same score, so feature attributions describe the ranking, not the calibrated probability. 2,048 Morgan bits are hashed substructures:
    attributions are mapped back to atom environments of a given drug with `morgan_bit_substructures` (a bit can collide: several environments).
  * Logistic Regression     -> coefficients (a linear model; SHAP adds nothing). Not implemented here: read `coef_` of the saved estimator.
  * MLP, Naive Bayes        -> NOT implemented: model-agnostic SHAP (kernel) on 2,051 sparse binary inputs is expensive and unstable, and the
    attributions would explain a model that is not part of the headline comparison. Documented limitation, not a gap to paper over.
  * Node2Vec + LR           -> NOT appropriate: its inputs are learned embedding products (Hadamard); feature-level attributions have no biological meaning.
  * GNNs (GCN, GraphSAGE, GAT, RGCN, HGT) -> PyG GNNExplainer on a k-hop neighbourhood of one (drug, disease) pair: edge masks (which relations / neighbours
    drove this prediction) and node-feature masks. Instance-level and model-specific: it says what the MODEL used, not what is causally true; masks can be
    unstable across runs, so report them with the seed and treat them as hypotheses.
Held-out discipline: explain the COLD-START models (saved by train_baselines.py as baseline_<key>_coldstart.pkl, by train_gnn.py as gnn_<name>.pth) on TEST pairs.
The pooled all-data baseline_<key>.pkl has seen the test pairs and is for global importance only.

Output schemas (written by scripts/explain_models.py to outputs/<exp>/explain/):
  shap_<key>_top_features.csv  feature, mean_abs_shap, mean_shap, n_rows            (global importance on test pairs)
  shap_<key>_values.npz        idx (test-row indices), shap (n, features), base_value
  shap_<key>_bit_substructures.csv  bit, mean_abs_shap, example_drug_id, example_smiles, environment_smiles (| separated)
  gnn_<name>_link_explanations.csv  drug_id, disease_id, label, prob, src_type, relation, dst_type, src_node_id, dst_node_id, edge_mask
  gnn_<name>_relation_importance.csv drug_id, disease_id, relation, mean_edge_mask, n_edges
"""
import numpy as np
import pandas as pd

DISEASE_FEATURE_NAMES = ("is_ntd", "daly_normalized", "daly_rate_log")      # src/features/disease.disease_feature_vector


def feature_names(drug_dim: int, disease_names=DISEASE_FEATURE_NAMES):
    return [f"morgan_{i}" for i in range(drug_dim)] + list(disease_names)


def unwrap_estimator(model):
    """Saved baseline (joblib) -> fitted base estimator (first clone of a CalibratedClassifierCV)."""
    if hasattr(model, "calibrated_classifiers_"):
        return model.calibrated_classifiers_[0].estimator
    return model


def tree_shap(estimator, X, max_rows=1000, seed=0):
    """-> (row_indices, shap (n, f) for the POSITIVE class, base_value). XGBoost uses its native contributions (shap.TreeExplainer breaks on some versions)."""
    rng = np.random.default_rng(seed)
    idx = np.sort(rng.choice(len(X), min(max_rows, len(X)), replace=False))
    if estimator.__class__.__name__.startswith("XGB"):
        import xgboost as xgb
        c = estimator.get_booster().predict(xgb.DMatrix(X[idx]), pred_contribs=True)
        return idx, c[:, :-1], float(c[0, -1])
    import shap
    ex = shap.TreeExplainer(estimator)
    sv, ev = ex.shap_values(X[idx]), ex.expected_value
    if isinstance(sv, list):
        sv, ev = sv[1], np.atleast_1d(ev)[1]
    elif getattr(sv, "ndim", 2) == 3:
        sv, ev = sv[:, :, 1], np.atleast_1d(ev)[1]
    return idx, sv, float(ev)


def top_features(sv, names, top=25):
    d = pd.DataFrame({"feature": names, "mean_abs_shap": np.abs(sv).mean(0), "mean_shap": sv.mean(0)})
    d["n_rows"] = sv.shape[0]
    return d.sort_values("mean_abs_shap", ascending=False).head(top).reset_index(drop=True)


def morgan_bit_substructures(smiles, bit, radius=2, n_bits=2048, max_envs=3):
    """Atom environments (as SMILES) that set `bit` in this molecule's Morgan fingerprint (same radius/size as src/features/drug.py)."""
    from rdkit import Chem
    from rdkit.Chem import rdFingerprintGenerator
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return []
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=n_bits)
    ao = rdFingerprintGenerator.AdditionalOutput()
    ao.AllocateBitInfoMap()
    gen.GetFingerprint(mol, additionalOutput=ao)
    envs = []
    for atom, r in ao.GetBitInfoMap().get(int(bit), [])[:max_envs]:
        if r == 0:
            envs.append(mol.GetAtomWithIdx(atom).GetSymbol())
            continue
        path = Chem.FindAtomEnvironmentOfRadiusN(mol, r, atom)
        amap = {}
        sub = Chem.PathToSubmol(mol, path, atomMap=amap)
        envs.append(Chem.MolToSmiles(sub))
    return envs


def hetero_khop_subset(data, seeds, k=2, max_neighbors=50, rng=None):
    """BFS over ALL edge types of a HeteroData from seed nodes (dict type -> list of ids); at most `max_neighbors` new nodes per frontier node and edge type.
    Returns dict type -> sorted LongTensor of node ids."""
    import torch
    rng = rng or np.random.default_rng(0)
    nodes = {t: set(int(i) for i in seeds.get(t, [])) for t in data.node_types}
    frontier = {t: set(v) for t, v in nodes.items()}
    for _ in range(k):
        new = {t: set() for t in data.node_types}
        for (s, _r, d), store in data.edge_items():
            ei = store.edge_index
            if ei.numel() == 0 or not frontier[s]:
                continue
            f = torch.as_tensor(sorted(frontier[s]))
            mask = torch.isin(ei[0], f)
            src, dst = ei[0][mask].numpy(), ei[1][mask].numpy()
            if len(dst) == 0:
                continue
            by_src = {}
            for a, b in zip(src, dst):
                by_src.setdefault(int(a), []).append(int(b))
            for a, bs in by_src.items():
                if len(bs) > max_neighbors:
                    bs = list(rng.choice(bs, max_neighbors, replace=False))
                new[d].update(int(x) for x in bs)
        for t in data.node_types:
            new[t] -= nodes[t]
            nodes[t] |= new[t]
        frontier = new
    return {t: torch.as_tensor(sorted(v), dtype=torch.long) for t, v in nodes.items()}


def explain_link_gnn(model, data, drug_idx, disease_idx, hops=2, epochs=100, max_neighbors=50, seed=0, device="cpu"):
    """GNNExplainer for ONE drug->disease pair on the k-hop neighbourhood. `model` = GNNLinkPredictionModel (eval mode), `data` = the message-passing HeteroData
    (treats edges already removed). Returns (prob, edges_df, relation_df)."""
    import torch
    from torch_geometric.explain import Explainer, GNNExplainer
    torch.manual_seed(seed)
    subset = hetero_khop_subset(data, {"drug": [drug_idx], "disease": [disease_idx]}, k=hops, max_neighbors=max_neighbors, rng=np.random.default_rng(seed))
    sub = data.subgraph(subset).to(device)
    d_pos = int(torch.searchsorted(subset["drug"], torch.tensor(drug_idx)))
    s_pos = int(torch.searchsorted(subset["disease"], torch.tensor(disease_idx)))
    eli = torch.tensor([[d_pos], [s_pos]], dtype=torch.long, device=device)
    model = model.to(device).eval()
    ex = Explainer(model, algorithm=GNNExplainer(epochs=epochs), explanation_type="model", node_mask_type="attributes", edge_mask_type="object",
                   model_config=dict(mode="binary_classification", task_level="edge", return_type="probs"))
    with torch.no_grad():
        prob = float(model(sub.x_dict, sub.edge_index_dict, eli)[0])
    e = ex(sub.x_dict, sub.edge_index_dict, index=0, edge_label_index=eli)
    rows = []
    for (s, r, d), mask in e.edge_mask_dict.items():
        ei = sub[(s, r, d)].edge_index.cpu()
        for j in range(ei.shape[1]):
            rows.append({"src_type": s, "relation": r, "dst_type": d, "src_node_id": int(subset[s][ei[0, j]]), "dst_node_id": int(subset[d][ei[1, j]]),
                         "edge_mask": float(mask[j])})
    edges = pd.DataFrame(rows).sort_values("edge_mask", ascending=False).reset_index(drop=True)
    rel = edges.groupby("relation").edge_mask.agg(mean_edge_mask="mean", n_edges="size").reset_index().sort_values("mean_edge_mask", ascending=False)
    return prob, edges, rel
