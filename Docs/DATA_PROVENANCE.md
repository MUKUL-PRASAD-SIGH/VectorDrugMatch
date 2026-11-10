# Data provenance

Generated 2026-11-11. Every external source: where it came from, which version, how it was verified. Licences are in `Docs/LICENCE_AUDIT.md`; Open Targets detail in `Docs/OPEN_TARGETS_PROVENANCE.md`; WHO NTD detail in `Docs/NTD_MAPPING.md`; the machine-readable evidence log is `Docs/source_evidence/fetch_log_2026-11-10.json`; checksums of the processed release are in `Docs/release/`.

| dataset | source / version | sha256 | raw path | processed | verified how |
|---|---|---|---|---|---|
| PrimeKG kg.csv | Harvard Dataverse doi:10.7910/DVN/IXA7BM, version 2.1 (released 2022-05-02); kg.csv 981,751,236 bytes | 0a5a010fcd88dcec | data/external/primekg_kg.csv | data/processed/primekg/*, splits/seed42.npz | hash recorded at build; validate_primekg_dataset.py |
| MONDO ontology | releases/2026-11-03 | see freeze manifest | data/external/mondo.obo | disease mapping columns in diseases.csv; NTD tables | mapping audit; build_ntd_mapping.py name checks |
| Open Targets (3 parquet files) | release 26.09 (byte-identical) | e10ced7ce09495cd | data/external/downloads/open_targets/ (+ open_targets_release_26.09/ for clinical_report) | data/processed/open_targets/* | SHA-256 equality with release files; validate_open_targets.py |
| WHO Model List of Essential Medicines, 24th list (2025) | WHO DOI 10.2471/B09474; PDF metadata title says '23rd List (2023)' but page 1 states 24th list (2025) | 69daf7c8399b8597 | data/external/B09474-eng.pdf | data/external/who_eml.csv; data/processed/eml/* | tests/test_who_eml_extraction.py; eml_mapping_audit.csv |
| WHO NTD list | WHO health-topic page, accessed 2026-11-10 | f5472b1665a55723 | (web page; hash in evidence log) | data/processed/ntd/* | direct fetch; build_ntd_mapping.py asserts |
| HAI price surveys (3) | Karnataka Nov 2004, Maharashtra Jan 2005, Delhi Jul 2011 | per-file SHA-1 in Docs/HAI_DOWNLOAD_MANIFEST.md | data/external/downloads/hai_price_surveys/ | data/processed/hai/* | audit_hai_parsing.py |
| IHME GBD 2023 export | IHME-GBD_2023_DATA-9feb184e-1.zip (6 rows, cause 'All causes' only) | SHA-1 70aea470 (manifest) | data/external/downloads/ihme_gbd/ | (none: rejected by process_ihme_daly.py) | process_ihme_daly.py rejects it |
| SMILES / fingerprints | resolved at build time via MyChem.info then PubChem PUG REST (scripts/fetch_smiles.py); Morgan radius 2, 2048 bits (RDKit) | freeze manifest | data/external/drugbank_smiles_cache.json (cache) | drugs.csv, drug_features.npy | 1801 split drugs; 996 drugs without SMILES, 997 zero-fingerprint rows |

## Benchmark definition (frozen)
Target: drug -> disease **indication** (PrimeKG relation CtD). Contraindications and off-label uses stay as separate graph relations and are never labels. Split: seed 42, strategy 'hard', neg_ratio 5.0, drug-disjoint 0.15/0.15 + remainder, stratified on NTD.
Full variant: train/val/test positives 6,730/1,397/1,261; negatives 33,650/6,985/6,305; NTD positives 55/12/15.
Structure-covered variant: keep pairs whose drug has SMILES and a non-zero fingerprint; partition and negatives inherited; positives 6,336/1,352/1,167; negatives 30,114/6,342/5,560; NTD positives 55/12/15.

## HAI
{'price_availability': 906, 'median_price': 386, 'affordability': 108, 'unique_medicines': 60} (price/availability, median price, affordability, unique medicines); DrugBank mapping {'mapped': 55, 'unmapped': 5} by tiers {'1_exact_name': 49, '3_curated_inn_synonym': 5, 'none': 5, '2_normalised_name': 1}; unmapped: Benzathine benzyl penicillin, Budesonide+Formeterol, Co-amoxiclav, Co-trimoxazole, Sulfadoxine+Pyrimethamine. Audit: `Docs/HAI_AUDIT.md`.

## WHO EML mapping
646 entries (592 single, 54 combination); single status {'mapped': 497, 'unmapped': 95}; mapped by tier {'1_exact_name': 446, '4_curated_inn_synonym': 25, '2_primary_or_alias': 15, '3_salt_stripped': 11}; 378 distinct PrimeKG drugs flagged; combination components {'components': 127, 'status': {'mapped': 120, 'unmapped': 7}}.

## Equity table
9,388 indication pairs; inputs present {'eml': True, 'daly': False, 'access': True}; component coverage (all pairs) {'eml': 94.98, 'daly': 0.0, 'access': 6.58}; NDPI available for 8,935 pairs. DALY is absent, so NDPI is not burden-aware.
