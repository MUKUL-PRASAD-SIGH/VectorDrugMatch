"""
src/features/disease.py - Disease Feature Engineering

Encodes disease metadata into numerical features:
  - DALY burden (normalised [0,1])
  - WHO NTD classification flag
  - Disease category encoding
"""

import numpy as np
import pandas as pd
from typing import Tuple
from sklearn.preprocessing import RobustScaler


# WHO-classified Neglected Tropical Diseases (NTDs)
WHO_NTD_NAMES = {
    "lymphatic filariasis",
    "leishmaniasis",
    "chagas disease",
    "african trypanosomiasis",
    "sleeping sickness",
    "schistosomiasis",
    "onchocerciasis",
    "river blindness",
    "buruli ulcer",
    "dengue",
    "rabies",
    "soil-transmitted helminthiases",
    "trachoma",
    "leprosy",
    "yaws",
    "dracunculiasis",
    "echinococcosis",
    "foodborne trematodiases",
    "mycetoma",
    "chromoblastomycosis",
    "snakebite envenoming",
}


def is_ntd(disease_name: str) -> int:
    """Check if a disease name matches a WHO NTD.

    Returns:
        1 if the disease is classified as an NTD, 0 otherwise.
    """
    name_lower = disease_name.lower().strip()
    for ntd in WHO_NTD_NAMES:
        if ntd in name_lower or name_lower in ntd:
            return 1
    return 0


def normalize_daly(daly_values: pd.Series) -> pd.Series:
    """Min-max normalise DALY values to [0, 1].

    Args:
        daly_values: Series of raw DALY rates.

    Returns:
        Normalised Series. Returns 0 if all values are equal.
    """
    min_val = daly_values.min()
    max_val = daly_values.max()
    if max_val == min_val:
        return pd.Series(np.zeros(len(daly_values)), index=daly_values.index)
    return (daly_values - min_val) / (max_val - min_val)


def featurize_diseases_df(diseases_df: pd.DataFrame) -> pd.DataFrame:
    """Add numerical features to a diseases DataFrame.

    Adds/updates columns:
      - is_ntd: 1 if WHO NTD, 0 otherwise
      - daly_normalized: normalised DALY rate [0, 1]

    Args:
        diseases_df: DataFrame with disease_name and optionally daly_rate columns.

    Returns:
        Updated DataFrame with feature columns.
    """
    result = diseases_df.copy()

    # NTD flag
    if "disease_name" in result.columns:
        result["is_ntd"] = result["disease_name"].apply(is_ntd)

    # Normalised DALY
    if "daly_rate" in result.columns:
        result["daly_normalized"] = normalize_daly(result["daly_rate"].fillna(0))
    else:
        result["daly_rate"] = 0.0
        result["daly_normalized"] = 0.0

    return result


def disease_feature_vector(disease_row: pd.Series) -> np.ndarray:
    """Produce a feature vector for a single disease.

    Layout: [is_ntd, daly_normalized, daly_rate_log]

    Args:
        disease_row: A row from the diseases DataFrame.

    Returns:
        1D numpy array of shape (3,).
    """
    is_ntd_val = float(disease_row.get("is_ntd", 0))
    daly_norm = float(disease_row.get("daly_normalized", 0.0))
    daly_raw = float(disease_row.get("daly_rate", 0.0))
    daly_log = np.log1p(daly_raw)

    return np.array([is_ntd_val, daly_norm, daly_log], dtype=np.float32)

def build_disease_feature_matrix(diseases_df: pd.DataFrame, config_flags: dict) -> np.ndarray:
    """
    Builds the final disease feature matrix based on configuration flags.
    If SapBERT is requested, it concatenates (or replaces) basic features.
    """
    # Always generate basic features first
    df = featurize_diseases_df(diseases_df)
    basic_feats = np.vstack([disease_feature_vector(row) for _, row in df.iterrows()])
    
    # Scale disease features for linear/MLP models
    scaler = RobustScaler()
    basic_feats = scaler.fit_transform(basic_feats).astype(np.float32)
    
    if config_flags.get("use_sapbert", False):
        sapbert_feats = compute_sapbert_embeddings(diseases_df, name_col="disease_name")
        print("    Replacing basic disease features with 768-dim SapBERT embeddings.")
        return sapbert_feats
        
    return basic_feats

def compute_sapbert_embeddings(diseases_df: pd.DataFrame, name_col: str = "name") -> np.ndarray:
    raise NotImplementedError("Implemented in Phase 4")
