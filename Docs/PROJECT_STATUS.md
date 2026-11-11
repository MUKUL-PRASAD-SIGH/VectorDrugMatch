# Project status after the Colab run (single source of truth, 2026-11-11)

This file reconciles the repository with the completed Colab work. Where an older document says "pending", "not yet run" or names an older pin, **this file wins**.
Sources: `Docs/COLAB_RESEARCH_VALIDATION_LOG.md` (project owner's log), `Docs/FINAL_PROJECT_HANDOFF_20261111.md`, `Docs/paper/RESULTS_AND_VALIDATION_ADDENDUM_20261111.md`, `reports/research_validation_20261111/`, the saved executed notebook and the code commits. Facts that exist only in the owner's log or in Drive are marked *(owner-reported)*: they were not re-checked here.

## 1. What is done
* Final training and evaluation ran in Google Colab (Tesla T4; PyTorch 2.14.1+cu130, PyG 2.8.1, pyg-lib 0.9.0, from the saved notebook output) on the frozen drug-disjoint benchmark and the structure-covered variant.
* Five-seed evaluation (seeds 21, 42, 52, 72, 100; same saved split) of four selected variants, with bootstrap intervals, calibration, error and ranking analyses: `reports/research_validation_20261111/`.
* A GCN inference package reproduced the saved test predictions *(owner-reported; addendum section 3)*: 7,566 rows, entity order identical, maximum absolute probability difference 6.6e-07, 100% prediction agreement.
* Open Targets evidence assessment *(owner-reported)*: 16,410 candidate pairs, 9,065 scored; Spearman rho 0.0945 (pair level) and 0.0605 (drug-stage aggregated, bootstrap 95% interval 0.0318 to 0.0913). Positive-evidence-only, shares upstream sources with PrimeKG: **not independent validation**.
* Model bundle *(owner-reported)*: 315 files, 10 GNN checkpoints, 20 baseline files, SHA-256 and ZIP integrity verified. It is in **private Drive** (`VDM_Outputs/releases/`), not in GitHub. Node2Vec has metrics and predictions but no checkpoint; the disease-profile variants are classical models only.

## 2. Results (benchmark, not clinical)
Seed-42 results of the selected model per variant (addendum / handoff):

| Variant | Selected model | ROC-AUC | PR-AUC |
|---|---|---:|---:|
| PrimeKG | GCN | 0.7787 | 0.4919 |
| PrimeKG + disease profile | Random Forest | 0.8043 | 0.6041 |
| Structure-covered | GCN | 0.7838 | 0.5183 |
| Structure-covered + disease profile | XGBoost | 0.8433 | 0.6979 |

Five-seed mean ± SD (`reports/research_validation_20261111/five_seed_performance.csv`): PrimeKG GCN 0.7880 ± 0.0118 / 0.5285 ± 0.0334; PrimeKG RF 0.8049 ± 0.0020 / 0.6113 ± 0.0078; structure GCN 0.7847 ± 0.0089 / 0.5390 ± 0.0182; structure XGBoost 0.8433 ± 0.0000 / 0.6979 ± 0.0000 (ROC-AUC / PR-AUC). The XGBoost zero SD means identical predictions across seeds, not robustness. Paired bootstrap (fixed test samples): RF minus GCN ROC-AUC +0.02562 [0.01082, 0.04124]; structure XGBoost minus structure GCN +0.05945 [0.04477, 0.07459].
**Read with care:** the two feature sets differ (the disease-profile variants add a training-side popularity-like signal, see the addendum), the structure-covered test set is a subset, negatives are sampled, all seeds share one split, and **how the "selected model" per variant was chosen is not documented in the repository**: do not present these as a superiority ranking. Results for the other GNNs, Node2Vec and the remaining baselines exist in Drive *(owner-reported)* but not in this repository.

## 3. Code of record and what changed during the run (important for reproduction)
The notebook was pinned to `b86df0d`. During the run the following fixes were applied in the Colab runtime and committed afterwards as **`1c85d98`** (commit "release: finalize VectorDrugMatch research artifacts and fixes"):
* **GCN** (`src/models/gnn/gcn.py`): the original GCN (sum aggregation, unscaled degree features) produced extreme logits (about -3.7 million on test pairs in the debugging session) and could not reproduce its saved predictions. It was replaced by a stabilised version: log1p scaling of the disease/gene degree features inside the encoder and mean aggregation; parameters are wrapped under `gnn.encoder.*`. **Any GCN number from before this fix is superseded; the reported GCN results are from the stabilised model.**
* **Loss** (`scripts/train_gnn.py`, `src/models/gnn/base.py`): training uses `binary_cross_entropy_with_logits` on logits (FP32) instead of sigmoid then BCE; models gained `forward_logits`.
* **RGCN / HGT**: convolutions run in FP32 inside the mixed-precision loop (dtype error in `segment_matmul`).
* **Embedding extraction** moved to the model device; **Node2Vec backend check** uses `pyg_lib` (the `torch_cluster` build was dropped).
* **GNN explanations**: `explain_link_gnn` is no longer PyG GNNExplainer. It is a **local relation-family perturbation**: remove each relation family (with its reverse edges) from the k-hop neighbourhood and record the change in predicted probability. Its output is relation-level, not edge-level (`tests/test_explainability.py` was updated to the new columns). Documents that say "GNNExplainer" describe the earlier design.
* The exact commit state under which each individual model finished training is **not recorded in the repository**. Per-session environment records (`run_environment_*.json`, `pip_freeze_*.txt`, `pipeline_log.jsonl`) are on Drive in `VDM_Outputs/outputs/` *(owner-reported)*; check their `commit` and dirty flags before claiming that every model came from a single commit.
* Pin for any re-run: `1c85d98a356d62d232aa8f8e3acf5ac497c2532a`. The `b86df0d` pin in older copies would reproduce the **old** GCN.

## 4. Not done / not claimed
No clinical validation or efficacy claim; no deployed API, `/predict` endpoint, web interface or hosting (log section 13: a verified end-to-end inference path exists only as the private GCN inference package); no model-versus-model superiority claim; the NDPI-weighted candidate ranking over unseen pairs is not implemented; licence questions in `Docs/LICENCE_AUDIT.md` are open, so the private Drive bundles and pair-level derived tables must not be published.

## 5. Model size
Parameter counts reported in the owner's Colab session *(owner-reported; counted from initialised models before the GCN fix, on the configuration of that session)*: GCN 1,155,649; GraphSAGE 1,155,649; GAT 1,109,569; RGCN 242,561; HGT 298,023. All five are graph neural networks, about 0.2 to 1.2 million parameters each; they are not language models. The count is not a statement about accuracy.

## 6. Known defects found while aligning the repository (2026-11-11)
1. `reports/research_validation_20261111/figures/01_model_performance.png` and `05_seed_stability.png` show **only the PrimeKG GCN**: the performance table they were drawn from had empty rows for the other three models. `research_report.md` showed `nan` for them and literal `\n` characters in its tables. **Fixed here:** the report text and `five_seed_performance.csv` now carry the values from log section 3. **Not fixed:** the two figures need regenerating from `seed_wise_metrics.csv` in Drive (`MyDrive/VDM_Outputs/external_validation/multiseed_results_20261111/`), which is not in this repository. Do not use them in the paper until regenerated.
2. The log's ranking table (section 7) labels the columns in the wrong order; the committed CSV and report are consistent with each other and with the arithmetic (PrimeKG GCN: Precision@500 0.7236 and Recall@500 0.2869 follow from 1,261 positives). Use the CSV.
3. `tests/test_explainability.py` was failing after the explanation method changed; updated (37 tests pass).
4. Source docstrings in `src/explainability/` and `scripts/explain_models.py` still say GNNExplainer; behaviour is as in section 3.
5. The executed notebook replaced the repository notebook; its Step 2 library cell differs from the design (section 3). The saved copy is the record of what ran.

## 7. Where things are
| what | where |
|---|---|
| Results report, tables, six figures | `reports/research_validation_20261111/` |
| Dated results addendum, handoff | `Docs/paper/RESULTS_AND_VALIDATION_ADDENDUM_20261111.md`, `Docs/FINAL_PROJECT_HANDOFF_20261111.md` |
| Owner's Colab log (redacted copy) | `Docs/COLAB_RESEARCH_VALIDATION_LOG.md` |
| Private bundles (not in GitHub) | Drive: `VDM_Outputs/releases/` (computational snapshot, GCN inference release, full model release and ZIP), `VDM_Outputs/external_validation/` |
| Release tag | `research-release-2026-11-11` (points at merge `9909bf0` on `main`) |
| How to re-run | `Docs/COLAB_BEGINNER_HANDBOOK.md`, `Docs/GOOGLE_DRIVE_UPLOAD_GUIDE.md` |
