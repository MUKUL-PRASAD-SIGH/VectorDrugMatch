"""
scripts/open_targets_source_attribution.py - attribute every Open Targets indication pair to its upstream providers/sources.

    python scripts/open_targets_source_attribution.py

Needs the SAME-RELEASE clinical_report dataset. Release identification (done 2026-11-10): our three parquet files are byte-identical (SHA-256)
to release 26.09 `clinical_indication`, `drug_molecule` and `drug_mechanism_of_action`
(https://ftp.ebi.ac.uk/pub/databases/opentargets/platform/26.09/output/<dataset>/00000000.parquet); the matching clinical_report file was downloaded to
data/external/downloads/open_targets_release_26.09/clinical_report.parquet (git-ignored). The script refuses to run if the indication table is not
byte-identical to that release's clinical_indication.

Outputs (data/processed/open_targets/):
    source_attribution_pairs.csv   one row per indication pair: n_reports, providers, sources, origins, per-provider report counts, quality-control flags,
                                   drug/disease mapping tier, whether the pair is also a PrimeKG indication
    source_attribution_report.json provider/source/origin counts for reports and pairs, single-provider pairs, tier-1 and PrimeKG-overlap breakdowns
Providers (Open Targets 'provider' field): AACT (ClinicalTrials.gov), ChEMBL (curated indications; sources DailyMed, ATC, FDA, USAN, INN, WHO, ...),
TTD, EMA, PMDA. Nothing is merged into PrimeKG training data.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
REL = REPO / "data" / "external" / "downloads" / "open_targets_release_26.09"
LOC = REPO / "data" / "external" / "downloads" / "open_targets" / "00000000.parquet"
OT = REPO / "data" / "processed" / "open_targets"
PK = REPO / "data" / "processed" / "primekg"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    assert sha(LOC) == sha(REL / "clinical_indication.parquet"), "our indication file is NOT byte-identical to release 26.09 clinical_indication"
    ind = pd.read_parquet(LOC)
    rep = pd.read_parquet(REL / "clinical_report.parquet", columns=["id", "clinicalStage", "origin", "type", "source", "provider", "qualityControls", "title", "year"])
    ex = ind[["id", "drugId", "diseaseId", "maxClinicalStage", "clinicalReportIds"]].explode("clinicalReportIds").rename(columns={"clinicalReportIds": "report_id", "id": "indication_id"})
    j = ex.merge(rep, left_on="report_id", right_on="id", how="left", suffixes=("", "_rep"))
    found = j.id.notna().mean()
    j["qc_flagged"] = j.qualityControls.map(lambda v: bool(v is not None and len(v) > 0))
    agg = j.groupby("indication_id").agg(
        n_reports=("report_id", "size"), n_reports_found=("id", lambda s: int(s.notna().sum())),
        providers=("provider", lambda s: "|".join(sorted(set(s.dropna())))), sources=("source", lambda s: "|".join(sorted(set(s.dropna())))),
        origins=("origin", lambda s: "|".join(sorted(set(s.dropna())))), types=("type", lambda s: "|".join(sorted(set(s.dropna())))),
        n_qc_flagged=("qc_flagged", "sum")).reset_index()
    for prov in ("AACT", "ChEMBL", "TTD", "EMA", "PMDA"):
        c = j[j.provider == prov].groupby("indication_id").size().rename(f"n_reports_{prov}")
        agg = agg.merge(c, left_on="indication_id", right_index=True, how="left")
        agg[f"n_reports_{prov}"] = agg[f"n_reports_{prov}"].fillna(0).astype(int)
    agg["n_providers"] = agg.providers.map(lambda s: len(s.split("|")) if s else 0)
    agg["all_reports_flagged"] = (agg.n_qc_flagged == agg.n_reports).astype(int)      # every supporting report carries a quality-control flag (UNVALIDATED_INDICATION)
    m = pd.read_csv(OT / "indications_mapped.csv", keep_default_na=False, low_memory=False)
    out = ind[["id", "drugId", "diseaseId", "maxClinicalStage"]].rename(columns={"id": "indication_id"}).merge(agg, on="indication_id", how="left")
    mm = m[["chembl_id", "ot_disease_id", "drug_map_tier", "drugbank_ids", "mondo_id", "mondo_status"]].rename(columns={"chembl_id": "drugId", "ot_disease_id": "diseaseId"})
    out = out.merge(mm, on=["drugId", "diseaseId"], how="left")
    # PrimeKG overlap (read-only), on tier-1 pairs: DrugBank id x MONDO id (grouped PrimeKG nodes expanded to components)
    e = pd.read_csv(PK / "edges.csv", usecols=["source_id", "target_id", "primekg_relation"], low_memory=False)
    e = e[e.primekg_relation == "indication"]
    pk = set()
    for d, t in zip(e.source_id, e.target_id):
        if t.startswith("MONDO_GROUP:"):
            pk.update((d, "MONDO:" + c.zfill(7)) for c in t.split(":", 1)[1].split("_"))
        else:
            pk.add((d, t))
    t1 = out.drug_map_tier.eq("1_exact_xref") & out.mondo_id.str.match(r"^MONDO:\d{7}$", na=False) & ~out.mondo_id.str.contains(r"\|", na=False)
    out["in_primekg_indication"] = [int((a, b) in pk) if flag else -1 for a, b, flag in zip(out.drugbank_ids, out.mondo_id, t1)]   # -1 = not comparable (not tier-1)
    out.to_csv(OT / "source_attribution_pairs.csv", index=False)

    n = len(out)
    approved = out.maxClinicalStage.eq("APPROVAL")

    def share(mask):
        d = out[mask]
        return {"pairs": int(len(d)), "all_reports_flagged_UNVALIDATED": int(d.all_reports_flagged.sum()), "at_least_one_unflagged_report": int((d.all_reports_flagged == 0).sum()), **{f"has_{p}": int((d[f"n_reports_{p}"] > 0).sum()) for p in ("AACT", "ChEMBL", "TTD", "EMA", "PMDA")},
                "single_provider_pairs": {k: int(v) for k, v in d[d.n_providers == 1].providers.value_counts().items()}, "n_providers_dist": {int(k): int(v) for k, v in d.n_providers.value_counts().sort_index().items()}}
    R = {
        "release": "26.09 (our indication, drug_molecule and mechanism files are byte-identical to the release files; SHA-256 prefixes "
                   f"{sha(LOC)[:16]}, clinical_report {sha(REL / 'clinical_report.parquet')[:16]})",
        "reports_in_release": int(len(rep)), "report_provider_counts": rep.provider.value_counts().to_dict(), "report_source_counts": rep.source.value_counts().head(12).to_dict(),
        "report_origin_counts": rep.origin.value_counts().to_dict(),
        "our_pairs": n, "report_refs": int(len(ex)), "report_refs_found_in_clinical_report": round(float(found), 6), "distinct_reports_referenced": int(ex.report_id.nunique()),
        "referenced_report_types": j.type.value_counts().to_dict(), "referenced_reports_provider_counts": j.provider.value_counts().to_dict(),
        "referenced_reports_source_counts": j.source.value_counts().head(15).to_dict(), "referenced_reports_origin_counts": j.origin.value_counts().to_dict(),
        "referenced_reports_with_quality_control_flags": int(j.qc_flagged.sum()),
        "quality_control_flag_values": {str(k): int(v) for k, v in j.explode("qualityControls").qualityControls.value_counts(dropna=False).items()},
        "quality_control_note": "the only flag value is UNVALIDATED_INDICATION; the Open Targets pages read describe two exclusion criteria (Phase IV without approval; trials whose primary purpose is not to measure the effect on the condition) and say flagged reports do not contribute to clinical indications, yet flagged reports ARE referenced here: flag semantics unresolved",
        "all_pairs": share(np.ones(n, bool)), "approved_pairs": share(approved), "tier1_pairs_rows": share(t1),
        "tier1_in_primekg": share(t1 & out.in_primekg_indication.eq(1)), "tier1_not_in_primekg": share(t1 & out.in_primekg_indication.eq(0)),
        "note": "provider field: AACT = ClinicalTrials.gov via AACT (LLM-extracted entities from release 26.06 per Open Targets documentation); ChEMBL = curated indications (DailyMed, ATC, FDA, USAN, INN, WHO ...); TTD; EMA; PMDA",
    }
    (OT / "source_attribution_report.json").write_text(json.dumps(R, indent=1, default=int), encoding="utf-8")
    print(json.dumps({k: R[k] for k in ("release", "our_pairs", "report_refs_found_in_clinical_report", "referenced_reports_provider_counts", "referenced_report_types", "referenced_reports_with_quality_control_flags")}, indent=1))
    for k in ("all_pairs", "approved_pairs", "tier1_in_primekg", "tier1_not_in_primekg"):
        print(k, json.dumps(R[k]))


if __name__ == "__main__":
    main()
