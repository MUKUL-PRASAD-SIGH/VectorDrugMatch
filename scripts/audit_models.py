"""
scripts/audit_models.py - STATIC execution-readiness audit of every model, WITHOUT training.

    python scripts/audit_models.py

Checks (all tiny; no experiment is run):
  1. every script/module compiles;
  2. each baseline class instantiates and fits/predicts on 200 random rows (shape + finite probabilities);
  3. each GNN (GCN, GraphSAGE, GAT, RGCN, HGT) builds on a tiny synthetic hetero graph and does ONE eval forward pass
     (output shape = number of query edges, values in [0,1]) - synthetic data is used ONLY here, never saved or reported;
  4. both benchmark variants load through the real loaders (hetero graph + saved split) with consistent shapes;
  5. Node2Vec trainer's walk-graph leakage assertion runs (dry run).
Writes outputs/audit/models_audit.json (git-ignored). Missing optional deps are reported, not hidden.
"""
import json
import py_compile
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
res = {"compile": {}, "baselines": {}, "gnn": {}, "loaders": {}, "node2vec_dry_run": None, "missing_modules": []}


def main():
    for p in sorted(list((REPO / "scripts").glob("*.py")) + list((REPO / "src").rglob("*.py"))):
        try:
            py_compile.compile(str(p), doraise=True)
            res["compile"][str(p.relative_to(REPO))] = "ok"
        except Exception as e:
            res["compile"][str(p.relative_to(REPO))] = f"FAIL {e}"

    rng = np.random.default_rng(0)
    X, y = rng.random((200, 20)).astype("float32"), (rng.random(200) > 0.7).astype(int)
    try:
        from train_baselines import get_available_models
        for key, (label, cls) in get_available_models().items():
            try:
                m = cls() if key not in ("rf",) else cls(n_estimators=5, max_depth=3)
                m.train(X, y)
                p = np.asarray(m.predict_proba(X))
                ok = p.shape == (200,) and np.isfinite(p).all() and (p >= 0).all() and (p <= 1).all()
                res["baselines"][key] = {"name": label, "status": "ok" if ok else f"bad output shape/values {p.shape}"}
            except Exception as e:
                res["baselines"][key] = {"name": label, "status": f"FAIL {type(e).__name__}: {e}"[:200]}
        res["baselines"]["xgb_available"] = "xgb" in get_available_models()
    except Exception as e:
        res["baselines"]["_import"] = f"FAIL {type(e).__name__}: {e}"[:200]

    try:
        import torch
        from torch_geometric.data import HeteroData
        from src.models.gnn.base import GNNLinkPredictionModel
        from src.models.gnn.gat import create_gat_model
        from src.models.gnn.gcn import create_gcn_model
        from src.models.gnn.graphsage import create_graphsage_model
        from src.models.gnn.hgt import create_hgt_model
        from src.models.gnn.rgcn import create_rgcn_model
        torch.manual_seed(0)
        d = HeteroData()
        d["drug"].x, d["disease"].x, d["gene"].x = torch.rand(30, 64), torch.rand(20, 3), torch.ones(15, 1)
        def edges(n1, n2, k):
            return torch.stack([torch.randint(0, n1, (k,)), torch.randint(0, n2, (k,))])
        d["drug", "binds", "gene"].edge_index = edges(30, 15, 60)
        d["gene", "rev_binds", "drug"].edge_index = d["drug", "binds", "gene"].edge_index.flip(0)
        d["disease", "associates", "gene"].edge_index = edges(20, 15, 50)
        d["gene", "rev_associates", "disease"].edge_index = d["disease", "associates", "gene"].edge_index.flip(0)
        d["gene", "interacts", "gene"].edge_index = edges(15, 15, 40)
        d["drug", "contraindicated_for", "disease"].edge_index = edges(30, 20, 40)
        d["disease", "rev_contraindicated_for", "drug"].edge_index = d["drug", "contraindicated_for", "disease"].edge_index.flip(0)
        q = edges(30, 20, 12)
        fac = {"GCN": lambda: create_gcn_model(d.metadata(), hidden_channels=64, out_channels=64),
               "GraphSAGE": lambda: create_graphsage_model(d.metadata(), hidden_channels=64, out_channels=64),
               "GAT": lambda: create_gat_model(d.metadata(), hidden_channels=32, out_channels=64, heads=2),
               "RGCN": lambda: create_rgcn_model(d.metadata(), hidden_channels=64, out_channels=64),
               "HGT": lambda: create_hgt_model(d.metadata(), hidden_channels=64, out_channels=64, heads=4)}
        for name, f in fac.items():
            try:
                t0 = time.time()
                m = GNNLinkPredictionModel(f(), in_channels=64, hidden_channels=32).eval()
                with torch.no_grad():
                    p = m(d.x_dict, d.edge_index_dict, q)
                    p2 = m(d.x_dict, d.edge_index_dict, q)
                deterministic = bool(torch.allclose(p, p2))        # eval mode must be deterministic (dropout bug found 2026-11-10 in GCN/GraphSAGE/GAT)
                ok = tuple(p.shape) == (12,) and bool(torch.isfinite(p).all()) and float(p.min()) >= 0 and float(p.max()) <= 1 and deterministic
                res["gnn"][name] = {"status": "ok" if ok else f"bad output {tuple(p.shape)} / deterministic={deterministic}", "eval_deterministic": deterministic, "params": int(sum(x.numel() for x in m.parameters())),
                                    "seconds": round(time.time() - t0, 2)}
            except Exception as e:
                res["gnn"][name] = {"status": f"FAIL {type(e).__name__}: {e}"[:250]}
        res["gnn"]["torch"] = torch.__version__
        res["gnn"]["cuda_available"] = bool(torch.cuda.is_available())
    except Exception as e:
        res["gnn"]["_import"] = f"FAIL {type(e).__name__}: {e}"[:250]

    try:
        from src.data.dataset import build_message_passing_graph, build_tabular_dataset
        from src.data.graph_builder import build_hetero_data
        for exp, split in (("primekg", "primekg"), ("primekg_structcov", "primekg_structcov")):
            proc = REPO / "data" / "processed" / exp
            if not proc.exists():
                res["loaders"][exp] = "processed dir missing"
                continue
            data = build_hetero_data(proc, include_features=True)
            sp = build_tabular_dataset(data, presplit=f"data/processed/{split}/splits/seed42.npz")
            mp = build_message_passing_graph(data, f"data/processed/{split}/splits/seed42.npz")
            res["loaders"][exp] = {"X_train": list(sp["X_train"].shape), "X_val": list(sp["X_val"].shape), "X_test": list(sp["X_test"].shape),
                                   "treats_edges_in_mp_graph": int(mp["drug", "treats", "disease"].edge_index.shape[1]),
                                   "node_counts": {t: int(data[t].num_nodes) for t in data.node_types}, "status": "ok"}
    except Exception as e:
        res["loaders"]["_error"] = f"{type(e).__name__}: {e}"[:250]

    r = subprocess.run([sys.executable, "-I", str(REPO / "scripts" / "train_node2vec.py"), "--config", "configs/primekg_morgan.yaml", "--dry-run"],
                       capture_output=True, text=True, timeout=600)
    res["node2vec_dry_run"] = "ok" if (r.returncode == 0 and "held-out pairs absent: OK" in r.stdout) else f"FAIL: {r.stderr[-200:]}"
    try:
        import pyg_lib  # noqa: F401
        from torch_geometric.nn import Node2Vec  # noqa: F401
    except Exception as e:
        res["missing_modules"].append(f"PyG Node2Vec backend unavailable: {type(e).__name__}: {e}"[:200])
    try:
        import shap  # noqa: F401
    except Exception:
        res["missing_modules"].append("shap (installed in Colab Step 3; no SHAP code exists in src/explainability yet)")

    out = REPO / "outputs" / "audit"
    out.mkdir(parents=True, exist_ok=True)
    (out / "models_audit.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    bad = [k for k, v in res["compile"].items() if v != "ok"]
    print(json.dumps({"compile_failures": bad, "baselines": res["baselines"], "gnn": res["gnn"], "loaders": res["loaders"],
                      "node2vec_dry_run": res["node2vec_dry_run"], "missing_modules": res["missing_modules"]}, indent=1))


if __name__ == "__main__":
    main()
