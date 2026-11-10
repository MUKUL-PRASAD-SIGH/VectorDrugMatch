# WHO NTD list: official groupings and reconciliation with the project's 22 frozen groups

Generated 2026-11-10 from `data/processed/ntd/*.csv` (built by `scripts/build_ntd_mapping.py`).

## 1. Source and access record
* **Page:** <https://www.who.int/health-topics/neglected-tropical-diseases>, fetched directly (HTTP 200, 146,039 bytes, SHA-256 `f5472b1665a5572392d14af5e9112320bd8f0b11d7f8c149f01604e6305742dc`), accessed **2026-11-10**. Evidence log: `Docs/source_evidence/fetch_log_2026-11-10.json`.
* **Where the list is:** footnote 1 of the page, verbatim: *"NTDs include: Buruli ulcer; Chagas disease; dengue and chikungunya; dracunculiasis; echinococcosis; foodborne trematodiases; human African trypanosomiasis; leishmaniasis; leprosy; lymphatic filariasis; mycetoma, chromoblastomycosis and other deep mycoses; noma; onchocerciasis; rabies; scabies and other ectoparasitoses; schistosomiasis; soil-transmitted helminthiases; snakebite envenoming; taeniasis/cysticercosis; trachoma; and yaws."*
* **What WHO does not say on that page:** when any entry was added, the inclusion criteria, or whether the list is exhaustive ("NTDs include"). The page's news list has the headline (2026-10-15) *"Requests for inclusion of new neglected tropical diseases put on hold pending review of criteria"*; the article itself was not read.
* The earlier agent-assisted read reported 26 fact sheets; the direct extraction finds **25** distinct fact-sheet links. The 25 are used here.

## 2. Three different things the page contains (kept separate)
1. **21 groupings** in the list footnote (table below). "Grouping" is used loosely: 14 entries name one disease, 7 name several diseases or an open group (`multi`, our classification; WHO does not label them).
2. **Individual diseases** named inside groupings (column `named_diseases`).
3. **Fact sheets** (25 links): 22 correspond to a named disease inside the 21 groupings (entry 11 has two); **3 are fact-sheet-only** and not named in the list footnote: podoconiosis, sporotrichosis, tungiasis. WHO does not say whether they belong to "other deep mycoses" / "other ectoparasitoses" / elsewhere.

| entry_no | who_grouping_as_listed | kind_project_classification | named_diseases | fact_sheets_matching |
|---|---|---|---|---|
| 1 | Buruli ulcer | single | Buruli ulcer | Buruli ulcer (Mycobacterium ulcerans infection) |
| 2 | Chagas disease | single | Chagas disease | Chagas disease (also known as American trypanosomiasis) |
| 3 | dengue and chikungunya | multi | dengue; chikungunya | Dengue |
| 4 | dracunculiasis | single | dracunculiasis | Dracunculiasis (Guinea-worm disease) |
| 5 | echinococcosis | single | echinococcosis | Echinococcosis |
| 6 | foodborne trematodiases | multi | (members not enumerated by WHO) | Foodborne trematode infections |
| 7 | human African trypanosomiasis | single | human African trypanosomiasis | Trypanosomiasis, human African (sleeping sickness) |
| 8 | leishmaniasis | single | leishmaniasis | Leishmaniasis |
| 9 | leprosy | single | leprosy | Leprosy |
| 10 | lymphatic filariasis | single | lymphatic filariasis | Lymphatic filariasis |
| 11 | mycetoma, chromoblastomycosis and other deep mycoses | multi | mycetoma; chromoblastomycosis; other deep mycoses (not enumerated) | Mycetoma / Chromoblastomycosis |
| 12 | noma | single | noma | Noma |
| 13 | onchocerciasis | single | onchocerciasis | Onchocerciasis |
| 14 | rabies | single | rabies | Rabies |
| 15 | scabies and other ectoparasitoses | multi | scabies; other ectoparasitoses (not enumerated) | Scabies |
| 16 | schistosomiasis | single | schistosomiasis | Schistosomiasis |
| 17 | soil-transmitted helminthiases | multi | (members not enumerated by WHO) | Soil-transmitted helminth infections |
| 18 | snakebite envenoming | single | snakebite envenoming | Snakebite envenoming |
| 19 | taeniasis/cysticercosis | multi | taeniasis; cysticercosis | Taeniasis/cysticercosis |
| 20 | trachoma | single | trachoma | Trachoma |
| 21 | yaws | single | yaws | Yaws |
|  | (fact sheet only; not named in the list footnote) | fact_sheet_only | Podoconiosis (non-filarial lymphoedema) | Podoconiosis (non-filarial lymphoedema) |
|  | (fact sheet only; not named in the list footnote) | fact_sheet_only | Sporotrichosis | Sporotrichosis |
|  | (fact sheet only; not named in the list footnote) | fact_sheet_only | Tungiasis | Tungiasis |

## 3. Reconciliation with the 22 frozen project groups
The benchmark flag `is_ntd` (`diseases.csv`, **68 flagged disease nodes**) uses the 22 groups in `src/data/mondo.NTD_ROOTS`. **It was not changed.** Relation of each project group to the WHO entry (`ntd_group_reconciliation.csv`):

| project_group | who_entry_no | who_entry | relation | n_primekg_indication_pairs | note |
|---|---|---|---|---|---|
| Buruli ulcer | 1 | Buruli ulcer | identical | 0 |  |
| Chagas disease | 2 | Chagas disease | identical | 2 |  |
| dengue | 3 | dengue and chikungunya | subset_of_entry | 0 | chikungunya (the other named disease) is NOT in the frozen project flag; evaluated as candidate extension |
| dracunculiasis | 4 | dracunculiasis | identical | 0 |  |
| echinococcosis | 5 | echinococcosis | identical | 2 |  |
| foodborne trematodiases | 6 | foodborne trematodiases | project_defined_members | 2 | WHO does not enumerate members; project chose clonorchiasis, opisthorchiasis, fascioliasis, paragonimiasis |
| human African trypanosomiasis | 7 | human African trypanosomiasis | identical | 4 |  |
| leishmaniasis | 8 | leishmaniasis | identical | 6 | project roots: leishmaniasis + visceral, cutaneous, mucocutaneous |
| leprosy | 9 | leprosy | identical | 3 |  |
| lymphatic filariasis | 10 | lymphatic filariasis | identical_but_broad | 6 | MONDO has only generic 'filariasis' (also covers onchocerciasis etc.): upper bound |
| mycetoma | 11 | mycetoma, chromoblastomycosis and other deep mycoses | split_component_of_entry | 1 | WHO entry 11 is one grouping; project splits it into two groups |
| chromoblastomycosis | 11 | mycetoma, chromoblastomycosis and other deep mycoses | split_component_of_entry | 2 | 'other deep mycoses' not enumerated by WHO and not in the project flag (sporotrichosis has its own WHO fact sheet; WHO does not say it is part of this entry) |
| noma | 12 | noma | identical_but_unmappable | 0 | no MONDO term found |
| onchocerciasis | 13 | onchocerciasis | identical | 3 |  |
| rabies | 14 | rabies | identical | 0 |  |
| scabies | 15 | scabies and other ectoparasitoses | subset_of_entry | 10 | 'other ectoparasitoses' not enumerated by WHO; tungiasis has its own fact sheet, WHO does not say it is part of this entry; candidate extension only |
| schistosomiasis | 16 | schistosomiasis | identical | 3 |  |
| soil-transmitted helminthiases | 17 | soil-transmitted helminthiases | project_defined_members | 10 | WHO does not enumerate members; project chose ascariasis, trichuriasis, hookworm infectious disease, ancylostomiasis, necatoriasis |
| snakebite envenoming | 18 | snakebite envenoming | identical | 0 |  |
| taeniasis/cysticercosis | 19 | taeniasis/cysticercosis | identical | 1 | taeniasis + cysticercosis |
| trachoma | 20 | trachoma | identical | 11 |  |
| yaws | 21 | yaws | identical | 19 |  |

Relation counts: {'identical': 14, 'subset_of_entry': 2, 'project_defined_members': 2, 'split_component_of_entry': 2, 'identical_but_broad': 1, 'identical_but_unmappable': 1}. Differences that matter for the paper:
1. **21 WHO groupings vs 22 project groups:** the project splits WHO entry 11 (mycetoma / chromoblastomycosis / other deep mycoses) into two groups.
2. **Partial coverage of three multi-disease entries:** chikungunya (entry 3), other deep mycoses (entry 11) and other ectoparasitoses (entry 15) are not in the frozen flag.
3. **Project-defined members:** WHO does not enumerate the members of "foodborne trematodiases" or "soil-transmitted helminthiases"; the members were chosen by the project and are listed in the note column.
4. **Ontology limits:** lymphatic filariasis is an upper bound (MONDO only has generic "filariasis"); noma has no MONDO term.

## 4. Candidate extensions and fact-sheet-only diseases (NOT in the frozen flag)
| group_key | scope | mondo_roots | n_primekg_disease_nodes | n_primekg_indication_pairs | note |
|---|---|---|---|---|---|
| chikungunya | candidate_extension | MONDO:0017941 (chikungunya) | 1 | 0 | part of the WHO entry 'dengue and chikungunya'; not in the frozen benchmark flag |
| tungiasis | candidate_extension | MONDO:0019498 (tungiasis) | 1 | 0 | WHO fact sheet exists; WHO page does not say whether it falls under 'other ectoparasitoses' |
| podoconiosis | who_factsheet_only | MONDO:0005425 (podoconiosis) | 1 | 0 | WHO fact sheet only; not named in the WHO list footnote |
| sporotrichosis | who_factsheet_only | MONDO:0005968 (sporotrichosis) | 2 | 6 | WHO fact sheet only; not named in the WHO list footnote |

Changing the frozen flag would alter the NTD stratification of the saved split and the NTD counts (55 / 12 / 15 positives), so any extension is a *separate, labelled analysis*, not an edit of the benchmark.

## 5. Coverage summary (from the files)
* WHO groupings with **no PrimeKG indication pair** (via their project groups): Buruli ulcer, dengue and chikungunya, dracunculiasis, noma, rabies, snakebite envenoming.
* Test-split NTD positives: 15 (exploratory only). See `ntd_disease_mapping.csv` for per-group train / val / test counts.
