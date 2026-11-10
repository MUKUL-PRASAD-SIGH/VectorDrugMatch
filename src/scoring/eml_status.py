"""Classify a drug's WHO EML evidence. Missing or unresolved evidence is NEVER converted into a confirmed negative.

classes (eml_evidence) and the numeric eml_status they give:
  confirmed_positive_single_entry      1.0   drug mapped to a single-ingredient EML entry
  combination_component_only           NaN   drug appears only inside fixed-dose combinations
  unresolved_possible_unmapped_entry   NaN   drug name shares a stem with an EML single entry that could not be mapped
  negative_no_candidate_entry          0.0   no candidate entry found by any tier: NOT a verified negative (name-matching is bounded)
"""
import re

import numpy as np

STOP = {"sodium", "potassium", "calcium", "chloride", "sulfate", "acid", "oral", "solution", "human", "vaccine", "immunoglobulin", "injection", "water",
        "compound", "salts", "salt", "plasma", "recombinant", "analogue", "derived", "base", "resin", "system", "device", "hydrogen", "carbonate",
        "purified", "protein", "derivative", "agents", "replacement", "therapy", "broad", "spectrum", "based", "with", "long", "acting", "short", "rapid",
        "intermediate", "pathogen", "reduced", "powder", "multiple"}
CONFIRMED, COMBO, UNRESOLVED, NEGATIVE = ("confirmed_positive_single_entry", "combination_component_only",
                                          "unresolved_possible_unmapped_entry", "negative_no_candidate_entry")


def stems(text):
    return {t[:5] for t in re.findall(r"[a-z]{5,}", str(text).lower()) if t not in STOP}


def classify(drug_id, drug_name, on, combo_only, unmapped_entry_names):
    um = set().union(*(stems(n) for n in unmapped_entry_names)) if unmapped_entry_names else set()
    if drug_id in on:
        return CONFIRMED, 1.0
    if drug_id in combo_only:
        return COMBO, np.nan
    if stems(drug_name) & um:
        return UNRESOLVED, np.nan
    return NEGATIVE, 0.0
