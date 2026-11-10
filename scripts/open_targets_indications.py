"""
scripts/open_targets_indications.py - audit-first loader for Open Targets clinical indications.

    python scripts/open_targets_indications.py [--ot-dir data/external/downloads/open_targets]

STRICTLY SEPARATE from the PrimeKG benchmark: reads only raw downloads + mondo.obo (+ PrimeKG tables
READ-ONLY for the overlap report) and writes only to data/processed/open_targets/. Nothing here is merged into
PrimeKG train / validation / test data.

Inputs (data/external/downloads/open_targets/, identified by columns, not by file name):
    clinical reports  (id, maxClinicalStage, clinicalReportIds, diseaseId, drugId)
    drug molecules    (id, crossReferences, parentId, ...)           -> ChEMBL -> DrugBank (explicit xrefs only)
    mechanisms        (read for provenance only; not used for labels)

Mapping rules (conservative; every input row is kept with a status, nothing is dropped silently):
  drugs    ChEMBL id -> DrugBank ids from the molecule's own `crossReferences` (source == drugbank).
           >1 DrugBank id = `ambiguous` (kept, flagged, excluded from the clean pairs file).
           Parent/child ChEMBL fall-backs are only COUNTED in the report, never applied.
  diseases MONDO_*  -> used directly; obsolete ids followed through replaced_by (src/data/mondo.py).
           EFO_/Orphanet_/NCIT_ -> MONDO only through MONDO xrefs qualified source="MONDO:equivalentTo".
           HP/MP/GO/OBA/OTAR are phenotype / non-disease ontologies -> `non_disease_ontology`, not mapped.
           MONDO -> DOID only via exact DOID xrefs (as in the PrimeKG pipeline).
  stage    maxClinicalStage is preserved verbatim; the pair-level value is the HIGHEST stage among its rows.

Outputs (data/processed/open_targets/):
    indications_mapped.csv        every input row + drug / disease mapping status + provenance
    pairs_drugbank_mondo.csv      de-duplicated TIER-1 pairs (exact DrugBank xref x resolved MONDO)
    pairs_drugbank_mondo_parent_fallback.csv   TIER-2 pairs (drug mapped via parent ChEMBL molecule); separate by design
    unmatched_drugs.csv, unmatched_diseases.csv
    primekg_overlap.csv           per-stage overlap with PrimeKG indications (description only)
    mapping_report.json / .md     exact coverage, duplicates, provenance (input SHA-1s, MONDO release)

Overlap with PrimeKG is NOT independent validation: PrimeKG's indication labels and Open Targets' clinical
reports can draw on the same upstream records, and these files do not say which source each report came from.
"""
import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from src.data.mondo import mondo_version, parse_mondo, resolve_status  # noqa: E402

# ORDINAL CONVENTION (ours, NOT published by Open Targets). The official clinical-report page
# (platform-docs.opentargets.org/drug/clinical-report, read 2026-11-10) lists the harmonised categories and their
# descriptions but states no ranking and no enum spellings; its list order (Withdrawal first) is not a progression.
# We order by the *described* development progression: Unknown < Preclinical < IND (filing before first-in-human)
# < Early Phase I < Phase I < I/II < II < II/III < III < Phase IV (post-marketing) < Preapproval < Approval.
# Nothing downstream depends on it: the original stage is preserved on every row, every pair lists `stages_seen`,
# and `approved` is a plain flag (any report with stage APPROVAL). Phase IV/WITHDRAWAL do not occur in this export.
STAGE_RANK = {"UNKNOWN": 0, "PRECLINICAL": 1, "IND": 2, "EARLY_PHASE_1": 3, "PHASE_1": 4, "PHASE_1_2": 5, "PHASE_2": 6,
              "PHASE_2_3": 7, "PHASE_3": 8, "PHASE_4": 9, "PREAPPROVAL": 10, "APPROVAL": 11}
NON_DISEASE = {"HP", "MP", "GO", "OBA", "OTAR"}
XREF_NS = {"EFO", "Orphanet", "NCIT"}


def sha1(p: Path) -> str:
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def find_files(d: Path):
    """Identify the three parquet files by their columns."""
    found = {}
    for p in sorted(d.glob("*.parquet")):
        cols = set(pd.read_parquet(p).columns[:0]) or set(pd.read_parquet(p).head(0).columns)
        if {"drugId", "diseaseId", "maxClinicalStage"} <= cols:
            found["indications"] = p
        elif {"canonicalSmiles", "crossReferences", "parentId"} <= cols:
            found["molecules"] = p
        elif {"mechanismOfAction", "actionType"} <= cols:
            found["mechanisms"] = p
    missing = {"indications", "molecules", "mechanisms"} - set(found)
    if missing:
        sys.exit(f"could not identify {sorted(missing)} among {[p.name for p in d.glob('*.parquet')]}")
    return found


def mondo_xref_index(path: Path):
    """prefix:id -> set(MONDO) using only xrefs qualified MONDO:equivalentTo (non-obsolete terms)."""
    exact, related = defaultdict(set), defaultdict(set)
    cur, obsolete = None, False
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("[Term]"):
                cur, obsolete = None, False
            elif line.startswith("id: MONDO:"):
                cur = line[4:].strip()
            elif line.startswith("is_obsolete: true"):
                obsolete = True
            elif cur and not obsolete and line.startswith("xref: "):
                m = re.match(r"xref: ((?:EFO|Orphanet|NCIT):[A-Za-z0-9_]+)(.*)", line)
                if m:
                    (exact if "MONDO:equivalentTo" in m.group(2) else related)[m.group(1)].add(cur)
    return exact, related


def ot_to_curie(x: str) -> str:
    return x.replace("_", ":", 1)


def map_diseases(ids, terms, xexact, xrelated):
    rows = {}
    for oid in ids:
        ns = oid.split("_", 1)[0]
        cur = ot_to_curie(oid)
        r = {"ot_disease_id": oid, "namespace": ns, "mondo_id": "", "mondo_status": "", "doid_exact": "", "n_mondo": 0}
        if ns == "MONDO":
            res, st = resolve_status(terms, cur)
            r.update(mondo_id=res if st in ("current", "replaced") else "", n_mondo=1 if st in ("current", "replaced") else 0,
                     mondo_status={"current": "native", "replaced": "native_replaced"}.get(st, "native_" + st))
        elif ns in XREF_NS:
            hits = sorted(xexact.get(cur, ()))
            if len(hits) == 1:
                res, st = resolve_status(terms, hits[0])
                r.update(mondo_id=res, n_mondo=1, mondo_status="xref_exact" if st == "current" else "xref_exact_" + st)
            elif len(hits) > 1:
                r.update(mondo_id="|".join(hits), n_mondo=len(hits), mondo_status="xref_ambiguous")
            else:
                r["mondo_status"] = "xref_related_only" if cur in xrelated else "unmapped_no_xref"
        elif ns in NON_DISEASE:
            r["mondo_status"] = "non_disease_ontology"
        else:
            r["mondo_status"] = "unsupported_namespace"
        if r["n_mondo"] == 1 and r["mondo_id"] in terms and not terms[r["mondo_id"]]["obsolete"]:
            r["doid_exact"] = "|".join(sorted(terms[r["mondo_id"]]["doid_exact"]))
        elif r["mondo_status"].startswith(("native_obsolete", "native_not_in", "xref_exact_obsolete", "xref_exact_not_in")):
            r["mondo_id"], r["n_mondo"] = "", 0
        rows[oid] = r
    return pd.DataFrame(rows.values())


def map_drugs(chembl_ids, mol):
    db = {}
    for r in mol.itertuples():
        ids = []
        if r.crossReferences is not None:
            for x in r.crossReferences:
                if str(x.get("source", "")).lower() == "drugbank":
                    ids += [str(i) for i in x["ids"]]
        db[r.id] = sorted(set(ids))
    parent = dict(zip(mol.id, mol.parentId))
    rows, parent_recoverable = [], 0
    for c in chembl_ids:
        ids = db.get(c, [])
        p = parent.get(c)
        pids = db.get(p, []) if (p and not ids) else []
        parent_recoverable += int(bool(pids))
        rows.append({"chembl_id": c, "in_molecule_table": c in db, "drugbank_ids": "|".join(ids),
                     "n_drugbank": len(ids), "drug_status": "mapped" if len(ids) == 1 else ("ambiguous" if ids else "no_drugbank_xref"),
                     # separate, explicitly labelled TIER-2 mapping (never mixed into tier 1)
                     "parent_chembl_id": p if pids else "", "parent_drugbank_ids": "|".join(pids),
                     "drug_map_tier": "1_exact_xref" if len(ids) == 1 else ("2_parent_fallback" if len(pids) == 1 else "none")})
    return pd.DataFrame(rows), parent_recoverable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ot-dir", default="data/external/downloads/open_targets")
    ap.add_argument("--mondo", default="data/external/mondo.obo")
    ap.add_argument("--primekg-dir", default="data/processed/primekg")
    ap.add_argument("--out", default="data/processed/open_targets")
    a = ap.parse_args()
    ot_dir, mondo_p, pk, out = REPO / a.ot_dir, REPO / a.mondo, REPO / a.primekg_dir, REPO / a.out
    out.mkdir(parents=True, exist_ok=True)

    files = find_files(ot_dir)
    ind = pd.read_parquet(files["indications"])
    mol = pd.read_parquet(files["molecules"], columns=["id", "crossReferences", "parentId"])
    n_mech = len(pd.read_parquet(files["mechanisms"], columns=["actionType"]))
    print(f"indication rows {len(ind):,} | molecules {len(mol):,} | mechanisms {n_mech:,}")

    terms = parse_mondo(mondo_p)
    xexact, xrelated = mondo_xref_index(mondo_p)

    dr, parent_recoverable = map_drugs(sorted(ind.drugId.unique()), mol)
    dz = map_diseases(sorted(ind.diseaseId.unique()), terms, xexact, xrelated)

    m = ind.merge(dr, left_on="drugId", right_on="chembl_id", how="left") \
           .merge(dz, left_on="diseaseId", right_on="ot_disease_id", how="left", suffixes=("", "_d"))
    m["n_clinical_reports"] = m.clinicalReportIds.map(lambda x: 0 if x is None else len(x))
    m["clinical_report_ids"] = m.clinicalReportIds.map(lambda x: "" if x is None else "|".join(map(str, x)))
    m["source"] = "OpenTargets"
    m["source_file_sha1"] = sha1(files["indications"])[:12]
    cols = ["drugId", "drugbank_ids", "drug_status", "drug_map_tier", "parent_chembl_id", "parent_drugbank_ids", "diseaseId", "namespace", "mondo_id", "mondo_status", "doid_exact",
            "maxClinicalStage", "n_clinical_reports", "clinical_report_ids", "source", "source_file_sha1"]
    m[cols].rename(columns={"drugId": "chembl_id", "diseaseId": "ot_disease_id", "maxClinicalStage": "max_clinical_stage"}) \
        .to_csv(out / "indications_mapped.csv", index=False)

    # ---- clean pairs: unambiguous DrugBank x single resolved MONDO ----
    ok = m[(m.drug_status == "mapped") & (m.n_mondo == 1)].copy()
    ok["stage_rank"] = ok.maxClinicalStage.map(STAGE_RANK).fillna(-1)
    unknown_stages = sorted(set(ind.maxClinicalStage) - set(STAGE_RANK))
    g = ok.groupby(["drugbank_ids", "mondo_id"], sort=True)
    pairs = g.agg(max_clinical_stage=("maxClinicalStage", lambda s: max(s, key=lambda x: STAGE_RANK.get(x, -1))),
                  n_source_rows=("drugId", "size"), chembl_ids=("drugId", lambda s: "|".join(sorted(set(s)))),
                  ot_disease_ids=("diseaseId", lambda s: "|".join(sorted(set(s)))),
                  stages_seen=("maxClinicalStage", lambda s: "|".join(sorted(set(s), key=lambda x: STAGE_RANK.get(x, -1)))),
                  n_clinical_reports=("n_clinical_reports", "sum"), doid_exact=("doid_exact", "first")).reset_index() \
        .rename(columns={"drugbank_ids": "drugbank_id"})
    pairs["approved"] = pairs.stages_seen.map(lambda x: int("APPROVAL" in x.split("|")))   # any report with stage APPROVAL (PREAPPROVAL does not count)
    pairs["drug_map_tier"] = "1_exact_xref"
    pairs["source"] = "OpenTargets"
    pairs.to_csv(out / "pairs_drugbank_mondo.csv", index=False)
    # tier 2: parent-ChEMBL fallback, kept in its OWN file, never mixed into the exact-xref pairs
    fb = m[(m.drug_map_tier == "2_parent_fallback") & (m.n_mondo == 1)].copy()
    fb["drugbank_id"] = fb.parent_drugbank_ids
    fgrp = fb.groupby(["drugbank_id", "mondo_id"]).agg(
        max_clinical_stage=("maxClinicalStage", lambda s_: max(s_, key=lambda x: STAGE_RANK.get(x, -1))),
        n_source_rows=("drugId", "size"), chembl_ids=("drugId", lambda s_: "|".join(sorted(set(s_)))),
        parent_chembl_ids=("parent_chembl_id", lambda s_: "|".join(sorted(set(s_)))),
        stages_seen=("maxClinicalStage", lambda s_: "|".join(sorted(set(s_), key=lambda x: STAGE_RANK.get(x, -1))))).reset_index()
    fgrp["approved"] = fgrp.stages_seen.map(lambda x: int("APPROVAL" in x.split("|")))
    fgrp["drug_map_tier"] = "2_parent_fallback"
    fgrp["source"] = "OpenTargets"
    fgrp["already_in_tier1"] = [(d, t) in set(zip(pairs.drugbank_id, pairs.mondo_id)) for d, t in zip(fgrp.drugbank_id, fgrp.mondo_id)]
    fgrp.to_csv(out / "pairs_drugbank_mondo_parent_fallback.csv", index=False)

    dr[dr.drug_status != "mapped"].merge(ind.groupby("drugId").size().rename("n_rows"), left_on="chembl_id", right_index=True) \
        .to_csv(out / "unmatched_drugs.csv", index=False)
    dz[dz.n_mondo != 1].merge(ind.groupby("diseaseId").size().rename("n_rows"), left_on="ot_disease_id", right_index=True) \
        .sort_values("n_rows", ascending=False).to_csv(out / "unmatched_diseases.csv", index=False)

    # ---- PrimeKG overlap (READ-ONLY, descriptive) ----
    overlap_rows, ov = [], {}
    edges_p, drugs_p = pk / "edges.csv", pk / "drugs.csv"
    if edges_p.exists() and drugs_p.exists():
        e = pd.read_csv(edges_p, usecols=["source_id", "target_id", "primekg_relation"], low_memory=False)
        e = e[e.primekg_relation == "indication"]
        pk_pairs, pk_comp = set(), set()
        for d, t in zip(e.source_id, e.target_id):
            pk_pairs.add((d, t))
            if t.startswith("MONDO_GROUP:"):
                for c in t.split(":", 1)[1].split("_"):
                    pk_comp.add((d, "MONDO:" + c.zfill(7)))
            else:
                pk_comp.add((d, t))
        pk_drugs = set(pd.read_csv(drugs_p, usecols=["drug_id"]).drug_id)
        ot_set = set(zip(pairs.drugbank_id, pairs.mondo_id))
        in_pk_drugs = pairs[pairs.drugbank_id.isin(pk_drugs)]
        ov = {"primekg_indication_pairs": len(pk_pairs),
              "ot_clean_pairs": len(pairs),
              "ot_clean_pairs_with_primekg_drug": len(in_pk_drugs),
              "primekg_pairs_found_in_ot": len(pk_comp & ot_set),
              "primekg_pairs_found_in_ot_frac": round(len(pk_comp & ot_set) / max(1, len(pk_comp)), 4)}
        ot_drugs = set(pairs.drugbank_id)
        pk_mappable = {x for x in pk_comp if x[0] in ot_drugs}       # PrimeKG pairs whose drug Open Targets can map
        ov["primekg_pairs_with_ot_mappable_drug"] = len(pk_mappable)
        ov["primekg_pairs_found_in_ot_frac_among_mappable_drugs"] = round(len(pk_mappable & ot_set) / max(1, len(pk_mappable)), 4)
        for st in sorted(set(pairs.max_clinical_stage), key=lambda x: STAGE_RANK.get(x, -1), reverse=True):
            s = pairs[pairs.max_clinical_stage == st]
            sp = set(zip(s.drugbank_id, s.mondo_id))
            sd = s[s.drugbank_id.isin(pk_drugs)]
            both = len(sp & pk_comp)
            overlap_rows.append({"max_clinical_stage": st, "ot_pairs": len(s), "ot_pairs_primekg_drug": len(sd),
                                 "also_primekg_indication": both,
                                 "frac_of_pairs_with_primekg_drug": round(both / max(1, len(sd)), 4),
                                 "ot_only_pairs_with_primekg_drug": len(sd) - both})
        pd.DataFrame(overlap_rows).to_csv(out / "primekg_overlap.csv", index=False)

    # ---- report ----
    n = len(ind)
    rep = {
        "date": str(date.today()), "mondo_release": mondo_version(mondo_p),
        "inputs": {k: {"file": p.name, "sha1": sha1(p)} for k, p in files.items()} | {"mondo.obo": {"sha1": sha1(mondo_p)}},
        "rows": {"clinical_reports": n, "distinct_chembl_drugs": int(ind.drugId.nunique()),
                 "distinct_ot_diseases": int(ind.diseaseId.nunique()),
                 "duplicate_raw_pairs(drug,disease)": int(n - len(ind[["drugId", "diseaseId"]].drop_duplicates()))},
        "max_clinical_stage_counts": ind.maxClinicalStage.value_counts().to_dict(),
        "unknown_stage_values_not_ranked": unknown_stages,
        "drugs": {"by_status(drugs)": dr.drug_status.value_counts().to_dict(),
                  "rows_by_status": m.drug_status.value_counts().to_dict(),
                  "not_in_molecule_table": int((~dr.in_molecule_table).sum()),
                  "drugs_by_tier": dr.drug_map_tier.value_counts().to_dict(),
                  "rows_by_tier": m.drug_map_tier.value_counts().to_dict(),
                  "no_xref_but_parent_has_drugbank(tier 2, separate file)": parent_recoverable},
        "diseases": {"by_namespace(ids)": dz.namespace.value_counts().to_dict(),
                     "by_status(ids)": dz.mondo_status.value_counts().to_dict(),
                     "rows_by_status": m.mondo_status.value_counts().to_dict(),
                     "rows_with_exact_doid": int((m.doid_exact.fillna("") != "").sum())},
        "pairs": {"rows_usable(drug mapped & single MONDO)": int(len(ok)), "rows_usable_frac": round(len(ok) / n, 4),
                  "clean_pairs_after_dedup": int(len(pairs)),
                  "duplicate_rows_collapsed": int(len(ok) - len(pairs)),
                  "pairs_by_max_stage": pairs.max_clinical_stage.value_counts().to_dict(),
                  "approved_pairs(any APPROVAL report)": int(pairs.approved.sum()),
                  "tier2_parent_fallback_pairs": int(len(fgrp)),
                  "tier2_pairs_not_already_in_tier1": int((~fgrp.already_in_tier1).sum()),
                  "pairs_with_exact_doid": int((pairs.doid_exact.fillna("") != "").sum()),
                  "distinct_drugbank": int(pairs.drugbank_id.nunique()), "distinct_mondo": int(pairs.mondo_id.nunique())},
        "primekg_overlap": ov,
        "caveat": "Open Targets clinical reports and PrimeKG indications may share upstream sources; the files do not label "
                  "the source of each report, so overlap is NOT independent validation. Not merged into any PrimeKG split.",
    }
    (out / "mapping_report.json").write_text(json.dumps(rep, indent=2, default=int), encoding="utf-8")
    md = ["# Open Targets indications - mapping audit", f"MONDO release: {rep['mondo_release']}", ""]
    for k in ("rows", "drugs", "diseases", "pairs", "primekg_overlap"):
        md += [f"## {k}", "```", json.dumps(rep[k], indent=2, default=int), "```"]
    if overlap_rows:
        md += ["## overlap with PrimeKG indications by Open Targets stage", "```", pd.DataFrame(overlap_rows).to_string(index=False), "```"]
    md += ["", "**Caveat:** " + rep["caveat"]]
    (out / "mapping_report.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("rows", "drugs", "diseases", "pairs", "primekg_overlap")}, indent=1, default=int))
    print(f"\nDONE -> {out}")


if __name__ == "__main__":
    main()
