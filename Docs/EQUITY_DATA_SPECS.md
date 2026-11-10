# Equity data: status, specifications and validation

Generated 2026-11-11. All processors refuse bad input and never fill gaps with 0.

| component | status | where | validation |
|---|---|---|---|
| WHO EML (24th list, 2025) | **DONE**: extracted from `data/external/B09474-eng.pdf` (590 single + 56 combination entries); mapped to PrimeKG (497 single entries -> 378 drugs) | `data/external/who_eml.csv`, `data/processed/eml/` | `tests/test_who_eml_extraction.py`; `eml_mapping_audit.csv` |
| HAI price/availability (3 Indian surveys) | **DONE** (regional pilot) | `data/processed/hai/` | `scripts/audit_hai_parsing.py` |
| IHME DALY (GBD 2023) | **DONE**: `ihme_ntd_dalys_2023.csv` (17 causes) validated and processed; 15 of 22 project groups have a DALY rate, 7 are missing (scabies, Buruli ulcer, mycetoma, chromoblastomycosis, noma, snakebite envenoming, yaws); unit of 'Rate' not verified against IHME documentation | `data/processed/ihme/` | `scripts/process_ihme_daly.py` (self-test + real file); mapping notes in `daly_by_ntd_group.csv` |

## IHME export: received and processed (settings kept for reference)
GBD Results tool (https://vizhub.healthdata.org/gbd-results/). The exported file `IHME-GBD_2023_DATA-028a73a1-1` (17 causes) used the settings below; **only the cause selection is missing**.
| setting | value |
|---|---|
| Base | Single |
| Measure | DALYs (Disability-Adjusted Life Years) |
| Metric | Rate |
| Location | Global |
| Sex | Both |
| Age | All ages (or Age-standardized: then run `process_ihme_daly.py --age "Age-standardized"`) |
| Year | 2023 (one year) |
| Metric units | **Not verified from IHME documentation** (the Appendix 3 metric definitions could not be read). The usual GBD convention is DALY rate = per 100,000 population; the processor records the metric name and treats the values as relative burden only. |
| Cause availability | **Not verified.** The IHME tool is interactive and the cause-list page could not be fetched. Secondary GBD 2021 papers (found by search, not read in full) name Chagas disease, cutaneous/mucocutaneous and visceral leishmaniasis, food-borne trematodiases, Guinea worm disease and an 'other NTDs' category as separate causes; the rest of the list below is expected, not confirmed. Check each name in the tool's cause picker; `process_ihme_daly.py` prints unmatched names. |
| Cause | the NTD causes the tool offers, expected names: Visceral leishmaniasis; Cutaneous and mucocutaneous leishmaniasis; Chagas disease; African trypanosomiasis; Schistosomiasis; Cystic echinococcosis; Lymphatic filariasis; Onchocerciasis; Leprosy; Trachoma; Dengue; Rabies; Ascariasis; Trichuriasis; Hookworm disease; Food-borne trematodiases; Guinea worm disease; Scabies |
Columns in the file: `measure_id, measure_name, location_id, location_name, sex_id, sex_name, age_id, age_name, cause_id, cause_name, metric_id, metric_name, year, val, upper, lower` (+ population-group columns). Placed as `data/external/downloads/ihme_gbd/ihme_ntd_dalys_2023.csv`; original ZIP and `citation.txt` preserved in `data/external/downloads/ihme_gbd_source_2023/` (and the project root). **Reconciliation with the real export (17 causes).** Requested but not exported: Visceral leishmaniasis and Cutaneous/mucocutaneous leishmaniasis (the export has the parent 'Leishmaniasis', id 347, treated as covering both; the id gap 347 -> 350 suggests the children were omitted: an inference, the hierarchy was not read) and Scabies (group stays missing). Exported but not requested: Cysticercosis (id 352), mapped to the project group taeniasis/cysticercosis (cysticercosis only; taeniasis is not a separate cause there). Cystic echinococcosis covers only part of the WHO echinococcosis group. Six project groups have no GBD cause at all (Buruli ulcer, mycetoma, chromoblastomycosis, noma, snakebite envenoming, yaws) and stay missing, never 0. The unit of 'Rate' is not stated in the file (usual GBD convention: per 100,000).
The IHME agreement forbids providing third parties the ability to download the data: keep the files out of git and out of any public hosting.

## Processing order (already run on 2026-11-11)
1. `python scripts/process_ihme_daly.py` -> `data/processed/ihme/daly_by_ntd_group.csv`, `daly_report.json`
2. `python scripts/build_equity_features.py` -> `data/processed/equity/*` (EML + DALY + HAI; weights 0.45/0.45/0.10 are a proposal; the sensitivity grid becomes meaningful once DALY exists)
3. `python scripts/make_readiness_report.py`, `python scripts/make_final_docs.py`, `python scripts/freeze_release.py --tag vdm_v1`

## EML semantics
`eml_status` = 1 confirmed positive (single-ingredient entry); empty if the drug appears only inside fixed-dose combinations, or is **unresolved** (its name shares a 5+ letter token with one of the 93 unmapped single entries in `data/processed/eml/eml_unmatched.csv`); 0 only where no candidate entry was found, which is not proof of absence. The 'EML coverage' percentage counts those zeros and is not evidence coverage: use `eml_confirmed_positive_pct` / `eml_evidence_counts_all_pairs` in `equity_report.json`.
