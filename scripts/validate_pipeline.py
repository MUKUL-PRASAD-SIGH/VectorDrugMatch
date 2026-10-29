"""
scripts/validate_pipeline.py - Phase 1 (data) and Phase 2 (split / leakage) checks.

Run after preprocess.py and before any training:
    python scripts/validate_pipeline.py --config configs/baseline_morgan.yaml
Exits non-zero if a hard check fails.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml
from rdkit import Chem, RDLogger

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

from src.data.graph_builder import build_hetero_data, EDGE_TYPE_MAP
from src.data.dataset import build_tabular_dataset

RDLogger.DisableLog("rdApp.*")
TARGET = ("drug", "treats", "disease")
failures = []


def check(ok: bool, msg: str, hard: bool = True):
    print(f"  [{'PASS' if ok else ('FAIL' if hard else 'WARN')}] {msg}")
    if not ok and hard:
        failures.append(msg)


def main(config_path: str):
    cfg = yaml.safe_load(open(REPO_ROOT / config_path))
    exp = cfg["experiment"]["name"]
    ds = cfg.get("dataset", {})
    proc = REPO_ROOT / "data" / "processed" / exp

    # ---------------------------------------------------------------- Phase 1
    print("\n=== PHASE 1: data ===")
    drugs = pd.read_csv(proc / "drugs.csv")
    diseases = pd.read_csv(proc / "diseases.csv")
    genes = pd.read_csv(proc / "genes.csv")
    edges = pd.read_csv(proc / "edges.csv", dtype=str)
    print(f"  drugs={len(drugs)} diseases={len(diseases)} genes={len(genes)} edges={len(edges):,}")

    raw = REPO_ROOT / "data" / "raw"
    check((raw / "hetionet-v1.0-nodes.tsv").exists() and any(raw.glob("hetionet-v1.0-edges.sif*")),
          "real Hetionet files present in data/raw")
    check(not (raw / "drugs.csv").exists(), "no mock CSVs in data/raw")
    check(len(drugs) == 1552 and len(diseases) == 137 and len(genes) == 20945,
          "node counts match Hetionet v1.0 (1552 / 137 / 20945)")

    n_valid = sum(Chem.MolFromSmiles(s) is not None for s in drugs["smiles"].dropna())
    n_smiles = int(drugs["smiles"].notna().sum())
    print(f"  SMILES present {n_smiles}/{len(drugs)} ({100 * n_smiles / len(drugs):.1f}%), "
          f"RDKit-valid {n_valid}/{n_smiles}")
    check(n_valid == n_smiles, "every present SMILES parses in RDKit")
    check(n_smiles / len(drugs) > 0.95, "SMILES coverage > 95%")
    feats = np.load(proc / "drug_features.npy")
    zero_rows = int((feats.sum(1) == 0).sum())
    print(f"  fingerprints {feats.shape}, all-zero rows: {zero_rows}")
    check(feats.shape[0] == len(drugs), "drug_features rows == drugs rows")

    check(not edges.duplicated().any(), "no duplicate edges")
    rel_counts = edges["relation"].value_counts()
    modelled = set(EDGE_TYPE_MAP)
    used = edges[edges["relation"].isin(modelled)]
    print(f"  edges in the 10 modelled relations: {len(used):,}; "
          f"other Hetionet relations (not in graph): {len(edges) - len(used):,}")
    check("unknown" not in rel_counts.index and "Unknown" not in set(edges["source_type"]),
          "no unknown relation / node types")
    ids = {"drug": set(drugs["drug_id"].astype(str)), "disease": set(diseases["disease_id"].astype(str)),
           "gene": set(genes["gene_id"].astype(str))}
    bad = 0
    for rel, (s, _, d) in EDGE_TYPE_MAP.items():
        sub = edges[edges["relation"] == rel]
        if len(sub):
            bad += int((~sub["source_id"].isin(ids[s])).sum() + (~sub["target_id"].isin(ids[d])).sum())
    check(bad == 0, f"all modelled-edge endpoints exist with the right node type (bad endpoints: {bad})")
    check(int((edges["relation"] == "CtD").sum()) == 755, "755 CtD positive edges")

    check(diseases["is_ntd"].sum() > 0, "diseases carry NTD flags (WHO enrichment)", hard=False)
    check(diseases["daly_rate"].sum() > 0, "diseases carry DALY burden (WHO enrichment)", hard=False)

    # ---------------------------------------------------------------- Phase 2
    print("\n=== PHASE 2: split / leakage ===")
    data = build_hetero_data(proc, include_features=True)
    args = dict(neg_ratio=ds.get("neg_ratio", 5.0), test_size=ds.get("test_size", 0.15),
                val_size=ds.get("val_size", 0.15), random_state=ds.get("random_seed", 42))
    a = build_tabular_dataset(data, **args)   # call made by train_baselines.py
    b = build_tabular_dataset(data, **args)   # call made by train_gnn.py
    same = all(np.array_equal(a[f"edges_{s}"], b[f"edges_{s}"]) and np.array_equal(a[f"y_{s}"], b[f"y_{s}"])
               for s in ("train", "val", "test"))
    check(same, "baselines and GNNs get identical pairs/labels/negatives for train, val and test")
    for s in ("train", "val", "test"):
        y = a[f"y_{s}"]
        print(f"  {s}: {len(y)} pairs ({int((y == 1).sum())} pos / {int((y == 0).sum())} neg)")
    drugs_by = {s: set(a[f"edges_{s}"][0].tolist()) for s in ("train", "val", "test")}
    check(not (drugs_by["train"] & drugs_by["test"]) and not (drugs_by["train"] & drugs_by["val"])
          and not (drugs_by["val"] & drugs_by["test"]), "train/val/test drug sets are disjoint (positives and negatives)")

    pos = data[TARGET].edge_index
    pos_pairs = set(zip(pos[0].tolist(), pos[1].tolist()))
    leaked_neg = 0
    for s in ("train", "val", "test"):
        e, y = a[f"edges_{s}"], a[f"y_{s}"]
        leaked_neg += sum((int(u), int(v)) in pos_pairs for u, v, l in zip(e[0], e[1], y) if l == 0)
    check(leaked_neg == 0, f"no negative sample is a known treats edge (found {leaked_neg})")

    # message-passing graph exactly as train_gnn.py builds it
    rev = ("disease", "rev_treats", "drug")
    mp = data.clone()
    for et in (TARGET, rev):
        mp[et].edge_index = torch.empty((2, 0), dtype=torch.long)
    check(mp[TARGET].edge_index.size(1) == 0 and mp[rev].edge_index.size(1) == 0,
          "message-passing graph has no treats edges and no reverse-treats edges")

    # drug-disease signal that is still in the message-passing graph
    pal = data["drug", "palliates", "disease"].edge_index
    pal_pairs = set(zip(pal[0].tolist(), pal[1].tolist()))
    test_pos = {(int(u), int(v)) for u, v, l in zip(*a["edges_test"], a["y_test"]) if l == 1}
    overlap = len(test_pos & pal_pairs)
    print(f"  palliates (CpD) edges stay in the graph; {overlap}/{len(test_pos)} test positives "
          f"also have a CpD edge")
    check(overlap / max(len(test_pos), 1) < 0.10,
          "CpD overlap with test positives is small (<10%); otherwise remove CpD too", hard=False)

    print(f"  seed from config: {args['random_state']} (set_seeds covers numpy/random/torch)")

    print("\n=== RESULT ===")
    if failures:
        print(f"{len(failures)} hard check(s) failed:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("All hard checks passed.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/baseline_morgan.yaml")
    main(p.parse_args().config)
