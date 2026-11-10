# VectorDrugMatch - final project handoff

Finalization pass of 2026-11-11. Scope is frozen: no new models, datasets, features, labels or splits. Nothing was trained locally, nothing was pushed, no history was rewritten, nothing was deleted.

## 0. Git commit and notebook pin
| item | value |
|---|---|
| Code commit pinned by the notebook (`PIN` in `notebooks/colab_final_run.ipynb`) | `438495791883aae3a80c9d4709282f9869ce3d40` |
| HEAD | the commit that contains this file (`git rev-parse HEAD`). Commits after the pin change only `notebooks/` and `Docs/`; check with `git diff --name-only 4384957 HEAD` |
| Branch / remote state | local branch `mukul`; every commit since `origin/mukul` is **local only** (`git rev-list --count origin/mukul..HEAD`). Colab clones from GitHub, so **the pin does not exist for Colab until a push is approved** (section 3, A4). A clean external clone cannot reach it before then |
| Release manifest | `Docs/release/vdm_v1_candidate_manifest.json` (63 files: SHA-256, sizes, rows, Python/package versions, split seeds). `python scripts/freeze_release.py --verify vdm_v1_candidate` -> `VERIFIED: all files match` (checked in this pass, also after re-running the deterministic builders) |
| Final manifest tag | after the Colab run: `python scripts/freeze_release.py --tag vdm_v1` (notebook step 9) |

## 1. What is complete (DONE AND VALIDATED)
Full status table with evidence: `Docs/FINAL_RELEASE_READINESS.md` (24 DONE AND VALIDATED, 9 IMPLEMENTED BUT NOT VALIDATED, 4 BLOCKED ON MY INPUT, 2 NOT STARTED, 1 NOT APPLICABLE). Summary:
* **PrimeKG benchmark**: 7,957 drugs, 17,080 diseases, 9,388 indications; drug-disjoint split (seed 42, hard sampled negatives 5:1, test 7,566 pairs); held-out/reverse-edge leakage checks; negatives audited (none is a known indication, contraindication or off-label pair). Frozen; manifest-verified.
* **Structure-covered variant** (same drug partition, pairs without a usable fingerprint dropped; test 6,727 pairs, NTD positives 55/12/15) with its own validation.
* **NTD mapping**: official WHO list (21 groupings) read directly, reconciled with the 22 frozen project groups (68 flag nodes), nested-root overlaps audited, candidate extensions kept separate.
* **HAI** (3 Indian surveys, regional pilot): parser + audit (0 FAIL, 3 WARN), mapping 55/60 medicines.
* **Open Targets** (release 26.09 identified by byte identity): loader, validator, per-provider attribution of all 321,785 report references.
* **EML counts reconciled** (section 5), equity table with explicit denominators, no component ever filled with 0 when missing; NDPI renormalises over available components.
* **Defects found and fixed by static audit**: GCN/GraphSAGE/GAT eval-mode dropout (regression tests), per-model reseeding, saved cold-start baseline models, RF SHAP class slice, IHME stub rejection, EML extraction (co-packs, footnote marks), curated-synonym key normalisation.
* **Reproducibility**: clean-clone check of the final commit (compile, 50-step dry run of `--stage all`, 25 tests pass / 7 skip because they need git-ignored data); 32 tests pass locally (`python -m pytest -q tests`).
* **Static audit of this pass**: all 24 notebook code cells reference existing scripts; all pipeline scripts import and parse arguments; third-party imports are covered by `requirements.txt` (added `markdown`, `joblib`; `torch_cluster`/PyG wheels are installed by the notebook); no data, model, DrugBank or key file is tracked (`git ls-files data` = README + .gitkeep).

## 2. Implemented but NOT validated (cannot be validated before the Colab run, or evidence is partial)
| item | what is missing |
|---|---|
| Node2Vec, five GNNs, five classical baselines (both variants) on real data | never trained; the local audits only cover code paths and tiny forward passes |
| Disease-profile baseline variant (`configs/*_dp.yaml`) | construction and leakage are tested (8 tests incl. real-split identity); **its effect on any metric is unknown**. The variant gets predictions, `baseline_comparison.csv` and `ranking_report.*` but no figure package (the package runs on the drug-only config only) |
| Cold-start ablation (`run_ablations_coldstart.py`) | compiled only; runs on the drug-only config |
| Results exporter (`make_results_package.py`) | validated on one real baseline prediction file only |
| Explainability (`explain_models.py`: SHAP for RF/XGBoost, GNNExplainer for HGT/RGCN) | synthetic API tests only; the GNNExplainer step is optional in the pipeline |
| WHO EML extraction | automated structure tests and spot checks only; **not manually reviewed entry by entry**; limitations below |
| NDPI | EML flag + HAI pilot only; **not burden-aware** until IHME data exist; weights 0.45/0.45/0.10 are a proposal; sensitivity grid not meaningful yet |
| Open Targets quality flag `UNVALIDATED_INDICATION` | filter implemented; flag meaning undocumented upstream |
| Citations | metadata and abstract-level claim support checked; full-text verification pending |
| Licensing | evidence log built; legal conclusions deliberately not drawn |

### EML extraction limitations (current, `Docs/EML_EXTRACTION_CORRECTIONS.md`)
* 646 entries (590 single, 56 combination) from the 24th-list PDF; 497 single entries map to 378 PrimeKG drugs; **93 unmapped, each with a reason** in `data/processed/eml/eml_unmatched.csv`.
* Two extraction defects were found and fixed with PDF evidence (en-dash co-packs on pp. 29/30/53/60; superscript "th" marks on pp. 55/59). Other layout defects may remain undetected because the review was not exhaustive.
* `eml_status`: 1 = confirmed positive; empty = combination-only or *unresolved* (name shares a 5-letter stem with an unmapped entry); 0 = **no candidate entry found, not a verified negative**. The stem heuristic can miss synonyms that share no stem.
* Formulation and strength text, ATC codes and DrugBank IDs are not extracted.

## 3. What requires your input
| id | action | needed for | when |
|---|---|---|---|
| A1 | **IHME disease-specific DALY export** (section 4) | burden component, NDPI, equity figures | before the `external` stage if you want NDPI burden-aware; not needed for the prediction benchmark |
| A2 | **Essential manual EML decision: none.** Optional only: review `eml_unmatched.csv` (93 rows) if you want a stricter claim than "documented, not manually verified" | EML wording in the paper | optional |
| A3 | **Licensing and redistribution approvals**: (i) confirm DrugBank and IHME entitlements and decide on the three small DrugBank-derived blobs in the history of `origin/mukul` (no rewrite was done); (ii) read ClinicalTrials.gov/AACT, TTD and PMDA terms in a browser (JavaScript pages that could not be fetched) before publishing Open Targets-derived tables; (iii) legal judgement on ShareAlike for derived EML/ChEMBL tables and on CC0 over non-commercial constituents | any public release or submission; **not needed for Colab** | before release |
| A4 | **Push approval** (all local commits to `origin/mukul`) and the **Drive upload** of git-ignored inputs: `data/external/downloads/` (Open Targets, HAI, IHME), and `data/external/who_eml.csv` or `data/external/B09474-eng.pdf`, to `MyDrive/VDM_Data/` | the Colab run (the notebook clones the pinned commit; the `external` stage uses the Drive files) | Colab time |
| A5 | **Colab execution and result review**: run the notebook, then read results against section 8 | all results | after A4 |
| A6 | Approve final claims and full-text reference verification | submission | before submission |

## 4. Exact IHME export instructions
Tool: GBD Results (https://vizhub.healthdata.org/gbd-results/). The existing file `data/external/downloads/ihme_gbd/` (one zip, 6 rows) has the right dimensions but only the cause "All causes", so the processor rejects it; keep it, add the new zip beside it.

| setting | value |
|---|---|
| Base | Single |
| Measure | DALYs (Disability-Adjusted Life Years) |
| Metric | Rate |
| Location | Global |
| Sex | Both |
| Age | All ages (or Age-standardized, then run `python scripts/process_ihme_daly.py --age "Age-standardized"`) |
| Year | 2023 (single year) |
| Cause | Visceral leishmaniasis; Cutaneous and mucocutaneous leishmaniasis; Chagas disease; African trypanosomiasis; Schistosomiasis; Cystic echinococcosis; Lymphatic filariasis; Onchocerciasis; Leprosy; Trachoma; Dengue; Rabies; Ascariasis; Trichuriasis; Hookworm disease; Food-borne trematodiases; Guinea worm disease; Scabies |

Expected columns: `measure_id, measure_name, location_id, location_name, sex_id, sex_name, age_id, age_name, cause_id, cause_name, metric_id, metric_name, year, val, upper, lower`.

**Not verified by me:** the cause names (the tool is interactive; I could not read its cause list, and only some names appear in secondary GBD 2021 papers) and the unit of "Rate" (per 100,000 population is the usual GBD convention; the IHME metric definitions were not read). Check each name in the tool's cause picker and the unit in its metric definition; GBD may lack causes for snakebite, noma, mycetoma or yaws, which will then be reported as missing, never as 0. `process_ihme_daly.py` prints unmatched names. The IHME agreement forbids providing third parties the ability to download the data: keep the files out of git and out of any public hosting. After the file is in place, locally:
```
python scripts/process_ihme_daly.py
python scripts/build_equity_features.py
python scripts/make_readiness_report.py
python scripts/make_final_docs.py
python scripts/freeze_release.py --tag vdm_v1_candidate
```
(then commit and re-pin, since the manifest and docs change; or simply upload the zip to Drive and let the Colab `external` stage process it).

## 5. Reconciled data counts (from the generated CSV/JSON files)
EML: 646 entries = 590 single + 56 combination; singles 497 mapped + 93 unmapped; 378 PrimeKG drugs flagged, 297 of them with an indication pair.

| EML evidence | all pairs (9,388) | all drugs (1,801) | NTD pairs (82) | NTD drugs (50) |
|---|---|---|---|---|
| confirmed positive | 2,942 (31.3%) | 297 | 51 | 31 |
| unresolved | 339 (3.6%) | 55 | 1 | 1 |
| combination component only | 132 | 33 | 0 | 0 |
| no candidate entry found | 5,975 | 1,416 | 30 | 18 |

The "EML component coverage" figure in `equity_report.json` counts the zeros and is not evidence coverage. HAI access covers 6.58% of pairs (17.07% of NTD pairs). DALY coverage is 0% until A1. NDPI exists for 8,935 pairs (81 NTD).

## 6. Exact final Colab execution sequence
Prerequisites: A4 done (pushed; Drive populated). Open `notebooks/colab_final_run.ipynb` in Colab with a T4 GPU and run cells top to bottom:

| step | what it does |
|---|---|
| 1 | checks `torch`, `GPU available: True` |
| 2 | mounts Drive, clones the repo, `git checkout 438495791883aae3a80c9d4709282f9869ce3d40`, installs libraries (PyG wheels matched to the torch/CUDA version), writes `outputs/pip_freeze_colab.txt` |
| 3 | copies `downloads/`, `who_eml.csv`/`B09474-eng.pdf`, optional `drugbank_smiles_cache.json` from `MyDrive/VDM_Data/` (missing inputs are reported as missing, never as 0) |
| 4 | `python scripts/run_full_pipeline.py --stage prepare` (download PrimeKG + MONDO, build tables, save split, safety check, structure-covered variant). A `[FAIL]` means: stop |
| 5 | `... --stage external` (Open Targets, HAI, IHME, EML, equity table; optional steps log a failure and continue) |
| 6 | `... --stage smoke` (torch_cluster, Node2Vec 1 epoch, 5 epochs per GNN, one baseline). Check runtime and GPU memory before the long run |
| 7 | `... --stage train --variant full` then `--stage report --variant full`. `train` runs: five baselines (drug-only), Node2Vec, five GNNs, cold-start ablation, five baselines (disease-profile variant) |
| 7b | `... --stage explain --variant full` (SHAP RF/XGBoost; GNNExplainer is optional) |
| 8 | the same `train` and `report` for `--variant structcov` |
| 9 | `scripts/freeze_release.py --tag vdm_v1`, `make_readiness_report.py --skip-validators`, zips `vdm_results.zip`, copies it to `MyDrive/VDM_Outputs/` and downloads it |

If Colab disconnects: re-run steps 1-3 and the interrupted step; finished prediction files are rewritten, nothing else is affected. Step 7 takes the longest.

## 7. Expected output files (per experiment folder `outputs/<exp>/`, `<exp>` in `primekg`, `primekg_structcov`, and for baselines also `primekg_dp`, `primekg_structcov_dp`)
* `baseline_{logistic,nb,xgb,rf,mlp}_coldstart_predictions.csv`, `baseline_node2vec_coldstart_predictions.csv` (drug-only: `primekg*`; disease-profile baselines: `*_dp`, five models, no Node2Vec)
* `predictions/gnn_{GCN,GraphSAGE,GAT,RGCN,HGT}_predictions.csv`, `gnn_*_history.csv`, `gnn_comparison.csv`, `baseline_comparison.csv`
* `models/baseline_*_coldstart.pkl`, `models/*_metrics.json`, `models/gnn_*.pth`
* `ablation_coldstart.csv|json` (drug-only config only)
* `ranking_report.csv|md` (all four folders)
* `paper_package/` for `primekg` and `primekg_structcov`: `tables/` (model_comparison, subset_metrics, structure_sensitivity, ntd_breakdown) and `figures/` (ROC/PR, confusion, calibration, model comparison, NTD breakdown, structure sensitivity, training curves, embeddings), `results_metrics.json`
* `explain/` (`shap_*_top_features.csv`, `shap_*_bit_substructures.csv`, `gnn_*_link_explanations.csv`, `explain_manifest.json`) when step 7b succeeds
* `outputs/pipeline_log.jsonl` (one record per step with exit code and wall time), `outputs/pip_freeze_colab.txt`
* `Docs/release/vdm_v1_manifest.json`, `vdm_results.zip`, and `data/processed/{equity,ntd,open_targets,hai,eml}` copies inside the zip

## 8. How to verify successful completion
1. `outputs/pipeline_log.jsonl`: every non-optional step has exit code 0; list failures with `grep -v '"returncode": 0' outputs/pipeline_log.jsonl` and confirm each has `"optional": true` (an external step whose input you did not supply).
2. The prepare stage printed no `[FAIL]`; `python scripts/freeze_release.py --verify vdm_v1_candidate` matches for the split files (`data/processed/primekg*/splits/seed42.npz`).
3. Each folder has the prediction files above; `ranking_report.md` has no "covers N/M test pairs" warning.
4. The shuffled-label control in `ablation_coldstart.*` has ROC-AUC near 0.5; if not, **do not report the results** (leakage or a bug).
5. GNN prediction rows are deterministic: evaluation twice on the same checkpoint gives identical numbers (the dropout bug was fixed; regression test `tests/test_gnn_eval_determinism.py`).
6. Report only `coldstart_*` baseline numbers and the `all` subset first; NTD rows rest on ~15 test positives (exploratory). Never report the pooled 5-fold CV or the legacy `train_benchmark.py` / `run_ablations.py` outputs as cold-start results.
7. Report both baseline variants side by side and never pooled. A difference between them is a statement about the disease-profile block, not about the benchmark.
8. NDPI and equity results are described as burden-aware only if the IHME export was processed (`data/processed/ihme/daly_report.json` exists and `equity_report.json` shows DALY coverage > 0).

## 9. Remaining publication and licensing restrictions
Detailed evidence: `Docs/LICENCE_AUDIT.md`, `Docs/DATA_PROVENANCE.md`, `Docs/OPEN_TARGETS_PROVENANCE.md`, `Docs/source_evidence/`. No legal conclusion is drawn here.
* **Do not redistribute**: DrugBank-derived data (CC BY-NC 4.0 / licence), IHME files (agreement forbids third-party download), the WHO EML PDF and derived CSV (CC BY-NC-SA 3.0 IGO; whether derived tables are adaptations needing ShareAlike is an open question), Open Targets-derived tables until A3(ii) is done. Raw/derived data stay git-ignored; only aggregate counts, figures and audit documents are tracked.
* PrimeKG is marked CC0 at the dataset level, but its README says constituent licences apply separately.
* ChEMBL is CC BY-SA 3.0; ClinicalTrials.gov/AACT and TTD terms are **not verified**; EMA and PMDA notices permit reuse with acknowledgement (PMDA content under PDL 1.0).
* HAI evidence is regional and historical (India 2004-2011): never describe it as global access.
* The DrugBank-derived blobs in remote history remain; resolving that needs a separate decision (history rewrite is not done and not recommended without coordination).
* Open Targets overlap with PrimeKG is **not independent validation** (shared upstream sources).

## 10. Exact commands to reproduce the project
Local (no training; data layer, audits, tests):
```
pip install -r requirements.txt            # exact validated local versions: requirements-validated-local.txt
python scripts/run_full_pipeline.py --stage prepare        # needs network for PrimeKG/MONDO; or reuse data/processed
python scripts/run_full_pipeline.py --stage external       # optional inputs: Open Targets, HAI, IHME, EML under data/external
python -m pytest -q tests
python scripts/make_readiness_report.py && python scripts/make_final_docs.py
python scripts/freeze_release.py --verify vdm_v1_candidate
python scripts/check_paper.py
```
Colab (training): run the notebook as in section 6, or equivalently (GPU, after `pip install` as in notebook step 2):
```
python scripts/run_full_pipeline.py --stage prepare
python scripts/run_full_pipeline.py --stage external
python scripts/run_full_pipeline.py --stage smoke
python scripts/run_full_pipeline.py --stage train  --variant full
python scripts/run_full_pipeline.py --stage report --variant full
python scripts/run_full_pipeline.py --stage explain --variant full
python scripts/run_full_pipeline.py --stage train  --variant structcov
python scripts/run_full_pipeline.py --stage report --variant structcov
python scripts/freeze_release.py --tag vdm_v1
```
`--dry-run` prints the commands without running them (50 steps for `--stage all`).

## 11. Where the paper stands
`Docs/paper/PAPER_DRAFT_IEEE.md`: dataset, provenance, leakage control, mapping audits, structure coverage, Open Targets, protocol (both baseline variants), equity methodology and limitations are written with real numbers. **Results, ablation, explanation and NDPI-ranking sections are [PENDING]** (need Colab and A1). No figure or number in the draft comes from synthetic predictions. `python scripts/check_paper.py` passes.
