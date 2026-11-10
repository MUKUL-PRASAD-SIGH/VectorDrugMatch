import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.scoring.eml_status import CONFIRMED, COMBO, NEGATIVE, UNRESOLVED, classify, stems  # noqa: E402

UM = ["pancreatic enzymes", "sodium thiosulfate", "octreotide"]


def test_confirmed_positive():
    assert classify("DB1", "Anything", {"DB1"}, set(), UM) == (CONFIRMED, 1.0)


def test_combination_only_is_empty_not_zero():
    ev, v = classify("DB2", "Lopinavir", {"DB1"}, {"DB2"}, UM)
    assert ev == COMBO and np.isnan(v)


def test_unresolved_possible_match_is_empty_not_zero():
    ev, v = classify("DB3", "Sodium thiosulfate pentahydrate", set(), set(), UM)       # stem 'thios' overlaps an unmapped entry
    assert ev == UNRESOLVED and np.isnan(v)
    ev, v = classify("DB4", "Pancrelipase", set(), set(), UM)                          # stem 'pancr' overlaps 'pancreatic enzymes'
    assert ev == UNRESOLVED and np.isnan(v)


def test_no_candidate_is_zero_but_labelled_not_verified():
    ev, v = classify("DB5", "Zzzdrug", set(), set(), UM)
    assert ev == NEGATIVE and v == 0.0 and "verified" not in ev


def test_generic_words_do_not_create_false_unresolved():
    assert "sodium" not in stems("sodium chloride") and classify("DB6", "Sodium chloride", set(), set(), ["sodium nitrite"])[0] == NEGATIVE


def test_unresolved_never_becomes_zero_without_candidate_loss():
    # every drug sharing a stem with any unmapped entry must stay empty
    for name in ["Octreotide acetate", "Pancreatin", "Thiosulfate"]:
        ev, v = classify("X", name, set(), set(), UM)
        assert np.isnan(v) and ev == UNRESOLVED


def test_ndpi_does_not_treat_missing_as_zero():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import build_equity_features as b
    W = {"eml": 0.45, "daly": 0.45, "access": 0.10}
    df = pd.DataFrame({"eml_score": [1.0, np.nan, np.nan], "daly_score": [np.nan, np.nan, 0.5], "access_score": [np.nan, np.nan, np.nan]})
    out = b.ndpi(df, W)
    assert out.iloc[0] == 1.0 and out.iloc[2] == 0.5 and np.isnan(out.iloc[1])        # renormalised; no component -> empty, not 0
