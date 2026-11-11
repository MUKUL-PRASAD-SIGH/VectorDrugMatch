# VectorDrugMatch — Research and Results Addendum

**Date:** 11 November 2026
**Purpose:** Reconcile project status with completed computational runs and preserved artifacts.
**Relationship to earlier documents:** This is a dated addendum. It does not overwrite historical project records.

## 1. Completed benchmark results

The following are recorded ROC-AUC / PR-AUC results from the existing seed-42 benchmark:

| Benchmark configuration | Selected model | ROC-AUC | PR-AUC |
|---|---|---:|---:|
| PrimeKG | GCN | 0.7787 | 0.4919 |
| PrimeKG + disease profile | Random Forest | 0.8043 | 0.6041 |
| Structure-covered PrimeKG | GCN | 0.7838 | 0.5183 |
| Structure-covered + disease profile | XGBoost | 0.8433 | 0.6979 |

These are benchmark results, not clinical efficacy estimates. They use a single drug-disjoint seed-42 split and should not be interpreted as independent clinical validation.

The structure-covered benchmark contains 6,727 test pairs. The full benchmark includes 839 test pairs without structure; the structure-covered results do not establish performance on structureless drugs.

The NTD-only evaluation is small: 140 pairs with 15 positives in the full benchmark, and 122 pairs with 15 positives in the structure-covered benchmark. These results are exploratory.

## 2. Disease-profile feature audit

Disease-profile features are constructed from training-side positive indications. The train positive pair uses leave-one-out handling; validation and test features use training information only. The audit and automated tests completed with 8 passed and 2 warnings.

The feature remains a potential popularity signal. Its availability and provenance at real-world inference time must be considered.

## 3. GCN inference reproducibility

The packaged GCN inference implementation was tested against the saved benchmark predictions:

- Held-out rows: 7,566
- Entity order: exact match
- All probabilities finite: yes
- Maximum absolute probability difference: 6.5955e-07
- Mean absolute probability difference: 2.8338e-08
- Prediction agreement: 100%

The benchmark reproduction test passed. This establishes inference reproducibility for this saved benchmark, not clinical validity.

## 4. Open Targets evidence assessment

A conservative Open Targets evidence cohort contained 16,410 candidate pairs. Of these, 9,065 pairs had both entities covered by the packaged GCN inference inputs and were scored.

The stage analysis found:
- Pair-level Spearman correlation between clinical-stage ordering and model score: rho = 0.0945.
- Drug-stage aggregated correlation: rho = 0.0605.
- Drug-cluster bootstrap 95% interval for the aggregated correlation: [0.0318, 0.0913].

These are weak positive associations in a positive-evidence-only cohort. There are no negative labels in this analysis, so AUROC/AUPRC cannot be calculated. Open Targets and PrimeKG may share upstream evidence sources. Clinical stage is not equivalent to efficacy or approval success.

This assessment is exploratory evidence analysis, not independent external validation.

## 5. Preserved computational and model artifacts

The computational snapshot was preserved and checksum-verified.

The full model release was created at:

`VDM_Outputs/releases/VectorDrugMatch_Full_Model_Release_20261111`

The ZIP archive is:

`VDM_Outputs/releases/VectorDrugMatch_Full_Model_Release_20261111.zip`

Packaging verification:
- 315 manifest files
- 10 GNN checkpoints
- 20 baseline model files
- ZIP integrity passed
- SHA-256 verification passed

The separate GCN inference release and Open Targets evidence assessment bundle were also preserved and verified.

Node2Vec has metrics and predictions but no saved checkpoint. The disease-profile variants contain classical baseline artifacts only; no disease-profile GNN checkpoints were produced.

## 6. Limitations and outstanding work

1. Independent clinical validation has not been established.
2. The Open Targets cohort is positive-evidence-only and may share sources with PrimeKG.
3. NTD evaluation sample sizes are small.
4. NDPI/equity features have incomplete coverage; missing values must not be interpreted as zero.
5. NDPI weights remain exploratory and require sensitivity and external assessment.
6. DrugBank, ChEMBL, AACT, TTD, EMA, PMDA, WHO, IHME, HAI and molecular structure data have outstanding licence or redistribution questions documented in the licence audit.
7. The current evidence does not justify clinical deployment or treatment recommendations.

## 7. Reproducibility and publication statement

The benchmark artifacts and inference package have been preserved. The saved GCN inference reproduces the benchmark prediction file within numerical tolerance. This is computational reproducibility for the recorded setup; it does not establish that the dataset is unbiased, that evidence sources are independent, or that predictions are clinically actionable.

Before public redistribution, complete the outstanding licence review. Do not publish restricted raw data or derived pair-level datasets without clearance.
