# Data and pipeline readiness report

Generated 2026-11-11 02:04 by `scripts/make_readiness_report.py` from the files on disk. Numbers are read from data/report files; validator lines are from running the validators during generation. Section 6 (unresolved issues) is curated text.

## 1. Datasets

| dataset | source / version | licence | raw path | processed path | rows | unique drugs | unique diseases | missing values | status |
|---|---|---|---|---|---|---|---|---|---|
| PrimeKG nodes: drugs | PrimeKG kg.csv (Harvard Dataverse doi:10.7910/DVN/IXA7BM), MONDO 2026-11-03 | CC0 per Dataverse metadata; upstream terms (DrugBank) unchecked | data/external/primekg_kg.csv | data/processed/primekg/drugs.csv | 7957 | 7957 |  | smiles empty 996 | built; validated |
| PrimeKG nodes: diseases | same | same | same | data/processed/primekg/diseases.csv | 17080 |  | 17080 | daly_rate empty 17080 (no DALY data yet) | built; validated |
| PrimeKG nodes: genes | same | same | same | data/processed/primekg/genes.csv | 19051 |  |  | none | built |
| PrimeKG edges (all relations) | same | same | same | data/processed/primekg/edges.csv | 501779 | 6642 |  |  | built; validated |
| PrimeKG indication pairs (target) | same | same | same | data/processed/primekg/edges.csv (primekg_relation=indication) | 9388 | 1801 | 1363 | none | validated |
| Full benchmark split | derived from PrimeKG indications; seed 42, hard negatives 5:1, drug-disjoint 70/15/15 | derived | - | data/processed/primekg/splits/seed42.npz | 56328 | 1801 | 1363 | none | validated |
| Structure-covered split | derived from PrimeKG indications; seed 42, hard negatives 5:1, drug-disjoint 70/15/15 | derived | - | data/processed/primekg_structcov/splits/seed42.npz | 50871 | 1615 | 1363 | none | built-in checks passed |
| Open Targets pairs_drugbank_mondo | Open Targets Platform export (3 parquet files; SHA-1 in Docs/HAI_DOWNLOAD_MANIFEST.md) | OT outputs CC0; upstream sources keep own licences (ChEMBL CC BY-SA 3.0; others not listed on OT licence page) | data/external/downloads/open_targets/ | data/processed/open_targets/pairs_drugbank_mondo.csv | 40937 | 5104 | 2336 | none in keys | validated (tier 1); NOT merged into training |
| Open Targets pairs_drugbank_mondo_parent_fallback | Open Targets Platform export (3 parquet files; SHA-1 in Docs/HAI_DOWNLOAD_MANIFEST.md) | OT outputs CC0; upstream sources keep own licences (ChEMBL CC BY-SA 3.0; others not listed on OT licence page) | data/external/downloads/open_targets/ | data/processed/open_targets/pairs_drugbank_mondo_parent_fallback.csv | 5901 | 1009 | 1269 | none in keys | validated (tier 2, separate); NOT merged into training |
| HAI hai_price_availability | WHO/HAI price surveys: Karnataka 2004-11, Maharashtra 2005-01, Delhi 2011-07 | check HAI terms | data/external/downloads/hai_price_surveys/ | data/processed/hai/hai_price_availability.csv | 906 | 55 |  | numeric blanks = not reported/free (kept as status) | parsed; regional pilot |
| HAI hai_median_price | WHO/HAI price surveys: Karnataka 2004-11, Maharashtra 2005-01, Delhi 2011-07 | check HAI terms | data/external/downloads/hai_price_surveys/ | data/processed/hai/hai_median_price.csv | 386 | 53 |  | numeric blanks = not reported/free (kept as status) | parsed; regional pilot |
| HAI hai_affordability | WHO/HAI price surveys: Karnataka 2004-11, Maharashtra 2005-01, Delhi 2011-07 | check HAI terms | data/external/downloads/hai_price_surveys/ | data/processed/hai/hai_affordability.csv | 108 | 22 |  | numeric blanks = not reported/free (kept as status) | parsed; regional pilot |
| HAI hai_medicines | WHO/HAI price surveys: Karnataka 2004-11, Maharashtra 2005-01, Delhi 2011-07 | check HAI terms | data/external/downloads/hai_price_surveys/ | data/processed/hai/hai_medicines.csv | 60 | 55 |  | numeric blanks = not reported/free (kept as status) | parsed; regional pilot |
| NTD mapping table | WHO NTD list (read 2026-11-10) + MONDO + PrimeKG | n/a | - | data/processed/ntd/ntd_disease_mapping.csv | 26 |  |  | none | built from files (rows = WHO entry x group) |
| Equity feature table | PrimeKG pairs + HAI (+ IHME, EML when supplied) | derived | - | data/processed/equity/equity_features.csv | 9388 | 1801 | 1363 | ndpi empty 452/9388 | built; EML + HAI + DALY (DALY for NTD pairs only) |
| IHME DALY by NTD group | IHME GBD 2023 export IHME-GBD_2023_DATA-028a73a1-1 | IHME terms | data/external/downloads/ihme_gbd/ihme_ntd_dalys_2023.csv | data/processed/ihme/daly_by_ntd_group.csv | 22 |  |  | 15 of 22 groups with data | processed; 7 groups missing; unit of Rate not verified |
| WHO EML flags | WHO Model List (file not supplied) | WHO terms | data/external/who_eml.csv (absent) | data/processed/eml/eml_drug_flags.csv (not created) | 0 |  |  | n/a | BLOCKED: file not supplied |

### Validators run during generation

| check | result |
|---|---|
| PrimeKG dataset + leakage (validate_primekg_dataset.py) | === RESULT === all hard checks passed / report: C:\Users\Mukul Prasad\Desktop\PROJECTS\Vector Drug Match\VectorDrugMatch\outputs\primekg\validation_report.md |
| Open Targets (validate_open_targets.py) | === RESULT === all hard checks passed |
| IHME processor self-test | selftest ok: stub rejected, duplicates rejected, partial/missing groups handled, no zero filling |
| Paper structure (check_paper.py) | === RESULT === all paper checks passed |
| Model/loader audit (audit_models.py) | see section 3 |

## 2. Mappings

**Disease MONDO -> DOID (PrimeKG nodes, exact xrefs only):**

| status | nodes |
|---|---|
| unmapped_no_doid | 7788 |
| mapped | 7407 |
| unmapped_obsolete_unresolved | 905 |
| partial | 490 |
| unmapped | 360 |
| ambiguous | 94 |
| unmapped_related_only | 36 |

**WHO NTD -> MONDO -> PrimeKG:** 21 official WHO entries; 22 benchmark groups (21 with a MONDO term, 16 with >=1 indication pair; 85 pair-memberships). WHO entries with no indications: Buruli ulcer, dengue and chikungunya, dracunculiasis, noma, rabies, snakebite envenoming. Candidate extensions (chikungunya, tungiasis) and fact-sheet-only diseases are NOT in the frozen flag. Source: https://www.who.int/health-topics/neglected-tropical-diseases (accessed 2026-11-10).

**Open Targets:** drug tiers (ChEMBL ids) {'1_exact_xref': 5494, 'none': 4697, '2_parent_fallback': 1187}; disease status (OT ids) {'native': 2656, 'non_disease_ontology': 479, 'unmapped_no_xref': 470, 'xref_related_only': 12, 'xref_exact': 10, 'native_replaced': 3, 'native_obsolete_no_replacement': 1}; 40,937 tier-1 pairs, 5,901 tier-2 pairs (3,351 not already in tier 1). Overlap with PrimeKG: {'primekg_indication_pairs': 9388, 'ot_clean_pairs': 40937, 'ot_clean_pairs_with_primekg_drug': 33209, 'primekg_pairs_found_in_ot': 2451, 'primekg_pairs_found_in_ot_frac': 0.1446, 'primekg_pairs_with_ot_mappable_drug': 14044, 'primekg_pairs_found_in_ot_frac_among_mappable_drugs': 0.1745}.

**HAI medicines -> DrugBank:** {'mapped': 55, 'unmapped': 5} (tiers {'1_exact_name': 49, '3_curated_inn_synonym': 5, 'none': 5, '2_normalised_name': 1}); unmapped: Benzathine benzyl penicillin, Budesonide+Formeterol, Co-amoxiclav, Co-trimoxazole, Sulfadoxine+Pyrimethamine.

**Equity component coverage (all pairs / NTD pairs):** {'eml': 94.98, 'daly': 0.53, 'access': 6.58} / {'eml': 98.78, 'daly': 60.98, 'access': 17.07} (%); NDPI available for 8936 pairs (82 NTD).


## 3. Models

| model | script | input | outputs | audit (instantiate+fit tiny) | trained |
|---|---|---|---|---|---|
| Logistic Regression | scripts/train_baselines.py --model logistic | pair features (drug fingerprint + 3 disease features), saved split | outputs/<exp>/baseline_logistic_coldstart_predictions.csv, models/baseline_logistic_metrics.json, baseline_comparison.csv | ok | no (Colab) |
| Naive Bayes | scripts/train_baselines.py --model nb | pair features (drug fingerprint + 3 disease features), saved split | outputs/<exp>/baseline_nb_coldstart_predictions.csv, models/baseline_nb_metrics.json, baseline_comparison.csv | ok | no (Colab) |
| Random Forest | scripts/train_baselines.py --model rf | pair features (drug fingerprint + 3 disease features), saved split | outputs/<exp>/baseline_rf_coldstart_predictions.csv, models/baseline_rf_metrics.json, baseline_comparison.csv | ok | no (Colab) |
| XGBoost | scripts/train_baselines.py --model xgb | pair features (drug fingerprint + 3 disease features), saved split | outputs/<exp>/baseline_xgb_coldstart_predictions.csv, models/baseline_xgb_metrics.json, baseline_comparison.csv | ok | no (Colab) |
| MLP | scripts/train_baselines.py --model mlp | pair features (drug fingerprint + 3 disease features), saved split | outputs/<exp>/baseline_mlp_coldstart_predictions.csv, models/baseline_mlp_metrics.json, baseline_comparison.csv | ok | no (Colab) |
| Node2Vec + LR | scripts/train_node2vec.py | walk graph = message-passing graph + TRAIN positives | baseline_node2vec_coldstart_predictions.csv, models/baseline_node2vec_metrics.json | dry run ok; torch_cluster absent locally | no (Colab) |
| GCN | scripts/train_gnn.py | hetero message-passing graph (treats edges removed), saved split | predictions/gnn_GCN_predictions.csv, models/gnn_GCN.pth, gnn_GCN_history.csv, embeddings .npy, gnn_comparison.csv | ok (tiny synthetic forward pass) | no (Colab) |
| GraphSAGE | scripts/train_gnn.py | hetero message-passing graph (treats edges removed), saved split | predictions/gnn_GraphSAGE_predictions.csv, models/gnn_GraphSAGE.pth, gnn_GraphSAGE_history.csv, embeddings .npy, gnn_comparison.csv | ok (tiny synthetic forward pass) | no (Colab) |
| GAT | scripts/train_gnn.py | hetero message-passing graph (treats edges removed), saved split | predictions/gnn_GAT_predictions.csv, models/gnn_GAT.pth, gnn_GAT_history.csv, embeddings .npy, gnn_comparison.csv | ok (tiny synthetic forward pass) | no (Colab) |
| RGCN | scripts/train_gnn.py | hetero message-passing graph (treats edges removed), saved split | predictions/gnn_RGCN_predictions.csv, models/gnn_RGCN.pth, gnn_RGCN_history.csv, embeddings .npy, gnn_comparison.csv | ok (tiny synthetic forward pass) | no (Colab) |
| HGT | scripts/train_gnn.py | hetero message-passing graph (treats edges removed), saved split | predictions/gnn_HGT_predictions.csv, models/gnn_HGT.pth, gnn_HGT_history.csv, embeddings .npy, gnn_comparison.csv | ok (tiny synthetic forward pass) | no (Colab) |
| Cold-start ablation (RF) | scripts/run_ablations_coldstart.py | saved split | ablation_coldstart.csv/json | compiles; not run | no (Colab) |
| Explainability (SHAP / GNNExplainer) | NOT IMPLEMENTED (src/explainability is empty) | - | - | - | - |

Loader audit: {"primekg": {"X_train": [40380, 2051], "X_val": [8382, 2051], "X_test": [7566, 2051], "treats_edges_in_mp_graph": 0, "node_counts": {"drug": 7957, "disease": 17080, "gene": 19051}, "status": "ok"}, "primekg_structcov": {"X_train": [36450, 2051], "X_val": [7694, 2051], "X_test": [6727, 2051], "treats_edges_in_mp_graph": 0, "node_counts": {"drug": 7957, "disease": 17080, "gene": 19051}, "status": "ok"}}

## 4. Evaluation metrics and planned outputs

**Metrics:** ROC-AUC, PR-AUC, F1, precision, recall, MCC, Brier (probability metrics); Precision@K, Recall@K, Hits@K, MRR, NDCG@K (per-disease ranking, `scripts/evaluate_primekg.py`); subsets all / ntd_only / mapped_only / sampled_negatives / with_structure / no_structure; threshold = Youden on validation only; test scored once.

**Paper figures (existing, from real data):** fig1-7 in `Docs/paper/figures/` (graph relations, split composition, disease mapping, NTD coverage, structure shortcut, Open Targets funnel and overlap).

**Paper figures (generated by `scripts/make_results_package.py` after training):** ROC/PR per model family, confusion matrices, calibration, model comparison, NTD breakdown, structure sensitivity, GNN training curves, disease-embedding PCA; tables model_comparison, subset_metrics, structure_sensitivity, ntd_breakdown; `results_metrics.json`. Verified locally on the single real baseline prediction file; other models/figures need the Colab run.

**Not yet planned/implemented:** NDPI ranking figure and equity-component contribution/sensitivity plots (inputs now exist; scripts not written: out of scope), drug-disease candidate network, coverage/missing-data heatmap.

## 5. Execution entry points (nothing below has been run for the final results)

`python scripts/run_full_pipeline.py --stage prepare|external|smoke|train|report|all [--variant full|structcov] [--dry-run]` (`external` steps that need files only you can supply are optional: they log a failure and the equity table reports the component as missing; log in `outputs/pipeline_log.jsonl`). Release integrity: `python scripts/freeze_release.py --tag vdm_v1` then `--verify vdm_v1`.

## 6. Unresolved scientific / data issues (curated)

| # | Issue | Blocks | Needs |
|---|---|---|---|
| 1 | IHME DALY covers 15 of 22 NTD groups (leishmaniasis via the parent cause; cysticercosis only for taeniasis/cysticercosis; echinococcosis cystic only); seven groups have no cause; 'Rate' unit unverified against IHME documentation; burden available for 50 of 82 NTD pairs and no non-NTD pair | burden-aware NDPI scope | none (limitation documented in Docs/EQUITY_DATA_SPECS.md) |
| 2 | WHO EML: extracted from the official 24th-list PDF (646 entries: 590 single, 56 combination; automated checks in tests/test_who_eml_extraction.py); 497 of 590 single entries map to 378 distinct PrimeKG drugs (297 of them have an indication pair in the benchmark) by exact/alias/salt/curated-INN tiers; 93 single entries unmapped, each with a recorded reason in eml_unmatched.csv (vaccines, biologics, blood products, devices, ambiguous names, drugs absent from PrimeKG). EML status separates confirmed positives, unresolved (name overlaps an unmapped entry) and no-candidate zeros | EML component accuracy | none (limitation documented); WHO text is CC BY-NC-SA 3.0 IGO |
| 3 | NDPI has EML (31.3% of pairs confirmed positive, 3.6% unresolved; the rest are no-candidate zeros or combination-only; see equity_report.json denominators) + HAI pilot (6.6%) + DALY for 50 of 82 NTD pairs only (0.53% of all pairs): NDPI is burden-aware only for those 50 pairs; weights 0.45/0.45/0.10 are an unvalidated proposal and on the 49 burden-aware pairs with >= 2 components the ranking is weight-sensitive (Spearman vs default from -0.42 to 0.87 median across the 66-point grid) | equity claims | none (documented) |
| 4 | HAI = three Indian surveys 2004-2011; 5 medicines unmapped (combinations, benzathine penicillin) | any global access claim | broader access evidence |
| 5 | WHO NTD list verified directly (21 groupings; 25 fact sheets; `Docs/NTD_MAPPING.md`). The 22 frozen project groups reconcile to it with documented differences (chikungunya, other deep mycoses, other ectoparasitoses not in the flag; WHO does not enumerate members of two groupings). Page says 'NTDs include', gives no dates; headline: new-NTD requests on hold pending a criteria review (article not read). Candidate extensions are NOT in the frozen flag (changing it would change the NTD stratification) | NTD framing | decide whether to run a separate extended-NTD analysis |
| 6 | NTD test set is tiny (15 positives, 13 groups with any test pair); MONDO has only a generic term for lymphatic filariasis; noma has none | NTD performance claims | report as exploratory |
| 7 | 996 drugs have no SMILES (mostly biologics); with/no-structure subsets and the structure-covered variant address the shortcut risk but do not remove it | interpretation | run both variants on Colab |
| 8 | Open Targets licence/provenance (`Docs/LICENCE_AUDIT.md`, `Docs/OPEN_TARGETS_PROVENANCE.md`): CC0 is platform-level; six upstream source families feed clinical reports but only ChEMBL (CC BY-SA 3.0) is in the licence table; terms of AACT/ClinicalTrials.gov, TTD and PMDA unverified, EMA partial; which families feed OUR 86,451 records is unknown (needs the same-release clinical-report dataset; release number also unknown); stage order matches the documented list order but is our encoding; overlap with PrimeKG is not independent validation | external corroboration claims, any redistribution | per-source attribution + terms review |
| 9 | PrimeKG upstream licence terms (DrugBank) unchecked; old DrugBank files remain in git history (commit 1829752 on origin/mukul) | public release | licence review; team decision on history cleanup |
| 10 | Explainability: SHAP (RF/XGBoost) and GNNExplainer (per-link, k-hop) implemented in `src/explainability/explain.py` + `scripts/explain_models.py`, API-tested on synthetic inputs only; MLP/NB/Node2Vec intentionally NOT explained (documented); real-model explanations need the Colab run | explainability section | Colab run |
| 11 | Legacy `scripts/run_ablations.py` and `scripts/train_benchmark.py` are not drug-disjoint / leak-prone; use `run_ablations_coldstart.py` and `train_node2vec.py` | ablation validity | do not report the legacy outputs |
| 12 | `train_baselines.py` prints pooled 5-fold CV numbers (easier than the real task), and its `mrr`/`hits_10`/`precision_10` (also in `compute_all_metrics`) are POOLED over the test set, not per disease: report only `coldstart_roc_auc/pr_auc/f1/mcc/brier`; ranking metrics come from `evaluate_primekg.py` (per disease). `evaluate_primekg.py` MCC is at a fixed 0.5, the results package uses validation-chosen thresholds | misreporting risk | report discipline |
| 13 | Node2Vec training untested (needs torch_cluster); GNNs untested on GPU/real graph; one local CPU logistic smoke run exists in `outputs/primekg/` and is NOT a result | Colab run | smoke stage of run_full_pipeline.py |
| 14 | `src/scoring/{equity,ndpi}.py` are the legacy Hetionet-era scorer; PrimeKG NDPI lives in `scripts/build_equity_features.py` | consistency | decide whether to retire the legacy modules |
| 15 | Bibliography verified at metadata level; claim support checked against abstracts only (Docs/paper/CITATION_AUDIT.md) | submission | full-text check |
| 16 | `notebooks/colab_primekg.ipynb` (pinned to 522deb3) predates the variants / results package / ablations; the final run uses `notebooks/colab_final_run.ipynb`, which drives `run_full_pipeline.py` and is pinned in its first code cell to the commit that contains those scripts | final Colab run | re-pin if code changes after the freeze |
| 17 | Local commits are unpushed by instruction; the final notebook pin must point to a pushed commit | Colab clone | explicit approval to push |
| 18 | Baseline disease representation: the PrimeKG disease features are `is_ntd` plus two columns that are constant (DALY absent) = ONE informative disease feature, so the classical baselines are effectively drug-only and cannot model drug-disease specificity; GNNs/Node2Vec see disease neighbourhoods. Mitigation (H2 = B, approved): a second baseline variant adds a train-side, leave-one-out disease-profile block (configs/*_dp.yaml); the drug-only variant is kept. Both are run in Colab; the effect is unknown until then | baseline comparison | none (decided) |
| 19 | Open Targets quality flag: the only flag is UNVALIDATED_INDICATION; 47,044 of 86,451 pairs have every supporting report flagged (mostly AACT trials) although the documentation says flagged reports do not feed clinical indications; semantics unresolved. Use pairs with >=1 unflagged report (or APPROVAL stage) for any corroboration | OT corroboration | optional: ask Open Targets |
| 20 | HAI: 10 of 289 comparable MPR values differ between detail pages and the median-price file (all Delhi 2011, lowest-price generic, liquid/drop forms; 1.02-2.93x); cause not established; MPR is not used in the equity score | HAI MPR use | none |
| 21 | Fixed 2026-11-10: GCN/GraphSAGE/GAT had dropout ACTIVE in eval mode (functional dropout frozen by to_hetero tracing); per-model reseeding added; baseline cold-start models are now saved; RF SHAP normalised to the positive class; regression tests added (tests/test_gnn_eval_determinism.py) | GNN/baseline validity | none (fixed) |
| 22 | `requirements.txt` is open-ended (>=) and listed neither pyarrow, pymupdf, lxml, mlflow, tabulate nor optuna (added); exact versions used locally are in `requirements-validated-local.txt`; Colab versions are recorded at run time, not pinned | exact reproducibility | none |
| 23 | Baselines hard-code random_state=42 (config seed not propagated): multi-seed variation needs a code change | optional multi-seed study | decision H10 |
| 24 | Nested NTD roots: onchocerciasis (2 nodes, 3 pairs) and dracunculiasis (1 node) sit inside the generic lymphatic-filariasis root; sum over groups = 85 pairs vs 82 unique; LF-specific indication pairs = 3 (not 6) | NTD per-group claims | report LF as an upper bound |
