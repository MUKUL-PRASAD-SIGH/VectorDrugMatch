"""
scripts/explain_models.py - explain the TRAINED cold-start models on held-out TEST pairs. Run in Colab AFTER training; not executed locally.

    python scripts/explain_models.py --config configs/primekg_morgan.yaml --models rf xgb --n-shap 1000
    python scripts/explain_models.py --config configs/primekg_morgan.yaml --gnn HGT RGCN --n-links 20

Inputs  : outputs/<exp>/models/baseline_<key>_coldstart.pkl   (saved by train_baselines.py: the model that produced the reported test metrics)
          outputs/<exp>/models/gnn_<name>.pth                 (saved by train_gnn.py; best-validation weights)
          the saved split, so the explained rows are the TEST pairs only.
Outputs : outputs/<exp>/explain/  (schemas in src/explainability/explain.py): shap_<key>_top_features.csv, shap_<key>_values.npz,
          shap_<key>_bit_substructures.csv, gnn_<name>_link_explanations.csv, gnn_<name>_relation_importance.csv, explain_manifest.json
Rules   : SHAP only for RF / XGBoost (appropriate); GNNExplainer only on the k-hop neighbourhood of selected TEST positives with the highest predicted
          probability (a convenience selection, recorded; not a random sample); MLP / Naive Bayes / Node2Vec are intentionally not explained (see explain.py).
          Attributions are properties of the MODEL, not causal biology.
"""
import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from src.explainability.explain import (explain_link_gnn, feature_names, morgan_bit_substructures, top_features, tree_shap,  # noqa: E402
                                        unwrap_estimator)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/primekg_morgan.yaml")
    ap.add_argument("--models", nargs="*", default=[], choices=["rf", "xgb"])
    ap.add_argument("--gnn", nargs="*", default=[], choices=["GCN", "GraphSAGE", "GAT", "RGCN", "HGT"])
    ap.add_argument("--n-shap", type=int, default=1000)
    ap.add_argument("--n-links", type=int, default=20)
    ap.add_argument("--hops", type=int, default=2)
    ap.add_argument("--epochs", type=int, default=100)
    a = ap.parse_args()
    cfg = yaml.safe_load(open(REPO / a.config))
    exp, ds = cfg["experiment"]["name"], cfg["dataset"]
    seed = ds.get("random_seed", 42)
    proc, out = REPO / "data" / "processed" / exp, REPO / "outputs" / exp
    ex = out / "explain"
    ex.mkdir(parents=True, exist_ok=True)
    man = {"config": a.config, "split": ds["presplit"], "seed": seed, "test_only": True, "explained": {}}
    from src.data.dataset import build_message_passing_graph, build_tabular_dataset
    from src.data.graph_builder import build_hetero_data
    data = build_hetero_data(proc, include_features=True)
    sp = build_tabular_dataset(data, presplit=ds["presplit"], random_state=seed)
    drugs = pd.read_csv(proc / "drugs.csv", low_memory=False)
    dis = pd.read_csv(proc / "diseases.csv", low_memory=False)
    names = feature_names(data["drug"].x.shape[1])

    for key in a.models:
        pkl = out / "models" / f"baseline_{key}_coldstart.pkl"
        if not pkl.exists():
            print(f"[SKIP] {pkl.name} not found (train_baselines.py must save the cold-start model)")
            continue
        est = unwrap_estimator(joblib.load(pkl))
        idx, sv, base = tree_shap(est, sp["X_test"], max_rows=a.n_shap, seed=seed)
        tf = top_features(sv, names, top=50)
        tf.to_csv(ex / f"shap_{key}_top_features.csv", index=False)
        np.savez(ex / f"shap_{key}_values.npz", idx=idx, shap=sv, base_value=base)
        rows = []
        for _, r in tf[tf.feature.str.startswith("morgan_")].head(20).iterrows():
            bit = int(r.feature.split("_")[1])
            # example drug = the test-row drug with the largest positive contribution on this bit among rows where the bit is on
            on = np.where(sp["X_test"][idx, bit] > 0)[0]
            if len(on) == 0:
                continue
            j = on[np.argmax(sv[on, bit])]
            did = int(sp["edges_test"][0][idx[j]])
            smi = drugs.smiles.iloc[did]
            rows.append({"bit": bit, "mean_abs_shap": float(r.mean_abs_shap), "example_drug_id": drugs.drug_id.iloc[did], "example_smiles": smi,
                         "environment_smiles": "|".join(morgan_bit_substructures(smi, bit)) if isinstance(smi, str) and smi else ""})
        pd.DataFrame(rows).to_csv(ex / f"shap_{key}_bit_substructures.csv", index=False)
        man["explained"][key] = {"rows": int(len(idx)), "method": "SHAP TreeExplainer / XGBoost native contributions (uncalibrated base estimator)"}

    if a.gnn:
        import torch
        from src.models.gnn.base import GNNLinkPredictionModel
        from src.models.gnn.gat import create_gat_model
        from src.models.gnn.gcn import create_gcn_model
        from src.models.gnn.graphsage import create_graphsage_model
        from src.models.gnn.hgt import create_hgt_model
        from src.models.gnn.rgcn import create_rgcn_model
        mp = build_message_passing_graph(data, ds["presplit"])
        for t in mp.node_types:
            mp[t].x = mp[t].x.float() if getattr(mp[t], "x", None) is not None else torch.ones((mp[t].num_nodes, 1))
        fac = {"GCN": lambda: create_gcn_model(mp.metadata(), 64, 64), "GraphSAGE": lambda: create_graphsage_model(mp.metadata(), 64, 64),
               "GAT": lambda: create_gat_model(mp.metadata(), 32, 64, heads=2), "RGCN": lambda: create_rgcn_model(mp.metadata(), 64, 64),
               "HGT": lambda: create_hgt_model(mp.metadata(), 64, 64, heads=4)}
        e, y = sp["edges_test"], sp["y_test"]
        for name in a.gnn:
            pth = out / "models" / f"gnn_{name}.pth"
            if not pth.exists():
                print(f"[SKIP] {pth.name} not found")
                continue
            model = GNNLinkPredictionModel(fac[name](), in_channels=64, hidden_channels=32)
            with torch.no_grad():
                model(mp.x_dict, mp.edge_index_dict, torch.as_tensor(e[:, :2], dtype=torch.long))      # initialise lazy layers before loading weights
            model.load_state_dict(torch.load(pth, map_location="cpu"))
            model.eval()
            with torch.no_grad():
                p = model(mp.x_dict, mp.edge_index_dict, torch.as_tensor(e, dtype=torch.long)).numpy()
            pos = np.where(y == 1)[0]
            pick = pos[np.argsort(-p[pos])][:a.n_links]                      # highest-probability TEST positives (selection recorded in the manifest)
            all_e, all_r = [], []
            for i in pick:
                prob, edges, rel = explain_link_gnn(model, mp, int(e[0, i]), int(e[1, i]), hops=a.hops, epochs=a.epochs, seed=seed)
                meta = {"drug_id": drugs.drug_id.iloc[int(e[0, i])], "disease_id": dis.disease_id.iloc[int(e[1, i])], "label": int(y[i]), "prob": prob}
                all_e.append(edges.head(50).assign(**meta))
                all_r.append(rel.assign(**{k: meta[k] for k in ("drug_id", "disease_id")}))
            pd.concat(all_e).to_csv(ex / f"gnn_{name}_link_explanations.csv", index=False)
            pd.concat(all_r).to_csv(ex / f"gnn_{name}_relation_importance.csv", index=False)
            man["explained"][name] = {"links": int(len(pick)), "selection": "highest-probability test positives", "hops": a.hops, "epochs": a.epochs}
    (ex / "explain_manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
    print(json.dumps(man, indent=1))


if __name__ == "__main__":
    main()
