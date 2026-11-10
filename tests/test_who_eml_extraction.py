"""Automated checks on the extracted WHO EML (data/external/who_eml.csv); skipped when the file is absent (it is git-ignored, CC BY-NC-SA 3.0 IGO)."""
from pathlib import Path

import pandas as pd
import pytest

F = Path(__file__).resolve().parents[1] / "data" / "external" / "who_eml.csv"
pytestmark = pytest.mark.skipif(not F.exists(), reason="who_eml.csv not present (run scripts/extract_who_eml_pdf.py)")
NTD_MEDICINES = ["praziquantel", "ivermectin", "albendazole", "mebendazole", "benznidazole", "nifurtimox", "miltefosine", "amphotericin B", "eflornithine",
                 "suramin sodium", "dapsone", "clofazimine", "permethrin", "benzyl benzoate", "triclabendazole", "niclosamide", "azithromycin", "rifampicin"]


def _d():
    return pd.read_csv(F, keep_default_na=False)


def test_structure_and_sections():
    d = _d()
    assert set(d.section_code.astype(str)) == {str(i) for i in range(1, 31)}, "the 24th list has 30 numbered sections"
    assert set(d.list) == {"core", "complementary"} and set(d.entry_type) == {"single", "combination"}
    assert d.pdf_page.between(6, 67).all(), "entries must come from the list pages only (annexes start on page 68)"
    assert (d.drugbank_id == "").all() and (d.atc_code == "").all(), "no identifiers may be invented"


def test_names_are_clean():
    d = _d()
    assert (d.name.str.len() <= 80).all() and not d.name.str.match(r"^\d").any()
    assert not d.name.str.contains(r"\s[a-z]$").any(), "footnote letters must not remain on names"
    assert not d.name.str.contains(r"[^\x20-\x7e]").any(), "stray glyphs must not remain on names"
    assert d.name.str.count(r"\(").eq(d.name.str.count(r"\)")).all(), "no unclosed parentheses"
    assert not d.name.str.contains("explanation|group antibiotics|antibiotic stewardship", case=False).any()


def test_known_ntd_medicines_present():
    names = set(_d().name.str.lower())
    missing = [m for m in NTD_MEDICINES if m.lower() not in names]
    assert not missing, f"expected WHO list entries not extracted: {missing}"


def test_combinations_are_split_correctly():
    d = _d()
    c = set(d[d.entry_type == "combination"].name)
    assert "ethambutol + isoniazid + pyrazinamide + rifampicin" in c and "artemether + lumefantrine" in c and "lopinavir + ritonavir" in c


def test_superscript_footnote_marks_do_not_enter_names():
    names = set(_d().name)
    for bad in ("thoctreotide", "thlevonorgestrel-releasing intrauterine system", "thefavirenz + emtricitabine + tenofovir"):
        assert bad not in names                      # 5.5pt superscript 'th' (PDF pp.55, 59) was glued to the next name
    assert {"octreotide", "levonorgestrel-releasing intrauterine system", "efavirenz + emtricitabine + tenofovir"} <= names
    assert "losartan" in names                       # genuine 9pt prefix fragments (lo + sartan) are still joined


def test_copackaged_entries_are_combinations():
    d = _d().set_index("name")
    for n in ("mifepristone + misoprostol", "oral rehydration salts + zinc sulfate", "artesunate + sulfadoxine + pyrimethamine", "amodiaquine + sulfadoxine + pyrimethamine"):
        assert d.loc[n, "entry_type"] == "combination" and "U+2013" in d.loc[n, "extraction_note"]
