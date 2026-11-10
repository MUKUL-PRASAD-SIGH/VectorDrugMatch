"""
src/features/disease.py - Disease Feature Engineering

Encodes disease metadata into numerical features:
  - DALY burden (normalised [0,1]); missing DALY stays NaN until the final matrix
  - WHO NTD classification flag (DOID join preferred, whole-word name match fallback)
  - Disease category encoding
"""

import re

import numpy as np
import pandas as pd
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
    "noma",
    "scabies",
    "snakebite envenoming",
}

_NTD_PATTERNS = [re.compile(r"\b" + re.escape(n) + r"\b") for n in sorted(WHO_NTD_NAMES)]


def is_ntd(disease_name: str) -> int:
    """Name-based WHO NTD check (fallback when no DOID list is available).

    Uses whole-word matching in one direction only (NTD term inside the disease name),
    so "melanoma" no longer matches "noma".
    """
    name_lower = str(disease_name).lower().strip()
    return int(any(p.search(name_lower) for p in _NTD_PATTERNS))


def normalize_daly(daly_values: pd.Series) -> pd.Series:
    """Min-max normalise DALY values to [0, 1], ignoring NaN (kept as NaN).

    Returns all-NaN if no value is known, so callers can tell "unknown" from "zero".
    """
    known = daly_values.dropna()
    if known.empty:
        return pd.Series(np.nan, index=daly_values.index)
    min_val, max_val = known.min(), known.max()
    if max_val == min_val:
        return daly_values.where(daly_values.isna(), 0.0)
    return (daly_values - min_val) / (max_val - min_val)


def featurize_diseases_df(diseases_df: pd.DataFrame) -> pd.DataFrame:
    """Add numerical features to a diseases DataFrame.

    - is_ntd: kept as-is if the column already exists (set from the WHO DOID join in
      preprocess.py); otherwise derived from the disease name.
    - daly_normalized: min-max of daly_rate; NaN where DALY is unknown.
    """
    result = diseases_df.copy()

    if "is_ntd" not in result.columns:
        if "disease_name" in result.columns:
            result["is_ntd"] = result["disease_name"].apply(is_ntd)
        else:
            result["is_ntd"] = 0

    if "daly_rate" in result.columns:
        result["daly_rate"] = pd.to_numeric(result["daly_rate"], errors="coerce")
        result["daly_normalized"] = normalize_daly(result["daly_rate"])
    else:
        result["daly_rate"] = np.nan
        result["daly_normalized"] = np.nan

    return result


def disease_feature_vector(disease_row: pd.Series) -> np.ndarray:
    """Feature vector [is_ntd, daly_normalized, daly_rate_log] (unknown DALY -> 0)."""
    is_ntd_val = float(disease_row.get("is_ntd", 0))
    daly_norm = disease_row.get("daly_normalized", np.nan)
    daly_raw = disease_row.get("daly_rate", np.nan)
    daly_norm = 0.0 if pd.isna(daly_norm) else float(daly_norm)
    daly_log = 0.0 if pd.isna(daly_raw) else float(np.log1p(daly_raw))
    return np.array([is_ntd_val, daly_norm, daly_log], dtype=np.float32)


def build_disease_feature_matrix(diseases_df: pd.DataFrame, config_flags: dict) -> np.ndarray:
    """Build the final disease feature matrix based on configuration flags."""
    df = featurize_diseases_df(diseases_df)
    basic_feats = np.vstack([disease_feature_vector(row) for _, row in df.iterrows()])

    # Constant columns (e.g. DALY all unknown) must not be scaled into NaN/inf
    scaler = RobustScaler()
    scaled = scaler.fit_transform(basic_feats)
    scaled = np.nan_to_num(scaled, nan=0.0, posinf=0.0, neginf=0.0)
    basic_feats = scaled.astype(np.float32)

    if config_flags.get("use_sapbert", False):
        sapbert_feats = compute_sapbert_embeddings(diseases_df, name_col="disease_name")
        print("    Replacing basic disease features with 768-dim SapBERT embeddings.")
        return sapbert_feats

    return basic_feats


def compute_sapbert_embeddings(diseases_df: pd.DataFrame, name_col: str = "name") -> np.ndarray:
    raise NotImplementedError("Implemented in Phase 4")
