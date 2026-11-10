# Equity data: what to export, where to put it, how it is validated

Three inputs are still needed for the equity-aware prioritisation (NDPI). All three have a processor that **refuses bad input and never fills gaps with 0**.

## 1. IHME GBD — disease-specific DALY rates  *(blocking; needs your IHME login)*

GBD Results tool → <https://vizhub.healthdata.org/gbd-results/>

| Field | Value |
|---|---|
| Measure | **DALYs (Disability-Adjusted Life Years)** |
| Metric | **Rate** (per 100,000) |
| Location | **Global** |
| Sex | **Both** |
| Age | **All ages** (or Age-standardized: then run the processor with `--age "Age-standardized"`) |
| Year | one year, e.g. 2023 |
| Cause | the NTD causes: Leishmaniasis (visceral; cutaneous and mucocutaneous), Chagas disease, African trypanosomiasis, Schistosomiasis, Cystic echinococcosis, Lymphatic filariasis, Onchocerciasis, Leprosy, Trachoma, Dengue, Rabies, Ascariasis, Trichuriasis, Hookworm disease, Food-borne trematodiases, Guinea worm disease, Scabies (and any other NTD causes the tool offers) |

The 2023 export currently in `data/external/downloads/ihme_gbd/` already has the right dimensions (Global, Both, All ages, 2023, DALYs and Rate) but contains **only the cause "All causes"**, so it is rejected. Re-export with the causes above and put the new zip/csv in the same folder.

Run: `python scripts/process_ihme_daly.py [--year 2023]` → `data/processed/ihme/daly_by_ntd_group.csv`.
The GBD cause-name table inside the script is our expectation; the processor prints any unmatched cause names so the table can be extended after the first real export. Groups with no matching cause stay empty; multi-cause groups (soil-transmitted helminthiases, leishmaniasis) are summed only when every part is present, otherwise marked `partial`.
GBD does not have a clean cause for every WHO group (e.g. snakebite, noma, mycetoma, yaws, trachoma sub-types): those groups will have **no DALY value** and the report says so.

## 2. WHO Essential Medicines List  *(you supply the file)*

Create `data/external/who_eml.csv` from the WHO Model List of Essential Medicines (state the edition, e.g. 23rd list, 2023):

| column | required | meaning |
|---|---|---|
| `name` | yes | generic medicine name as listed |
| `drugbank_id` | no | if you know it |
| `atc_code` | no | |
| `section` | no | therapeutic section |
| `edition` | no | e.g. `23rd List, 2023` |

Run: `python scripts/process_who_eml.py` → `data/processed/eml/eml_drug_flags.csv`, `eml_unmatched.csv`. Mapping is DrugBank id, else exact normalised name; ambiguous names are not used. When a list is supplied, `build_equity_features.py` sets `eml_status = 0` for drugs not on it (the list is treated as complete for that edition); with no file, EML status is **unknown (empty)**.

## 3. HAI price / availability surveys  *(done; regional pilot)*

`python scripts/parse_hai_surveys.py` → `data/processed/hai/` (three surveys: Karnataka 2004-11, Maharashtra 2005-01, Delhi 2011-07). Medicine → DrugBank by exact normalised name, then 5 curated INN synonyms (tier 3, listed in `hai_medicines.csv`); combination products stay unmapped. This is historical Indian evidence, **not** a global access score.

## Building the equity table

`python scripts/build_equity_features.py` → `data/processed/equity/equity_features.csv`, `ndpi_ntd_candidates.csv`, `equity_report.json`, `ndpi_weight_sensitivity.csv` (once ≥ 2 components exist). NDPI = weighted mean over the components that have evidence (weights EML 0.45, DALY 0.45, ACCESS 0.10 are a *proposal*), with `evidence_coverage` and `n_components` on every row.
