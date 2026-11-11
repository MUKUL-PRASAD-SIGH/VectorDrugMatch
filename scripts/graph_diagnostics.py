"""
scripts/graph_diagnostics.py - graph statistics, connectivity, drug-to-disease path coverage and the automated leakage audit for each message-passing variant.

    python scripts/graph_diagnostics.py [--out outputs/treats_edge_ablation_20261111/diagnostics] [--config configs/primekg_morgan.yaml]

CPU only, no training. Variants: original (A), train_treats (B), mechanism (C). For each: node and edge counts by relation, drug/disease degree summaries,
isolated nodes, connected components, the share of TEST pairs (positives and negatives separately) joined by a walk of length <= 1, 2 or 3, and the leakage audit.
Writes graph_stats_<variant>.json, leakage_audit_<variant>.json and graph_edge_counts.csv.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
import yaml
from scipy.sparse.csgraph import connected_components

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from src.data.dataset import build_message_passing_graph, build_tabular_dataset  # noqa: E402
from src.data.graph_builder import build_hetero_data  # noqa: E402
from src.data.treats_edges import build_variant_edges, leakage_audit, supervision_view, make_folds, train_positive_pairs, TARGET  # noqa: E402

VARIANTS = ("original", "train_treats", "mechanism")


def adjacency(edge_dict, n):
    off = {"drug": 0, "disease": n["drug"], "gene": n["drug"] + n["disease"]}
    rows, cols = [], []
    for (s, _, d), ei in edge_dict.items():
        if ei.numel() == 0:
            continue
        e = ei.cpu().numpy()
        rows.append(e[0] + off[s])
        cols.append(e[1] + off[d])
    r, c = np.concatenate(rows), np.concatenate(cols)
    N = sum(n.values())
    A = sp.coo_matrix((np.ones(len(r), dtype=np.float32), (r, c)), shape=(N, N)).tocsr()
    A = ((A + A.T) > 0).astype(np.float32).tocsr()
    A.setdiag(0)
    A.eliminate_zeros()
    return A, off


def walk_coverage(A, off, pairs, chunk=400):
    u = pairs[0].astype(np.int64) + off["drug"]
    v = pairs[1].astype(np.int64) + off["disease"]
    one = np.asarray(A[u, v]).ravel() > 0
    two = np.zeros(len(u), bool)
    three = np.zeros(len(u), bool)
    for i in range(0, len(u), chunk):
        ru, rv = A[u[i:i + chunk]], A[v[i:i + chunk]]
        two[i:i + chunk] = np.asarray(ru.multiply(rv).sum(1)).ravel() > 0
        three[i:i + chunk] = np.asarray((ru @ A).multiply(rv).sum(1)).ravel() > 0
    return {"direct_edge": float(one.mean()), "walk_le2": float((one | two).mean()), "walk_le3": float((one | two | three).mean())}


def summarize(x):
    x = np.asarray(x, dtype=float)
    return {"min": float(x.min()), "median": float(np.median(x)), "mean": float(x.mean()), "p90": float(np.percentile(x, 90)), "max": float(x.max()), "zero": int((x == 0).sum())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="outputs/treats_edge_ablation_20261111/diagnostics")
    ap.add_argument("--config", default="configs/primekg_morgan.yaml")
    a = ap.parse_args()
    out = REPO / a.out
    out.mkdir(parents=True, exist_ok=True)
    cfg = yaml.safe_load(open(REPO / a.config, encoding="utf-8"))
    exp = cfg["experiment"].get("processed_name", cfg["experiment"]["name"])
    presplit = cfg["dataset"]["presplit"]
    data = build_hetero_data(REPO / "data" / "processed" / exp, include_features=True)
    raw = np.load(REPO / presplit, allow_pickle=True)         # the saved split itself (edges, labels, drugs, held-out pairs)
    splits = {k: raw[k] for k in raw.files}
    base = build_message_passing_graph(data, presplit)
    n = {t: data[t].num_nodes for t in data.node_types}
    rows = []
    t_pos = np.asarray(splits["edges_test"])[:, np.asarray(splits["y_test"]).astype(bool)]
    t_neg = np.asarray(splits["edges_test"])[:, ~np.asarray(splits["y_test"]).astype(bool)]
    v_pos = np.asarray(splits["edges_val"])[:, np.asarray(splits["y_val"]).astype(bool)]
    for variant in VARIANTS:
        t0 = time.time()
        ed = build_variant_edges(base, splits, variant)
        A, off = adjacency(ed, n)
        deg = np.asarray(A.sum(1)).ravel()
        ncomp, lab = connected_components(A, directed=False)
        sizes = np.bincount(lab)
        big = int(sizes.argmax())
        stats = {
            "variant": variant, "nodes": n, "n_edge_types": len(ed),
            "edges_by_relation": {f"{s}|{r}|{d}": int(ei.shape[1]) for (s, r, d), ei in ed.items()},
            "target_edges": {"train_positive_in_mp": int(ed[TARGET].shape[1]), "heldout_val_positive": int(v_pos.shape[1]), "heldout_test_positive": int(t_pos.shape[1])},
            "non_target_edges_undirected_simple": int(A.nnz // 2),
            "drug_degree": summarize(deg[off["drug"]:off["disease"]]), "disease_degree": summarize(deg[off["disease"]:off["gene"]]), "gene_degree": summarize(deg[off["gene"]:]),
            "isolated_nodes": {"drug": int((deg[off["drug"]:off["disease"]] == 0).sum()), "disease": int((deg[off["disease"]:off["gene"]] == 0).sum()), "gene": int((deg[off["gene"]:] == 0).sum())},
            "connected_components": {"n": int(ncomp), "largest": int(sizes[big]), "share_drugs_in_largest": float((lab[off["drug"]:off["disease"]] == big).mean()),
                                     "share_diseases_in_largest": float((lab[off["disease"]:off["gene"]] == big).mean())},
            "walk_coverage_test_positive_pairs": walk_coverage(A, off, t_pos), "walk_coverage_test_negative_pairs": walk_coverage(A, off, t_neg),
            "walk_coverage_val_positive_pairs": walk_coverage(A, off, v_pos),
            "test_drugs_with_no_gene_edge": None,
        }
        gb = ed[("drug", "binds", "gene")]
        td = np.unique(np.asarray(splits["edges_test"])[0])
        stats["test_drugs_with_no_gene_edge"] = int(len(td) - len(np.intersect1d(td, np.unique(gb[0].cpu().numpy()))))
        # training-positive degree of the diseases that appear in the test positives (how much label evidence the disease side carries in variant B)
        tp = train_positive_pairs(splits)
        dcount = np.bincount(tp[1], minlength=n["disease"])
        stats["test_positive_diseases_train_positive_degree"] = summarize(dcount[t_pos[1]])
        stats["seconds"] = round(time.time() - t0, 1)
        audit_pos = train_positive_pairs(splits)
        import torch
        rng = np.random.default_rng(0)
        folds = make_folds(audit_pos.shape[1], splits["y_train"], 4, rng)
        full_pos = torch.as_tensor(audit_pos, dtype=torch.long)
        pos_idx_of = {int(i): j for j, i in enumerate(np.where(np.asarray(splits["y_train"]).astype(bool))[0])}
        sup = [torch.as_tensor([pos_idx_of[int(i)] for i in f if int(i) in pos_idx_of], dtype=torch.long) for f in folds]
        aud = leakage_audit(ed, splits, data, n["drug"], n["disease"], variant, sup_check=[(full_pos, sup)] if variant == "train_treats" else None)
        stats["leakage_all_pass"] = aud["all_pass"]
        (out / f"graph_stats_{variant}.json").write_text(json.dumps(stats, indent=1), encoding="utf-8")
        (out / f"leakage_audit_{variant}.json").write_text(json.dumps(aud, indent=1, default=str), encoding="utf-8")
        rows += [{"variant": variant, "relation": k, "edges": v} for k, v in stats["edges_by_relation"].items()]
        print(f"\n=== {variant} === leakage audit all_pass={aud['all_pass']}")
        for k, v in aud.items():
            if isinstance(v, dict) and "pass" in v:
                print(f"  [{'PASS' if v['pass'] else 'FAIL'}] {k}")
        print("  walk coverage (test positives):", stats["walk_coverage_test_positive_pairs"])
        print("  walk coverage (test negatives):", stats["walk_coverage_test_negative_pairs"])
        print("  components:", stats["connected_components"], "| isolated:", stats["isolated_nodes"])
    pd.DataFrame(rows).to_csv(out / "graph_edge_counts.csv", index=False)
    print("\nwritten to", out)


if __name__ == "__main__":
    main()
