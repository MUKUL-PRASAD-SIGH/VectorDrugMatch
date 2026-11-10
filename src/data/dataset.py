"""
src/data/dataset.py - Tabular Dataset Preparation

Orchestrates data splitting and pair feature generation to produce
clean Train/Val/Test sets for Classical ML Baselines, fully preventing data leakage.
"""

import numpy as np
import random
from pathlib import Path
import pandas as pd
from sklearn.model_selection import train_test_split

from src.data.link_prediction_dataset import build_link_prediction_dataset
from src.features.pair import build_pair_features

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CURATED_NEG = REPO_ROOT / "data" / "external" / "labels_pharmacotherapydb.csv"
# raw PharmacotherapyDB file (scripts/fetch_public_data.py) - used when the bundle's labels CSV is absent
RAW_INDICATIONS = REPO_ROOT / "data" / "external" / "indications_pharmacotherapydb.tsv"


def load_curated_negatives(hetero_data, path, src_type="drug", dst_type="disease"):
    """PharmacotherapyDB 'NOT' rows (curated non-indications) as node-index arrays."""
    path = Path(path)
    if not path.exists() and path == DEFAULT_CURATED_NEG and RAW_INDICATIONS.exists():
        path = RAW_INDICATIONS
    if not path.exists() or not hasattr(hetero_data[src_type], "node_ids"):
        return np.array([], dtype=np.int64), np.array([], dtype=np.int64)
    if path.suffix == ".tsv":                      # raw dhimmel/indications format
        df = pd.read_csv(path, sep="\t").rename(columns={"doid_id": "disease_id", "drugbank_id": "drug_id"})
    else:
        df = pd.read_csv(path)
    df = df[df["category"] == "NOT"]
    s_map = {n: i for i, n in enumerate(hetero_data[src_type].node_ids)}
    d_map = {n: i for i, n in enumerate(hetero_data[dst_type].node_ids)}
    pairs = [(s_map[a], d_map[b]) for a, b in zip(df["drug_id"].astype(str), df["disease_id"].astype(str))
             if a in s_map and b in d_map]
    if not pairs:
        return np.array([], dtype=np.int64), np.array([], dtype=np.int64)
    arr = np.array(sorted(set(pairs)), dtype=np.int64)
    return arr[:, 0], arr[:, 1]


def _resolve(path):
    path = Path(path)
    return path if path.is_absolute() else REPO_ROOT / path


def build_tabular_dataset_from_presplit(hetero_data, presplit, target_edge=('drug', 'treats', 'disease'), disease_profile=False):
    """Load a SAVED split (scripts/primekg_split.py) instead of splitting on the fly.

    Every model that calls this gets byte-identical pairs, labels and negatives. Returns the same keys as
    build_tabular_dataset plus curated_{split} (all False for PrimeKG) and diag_contra_/diag_offlabel_{split}
    (evaluation-only pairs of that split's drugs; never used as labels).
    """
    z = np.load(_resolve(presplit))
    src_type, _, dst_type = target_edge
    src_feats = hetero_data[src_type].x.numpy()
    dst_feats = hetero_data[dst_type].x.numpy()
    out, cw = {}, {}
    print(f"\nLoading saved split: {_resolve(presplit)}")
    for sp in ("train", "val", "test"):
        e, y = z[f"edges_{sp}"], z[f"y_{sp}"].astype(np.int8)
        out[f"X_{sp}"] = build_pair_features(src_feats, dst_feats, e[0], e[1])
        if disease_profile:                    # optional variant: + leak-free disease-profile block built from TRAIN edges/labels only
            from src.features.disease_profile import build_disease_profile_block
            out[f"X_{sp}"] = np.concatenate([out[f"X_{sp}"], build_disease_profile_block(src_feats, z["edges_train"], z["y_train"], e)], axis=1)
        out[f"y_{sp}"], out[f"edges_{sp}"] = y, e
        out[f"curated_{sp}"] = z[f"curated_{sp}"]
        for k in ("diag_contra", "diag_offlabel"):
            if f"{k}_{sp}" in z:
                out[f"{k}_{sp}"] = z[f"{k}_{sp}"]
        npos, nneg = int((y == 1).sum()), int((y == 0).sum())
        cw[sp] = nneg / npos if npos else 1.0
        print(f"  {sp}: {len(y):,} pairs ({npos:,} pos, {nneg:,} neg) | X {out[f'X_{sp}'].shape}")
    d = {sp: set(z[f"edges_{sp}"][0].tolist()) for sp in ("train", "val", "test")}
    assert not (d["train"] & d["val"]) and not (d["train"] & d["test"]) and not (d["val"] & d["test"]), \
        "CRITICAL LEAKAGE: drug overlap between saved splits"
    out["class_weights"] = cw
    return out


def _drop_pairs(edge_index, pairs, n_second):
    """Remove columns of edge_index whose (row0, row1) is in `pairs` (2,K numpy array)."""
    import torch
    if edge_index.numel() == 0 or pairs.shape[1] == 0:
        return edge_index
    key = edge_index[0].numpy().astype(np.int64) * n_second + edge_index[1].numpy().astype(np.int64)
    bad = np.isin(key, pairs[0].astype(np.int64) * n_second + pairs[1].astype(np.int64))
    return edge_index[:, torch.as_tensor(~bad)]


def build_message_passing_graph(data, presplit=None, target_edge=('drug', 'treats', 'disease')):
    """Graph used for message passing: NO label can reach a prediction through it.

    * every target (treats) edge and its reverse is removed (supervision comes only from edge_label_index);
    * if a saved split is given, any other drug->disease relation (contraindicated_for, offlabel_for) is also
      dropped on the HELD-OUT (val+test) indication pairs, in both directions, so a held-out positive cannot
      leak through an alternative relation path.
    """
    import torch
    mp = data.clone()
    src_t, rel, dst_t = target_edge
    for et in (target_edge, (dst_t, f"rev_{rel}", src_t)):
        if et in mp.edge_types:
            mp[et].edge_index = torch.empty((2, 0), dtype=torch.long)
    if presplit is not None:
        held = np.load(_resolve(presplit))["heldout_indication_pairs"]
        n_dst, n_src = mp[dst_t].num_nodes, mp[src_t].num_nodes
        for other in ("contraindicated_for", "offlabel_for"):
            fwd, rev = (src_t, other, dst_t), (dst_t, f"rev_{other}", src_t)
            if fwd in mp.edge_types:
                mp[fwd].edge_index = _drop_pairs(mp[fwd].edge_index, held, n_dst)
            if rev in mp.edge_types:
                mp[rev].edge_index = _drop_pairs(mp[rev].edge_index, held[::-1], n_src)
    return mp


def set_seeds(seed=42):
    """Enforce strict reproducibility across all RNGs."""
    import torch
    np.random.seed(seed)
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

def build_tabular_dataset(hetero_data, target_edge=('drug', 'treats', 'disease'), 
                          neg_ratio=5.0, test_size=0.15, val_size=0.15, random_state=42,
                          split_mode="cold_start_drug", strategy="hard",
                          curated_neg_path="auto", presplit=None, disease_profile=False):
    """
    Builds X, y tabular datasets with strict data leakage prevention.
    
    Protocol:
    1. Extract all positive edges.
    2. SPLIT FIRST based on split_mode (Random vs Cold-Start).
    3. Negative Sample INDEPENDENTLY for Train/Val/Test.
    4. Generate pair features.
    
    Args:
        split_mode: "random" (edges) or "cold_start_drug" (drugs).
        strategy: "random" or "hard" negative sampling.
        presplit: path to a saved split (.npz from scripts/primekg_split.py); when set, nothing is re-split.
        curated_neg_path: PharmacotherapyDB labels CSV whose 'NOT' rows are used as
            real negatives (routed to the split that owns the drug); "auto" uses
            data/external/labels_pharmacotherapydb.csv when present, None disables.
    """
    if disease_profile and not presplit:
        raise ValueError("disease_profile needs a saved split (presplit): it is built from the saved TRAIN edges only")
    if presplit:                                   # Track B: a saved, shared split
        set_seeds(random_state)
        return build_tabular_dataset_from_presplit(hetero_data, presplit, target_edge, disease_profile=disease_profile)
    print(f"\nBuilding tabular dataset for target {target_edge}...")
    set_seeds(random_state)
    
    src_type, _, dst_type = target_edge
    
    pos_edge_index = hetero_data[target_edge].edge_index
    if pos_edge_index is None or pos_edge_index.shape[1] == 0:
        raise ValueError(f"No positive edges found for {target_edge}.")
        
    pos_src = pos_edge_index[0].numpy()
    pos_dst = pos_edge_index[1].numpy()
    num_src_nodes = hetero_data[src_type].num_nodes
    num_dst_nodes = hetero_data[dst_type].num_nodes
    
    # -------------------------------------------------------------------------
    # 1. SPLIT FIRST (Prevent Leakage)
    # -------------------------------------------------------------------------
    if split_mode == "cold_start_drug":
        print("  Using Cold-Start Drug Split (No drug overlap between sets)")
        unique_drugs = np.unique(pos_src)
        
        # Split Drug IDs
        train_drugs, temp_drugs = train_test_split(unique_drugs, test_size=(test_size + val_size), random_state=random_state)
        val_drugs, test_drugs = train_test_split(temp_drugs, test_size=(test_size / (test_size + val_size)), random_state=random_state)
        
        # Assign edges based on Drug ID
        train_mask = np.isin(pos_src, train_drugs)
        val_mask = np.isin(pos_src, val_drugs)
        test_mask = np.isin(pos_src, test_drugs)
        
    elif split_mode == "random":
        print("  Using Random Edge Split (Transductive)")
        indices = np.arange(len(pos_src))
        train_idx, temp_idx = train_test_split(indices, test_size=(test_size + val_size), random_state=random_state)
        val_idx, test_idx = train_test_split(temp_idx, test_size=(test_size / (test_size + val_size)), random_state=random_state)
        
        train_mask = np.zeros(len(pos_src), dtype=bool); train_mask[train_idx] = True
        val_mask = np.zeros(len(pos_src), dtype=bool); val_mask[val_idx] = True
        test_mask = np.zeros(len(pos_src), dtype=bool); test_mask[test_idx] = True
    else:
        raise ValueError(f"Unknown split_mode: {split_mode}")
        
    # Apply masks to get split positive edges
    splits = {
        "train": (pos_src[train_mask], pos_dst[train_mask]),
        "val": (pos_src[val_mask], pos_dst[val_mask]),
        "test": (pos_src[test_mask], pos_dst[test_mask])
    }
    
    # -------------------------------------------------------------------------
    # 2. NEGATIVE SAMPLING & FEATURE EXTRACTION PER SPLIT
    # -------------------------------------------------------------------------
    # Curated true negatives, routed by the same rule as the positives (no leakage)
    cn_src = cn_dst = np.array([], dtype=np.int64)
    if curated_neg_path is not None and target_edge == ('drug', 'treats', 'disease'):
        cpath = DEFAULT_CURATED_NEG if curated_neg_path == "auto" else curated_neg_path
        cn_src, cn_dst = load_curated_negatives(hetero_data, cpath, src_type, dst_type)
    curated = {}
    if len(cn_src):
        if split_mode == "cold_start_drug":
            for name, drugs_in in (("train", train_drugs), ("val", val_drugs), ("test", test_drugs)):
                m = np.isin(cn_src, drugs_in)
                curated[name] = (cn_src[m], cn_dst[m])
        else:
            r = np.random.default_rng(random_state).random(len(cn_src))
            tr_cut = 1 - test_size - val_size
            for name, m in (("train", r < tr_cut), ("val", (r >= tr_cut) & (r < tr_cut + val_size)),
                            ("test", r >= tr_cut + val_size)):
                curated[name] = (cn_src[m], cn_dst[m])
        print("  Curated negatives (PharmacotherapyDB NOT): "
              + ", ".join(f"{k}={len(v[0])}" for k, v in curated.items()))

    src_feats = hetero_data[src_type].x.numpy()
    dst_feats = hetero_data[dst_type].x.numpy()
    
    final_data = {}
    class_weights = {}
    
    for split_name, (s_src, s_dst) in splits.items():
        if len(s_src) == 0:
            print(f"  [WARNING] Split '{split_name}' has 0 positive edges.")
            continue
            
        print(f"  Processing {split_name} split...")
        result = build_link_prediction_dataset(
            s_src, s_dst, num_src_nodes, num_dst_nodes,
            neg_ratio=neg_ratio, seed=random_state, strategy=strategy,
            fixed_neg=curated.get(split_name)
        )
        
        X = build_pair_features(src_feats, dst_feats, result.edge_index[0], result.edge_index[1])
        y = result.labels
        
        final_data[f"X_{split_name}"] = X
        final_data[f"y_{split_name}"] = y
        final_data[f"edges_{split_name}"] = result.edge_index
        final_data[f"curated_{split_name}"] = result.is_curated   # report curated vs sampled negatives separately
        
        # Calculate class weights for imbalanced training (e.g., scale_pos_weight in XGBoost)
        num_pos = np.sum(y == 1)
        num_neg = np.sum(y == 0)
        class_weights[split_name] = num_neg / num_pos if num_pos > 0 else 1.0
        
        print(f"    Edges: {len(y):,} ({num_pos:,} pos, {num_neg:,} neg) | X shape: {X.shape}")

    # -------------------------------------------------------------------------
    # 3. LEAKAGE ASSERTIONS
    # -------------------------------------------------------------------------
    if split_mode == "cold_start_drug":
        train_d = set(pos_src[train_mask])
        val_d = set(pos_src[val_mask])
        test_d = set(pos_src[test_mask])
        
        assert len(train_d.intersection(test_d)) == 0, "CRITICAL LEAKAGE: Train/Test drug overlap!"
        assert len(train_d.intersection(val_d)) == 0, "CRITICAL LEAKAGE: Train/Val drug overlap!"
        assert len(val_d.intersection(test_d)) == 0, "CRITICAL LEAKAGE: Val/Test drug overlap!"
        print("  [DONE] Leakage assertions passed: 0 overlap between splits.")

    final_data["class_weights"] = class_weights
    return final_data
