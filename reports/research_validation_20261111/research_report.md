# VectorDrugMatch: Research Validation Report

## Experimental design

Four model variants were evaluated over five random seeds:
21, 42, 52, 72, and 100.

- PrimeKG GCN
- PrimeKG disease-profile Random Forest
- Structure-covered GCN
- Structure-covered disease-profile XGBoost

All five seeds use the same saved train, validation, and test split.
Therefore, seed-wise standard deviations measure training-seed
variation conditional on the fixed split, not split variability.

## Performance

Results are reported as mean and sample standard deviation.

| Model | ROC-AUC | PR-AUC |
|---|---:|---:|
| PrimeKG GCN | 0.7880 ± 0.0118 | 0.5285 ± 0.0334 |
| PrimeKG RF | 0.8049 ± 0.0020 | 0.6113 ± 0.0078 |
| Structure GCN | 0.7847 ± 0.0089 | 0.5390 ± 0.0182 |
| Structure XGBoost | 0.8433 ± 0.0000 | 0.6979 ± 0.0000 |

## Ranking evaluation

Ranking metrics are calculated over the sampled candidate universe.
They should not be interpreted as prospective deployment performance.

| Model | AP | Precision@500 | Recall@500 | NDCG@500 |
|---|---:|---:|---:|---:|
| PrimeKG GCN | 0.5285 | 0.7236 | 0.2869 | 0.7518 |
| PrimeKG RF | 0.6113 | 0.8172 | 0.3240 | 0.8396 |
| Structure GCN | 0.5390 | 0.7324 | 0.3138 | 0.7595 |
| Structure XGBoost | 0.6979 | 0.9060 | 0.3882 | 0.9184 |

## Calibration

Lower Brier score, log loss, and ECE indicate better calibration
under the evaluated sampled test distribution.

| Model | Brier | Log loss | ECE |
|---|---:|---:|---:|
| PrimeKG GCN | 0.11320 ± 0.00574 | 0.47067 ± 0.02674 | 0.07255 ± 0.00801 |
| PrimeKG RF | 0.09658 ± 0.00078 | 0.33695 ± 0.00209 | 0.02705 ± 0.00347 |
| Structure GCN | 0.11727 ± 0.00349 | 0.50864 ± 0.03458 | 0.07944 ± 0.00469 |
| Structure XGBoost | 0.09155 ± 0.00000 | 0.32414 ± 0.00000 | 0.05056 ± 0.00000 |

## Error analysis

| Model | Mean FP | Mean FN | Mean total errors | Mean error rate |
|---|---:|---:|---:|---:|
| PrimeKG GCN | 1052.2 | 512.6 | 1564.8 | 20.68% |
| PrimeKG RF | 880.6 | 478.4 | 1359.0 | 17.96% |
| Structure GCN | 890.2 | 502.6 | 1392.8 | 20.70% |
| Structure XGBoost | 644.0 | 389.0 | 1033.0 | 15.36% |

## Statistical comparison

Previously computed paired bootstrap comparisons on fixed test samples:

- PrimeKG RF minus GCN: ROC-AUC difference +0.02562
  (95% CI: 0.01082 to 0.04124); PR-AUC difference +0.11227
  (95% CI: 0.08582 to 0.13765).
- Structure XGBoost minus GCN: ROC-AUC difference +0.05945
  (95% CI: 0.04477 to 0.07459); PR-AUC difference +0.17957
  (95% CI: 0.15357 to 0.20345).

These intervals quantify resampling uncertainty on fixed test samples,
not variation across independent datasets or populations.

## Limitations

1. Negative examples are sampled negatives, not experimentally
   confirmed non-interactions.
2. All five seeds use the same saved data split.
3. Bootstrap intervals resample fixed test samples.
4. The structure-covered test set is a subset, not an independent
   external cohort.
5. Structure XGBoost predictions were identical across all five seeds.
   Its zero standard deviation does not establish robustness.
6. Calibration metrics are specific to the sampled test distribution;
   they are not validated clinical probabilities.
7. ECE is estimated using ten bins.
8. The NTD test subset contains only 15 positives and does not support
   strong NTD-specific conclusions.
9. Contradictory indication, contraindication, and off-label records
   may exist in the underlying data.
10. External positive-evidence assessment is not independent clinical
    validation and does not establish verified negative labels.

## Conclusion

The evaluated models show different performance profiles across
classification, ranking, calibration, and error metrics. Results
support computational benchmarking on the evaluated datasets only.
They do not establish clinical validity or readiness for deployment.

## Figures

> **Known defect (found during the repository alignment, 2026-11-11):** figures 01 and 05 were generated from an incomplete performance table and show only the PrimeKG GCN; the other three models are missing. They must be regenerated from `seed_wise_metrics.csv` in Google Drive (see `Docs/PROJECT_STATUS.md`, section 6). The tables above and `five_seed_performance.csv` were corrected from the verified values recorded in `Docs/COLAB_RESEARCH_VALIDATION_LOG.md`. Corrected versions of the performance, ranking, calibration and error figures (paper figures 8-11, `scripts/make_results_figures.py`) are in `Docs/paper/figures/`. Figures 02, 03, 04 and 06 were not found to have this problem in the checks made.


- 01_model_performance.png
- 02_ranking_performance.png
- 03_calibration_comparison.png
- 04_error_analysis.png
- 05_seed_stability.png
- 06_precision_recall_at_k.png
