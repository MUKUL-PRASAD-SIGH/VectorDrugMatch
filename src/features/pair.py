"""
src/features/pair.py - Pairwise Feature Engineering

Generates tabular feature vectors (X) for pairs of nodes.
Classical ML models require a flat 1D vector per sample, so we must combine 
the source node (drug) features and destination node (disease) features.
"""

import numpy as np

def build_pair_features(src_feats: np.ndarray, dst_feats: np.ndarray, 
                        src_indices: np.ndarray, dst_indices: np.ndarray) -> np.ndarray:
    """
    Combine node features into edge/pair features for tabular ML models.
    
    This function strictly uses concatenation to preserve all individual node 
    information, which is the recommended approach for Phase 3 (where Drug 
    and Disease features typically have asymmetric dimensions).
    
    Args:
        src_feats: Feature matrix for all source nodes (N_src, D_src).
        dst_feats: Feature matrix for all destination nodes (N_dst, D_dst).
        src_indices: Array of source node indices for the selected edges.
        dst_indices: Array of destination node indices for the selected edges.
                
    Returns:
        X: Pairwise feature matrix (Num_Edges, D_src + D_dst) as float32.
    """
    # Shape validation
    if src_feats.ndim != 2:
        raise ValueError(f"src_feats must be a 2D array, got {src_feats.ndim}D")
    if dst_feats.ndim != 2:
        raise ValueError(f"dst_feats must be a 2D array, got {dst_feats.ndim}D")

    if len(src_indices) != len(dst_indices):
        raise ValueError(f"Mismatch in indices lengths: {len(src_indices)} vs {len(dst_indices)}")
        
    # Early return for empty datasets
    if len(src_indices) == 0:
        return np.empty((0, src_feats.shape[1] + dst_feats.shape[1]), dtype=np.float32)
        
    # Index validation
    if src_indices.min() < 0 or src_indices.max() >= len(src_feats):
        raise ValueError(f"Source indices out of bounds [0, {len(src_feats)-1}]")
    if dst_indices.min() < 0 or dst_indices.max() >= len(dst_feats):
        raise ValueError(f"Destination indices out of bounds [0, {len(dst_feats)-1}]")

    # Extract the features for the specific nodes in the edges
    edge_src_feats = src_feats[src_indices]
    edge_dst_feats = dst_feats[dst_indices]
    
    # Concatenate: [Drug_Features | Disease_Features]
    X = np.concatenate([edge_src_feats, edge_dst_feats], axis=1)
        
    return X.astype(np.float32)
