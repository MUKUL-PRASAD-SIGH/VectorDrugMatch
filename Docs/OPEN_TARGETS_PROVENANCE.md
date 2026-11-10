# Open Targets indication data: provenance

Generated 2026-11-10. Evidence log: `Docs/source_evidence/fetch_log_2026-11-10.json`. See `Docs/LICENCE_AUDIT.md` for terms.

## 1. What our files are
Three parquet files from an Open Targets Platform download (SHA-1 in `Docs/HAI_DOWNLOAD_MANIFEST.md`): an **indication table** (`id`, `maxClinicalStage`, `clinicalReportIds`, `diseaseId`, `drugId`; 86,451 rows, one per drug-disease pair), a **molecule table** and a **mechanism table**.
**The Open Targets release number is not recorded in the files and is unknown.** Consequence: we cannot say whether the AACT records were extracted with the LLM method that Open Targets documents from release 26.06.
The indication table is the *aggregated* "Clinical indication" dataset described by Open Targets: reports for the same drug and disease are consolidated into one record, preserving traceability to each contributing report (`clinicalReportIds`).
Consistency check supporting this: the stage values in our table contain **no `PHASE_4` and no withdrawal value**, exactly as the documented max-stage rule implies (a report of Phase IV or Withdrawal sets the maximum stage to Approval).

## 2. How Open Targets builds these records (from its documentation, read 2026-11-10)
* Clinical reports come from **six source families**: ClinicalTrials.gov via AACT; ChEMBL curated indications; ChEMBL drug warnings; Therapeutic Target Database (TTD); EMA Human Medicines; PMDA approvals. Pipeline: **Open Targets Mira** (repository formerly `clinical_mining`).
* Drug and disease entities are mapped to ChEMBL and EFO identifiers. For AACT records, entities are extracted with a large language model "from release 26.06"; all other sources supply structured labels.
* Quality filters exclude from downstream use: Phase IV reports for indications with no approval, and trials whose primary purpose is not to measure the effect of the intervention on the target condition.
* Max stage: reports are ranked by harmonised stage with one explicit rule (Phase IV or Withdrawal -> Approval). The documentation lists the categories in this order: Withdrawal, Approval, Phase IV, Preapproval, Phase III, Phase II/III, Phase II, Phase I/II, Phase I, Early Phase I, IND, Preclinical, Unknown. It does not print a numeric ranking, but for every stage that occurs in our data this order agrees with the ordering used in `open_targets_indications.py`; the code comment calls it a project convention that matches the documented order.

## 3. Which upstream sources contribute to OUR records
**Not determinable from our three files.** Each indication row carries only report identifiers: 321,785 report references across the 86,451 rows (149,579 distinct report ids; median 1 per row, max 856; every row has at least one). The source of each report lives in Open Targets' *clinical report* dataset, which we do not have.
All six source families can contribute in principle; ChEMBL is the one we know is present in the platform's licence table. **Required to close this:** download the clinical-report dataset of the same release, join on `clinicalReportIds`, and count rows and pairs by source family (including pairs supported by a single source). Until then no per-source claim is made.

## 4. Mapping into PrimeKG identifiers (this project)
Tier 1 (exact ChEMBL->DrugBank cross-reference + single MONDO id): **40,937** unique pairs; tier 2 (parent-molecule fallback, kept in a separate file): **5,901**. Drug tiers by ChEMBL id: {'1_exact_xref': 5494, 'none': 4697, '2_parent_fallback': 1187}. Disease status by Open Targets id: {'native': 2656, 'non_disease_ontology': 479, 'unmapped_no_xref': 470, 'xref_related_only': 12, 'xref_exact': 10, 'native_replaced': 3, 'native_obsolete_no_replacement': 1}.
Overlap with PrimeKG indications: {'primekg_indication_pairs': 9388, 'ot_clean_pairs': 40937, 'ot_clean_pairs_with_primekg_drug': 33209, 'primekg_pairs_found_in_ot': 2451, 'primekg_pairs_found_in_ot_frac': 0.1446, 'primekg_pairs_with_ot_mappable_drug': 14044, 'primekg_pairs_found_in_ot_frac_among_mappable_drugs': 0.1745}. Because PrimeKG's indication labels and these records may rest on shared upstream sources (e.g. ChEMBL/DrugCentral-type curation, regulatory labels), overlap is **not** independent validation. The dataset is not merged into any training, validation or test data.

## 5. Open items
1. Obtain the release number and the same-release clinical-report dataset; attribute records to sources.
2. Per-source terms for AACT/ClinicalTrials.gov, TTD and PMDA are unverified (see licence audit).
3. LLM-extracted AACT records may carry extraction errors; their share in our pairs is unknown until item 1.
