"""
scripts/train_node2vec.py - leakage-safe Node2Vec baseline on the SAVED split (Track B).

    python scripts/train_node2vec.py --config configs/primekg_morgan.yaml [--epochs 10] [--dry-run]

Why a new script: scripts/train_benchmark.py learns embeddings from EVERY treats edge (including test
positives) and then cross-validates on those same labels, which leaks. Here:
  * the walk graph = message-passing graph (no held-out label can be in it) + TRAIN indication edges only;
  * Logistic Regression on Hadamard(drug, disease) embeddings is fit on the train split only;
  * the decision threshold comes from the validation split; the test split is scored once.
Outputs (same conventions as the other baselines, so scripts/evaluate_primekg.py picks them up):
  outputs/<exp>/baseline_node2vec_coldstart_predictions.csv   (y_true, probability; test order)
  outputs/<exp>/models/baseline_node2vec_metrics.json
Needs torch-cluster (installed in the Colab playbook). --dry-run only builds/validates the walk graph.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_curve

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from src.data.dataset import build_message_passing_graph  # noqa: E402
from src.data.graph_builder import build_hetero_data  # noqa: E402
from src.utils.metrics import compute_all_metrics  # noqa: E402


def build_walk_graph(data, presplit_path, target_edge=("drug", "treats", "disease")):
    """Homogeneous edge_index over drug|disease|gene nodes: MP graph + TRAIN positives (nothing held out)."""
    z = np.load(presplit_path)
    mp = build_message_passing_graph(data, presplit_path, target_edge)
    types = [t for t in ("drug", "disease", "gene") if t in mp.node_types]
    off, tot = {}, 0
    for t in types:
        off[t], tot = tot, tot + mp[t].num_nodes
    parts = []
    for (s, _, d), store in mp.edge_items():
        if s in off and d in off and store.edge_index.numel():
            parts.append(store.edge_index + torch.tensor([[off[s]], [off[d]]]))
    e_tr, y_tr = z["edges_train"], z["y_train"]
    tr_pos = torch.as_tensor(e_tr[:, y_tr == 1], dtype=torch.long)       # train positives only
    parts.append(tr_pos + torch.tensor([[off["drug"]], [off["disease"]]]))
    ei = torch.cat(parts, dim=1)
    ei = torch.cat([ei, ei.flip(0)], dim=1)                               # undirected walks
    return ei, off, tot, tr_pos.shape[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/primekg_morgan.yaml")
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--dim", type=int, default=64)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(REPO / a.config))
    exp, ds = cfg["experiment"]["name"], cfg.get("dataset", {})
    seed = ds.get("random_seed", 42)
    presplit = REPO / ds["presplit"]
    proc, out = REPO / "data" / "processed" / exp, REPO / "outputs" / exp
    (out / "models").mkdir(parents=True, exist_ok=True)
    torch.manual_seed(seed)
    np.random.seed(seed)

    data = build_hetero_data(proc, include_features=False)
    ei, off, tot, n_tr = build_walk_graph(data, presplit)
    z = np.load(presplit)
    held = z["heldout_indication_pairs"]
    # sanity: no held-out indication pair is an edge of the walk graph (either direction)
    key = (ei[0] * tot + ei[1]).numpy()
    hk = (held[0] + off["drug"]).astype(np.int64) * tot + (held[1] + off["disease"]).astype(np.int64)
    assert not np.isin(hk, key).any(), "LEAK: a held-out indication pair is in the Node2Vec walk graph"
    print(f"walk graph: {tot:,} nodes, {ei.shape[1]:,} directed edges ({n_tr} train positives); held-out pairs absent: OK")
    if a.dry_run:
        return

    from torch_geometric.nn import Node2Vec
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    t0 = time.time()
    n2v = Node2Vec(ei, embedding_dim=a.dim, walk_length=20, context_size=10, walks_per_node=5,
                   num_negative_samples=1, p=1.0, q=1.0, sparse=True).to(dev)
    loader = n2v.loader(batch_size=256, shuffle=True, num_workers=0)
    opt = torch.optim.SparseAdam(list(n2v.parameters()), lr=0.01)
    for epoch in range(1, a.epochs + 1):
        n2v.train()
        tl = 0.0
        for pos, neg in loader:
            opt.zero_grad()
            loss = n2v.loss(pos.to(dev), neg.to(dev))
            loss.backward()
            opt.step()
            tl += loss.item()
        print(f"  epoch {epoch:02d}/{a.epochs} loss {tl / len(loader):.4f}")
    n2v.eval()
    with torch.no_grad():
        emb = n2v().cpu().numpy()
    drug_emb, dis_emb = emb[off["drug"]:off["disease"]], emb[off["disease"]:off["gene"]]

    def feats(sp):
        e = z[f"edges_{sp}"]
        return drug_emb[e[0]] * dis_emb[e[1]], z[f"y_{sp}"]

    (Xtr, ytr), (Xva, yva), (Xte, yte) = feats("train"), feats("val"), feats("test")
    clf = CalibratedClassifierCV(LogisticRegression(max_iter=2000, class_weight="balanced", random_state=seed),
                                 method="sigmoid", cv=3).fit(Xtr, ytr)
    fpr, tpr, thr = roc_curve(yva, clf.predict_proba(Xva)[:, 1])
    thr_val = float(thr[np.argmax(tpr - fpr)])                  # threshold from VAL only
    p_te = clf.predict_proba(Xte)[:, 1]
    m = compute_all_metrics(yte, p_te, threshold=thr_val)
    m.update({"name": "Node2Vec + LR (leak-free)", "type": "baseline", "seed": seed, "threshold": thr_val,
              "train_seconds": round(time.time() - t0, 1)})
    pd.DataFrame({"y_true": yte, "probability": p_te}).to_csv(out / "baseline_node2vec_coldstart_predictions.csv", index=False)
    (out / "models" / "baseline_node2vec_metrics.json").write_text(json.dumps(m, indent=2, default=float))
    print(json.dumps({k: m[k] for k in ("roc_auc", "pr_auc", "mcc", "threshold")}, indent=2))


if __name__ == "__main__":
    main()
