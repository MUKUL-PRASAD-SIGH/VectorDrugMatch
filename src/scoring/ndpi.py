"""
src/scoring/ndpi.py - Novel Drug Potential Index (NDPI)

Combines ML predictions, structural similarity, literature evidence, and equity 
considerations into a single composite score to rank repurposing candidates.
"""

from .similarity import compute_similarity_scores
from .literature import compute_literature_score
from .equity import compute_equity_score

def calculate_ndpi(
    ml_probability: float,
    similarity_score: float,
    literature_score: float,
    equity_score: float,
    weights: dict = None
) -> float:
    """
    Calculates the Novel Drug Potential Index (NDPI).
    
    Args:
        ml_probability: Raw probability output from the ML model [0.0, 1.0].
        similarity_score: Max or Mean Tanimoto similarity to known drugs [0.0, 1.0].
        literature_score: Normalized PubMed co-occurrence score [0.0, 1.0].
        equity_score: Combined EML, DALY, Affordability score [0.0, 1.0].
        weights: Dictionary of weights for the composite score. 
                 Defaults to 40% ML, 20% Sim, 20% Lit, 20% Equity.
                 
    Returns:
        NDPI composite score [0.0, 1.0].
    """
    if weights is None:
        weights = {
            "ml": 0.40,
            "similarity": 0.20,
            "literature": 0.20,
            "equity": 0.20
        }
        
    # config.yaml names the ML weight "gnn"; accept it as an alias for "ml"
    if "gnn" in weights and "ml" not in weights:
        weights = {**weights, "ml": weights["gnn"]}

    # Normalise by the total of the weights actually used
    total_weight = sum(weights.get(k, 0) for k in ("ml", "similarity", "literature", "equity"))
    
    score = (
        (ml_probability * weights.get("ml", 0)) +
        (similarity_score * weights.get("similarity", 0)) +
        (literature_score * weights.get("literature", 0)) +
        (equity_score * weights.get("equity", 0))
    ) / total_weight
    
    return float(score)
