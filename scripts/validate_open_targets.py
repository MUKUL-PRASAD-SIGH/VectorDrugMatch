"""
scripts/validate_open_targets.py - hard checks on data/processed/open_targets/ (written by open_targets_indications.py).

    python scripts/validate_open_targets.py

Exit code 1 if any [FAIL]. Checks: schema, ID formats, uniqueness, status reconciliation with the report,
tier separation (exact xref vs parent fallback), stage vocabulary / approved flag, no leakage into PrimeKG splits.
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "processed" / "open_targets"
fails = []


def check(ok, msg, hard=True):
    print(f"  [{'PASS' if ok else ('FAIL' if hard else 'WARN')}] {msg}")
    if not ok and hard:
        fails.append(msg)


def main():
    rep = json.loads((OUT / "mapping_report.json").read_text(encoding="utf-8"))
    m = pd.read_csv(OUT / "indications_mapped.csv", low_memory=False, keep_default_na=False)
    p1 = pd.read_csv(OUT / "pairs_drugbank_mondo.csv", keep_default_na=False)
    p2 = pd.read_csv(OUT / "pairs_drugbank_mondo_parent_fallback.csv", keep_default_na=False)

    print("=== schema ===")
    need_m = {"chembl_id", "drugbank_ids", "drug_status", "drug_map_tier", "ot_disease_id", "mondo_id", "mondo_status",
              "max_clinical_stage", "n_clinical_reports", "clinical_report_ids", "source", "source_file_sha1"}
    need_p = {"drugbank_id", "mondo_id", "max_clinical_stage", "stages_seen", "approved", "drug_map_tier", "source", "n_source_rows"}
    check(need_m <= set(m.columns), f"indications_mapped.csv has required columns")
    check(need_p <= set(p1.columns) and need_p <= set(p2.columns), "both pair files have required columns")

    print("=== row accounting ===")
    n = rep["rows"]["clinical_reports"]
    check(len(m) == n, f"every input row kept ({len(m):,} == {n:,})")
    check(sum(rep["drugs"]["rows_by_status"].values()) == n, "drug status counts sum to all rows")
    check(sum(rep["diseases"]["rows_by_status"].values()) == n, "disease status counts sum to all rows")
    check(m.drug_status.isin(["mapped", "ambiguous", "no_drugbank_xref"]).all(), "drug_status vocabulary closed")
    check(m.drug_map_tier.isin(["1_exact_xref", "2_parent_fallback", "none"]).all(), "drug_map_tier vocabulary closed")
    check(not m.duplicated(["chembl_id", "ot_disease_id"]).any(), "no duplicate (ChEMBL, OT disease) rows in the raw input")

    print("=== id formats ===")
    db_re, mondo_re = re.compile(r"^DB\d{5}$"), re.compile(r"^MONDO:\d{7}$")
    for name, d in (("tier-1", p1), ("tier-2", p2)):
        check(d.drugbank_id.map(lambda x: bool(db_re.match(x))).all(), f"{name} pairs: DrugBank ids well-formed (single id)")
        check(d.mondo_id.map(lambda x: bool(mondo_re.match(x))).all(), f"{name} pairs: MONDO ids well-formed (single id)")
        check(not d.duplicated(["drugbank_id", "mondo_id"]).any(), f"{name} pairs unique on (DrugBank, MONDO)")
    check(not m[(m.drug_status == "ambiguous")].drug_map_tier.eq("1_exact_xref").any(), "ambiguous drugs never reach tier 1")

    print("=== tier separation ===")
    t1_keys = set(zip(p1.drugbank_id, p1.mondo_id))
    check((p1.drug_map_tier == "1_exact_xref").all() and (p2.drug_map_tier == "2_parent_fallback").all(), "tier labels on pair files")
    check(set(p1.chembl_ids.str.split("|").explode()) <= set(m[m.drug_map_tier == "1_exact_xref"].chembl_id),
          "tier-1 pairs come only from exact-xref ChEMBL ids")
    check(not (set(p2.chembl_ids.str.split("|").explode()) & set(m[m.drug_map_tier == "1_exact_xref"].chembl_id)),
          "tier-2 pairs contain no exact-xref ChEMBL id (tiers are not mixed)")
    flag = p2.already_in_tier1.astype(str).str.lower().eq("true")
    check(flag.sum() == sum(k in t1_keys for k in zip(p2.drugbank_id, p2.mondo_id)), "tier-2 'already_in_tier1' flag is correct")
    check(rep["pairs"]["clean_pairs_after_dedup"] == len(p1), "report pair count equals pairs file")

    print("=== stages ===")
    known = {"UNKNOWN", "PRECLINICAL", "IND", "EARLY_PHASE_1", "PHASE_1", "PHASE_1_2", "PHASE_2", "PHASE_2_3", "PHASE_3",
             "PHASE_4", "PREAPPROVAL", "APPROVAL", "WITHDRAWN", "WITHDRAWAL"}
    check(not rep["unknown_stage_values_not_ranked"], f"all observed stages are in the ordering table "
          f"(unranked: {rep['unknown_stage_values_not_ranked']})")
    check(set(m.max_clinical_stage) <= known, f"stage vocabulary known: {sorted(set(m.max_clinical_stage) - known)}", hard=False)
    exp = p1.stages_seen.map(lambda x: int("APPROVAL" in x.split("|")))
    check((exp == p1.approved).all(), "approved flag == any report with stage exactly APPROVAL (PREAPPROVAL excluded)")
    check((p1.max_clinical_stage.isin(p1.stages_seen.str.split("|").explode())).all(), "pair max stage is among stages seen")

    print("=== provenance ===")
    check((m.source == "OpenTargets").all() and m.source_file_sha1.str.len().eq(12).all(), "source + file hash on every row")
    check(all("sha1" in v for v in rep["inputs"].values()), "input SHA-1s recorded in the report")

    print("=== separation from the PrimeKG benchmark ===")
    for f in ("edges.csv", "splits/seed42.npz"):
        check(not (OUT / f).exists(), f"no copy of PrimeKG {f} in the Open Targets output dir")
    z = REPO / "data" / "processed" / "primekg" / "splits" / "seed42.manifest.json"
    if z.exists():
        man = json.loads(z.read_text())
        check("open_targets" not in json.dumps(man).lower(), "PrimeKG split manifest does not reference Open Targets")

    print(f"\n=== RESULT === {'all hard checks passed' if not fails else str(len(fails)) + ' FAILED'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
