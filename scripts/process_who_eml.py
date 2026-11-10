"""
scripts/process_who_eml.py - map a WHO Essential Medicines List file onto PrimeKG drugs.

    python scripts/process_who_eml.py [--input data/external/who_eml.csv]

Input (you supply it; see Docs/EQUITY_DATA_SPECS.md): CSV with a `name` column (generic medicine), optional `drugbank_id`,
`atc_code`, `section`, `edition` (e.g. "23rd List, 2023"). If the file is absent the script exits WITHOUT writing anything, so
downstream code treats EML status as UNKNOWN (NaN) - it is never defaulted to 0.
Mapping: DrugBank id if given, else exact normalised name (no fuzzy matching); >1 DrugBank id for a name = ambiguous (not used).
A drug on the list gets eml_status=1 (matched_by recorded). When a list IS supplied, drugs not on it get eml_status=0 in
build_equity_features.py (the list is then treated as complete for the edition stated).
Output: data/processed/eml/eml_drug_flags.csv, eml_unmatched.csv, eml_report.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
SALTS = r"\b(hydrochloride|hcl|sodium|potassium|sulphate|sulfate|phosphate|acetate|maleate|besylate|tartrate|citrate|succinate|mesylate|bromide|calcium)\b"


def norm(s):
    return re.sub(r"\s+", " ", re.sub(SALTS, "", re.sub(r"[^a-z0-9+ ]", "", str(s).lower().replace("sulphate", "sulfate")))).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/external/who_eml.csv")
    a = ap.parse_args()
    p = REPO / a.input
    if not p.exists():
        sys.exit(f"{a.input} not found: EML status stays UNKNOWN downstream (nothing written).")
    eml = pd.read_csv(p)
    if "name" not in eml.columns:
        sys.exit("who_eml.csv needs a `name` column")
    dr = pd.read_csv(REPO / "data" / "processed" / "primekg" / "drugs.csv", usecols=["drug_id", "name"])
    by_id = set(dr.drug_id)
    idx = {}
    for d, n in zip(dr.drug_id, dr.name.astype(str)):
        idx.setdefault(norm(n), set()).add(d)
    rows, unmatched = [], []
    for r in eml.itertuples():
        dbid = getattr(r, "drugbank_id", None)
        if isinstance(dbid, str) and dbid in by_id:
            hit, how = {dbid}, "drugbank_id"
        else:
            hit, how = idx.get(norm(r.name), set()), "exact_normalised_name"
        if len(hit) == 1:
            rows.append({"drug_id": next(iter(hit)), "eml_status": 1, "matched_by": how, "eml_name": r.name,
                         "atc_code": getattr(r, "atc_code", None), "section": getattr(r, "section", None), "edition": getattr(r, "edition", None)})
        else:
            unmatched.append({"eml_name": r.name, "reason": "ambiguous" if len(hit) > 1 else "no_match"})
    out = REPO / "data" / "processed" / "eml"
    out.mkdir(parents=True, exist_ok=True)
    flags = pd.DataFrame(rows).drop_duplicates("drug_id")
    flags.to_csv(out / "eml_drug_flags.csv", index=False)
    pd.DataFrame(unmatched).to_csv(out / "eml_unmatched.csv", index=False)
    rep = {"eml_rows": len(eml), "mapped_drugs": int(len(flags)), "unmatched": len(unmatched), "mapped_by": flags.matched_by.value_counts().to_dict()}
    (out / "eml_report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
