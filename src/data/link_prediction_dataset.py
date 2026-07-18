"""
src/data/link_prediction_dataset.py - Graph Link Prediction Dataset Builder

Provides a reusable strategy for generating negative edges (links that do not exist)
and combining them with positive edges to train binary classifiers for link prediction.
"""

import numpy as np
from dataclasses import dataclass

@dataclass
class NegativeSamplingResult:
    edge_index: np.ndarray
    labels: np.ndarray

def _sample_negative_edges_random(pos_src: np.ndarray, pos_dst: np.ndarray, 
                                  num_src_nodes: int, num_dst_nodes: int, 
                                  num_neg: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Internal function for random negative sampling (Easy Negatives)."""
    max_possible = num_src_nodes * num_dst_nodes
    pos_set = set(zip(pos_src, pos_dst))
    
    if len(pos_set) + num_neg > max_possible:
        raise ValueError("Graph capacity exceeded.")
    
    neg_src_list, neg_dst_list = [], []
    attempts, max_attempts = 0, num_neg * 20
    
    while len(neg_src_list) < num_neg:
        if attempts >= max_attempts:
            raise RuntimeError("Could not generate enough random negative samples.")
            
        u = rng.integers(0, num_src_nodes)
        v = rng.integers(0, num_dst_nodes)
        attempts += 1
        
        if (u, v) not in pos_set:
            neg_src_list.append(u)
            neg_dst_list.append(v)
            pos_set.add((u, v))
            
    return np.array(neg_src_list, dtype=np.int64), np.array(neg_dst_list, dtype=np.int64)


def _sample_negative_edges_hard(pos_src: np.ndarray, pos_dst: np.ndarray, 
                                num_src_nodes: int, num_dst_nodes: int, 
                                num_neg: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Internal function for hard negative sampling (Corrupted Edges).
    
    Instead of picking nodes totally at random (which might pick inactive nodes),
    this forces the negative edge to be composed of an active drug and an active disease,
    forcing the model to learn specific chemistry rather than just 'is this node active?'.
    """
    pos_set = set(zip(pos_src, pos_dst))
    unique_src = np.unique(pos_src)
    unique_dst = np.unique(pos_dst)
    
    if len(unique_src) == 0 or len(unique_dst) == 0:
        # Fallback to random if no positives exist
        return _sample_negative_edges_random(pos_src, pos_dst, num_src_nodes, num_dst_nodes, num_neg, rng)
        
    neg_src_list, neg_dst_list = [], []
    attempts, max_attempts = 0, num_neg * 20
    
    while len(neg_src_list) < num_neg:
        if attempts >= max_attempts:
            # Fallback to random if we exhausted hard combinations
            break
            
        u = rng.choice(unique_src)
        v = rng.choice(unique_dst)
        attempts += 1
        
        if (u, v) not in pos_set:
            neg_src_list.append(u)
            neg_dst_list.append(v)
            pos_set.add((u, v))
            
    # If hard sampling failed to get enough (graph too dense), fill remainder with random
    remaining = num_neg - len(neg_src_list)
    if remaining > 0:
        print(f"    [WARNING] Hard negatives exhausted. Falling back to {remaining} random negatives.")
        rand_src, rand_dst = _sample_negative_edges_random(
            np.concatenate([pos_src, neg_src_list]), 
            np.concatenate([pos_dst, neg_dst_list]), 
            num_src_nodes, num_dst_nodes, remaining, rng
        )
        neg_src_list.extend(rand_src)
        neg_dst_list.extend(rand_dst)
            
    return np.array(neg_src_list, dtype=np.int64), np.array(neg_dst_list, dtype=np.int64)


def build_link_prediction_dataset(pos_src: np.ndarray, pos_dst: np.ndarray, 
                                  num_src_nodes: int, num_dst_nodes: int, 
                                  neg_ratio: float = 1.0, seed: int = 42,
                                  strategy: str = "hard") -> NegativeSamplingResult:
    """Generate negative edges and combine them with positive edges."""
    
    # Validation checks
    if len(pos_src) != len(pos_dst):
        raise ValueError("Length mismatch between pos_src and pos_dst.")
    if num_src_nodes <= 0 or num_dst_nodes <= 0:
        raise ValueError("Graph size invalid.")
    if neg_ratio <= 0:
        raise ValueError("neg_ratio must be > 0.")

    rng = np.random.default_rng(seed)
    num_pos = len(pos_src)
    num_neg = int(num_pos * neg_ratio)

    if strategy == "random":
        neg_src, neg_dst = _sample_negative_edges_random(pos_src, pos_dst, num_src_nodes, num_dst_nodes, num_neg, rng)
    elif strategy == "hard":
        neg_src, neg_dst = _sample_negative_edges_hard(pos_src, pos_dst, num_src_nodes, num_dst_nodes, num_neg, rng)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
            
    # Combine positive and negative edges
    all_src = np.concatenate([pos_src.astype(np.int64), neg_src])
    all_dst = np.concatenate([pos_dst.astype(np.int64), neg_dst])
    
    edge_index = np.vstack([all_src, all_dst])
    labels = np.concatenate([np.ones(num_pos, dtype=np.int8), np.zeros(num_neg, dtype=np.int8)])
    
    # Shuffle
    perm = rng.permutation(len(labels))
    edge_index = edge_index[:, perm]
    labels = labels[perm]
    
    return NegativeSamplingResult(edge_index=edge_index, labels=labels)
