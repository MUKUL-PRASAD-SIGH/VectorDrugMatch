# Colab training handoff (final run)

Prepared 2026-11-11. No model was trained, no Colab run was made, nothing was pushed. This document **supersedes sections 3 and 6 of `Docs/FINAL_PROJECT_HANDOFF.md`** for the Drive layout and the execution steps (the rest of that file still applies).

## 1. Exact commit to use
| item | value |
|---|---|
| Code commit pinned in `notebooks/colab_final_run.ipynb` (`PIN`) | `b86df0db7ce0985f798f417b71e6c48c03773046` |
| HEAD | the commit that contains this file. It differs from the pin only in `notebooks/` and `Docs/` (`git diff --name-only b86df0d HEAD`); all training/data code is identical |
| Branch | `mukul` on `https://github.com/MUKUL-PRASAD-SIGH/VectorDrugMatch` (**the repository is PUBLIC**) |
| On GitHub? | **Yes** for everything up to `59b05d5` (pushed to `origin/mukul` and merged into `main`, 2026-11-11). The pin commit and later commits are on GitHub only after the second push you approve separately; `git checkout <pin>` in Colab fails until then |
| Which notebook to open | the one at HEAD (Step 4b frozen-data check, Step 6b Drive-persistent outputs). Step-by-step instructions for a beginner: `Docs/COLAB_BEGINNER_HANDBOOK.md` |

## 2. What was audited for this handoff (evidence)
| check | result |
|---|---|
| Training configs | 4 configs, identical `dataset` block (seed 42, neg_ratio 5.0, 0.15/0.15, `presplit` path): `configs/primekg_morgan.yaml`, `primekg_morgan_structcov.yaml`, and the `*_dp.yaml` variants (differ only in `features.disease_profile.enabled`, experiment name and `processed_name`; `tests/test_disease_profile.py`) |
| One split for every model | baselines, ablation, Node2Vec and GNNs all load `splits/seed42.npz` (`presplit`); validator line: "baselines, Node2Vec and GNNs get identical pairs, labels, negatives and features from the saved split"; the disease-profile variant is asserted to have identical pairs/labels/negatives and byte-identical original columns |
| Leakage | validator (37 PASS, 0 FAIL on a regenerated copy): drug sets disjoint across train/val/test (positives and negatives); no negative is a known indication, contraindication or off-label pair; all `treats` and `rev_treats` edges removed from the message-passing graph; `{treats, contraindicated_for, offlabel_for, rev_treats, rev_contraindicated_for, rev_offlabel_for}` = 0 reachable held-out pairs; Node2Vec walk graph asserts no held-out pair; disease-profile features use TRAIN edges only (leave-one-out) |
| Required files / checkpoints | **no pretrained checkpoints and no external model files are needed.** Required inputs are only the raw data in section 3. `explain` loads checkpoints that the `train` stage of the same session writes |
| Frozen benchmark reproducible on a fresh machine | in a clean clone of the pin, `fetch`-free `prepare` steps (dataset, split, validator, structure-covered variant) were run from `primekg_kg.csv` + `mondo.obo` + SMILES cache **with the live MyChem/PubChem lookup for the 996 uncached drugs (it returned 0 new SMILES)**: all 20 benchmark files (tables, features, splits) are **byte-identical** to the frozen release manifest; only the two `primekg_provenance.json` files differ (creation timestamp and local file path) |
| `external` stage on a fresh machine | clean clone + only the files in section 3: all 10 steps exit 0 in 1 min 38 s; 58 of 66 manifest files byte-identical; the rest are line-ending differences (configs, one doc) and one `date` field |
| Drift risks found and closed | (a) `fetch_public_data.py` downloads the **latest** MONDO unless `mondo.obo` already exists: the local benchmark uses release `2026-11-03`, so **`mondo.obo` must be uploaded**; (b) the notebook now hash-checks the regenerated benchmark against the manifest (Step 4b) and stops or restores the frozen copy |
| Notebook | 26 cells; every script it calls exists; the Python cells parse; stage list = prepare, external, smoke, train/report (full), explain (full), train/report (structcov), freeze |
| Dependencies | `requirements.txt` covers every third-party import (+`markdown`, `joblib`); the notebook installs PyG wheels matched to the Colab torch/CUDA at run time and records `pip freeze` (versions are **not pinned** for Colab; validated local versions are in `requirements-validated-local.txt`) |
| Tests | 33 pass locally; clean clone: 26 pass, 7 skip (need git-ignored data) |
| Public-repo hygiene | no data, DrugBank file, IHME table or EML list is tracked; tracked docs/scripts no longer contain IHME values (two example values in the data dictionary and one number in a code comment were removed). Three small DrugBank-derived blobs remain in the **existing remote history** (not added by a push; no history rewrite done) |

## 3. Google Drive upload checklist
Create `MyDrive/VDM_Data/` and upload exactly (total about 340 MB):
```
MyDrive/VDM_Data/
  mondo.obo                                  53 MB   REQUIRED  data/external/mondo.obo (frozen MONDO release 2026-11-03)
  drugbank_smiles_cache.json                 0.5 MB  REQUIRED  data/external/drugbank_smiles_cache.json
  drugbank_cid_map.json                      0.2 MB  REQUIRED  data/external/drugbank_cid_map.json
  B09474-eng.pdf                             1.4 MB  REQUIRED for the EML component  data/external/B09474-eng.pdf
  downloads/
    hai_price_surveys/   (3 sub-folders)     0.4 MB  data/external/downloads/hai_price_surveys/
    open_targets/        (3 parquet files)   12 MB   data/external/downloads/open_targets/
    open_targets_release_26.09/ (4 parquet)  85 MB   data/external/downloads/open_targets_release_26.09/
    ihme_gbd/            (csv + citation txt + old stub zip)  13 KB  data/external/downloads/ihme_gbd/
  frozen_processed/                          SAFETY COPY (used only if Step 4b finds a difference)
    primekg/             94 MB   data/processed/primekg/
    primekg_structcov/   95 MB   data/processed/primekg_structcov/
```
Create `MyDrive/VDM_Outputs/` (empty; the notebook writes results there).
* Optional: `who_eml.csv` (regenerated from the PDF, not needed), `primekg_kg.csv` (981 MB; Step 4 downloads it from Harvard Dataverse and Step 4b checks its hash, so do not upload it unless the download fails).
* Keep file names exactly (including `00000000 (1).parquet`). Folder `downloads/` must contain the four sub-folders above and nothing is required beyond them.

**Do NOT upload / do not share**
* Do not make the Drive folder public or shared by link: it holds DrugBank-derived SMILES caches, IHME data (their agreement forbids third-party downloads), the WHO EML PDF and Open Targets files. Private to your account only.
* Do not upload anything to GitHub: no `data/`, `outputs/`, IHME files, DrugBank files, caches, `mlruns`, `.env` or keys.
* Not needed: `data/raw/`, `data/external/drug_target_drugbank.tsv`, `drugs_enriched.csv`, `diseases_enriched.csv`, `labels_pharmacotherapydb.csv`, `data/external/downloads/ihme_gbd_source_2023/`, the IHME ZIP in the project root, `outputs/`, `.git`.

## 4. Approvals and actions needed from you (and nothing else)
1. **Approve the push of all local commits to `origin/mukul`** (public repository). What becomes public: code, tests, configs, documentation, the paper draft, aggregate counts and figures, the notebook. What does not: any dataset, IHME values, EML list, DrugBank file. The three DrugBank-derived blobs already in remote history stay as they are (unchanged by this push). If you do not want a public push, say so: the alternative is a private repository, which needs a token inside Colab and a notebook edit.
2. **Upload the Drive files in section 3** and keep the folder private.
3. **Choose the Colab runtime**: T4 GPU is required (`torch_cluster` and GNN training). The duration is unknown until the smoke test; the run can be split over sessions.
4. Before any public release or submission (not before training): DrugBank/IHME entitlements, ClinicalTrials.gov/AACT/TTD/PMDA terms, final claims (see `Docs/FINAL_PROJECT_HANDOFF.md` section 3).

## 5. Ordered Colab execution plan
Open the notebook at HEAD, runtime T4 GPU, run top to bottom. After each step, the check in the last column must hold, otherwise stop.

| # | step (cell) | what it runs | must hold before continuing |
|---|---|---|---|
| 1 | GPU | torch version, `nvidia-smi` | `GPU available: True` |
| 2 | Drive, code, libraries | mount, `git clone`, `git checkout b86df0d...`, `git log -1`, pip installs, `pip freeze` | `git log -1` shows `b86df0d`; `ok: ... torch_cluster available` |
| 3 | Inputs | copies `VDM_Data` files into `data/external/` | prints `copied` for `mondo.obo`, both caches, the PDF and `downloads/`; the assert for `mondo.obo` passes |
| 4 | `--stage prepare` | downloads PrimeKG (1 GB), builds tables, saves split, runs the validator, builds the structure-covered variant, runs `audit_models.py` | no `[FAIL]`; the audit reports no failure |
| 4b | frozen-data check | SHA-256 of tables, features, splits, `mondo.obo`, `primekg_kg.csv` vs the manifest | `FROZEN BENCHMARK VERIFIED: 16 files match` (a restore from `frozen_processed/` is acceptable; an assertion error is a stop) |
| 5 | `--stage external` | NTD mapping, Open Targets, HAI, IHME, EML, equity table | optional steps may log a failure only if you left the input out; `data/processed/ihme/daly_report.json` exists |
| 6 | `--stage smoke` | `torch_cluster`, Node2Vec 1 epoch, 5 epochs per GNN, one baseline | read the printed runtimes and GPU memory; extrapolate (section 6) before step 7 |
| 6b | outputs on Drive | moves the smoke/setup outputs to `VDM_Outputs/smoke_and_setup_logs/<time>/`, removes them from `outputs/`, links `outputs/` to `MyDrive/VDM_Outputs/outputs`, writes `run_environment_<time>.json` (commit, GPU, torch/CUDA, seeds, config hashes) and `pip_freeze_<time>.txt` | prints `outputs -> /content/drive/MyDrive/VDM_Outputs/outputs` |
| 7 | `--stage train --variant full`, then `--stage report --variant full` | 5 baselines (drug-only), Node2Vec, 5 GNNs, cold-start ablation, 5 baselines (disease-profile), then evaluation + results package | `outputs/pipeline_log.jsonl`: no non-optional step with `returncode != 0` |
| 7b | `--stage explain --variant full` | SHAP (RF, XGBoost) on test pairs; GNNExplainer (HGT, RGCN) is optional | `outputs/primekg/explain/explain_manifest.json` |
| 8 | `--stage train --variant structcov`, then `report` | same as 7 on the structure-covered variant | as 7 |
| 9 | freeze, package, download | `freeze_release.py --tag vdm_v1`, readiness report, `vdm_results.zip` to Drive + browser | the zip downloads |

**If Colab disconnects mid-step 7/8:** `outputs/` already lives on Drive (step 6b), and every model is its own step (one `train_gnn.py --models <GNN>` call per GNN; baselines are one call per model). Re-run steps 1-6b, then the step 7/8 cell: `--resume` skips every training step that finished with exit 0 at this same commit (from `outputs/pipeline_log.jsonl`) and trains only the rest. `report`, `explain`, `prepare` and `external` always re-run (they are cheap or depend on all models). Comparison CSVs are merged per model, not overwritten.

Models covered: Logistic Regression, Naive Bayes, Random Forest, XGBoost, MLP (both baseline variants, both benchmark variants); Node2Vec; GCN, GraphSAGE, GAT, RGCN, HGT; cold-start ablation (drug-only config, full benchmark); explanations (full benchmark, drug-only config).

## 6. Runtime, GPU and storage (facts and local measurements only; Colab times are NOT estimated)
| item | fact |
|---|---|
| GPU | a T4 (16 GB) is the intended runtime. The graph has 7,957 drugs, 17,080 diseases, 19,051 genes and about 0.8 M edges (reverse relations are added); drug features are 2,048 bits (65 MB); GNNs train full-batch with 64-dimensional embeddings. No memory measurement exists yet: the smoke stage prints GPU memory |
| Training size | 40,380 / 8,382 / 7,566 train/val/test pairs (6,730 / 1,397 / 1,261 positives); up to 100 epochs per GNN, early stopping patience 20 |
| Measured locally (not on Colab) | `prepare` data-building steps 1 min 12 s (without the download); `external` stage 1 min 38 s |
| Everything else | **unknown until measured.** Step 6 (smoke test) prints the wall time of Node2Vec (1 epoch), each GNN (5 epochs) and one baseline; extrapolate from those (a GNN's maximum is 20x its 5-epoch time; Random Forest/XGBoost cost is dominated by the number of model fits, section 10) before committing to Steps 7 and 8 |
| Session limits | the run is built to be split across sessions (resume, section 5); no time limit assumption is made here |
| Storage | upload about 340 MB to Drive; Colab disk holds a 1 GB download plus processed data; result size is unknown until produced |

## 7. Expected output files
Per experiment folder `outputs/<exp>/` for `<exp>` in `primekg` and `primekg_structcov` (and `primekg_dp`, `primekg_structcov_dp` for the disease-profile baselines only):
* `baseline_{logistic,nb,xgb,rf,mlp}_coldstart_predictions.csv`; `baseline_node2vec_coldstart_predictions.csv` (not in `*_dp`); `baseline_comparison.csv`
* `models/baseline_*_coldstart.pkl`, `models/*_metrics.json`; GNN: `predictions/gnn_{GCN,GraphSAGE,GAT,RGCN,HGT}_predictions.csv`, `gnn_*_history.csv`, `gnn_comparison.csv`, `models/gnn_*.pth`
* `ablation_coldstart.csv|json` (`primekg`, `primekg_structcov`)
* `ranking_report.csv|md` (all four folders)
* `paper_package/` (`primekg`, `primekg_structcov`): `tables/`, `figures/`, `results_metrics.json`
* `explain/` (`primekg`): `shap_*_top_features.csv`, `shap_*_bit_substructures.csv`, `gnn_*_link_explanations.csv`, `explain_manifest.json`
* `outputs/pipeline_log.jsonl`, `outputs/pip_freeze_colab.txt`, `Docs/release/vdm_v1_manifest.json`, `vdm_results.zip`

## 8. Validation checks after the run
1. `pipeline_log.jsonl`: every non-optional step `returncode` 0 (`grep -v '"returncode": 0' outputs/pipeline_log.jsonl` shows only `"optional": true` lines).
2. Step 4b printed `FROZEN BENCHMARK VERIFIED`; the validator printed no `[FAIL]` in step 4.
3. All prediction files above exist; `ranking_report.md` shows no "covers N/M test pairs" warning; each baseline prediction file has 7,566 rows (6,727 for structcov), each GNN file the same.
4. The shuffled-label control in `ablation_coldstart.*` has ROC-AUC near 0.5. If not, **do not report any result** (a leakage or a pipeline bug).
5. Report only `coldstart_*` baseline numbers; never the pooled 5-fold CV; never `train_benchmark.py` / `run_ablations.py` outputs. Report the drug-only and disease-profile baselines side by side, never pooled. NTD rows rest on about 15 test positives (exploratory). Report the `all` subset first.
6. GNN numbers are deterministic at evaluation (dropout fix); an identical re-evaluation of one checkpoint must give identical metrics.
7. NDPI: burden-aware only for the 50 pairs with a DALY value; always show its weight sensitivity (`Docs/FINAL_PROJECT_HANDOFF.md` section 5).

## 9. Unverified / accepted limitations at the start of training
* No Colab run time has been measured. Colab library versions are not pinned (recorded in `pip_freeze_colab.txt`).
* No trained-model behaviour has been observed; explanation code ran only on synthetic API tests.
* The IHME rate unit is not verified against IHME documentation.
* The disease-profile baseline variant has never been trained; its effect is unknown.

## 10. Are the five-fold CV and the calibration needed? (analysis; `--coldstart-only` approved and implemented)
Source: `scripts/train_baselines.py`, `scripts/make_results_package.py`, `scripts/evaluate_primekg.py`.
* **What each baseline call does**: (1) a pooled 5-fold stratified CV on train+val+test pairs (`StratifiedKFold(5)`), each fold fitting a `CalibratedClassifierCV(cv=3, sigmoid)` for RF/XGBoost/Logistic (3 base fits per fold) or one plain fit for NB/MLP; (2) the **cold-start fit** on the train split only (calibrated for RF/XGBoost/Logistic = 3 fits), threshold from the validation split, test scored once, predictions and `baseline_<key>_coldstart.pkl` saved; (3) a **pooled final model** on all pairs (3 fits when calibrated) used only for feature importance and a pooled SHAP plot.
* **Fit count**: RF/XGBoost/Logistic = 15 (CV) + 3 (cold-start) + 3 (pooled final) = 21 fits, 15 of them (71%) for the pooled CV; NB/MLP = 5 + 1 + 1 = 7, 5 of them (71%) for the pooled CV. Over the four baseline configurations by fit count this is the largest share of classical-baseline compute. **Run times were not measured**, so no hours are attributed here; the smoke stage times one baseline.
* **What is reported**: every reported number comes from the cold-start prediction files (`baseline_*_coldstart_predictions.csv`) and `coldstart_*` thresholds; the evaluator and the results package read nothing from the CV. The CV columns (`roc_auc`, ...) in `baseline_<key>_metrics.json` are labelled pooled and our rules forbid presenting them as cold-start results. The pooled final model feeds only `<key>_feature_importance.csv` and `<key>_shap_*` (explicitly "not held-out evidence"); held-out SHAP comes from `explain_models.py` on the cold-start model.
* **Calibration**: it is part of the reported estimator (the cold-start model is the calibrated one). Sigmoid calibration with an internal 3-fold split on the training pairs only affects the probability scale, the Brier score, calibration plots and the validation-chosen threshold; it uses no validation or test data. **Keep it.**
* **Decision (approved by you; implemented in the pin commit)**: `train_baselines.py --coldstart-only` skips the pooled CV, the pooled final model, its pooled feature importance and pooled SHAP. The final pipeline passes it for all baseline steps (both configs, both variants) and the smoke baseline. Splits, negatives, features, models, calibration, thresholds, prediction files and `coldstart_*` metrics are unchanged. The pooled-CV columns and `<key>_feature_importance.csv` / `<key>_shap_*` files are therefore **not produced** in the final run (documented omission; they were never used for a reported number). Not run locally (no local training): the flag is covered by a step-list unit test and a syntax check only, so the Colab smoke test (Step 6) is its first real execution.
