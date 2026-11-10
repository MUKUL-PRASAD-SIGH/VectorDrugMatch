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
    is_curated: np.ndarray | None = None   # True for curated (explicit NOT) negatives

def _sample_negative_edges_random(pos_src: np.ndarray, pos_dst: np.ndarray, 
                                  num_src_nodes: int, num_dst_nodes: int, 
                                  num_neg: int, rng: np.random.Generator,
                                  forbid: set | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Internal function for random negative sampling (Easy Negatives)."""
    max_possible = num_src_nodes * num_dst_nodes
    pos_set = set(zip(pos_src, pos_dst)) | (forbid or set())
    
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
                                num_neg: int, rng: np.random.Generator,
                                forbid: set | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Internal function for hard negative sampling (Corrupted Edges).
    
    Instead of picking nodes totally at random (which might pick inactive nodes),
    this forces the negative edge to be composed of an active drug and an active disease,
    forcing the model to learn specific chemistry rather than just 'is this node active?'.
    """
    pos_set = set(zip(pos_src, pos_dst)) | (forbid or set())
    unique_src = np.unique(pos_src)
    unique_dst = np.unique(pos_dst)
    
    if len(unique_src) == 0 or len(unique_dst) == 0:
        # Fallback to random if no positives exist
        return _sample_negative_edges_random(pos_src, pos_dst, num_src_nodes, num_dst_nodes, num_neg, rng, forbid)
        
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
            num_src_nodes, num_dst_nodes, remaining, rng, forbid=forbid
        )
        neg_src_list.extend(rand_src)
        neg_dst_list.extend(rand_dst)
            
    return np.array(neg_src_list, dtype=np.int64), np.array(neg_dst_list, dtype=np.int64)


def build_link_prediction_dataset(pos_src: np.ndarray, pos_dst: np.ndarray, 
                                  num_src_nodes: int, num_dst_nodes: int, 
                                  neg_ratio: float = 1.0, seed: int = 42,
                                  strategy: str = "hard",
                                  fixed_neg: tuple | None = None,
                                  forbid_pairs: tuple | None = None) -> NegativeSamplingResult:
    """Generate negative edges and combine them with positive edges.

    forbid_pairs: optional (src, dst) arrays of KNOWN pairs of any relation (e.g. contraindications,
    off-label uses) that must never be sampled as negatives.
    fixed_neg: optional (src, dst) arrays of curated true negatives. They are always
    included (up to the neg_ratio budget) and the rest is filled by `strategy` sampling.
    """
    
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

    fixed_src = np.array([], dtype=np.int64)
    fixed_dst = np.array([], dtype=np.int64)
    if fixed_neg is not None and len(fixed_neg[0]) > 0:
        pos_set = set(zip(pos_src.tolist(), pos_dst.tolist()))
        pairs = {(int(a), int(b)) for a, b in zip(*fixed_neg) if (int(a), int(b)) not in pos_set}
        pairs = sorted(pairs)
        if len(pairs) > num_neg:
            keep = rng.choice(len(pairs), size=num_neg, replace=False)
            pairs = [pairs[i] for i in sorted(keep)]
        if pairs:
            fixed_src = np.array([a for a, _ in pairs], dtype=np.int64)
            fixed_dst = np.array([b for _, b in pairs], dtype=np.int64)
    n_sample = num_neg - len(fixed_src)
    forbid = (set(zip(np.asarray(forbid_pairs[0]).tolist(), np.asarray(forbid_pairs[1]).tolist()))
              if forbid_pairs is not None else None)
    # sampled negatives must not collide with positives or the curated negatives
    ex_src = np.concatenate([pos_src.astype(np.int64), fixed_src])
    ex_dst = np.concatenate([pos_dst.astype(np.int64), fixed_dst])

    if n_sample <= 0:
        samp_src = samp_dst = np.array([], dtype=np.int64)
    elif strategy == "random":
        samp_src, samp_dst = _sample_negative_edges_random(ex_src, ex_dst, num_src_nodes, num_dst_nodes, n_sample, rng, forbid)
    elif strategy == "hard":
        samp_src, samp_dst = _sample_negative_edges_hard(ex_src, ex_dst, num_src_nodes, num_dst_nodes, n_sample, rng, forbid)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
    neg_src = np.concatenate([fixed_src, samp_src])
    neg_dst = np.concatenate([fixed_dst, samp_dst])
            
    # Combine positive and negative edges
    all_src = np.concatenate([pos_src.astype(np.int64), neg_src])
    all_dst = np.concatenate([pos_dst.astype(np.int64), neg_dst])
    
    edge_index = np.vstack([all_src, all_dst])
    labels = np.concatenate([np.ones(num_pos, dtype=np.int8), np.zeros(len(neg_src), dtype=np.int8)])
    curated_flag = np.concatenate([np.zeros(num_pos, dtype=bool), np.ones(len(fixed_src), dtype=bool),
                                   np.zeros(len(samp_src), dtype=bool)])
    
    # Shuffle
    perm = rng.permutation(len(labels))
    edge_index = edge_index[:, perm]
    labels = labels[perm]
    curated_flag = curated_flag[perm]

    return NegativeSamplingResult(edge_index=edge_index, labels=labels, is_curated=curated_flag)
