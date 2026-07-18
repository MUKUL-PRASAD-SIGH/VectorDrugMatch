"""
src/data/dataset.py - Tabular Dataset Preparation

Orchestrates data splitting and pair feature generation to produce
clean Train/Val/Test sets for Classical ML Baselines, fully preventing data leakage.
"""

import numpy as np
import random
from sklearn.model_selection import train_test_split

from src.data.link_prediction_dataset import build_link_prediction_dataset
from src.features.pair import build_pair_features

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
                          split_mode="cold_start_drug", strategy="hard"):
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
    """
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
            neg_ratio=neg_ratio, seed=random_state, strategy=strategy
        )
        
        X = build_pair_features(src_feats, dst_feats, result.edge_index[0], result.edge_index[1])
        y = result.labels
        
        final_data[f"X_{split_name}"] = X
        final_data[f"y_{split_name}"] = y
        final_data[f"edges_{split_name}"] = result.edge_index
        
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
