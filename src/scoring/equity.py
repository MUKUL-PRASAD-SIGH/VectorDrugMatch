"""
src/scoring/equity.py - WHO Equity and Affordability Scoring

Evaluates the accessibility and public health impact of the drug for NTDs.
Combines:
  1. WHO Essential Medicines List (EML) presence
  2. WHO GHO DALY (Disability-Adjusted Life Years) burden
  3. Affordability proxy (molecular weight simplicity)
"""

import math
import pandas as pd


def get_affordability_score(molecular_weight: float) -> float:
    """Proxy for manufacturing cost based on molecular complexity.
    
    Smaller molecules tend to be cheaper to synthesize at scale.
    Formula: 1 / (1 + ln(1 + MW/200))
    
    Args:
        molecular_weight: MW from RDKit descriptors.
        
    Returns:
        Score [0.0, 1.0] where higher means more affordable.
    """
    if pd.isna(molecular_weight) or molecular_weight <= 0:
        return 0.5  # Neutral default
        
    # Scale: MW 200 -> ~0.58, MW 500 -> ~0.44, MW 1000 -> ~0.35
    return 1.0 / (1.0 + math.log1p(molecular_weight / 200.0))


def get_atc_proxy_score(atc_code: str) -> float:
    """Proxy for WHO/ATC category relevance to NTDs.
    
    J = Antiinfectives for systemic use
    P = Antiparasitic products, insecticides and repellents
    
    Args:
        atc_code: ATC code string (e.g., 'J01CA04').
        
    Returns:
        Score [0.0, 1.0] based on NTD relevance.
    """
    if not atc_code or pd.isna(atc_code):
        return 0.0
    
    atc_code = str(atc_code).upper().strip()
    if atc_code.startswith('P') or atc_code.startswith('J'):
        return 1.0
    # Other classes receive a partial bump
    return 0.5


def compute_equity_score(is_on_eml: bool, daly_normalized: float, mw: float, atc_code: str = None) -> float:
    """Compute the combined Equity Score [0, 1] for NDPI.
    
    Weights:
      - 35% WHO EML status (is it an established, accessible medicine?)
      - 35% DALY burden (does this disease desperately need attention?)
      - 15% Affordability (can it be cheaply manufactured?)
      - 15% ATC proxy (is it in a relevant therapeutic class?)
      
    Args:
        is_on_eml: Boolean indicating presence on WHO EML.
        daly_normalized: Normalised [0,1] DALY burden for the target disease.
        mw: Molecular weight of the candidate drug.
        atc_code: Anatomical Therapeutic Chemical code.
        
    Returns:
        Combined equity score [0.0, 1.0].
    """
    eml_component = 1.0 if is_on_eml else 0.0
    affordability_component = get_affordability_score(mw)
    atc_component = get_atc_proxy_score(atc_code)
    
    # Ensure daly_normalized is bounded
    daly_component = max(0.0, min(float(daly_normalized), 1.0))
    
    score = (
        (0.35 * eml_component) +
        (0.35 * daly_component) +
        (0.15 * affordability_component) +
        (0.15 * atc_component)
    )
    
    return float(score)
