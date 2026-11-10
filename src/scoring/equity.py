"""
src/scoring/equity.py - WHO Equity Scoring

    E = sum(w_k * c_k over KNOWN components) / sum(w_k over KNOWN components)

Components
  EML    1 if the drug is on the WHO Essential Medicines List, else 0.
  DALY   min-max normalised disease burden in [0, 1] (one consistent definition; see
         preprocess.load_daly_table).
  Access real availability / affordability / unmet-need score in [0, 1] (e.g. from a price
         guide or stockout data). No such data is wired in, so it is None by default.

Missing components (None / NaN) are DROPPED and the remaining weights renormalised, so an
unknown value neither raises nor lowers the score. If nothing is known the score is NaN.

ATC class is deliberately NOT part of the equity score: it classifies a drug
anatomically/therapeutically and says nothing about access. It stays available as a
drug attribute (`atc_codes`) for stratification / filtering (e.g. anti-infectives).
"""

import math

DEFAULT_WEIGHTS = {"eml": 0.45, "daly": 0.45, "access": 0.10}


def _known(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def compute_equity_score(is_on_eml=None, daly_normalized=None, access=None,
                         weights: dict | None = None) -> float:
    """Equity score in [0, 1], or NaN when no component is known. See module docstring."""
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    parts = []
    if _known(is_on_eml):
        parts.append((w["eml"], 1.0 if is_on_eml else 0.0))
    if _known(daly_normalized):
        parts.append((w["daly"], max(0.0, min(float(daly_normalized), 1.0))))
    if _known(access):
        parts.append((w["access"], max(0.0, min(float(access), 1.0))))
    total = sum(wt for wt, _ in parts)
    if total == 0:
        return float("nan")
    return float(sum(wt * v for wt, v in parts) / total)
