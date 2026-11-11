# VectorDrugMatch — Final Project Handoff

**Status date:** 11 November 2026

## Completed
- PrimeKG benchmark training and reporting.
- Structure-covered benchmark training and reporting.
- Disease-profile baseline variants and feature audit.
- Explainability analyses and reports.
- Computational snapshot with checksum verification.
- GCN inference release with benchmark reproduction test passed.
- Open Targets evidence assessment and scored candidate cohort.
- Full model artifact bundle with SHA-256 manifest and ZIP verification.

## Main model results

| Variant | Selected model | ROC-AUC | PR-AUC |
|---|---|---:|---:|
| PrimeKG | GCN | 0.7787 | 0.4919 |
| PrimeKG + disease profile | RF | 0.8043 | 0.6041 |
| Structure-covered | GCN | 0.7838 | 0.5183 |
| Structure-covered + disease profile | XGBoost | 0.8433 | 0.6979 |

## Release locations

- Computational snapshot: `VDM_Outputs/releases/VectorDrugMatch_Computational_Snapshot_20261111`
- GCN inference release: `VDM_Outputs/releases/VectorDrugMatch_GCN_Inference_Release_20261111`
- External evidence assessment: `VDM_Outputs/external_validation/VectorDrugMatch_External_Evidence_Assessment_20261111`
- Full model release: `VDM_Outputs/releases/VectorDrugMatch_Full_Model_Release_20261111`
- Full model ZIP: `VDM_Outputs/releases/VectorDrugMatch_Full_Model_Release_20261111.zip`

## Not completed / not claimed
- Independent clinical validation.
- Clinical utility or efficacy demonstration.
- Final legal clearance for redistribution of all upstream and derived data.
- Final manuscript submission or publication acceptance.
- Public upload of the private Drive bundles.

## Publication and GitHub caution
The repository has previously pushed commits to its public GitHub branch. The current private Drive bundles and subsequent local changes have not been pushed as part of this handoff. Do not rewrite Git history. Do not publish restricted data or model artifacts until the licence audit is resolved.

## Recommended next actions
1. Reconcile the main paper with the dated results addendum.
2. Review every unresolved licence entry with the relevant source terms or institutional guidance.
3. Conduct independent, appropriately labelled external validation before making clinical claims.
4. Review the public repository contents and history before any further release.
5. Obtain explicit approval before committing or pushing additional changes.
