# Open Targets indication data: provenance (resolved)

Generated 2026-11-10 from `data/processed/open_targets/source_attribution_report.json`. Evidence: `Docs/source_evidence/fetch_log_2026-11-10.json`.

## 1. Release identification
Our three local files are **byte-identical (SHA-256) to release 26.09**: `00000000.parquet` = `clinical_indication`, `00000000 (1).parquet` = `drug_molecule`, `00000000 (2).parquet` = `drug_mechanism_of_action`
(source: `https://ftp.ebi.ac.uk/pub/databases/opentargets/platform/26.09/output/<dataset>/00000000.parquet`). Identification method: only release 26.09 names all four datasets `00000000.parquet`; the downloaded 26.09 files then matched ours exactly. The same-release `clinical_report` file (289,954 reports) was downloaded to `data/external/downloads/open_targets_release_26.09/` (git-ignored).

## 2. Identifiers
`clinicalReportIds` in the indication table are keys to `clinical_report.id` (UUIDs): **321,785 references, 149,579 distinct reports, 100.0% resolved** in the 26.09 clinical-report dataset; every referenced report has type INDICATION (no safety reports). Each report carries `provider`, `source`, `origin`, `url`, `clinicalStage`, `qualityControls`, and for trials NCT-level fields.

## 3. Which upstream sources contribute to OUR records
Referenced reports by provider: {'AACT': 267087, 'ChEMBL': 39089, 'TTD': 10383, 'EMA': 3581, 'PMDA': 1645}. By source (top): {'ClinicalTrials.gov': 267087, 'DailyMed': 32650, 'TTD': 10383, 'EMA Human Drugs': 3581, 'ATC': 3245, 'USAN': 1825, 'PMDA': 1645, 'FDA': 724, 'INN': 644, 'EMA': 1}. By origin: {'CLINICAL_TRIAL': 267087, 'DRUG_LABEL': 32650, 'CURATED_RESOURCE': 16097, 'REGULATORY_AGENCY': 5951}.
Pairs (n = 86,451): with AACT 74,546; ChEMBL 9,847; TTD 9,384; EMA 1,735; PMDA 1,344. Single-provider pairs: {'AACT': 67085, 'ChEMBL': 6006, 'TTD': 4582, 'EMA': 399, 'PMDA': 377}.
APPROVAL-stage pairs (n = 10,952): with ChEMBL 7,604; TTD 2,997; AACT 4,238; EMA 1,614; PMDA 1,344.
**All five providers contribute**, so none of the five licence questions in `Docs/LICENCE_AUDIT.md` can be ruled out for our data. AACT entities are LLM-extracted from release 26.06 per the Open Targets documentation (our release 26.09 is later).

## 4. Quality flags
The only flag value is `UNVALIDATED_INDICATION`: 138,495 referenced reports carry it (51.5% of AACT references, 1.7% of ChEMBL, 4.7% of EMA, none of PMDA/TTD; shares measured 2026-11-10 from the referenced reports). **47,044 pairs have every supporting report flagged** (APPROVAL pairs: 43). The documentation pages read describe two exclusion criteria (Phase IV without approval; trials whose primary purpose is not to measure the effect on the condition) and say flagged reports do not contribute to clinical indications, yet flagged reports are referenced here: **semantics unresolved**. For any corroboration use pairs with >= 1 unflagged report (`all_reports_flagged = 0`: 39,407 pairs) or the APPROVAL stage.

## 5. Mapping into PrimeKG identifiers
Tier 1 (exact ChEMBL->DrugBank cross-reference + single MONDO id): 40,937 unique pairs; tier 2 (parent-molecule fallback, separate file): 5,901. Disease mapping by OT id: {'native': 2656, 'non_disease_ontology': 479, 'unmapped_no_xref': 470, 'xref_related_only': 12, 'xref_exact': 10, 'native_replaced': 3, 'native_obsolete_no_replacement': 1}. Pairs also PrimeKG indications: 2,453 (of which AACT supports 1,997, ChEMBL 939, TTD 687, EMA 337, PMDA 172); not PrimeKG: 38,491.

## 6. Independence from PrimeKG
**No independence claim is made.** PrimeKG's indication labels (DrugCentral/DrugBank-derived) and the ChEMBL/DailyMed/EMA/PMDA/TTD records can describe the same approvals; the overlap above is descriptive. Trial-derived (AACT) support is a different evidence type but is flagged UNVALIDATED for many pairs. Open Targets data are not merged into any PrimeKG training, validation or test split.
