# VectorDrugMatch - final research audit (2026-11-17/18)

Branch `exp/final-audit-20261117` (main untouched). Earlier reports, the frozen benchmark, the historical split and all earlier artifacts are unchanged.
Three tiers of results are kept apart throughout:
* **historical** - the seed-42 split, examined by many earlier experiments (comparisons only);
* **development** - 5 drug-grouped CV folds over 1,440 drugs, validation only (all selection);
* **final holdout** - 361 drugs, written once, hashed, locked, evaluated once after the selection was frozen.

## Final model and status
**Selected:** `vdm-1.0.0` = rank average of a 4-layer heterogeneous GCN (L3_combo, 5 seeds, 3.31 M parameters each) and a gradient-boosted model on
degree, connectivity and drug-cross-fitted fingerprint-profile features. **Locked holdout:** ROC-AUC **0.907** [0.899, 0.915], AP **0.793**
[0.778, 0.808] (hard negatives); ROC-AUC 0.860 [0.849, 0.870], AP 0.656 [0.635, 0.677] (popularity-matched negatives).

**Status: RESEARCH-VALIDATED — READY FOR STAGING**

## Answers to the acceptance questions
1. **Leakage-free?** No target leakage identified: 42/42 historical and 130/130 new runs pass automated audits; holdout never read before freezing.
   Fixed: a leave-one-out train/test shift in label-derived baseline features. Documented: same-source contraindication/off-label side
   information (legitimate for known drugs, inflates performance relative to novel compounds). `LEAKAGE_AUDIT.md`, `DATA_INTEGRITY_AUDIT.md`.
2. **What reproduces?** All 42 GPU ablation runs (commit fee2401): every metric recomputes from saved predictions within 1e-6, summaries match,
   metadata and audits complete. Checkpoints are not in the light archive (0/42). A_k4_L3 retrained with a longer budget reproduces within GPU
   run-to-run noise (historical test AUC 0.848 vs 0.853). `phase2_artifacts/`.
3. **Does A_k4_L3 remain best?** Not unchanged. The extended budget gives nothing (all seeds stop by epoch 116; `CONVERGENCE_ANALYSIS.md`).
   Controlled tuning on development CV improves it: L3_combo (4 layers, 128-d, dropout 0.4, wd 5e-4) val AP 0.675 vs 0.650. Treats edges,
   RGCN, a mechanism-only graph, 2 layers and full-batch training are all worse. `MODEL_SELECTION_REPORT.md`.
4. **Beats the feature-based RF on identical candidates?** Yes. Historical: A_k4_L3 − RF ΔAUC +0.048 [0.032, 0.063], ΔAP +0.037 [0.014, 0.059]
   (5/5 seeds, pHolm 0.014). Holdout: selected − RF ΔAUC +0.072, ΔAP +0.116. But the RF recipe is handicapped by its leave-one-out features; a
   cross-fitted GBM beats the GCN on AP.
5. **Generalises to unseen drugs?** Yes, within PrimeKG: drug-disjoint holdout AUC 0.907 / AP 0.793; per-drug full ranking recall@10 0.40,
   recall@100 0.59. Weaker for drugs without contraindication/off-label records (AUC 0.862) and for diseases without training indications (0.656).
6. **Value beyond degree, connectivity, fingerprints?** The GCN **alone does not** beat the best simple baseline (holdout AUC 0.870 vs 0.880,
   AP 0.698 vs 0.759). It **adds complementary signal**: the ensemble beats the GBM by ΔAUC +0.027 [0.022, 0.032], ΔAP +0.034 [0.026, 0.042];
   under popularity-matched negatives the AUC gain holds (+0.023) but the AP gain is not significant (+0.008, pHolm 0.08). `BASELINE_COMPARISON.md`.
7. **Stable across seeds and splits?** Fold-to-fold SD of validation AP 0.025 (ensemble); per-seed holdout AUC of the GCN 0.864-0.875. Top-of-list
   stability across GCN seeds is moderate (top-100 Jaccard 0.56, Spearman 0.86); the deployed model averages 5 seeds.
8. **Calibrated for its output?** The output is a ranking score (percentile), explicitly not a probability (its ECE 0.34 is expected). Components are
   roughly calibrated at the sampled 1:5 prevalence (ECE 0.02-0.04), over-confident under popularity matching, and meaningless as clinical
   probabilities at real prevalence (0.9 → ≈ 0.003). Serving a ranking score is the appropriate output.
9. **Ranking quality?** Holdout P@10 = P@100 = 1.00, P@500 0.996, NDCG@500 0.997 on the sampled candidate set; for a realistic per-drug search over
   ~17k diseases, MRR 0.38, recall@10 0.40, recall@100 0.59, median rank of an indication ≈ 3,000.
10. **Independent evidence for top predictions?** Of 20 top novel pairs (holdout drugs, one per drug): 3 independently supported, 4 established
    uses missing from PrimeKG, 4 plausible, 2 safety-concerning, 7 insufficient. Main failure mode: corticosteroid class/route over-generalisation.
    `INDEPENDENT_EVIDENCE_VALIDATION.md`.
11. **Architecture and size?** Heterogeneous GraphConv GCN, 4 layers, 128-d, BatchNorm + residual, MLP link head (64), dropout 0.4: 3,307,137
    parameters × 5 seeds; plus HistGradientBoosting (300 trees, 31 leaves) on 19 features; parameter-free rank averaging. Bundle 57.6 MB.
12. **Final metrics with CIs?** See the table above and `FINAL_METRICS.csv`, `STATISTICAL_COMPARISONS.md`.
13. **Limitations and failure modes?** Sampled negatives; PrimeKG label incompleteness; same-source side information; no route/formulation
    information; safety blind spots for unrecorded harms; hub/popularity concentration (top-500 pairs involve 52 drugs); weak for
    diseases without training indications; few NTD positives (18 in the holdout). `MODEL_CARD.md`.
14. **Is the API functional?** Yes: FastAPI `/health`, `/model-info`, `/score`, `/rank`; 9 API tests + 50 others pass; the frozen Docker image runs
    healthy locally (CPU: one drug vs all diseases 2.1 s, one disease vs all drugs 0.44 s).
15. **Has staging deployment succeeded?** **No. It has not been attempted** - it needs your authorisation for an outward-facing, billed GCP deployment.
16. **Exact deploy command?** `bash deploy/build_image.sh outputs/final_audit_20261117/bundles/vdm-1.0.0` then the Cloud Run commands in
    `DEPLOYMENT_READINESS.md` (`gcloud run deploy vdm-api-staging … --no-allow-unauthenticated …`).
17. **Suitable for research prioritisation; what before clinical use?** Suitable for **research-grade candidate prioritisation with expert review**.
    Before any clinical relevance: prospective/temporal validation on indications approved after the PrimeKG snapshot, evaluation against curated
    true negatives, route/formulation-aware drug representations, systematic safety screening, expert curation of top candidates, and experimental
    or clinical evidence. Computational metrics are not clinical validation.

## Why this status and not another
* Not "generalisation insufficient": the locked drug-disjoint holdout supports good generalisation within PrimeKG.
* Not "validation incomplete": selection, holdout evaluation, statistics, baselines and evidence review are complete and reproducible.
* Not "ready for production research use": staging has not run; the evidence review found safety-concerning and route-implausible top candidates,
  so the system needs a staged period with expert review before broader research use.

## Artifact index (`reports/final_audit_20261117/`)
Reports: `FINAL_RESEARCH_REPORT.md`, `DATA_INTEGRITY_AUDIT.md`, `LEAKAGE_AUDIT.md`, `STATISTICAL_COMPARISONS.md`, `MODEL_SELECTION_REPORT.md`,
`CONVERGENCE_ANALYSIS.md`, `BASELINE_COMPARISON.md`, `INDEPENDENT_EVIDENCE_VALIDATION.md`, `DEPLOYMENT_READINESS.md`, `MODEL_CARD.md`.
Tables: `FINAL_METRICS.csv`, `SEED_WISE_METRICS.csv`, `PAIRED_COMPARISONS.csv`, `PREDICTIONS.csv` (holdout), `DEV_CV_SUMMARY.csv`, `DEV_CV_RUNS.csv`.
Provenance: `EXPERIMENT_MANIFEST.json`, `FROZEN_SELECTION.json`, `HOLDOUT_EVALUATED.lock`, `protocol_manifest_committed.json`, `protocol_files/`.
Figures: `figures/` (holdout AP and AUC, dev-CV comparison, calibration, per-drug recall, AUC by drug sparsity, convergence).
Analyses: `analysis/`, `phase2_artifacts/`, `phase3_historical/` (`phase3_historical_LOO_superseded/` kept as a negative result), `evidence/`,
`convergence/`, `final_holdout/`, `gpu_runs/`.
Model and service: `outputs/final_audit_20261117/bundles/vdm-1.0.0` (not in git: large), `src/serving/`, `deploy/`.

## Reproduce
```bash
python -m pytest -q tests                                                             # 59 tests
python scripts/final_audit/verify_gpu_ablation.py --root <archive> --out reports/final_audit_20261117/phase2_artifacts
python scripts/final_audit/phase3_historical_stats.py --gpu-root <archive> --old-root <VDM_Outputs/outputs> --out <dir>
python scripts/final_audit/dev_cv_baselines.py --splits cv_fold0 cv_fold1 cv_fold2 cv_fold3 cv_fold4 final_train --out outputs/final_audit_20261117/dev_cv
# GPU: notebooks/colab_final_audit_20261117.ipynb (stages A, B, C, final)
python scripts/final_audit/select_dev.py freeze
python scripts/final_audit/export_bundle.py --selection reports/final_audit_20261117/FROZEN_SELECTION.json --version vdm-1.0.0
python scripts/final_audit/evaluate_final_holdout.py --bundle outputs/final_audit_20261117/bundles/vdm-1.0.0   # refuses to run twice
python scripts/final_audit/post_holdout_analysis.py --bundle outputs/final_audit_20261117/bundles/vdm-1.0.0
python scripts/final_audit/pubmed_evidence.py
python scripts/final_audit/make_final_tables.py --bundle outputs/final_audit_20261117/bundles/vdm-1.0.0
```
