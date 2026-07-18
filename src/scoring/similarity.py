"""
src/scoring/similarity.py - Molecular Similarity Scoring

Calculates the chemical similarity between a candidate drug and drugs 
already known to treat the target disease.

Method: Tanimoto similarity coefficient over 2048-bit Morgan Fingerprints.
"""

import numpy as np

try:
    from rdkit import Chem
    from rdkit.Chem import DataStructs, AllChem
    RDKIT_AVAILABLE = True
except ImportError:
    RDKIT_AVAILABLE = False

from functools import lru_cache
import pandas as pd

@lru_cache(maxsize=10000)
def _compute_fp(smiles: str, radius: int = 2, n_bits: int = 2048):
    """Helper to safely compute and cache RDKit fingerprint."""
    if not RDKIT_AVAILABLE or not smiles or pd.isna(smiles):
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return AllChem.GetMorganFingerprintAsBitVect(mol, radius=radius, nBits=n_bits)


def compute_similarity_scores(candidate_smiles: str, 
                               known_drugs_smiles: list[str],
                               top_k: int = 3) -> dict:
    """Compute normalized similarity scores [0, 1] for a candidate drug.
    
    Returns max, mean, and top-k Tanimoto similarities between the candidate
    and known drugs that treat the disease.
    
    Args:
        candidate_smiles: SMILES string of the candidate drug.
        known_drugs_smiles: List of SMILES strings for known drugs.
        top_k: K nearest known drugs to average for top-k score.
        
    Returns:
        Dict of max_sim, mean_sim, and top_k_mean.
    """
    empty_scores = {"max_sim": 0.0, "mean_sim": 0.0, f"top_{top_k}_mean": 0.0}
    
    if not RDKIT_AVAILABLE:
        return empty_scores
        
    cand_fp = _compute_fp(candidate_smiles)
    if cand_fp is None or not known_drugs_smiles:
        return empty_scores
        
    similarities = []
    for known_smi in known_drugs_smiles:
        known_fp = _compute_fp(known_smi)
        if known_fp is not None:
            sim = DataStructs.TanimotoSimilarity(cand_fp, known_fp)
            similarities.append(sim)
            
    if not similarities:
        return empty_scores
        
    similarities.sort(reverse=True)
    
    return {
        "max_sim": float(similarities[0]),
        "mean_sim": float(np.mean(similarities)),
        f"top_{top_k}_mean": float(np.mean(similarities[:top_k]))
    }
