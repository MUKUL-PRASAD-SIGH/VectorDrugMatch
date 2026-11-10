# Equity data: status, specifications and validation

Generated 2026-11-11. All processors refuse bad input and never fill gaps with 0.

| component | status | where | validation |
|---|---|---|---|
| WHO EML (24th list, 2025) | **DONE**: extracted from `data/external/B09474-eng.pdf` (592 single + 54 combination entries); mapped to PrimeKG (497 single entries -> 378 drugs) | `data/external/who_eml.csv`, `data/processed/eml/` | `tests/test_who_eml_extraction.py`; `eml_mapping_audit.csv` |
| HAI price/availability (3 Indian surveys) | **DONE** (regional pilot) | `data/processed/hai/` | `scripts/audit_hai_parsing.py` |
| IHME DALY | **BLOCKED**: the file in `data/external/downloads/ihme_gbd/` has only the cause 'All causes' (6 rows: Deaths and DALYs; Number/Percent/Rate; Global, Both, All ages, 2023) | `data/processed/ihme/` (not created) | `scripts/process_ihme_daly.py` rejects it |

## IHME export that is needed (the existing file cannot be used)
GBD Results tool (https://vizhub.healthdata.org/gbd-results/). The dimensions of the existing file are already right; **only the cause selection is missing**.
| setting | value |
|---|---|
| Base | Single |
| Measure | DALYs (Disability-Adjusted Life Years) |
| Metric | Rate |
| Location | Global |
| Sex | Both |
| Age | All ages (or Age-standardized: then run `process_ihme_daly.py --age "Age-standardized"`) |
| Year | 2023 (one year) |
| Cause | the NTD causes the tool offers, expected names: Visceral leishmaniasis; Cutaneous and mucocutaneous leishmaniasis; Chagas disease; African trypanosomiasis; Schistosomiasis; Cystic echinococcosis; Lymphatic filariasis; Onchocerciasis; Leprosy; Trachoma; Dengue; Rabies; Ascariasis; Trichuriasis; Hookworm disease; Food-borne trematodiases; Guinea worm disease; Scabies |
Expected columns (as in the existing file): `measure_id, measure_name, location_id, location_name, sex_id, sex_name, age_id, age_name, cause_id, cause_name, metric_id, metric_name, year, val, upper, lower` (+ population-group columns). Destination: `data/external/downloads/ihme_gbd/` (keep the old zip; add the new one). The cause names above are our expectation and were **not** verified against the GBD tool; the processor prints any unmatched names. GBD may not offer causes for every WHO group (e.g. snakebite, noma, mycetoma, yaws); those groups will have no DALY value and are reported as missing.
The IHME agreement forbids providing third parties the ability to download the data: keep the files out of git and out of any public hosting.

## Processing order after the export arrives
1. `python scripts/process_ihme_daly.py` -> `data/processed/ihme/daly_by_ntd_group.csv`, `daly_report.json`
2. `python scripts/build_equity_features.py` -> `data/processed/equity/*` (EML + DALY + HAI; weights 0.45/0.45/0.10 are a proposal; the sensitivity grid becomes meaningful once DALY exists)
3. `python scripts/make_readiness_report.py`, `python scripts/make_final_docs.py`, `python scripts/freeze_release.py --tag vdm_v1`

## EML semantics
`eml_status` = 1 confirmed positive (single-ingredient entry); empty if the drug appears only inside fixed-dose combinations, or is **unresolved** (its name shares a 5+ letter token with one of the 95 unmapped single entries in `data/processed/eml/eml_unmatched.csv`); 0 only where no candidate entry was found, which is not proof of absence. The 'EML coverage' percentage counts those zeros and is not evidence coverage: use `eml_confirmed_positive_pct` / `eml_evidence_counts_all_pairs` in `equity_report.json`.
