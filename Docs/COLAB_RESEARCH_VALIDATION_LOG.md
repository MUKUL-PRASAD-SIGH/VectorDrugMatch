> Copied from `VectorDrugMatch_Colab_Research_Validation_Log.md` (written by the project owner after the Colab session). The only change is that one e-mail address was replaced by a placeholder. Two statements in it were checked against the repository on 2026-11-11 and need a correction, recorded in `Docs/PROJECT_STATUS.md` section 6: (1) the ranking table in section 7 has the Precision@500, Recall@500 and NDCG@500 column labels shifted (the committed CSV and report are right: P@500 = 0.7236 for PrimeKG GCN); (2) the performance rows for three models were empty in the committed report files and have been filled from section 3 of this log.

# VectorDrugMatch --- Colab Research Validation & GitHub Publication Log

**Project:** VectorDrugMatch\
**Repository:** https://github.com/MUKUL-PRASAD-SIGH/VectorDrugMatch\
**Notebook:**
https://colab.research.google.com/github/MUKUL-PRASAD-SIGH/VectorDrugMatch/blob/mukul/notebooks/colab_final_run.ipynb\
**Validation date represented in artifact names:** 11 November 2026\
**Report directory:** `reports/research_validation_20261111/`\
**Target branch:** `mukul`, subsequently merged into `main`

------------------------------------------------------------------------

## 1. Purpose and scope

This document records the Colab work performed to assemble the
VectorDrugMatch research-validation report, generate visualizations,
restore the working environment after a runtime reset, commit the
report, and publish it to GitHub.

The work described here is **research evaluation and report
publication**. It does not mean that the model was deployed as a live
prediction service. A public inference API, interactive prediction
interface, production hosting, and operational monitoring were not
established as part of this workflow.

The goal was to use already-computed evaluation outputs rather than
rerun model training.

## 2. Research evaluation that was already completed

The evaluation results used by the report covered four model variants
and five random seeds.

### 2.1 Model variants

1.  PrimeKG GCN
2.  PrimeKG disease-profile Random Forest
3.  Structure-covered GCN
4.  Structure-covered disease-profile XGBoost

### 2.2 Seeds and evaluation design

The five seeds were:

`21, 42, 52, 72, 100`

All five seeds used the same saved train/validation/test split.
Therefore, the reported seed-wise standard deviation measures variation
across training seeds conditional on that fixed split. It does not
measure variability across independently sampled data splits.

The 20 model runs were already completed before the report-generation
workflow documented below.

### 2.3 Evaluation sample sizes

-   PrimeKG test set: 7,566 pairs, including 1,261 positive pairs and
    6,305 sampled negative pairs.
-   Structure-covered test set: 6,727 pairs, including 1,167 positive
    pairs.

The negative examples are **sampled negatives**, not experimentally
confirmed drug--disease non-interactions.

## 3. Five-seed performance results

Mean ± sample standard deviation:

  -----------------------------------------------------------------------
  Model                                 ROC-AUC                    PR-AUC
  ------------------- ------------------------- -------------------------
  PrimeKG GCN                   0.7880 ± 0.0118           0.5285 ± 0.0334

  PrimeKG RF +                  0.8049 ± 0.0020           0.6113 ± 0.0078
  Disease Profile                               

  Structure-covered             0.7847 ± 0.0089           0.5390 ± 0.0182
  GCN                                           

  Structure-covered             0.8433 ± 0.0000           0.6979 ± 0.0000
  XGBoost + Disease                             
  Profile                                       
  -----------------------------------------------------------------------

The structure-covered XGBoost predictions were identical across all five
seeds under the evaluated configuration. Its zero standard deviation is
a consequence of deterministic outputs in this setup; it is not proof of
robustness.

## 4. Bootstrap uncertainty and paired comparisons

Bootstrap confidence intervals were computed using 3,000 resamples on
fixed test samples.

  -----------------------------------------------------------------------
  Model                   ROC-AUC (95% CI)        PR-AUC (95% CI)
  ----------------------- ----------------------- -----------------------
  PrimeKG GCN             0.77866 \[0.76482,      0.49187 \[0.46326,
                          0.79276\]               0.52148\]

  PrimeKG RF              0.80427 \[0.78890,      0.60413 \[0.57581,
                          0.81908\]               0.63139\]

  Structure GCN           0.78380 \[0.76895,      0.51830 \[0.48731,
                          0.79788\]               0.54722\]

  Structure XGBoost       0.84326 \[0.82887,      0.69788 \[0.67244,
                          0.85716\]               0.72279\]
  -----------------------------------------------------------------------

Paired bootstrap comparisons used 5,000 resamples:

-   PrimeKG RF minus GCN:
    -   ROC-AUC difference: +0.02562; 95% CI \[0.01082, 0.04124\].
    -   PR-AUC difference: +0.11227; 95% CI \[0.08582, 0.13765\].
-   Structure XGBoost minus GCN:
    -   ROC-AUC difference: +0.05945; 95% CI \[0.04477, 0.07459\].
    -   PR-AUC difference: +0.17957; 95% CI \[0.15357, 0.20345\].

These intervals quantify resampling uncertainty on the fixed test
samples. They do not quantify variation across independent datasets or
populations.

## 5. Calibration results

Calibration values were already computed and verified in the preceding
evaluation work. A standalone calibration CSV was **not present** in the
Drive validation folders during the report rebuild. The verified values
were therefore encoded directly in the report-generation cell.

Mean ± sample SD; lower is better:

  -----------------------------------------------------------------------
  Model                 Brier score           Log loss                ECE
  -------------- ------------------ ------------------ ------------------
  PrimeKG GCN     0.11320 ± 0.00574  0.47067 ± 0.02674  0.07255 ± 0.00801

  PrimeKG RF      0.09658 ± 0.00078  0.33695 ± 0.00209  0.02705 ± 0.00347

  Structure GCN   0.11727 ± 0.00349  0.50864 ± 0.03458  0.07944 ± 0.00469

  Structure       0.09155 ± 0.00000  0.32414 ± 0.00000  0.05056 ± 0.00000
  XGBoost                                              
  -----------------------------------------------------------------------

PrimeKG RF had the lowest ECE among the PrimeKG variants. Structure
XGBoost had the lowest Brier score and log loss among the
structure-covered variants. These calibration measurements apply to the
sampled test distribution and are not validated clinical probabilities.
ECE was estimated using ten bins.

## 6. Error analysis

The error-analysis outputs were stored in Google Drive at:

`/content/drive/MyDrive/VDM_Outputs/external_validation/error_analysis_20261111/`

Files found:

-   `seed_wise_error_summary.csv`
-   `five_seed_error_summary.csv`
-   `all_prediction_errors.csv`
-   `top_10_confident_mistakes_seed42.csv`

Five-seed means:

  -----------------------------------------------------------------------
  Model                False          False   Total errors     Error rate
                   positives      negatives                
  ----------- -------------- -------------- -------------- --------------
  PrimeKG GCN         1052.2          512.6         1564.8         20.68%

  PrimeKG RF           880.6          478.4         1359.0         17.96%

  Structure            890.2          502.6         1392.8         20.70%
  GCN                                                      

  Structure            644.0          389.0         1033.0         15.36%
  XGBoost                                                  
  -----------------------------------------------------------------------

A repeated high-confidence false-negative pair included
`DB08903–MONDO_GROUP:41806_5861`. Such a model error is not necessarily
a biological false negative because the underlying labels may be
incomplete or noisy.

## 7. Ranking evaluation

Ranking outputs were stored in:

`/content/drive/MyDrive/VDM_Outputs/external_validation/ranking_evaluation_20261111/`

Files found:

-   `seed_wise_ranking_metrics.csv`
-   `five_seed_ranking_summary.csv`

Five-seed means:

  Model                 Average Precision   Precision@500   Recall@500   NDCG@500
  ------------------- ------------------- --------------- ------------ ----------
  PrimeKG GCN                     0.52849         0.28692      0.75175    0.72360
  PrimeKG RF                      0.61130         0.32403      0.83960    0.81720
  Structure GCN                   0.53901         0.31380      0.75950    0.73240
  Structure XGBoost               0.69788         0.38817      0.91842    0.90600

Structure XGBoost had Precision@10 = 1.00 in the reported ranking
evaluation. Top-K results describe the sampled candidate universe and
should not be interpreted as prospective deployment performance.

## 8. Google Colab and Drive workflow

### 8.1 Initial working repository

The repository was initially available in the Colab runtime at:

`/content/VectorDrugMatch`

The active target branch for publication was `mukul`.

The repository remote was:

`https://github.com/MUKUL-PRASAD-SIGH/VectorDrugMatch`

### 8.2 Existing Drive output locations

The validation data were stored in Google Drive under:

`/content/drive/MyDrive/VDM_Outputs/external_validation/`

Relevant folders:

-   `multiseed_results_20261111/`
-   `error_analysis_20261111/`
-   `ranking_evaluation_20261111/`
-   `gcn_open_targets_20261111/`
-   `VectorDrugMatch_External_Evidence_Assessment_20261111/`

The model release and inference release folders were also retained in
Drive under `VDM_Outputs/releases/`.

### 8.3 First report-generation attempt and Python syntax error

Git commands were initially entered directly into a Python code cell:

``` text
git status --short
```

Colab returned a `SyntaxError` because shell commands are not valid
Python statements by themselves.

The correction was to prefix shell commands with `!`, or use a shell
cell. For example:

``` python
!git status --short
!git add reports/research_validation_20261111/
```

For changing the working directory in a notebook, use:

``` python
%cd /content/VectorDrugMatch
```

### 8.4 First commit was made on the wrong branch

The first report commit was created on local `main`:

`482a314 docs: add research validation report and six visualizations`

The intended target was `mukul`. The local branch check showed:

-   Current local branch: `main`
-   Local branch available: `mukul`
-   Remote branches included `origin/main` and `origin/mukul`

A push attempt failed because GitHub credentials were not available in
that runtime:

``` text
fatal: could not read Username for 'https://github.com':
No such device or address
```

The local runtime subsequently reset, so the unpushed local commit was
not relied upon for publication.

### 8.5 Colab runtime reset and repository restoration

Colab displayed a connection/runtime message. After the runtime reset,
`/content/VectorDrugMatch` no longer existed and Git commands returned:

``` text
No such file or directory: '/content/VectorDrugMatch'
fatal: not a git repository
```

This happened because `/content` is runtime-local temporary storage. The
repository was cloned again from GitHub, explicitly using the `mukul`
branch:

``` python
%cd /content
!git clone -b mukul https://github.com/MUKUL-PRASAD-SIGH/VectorDrugMatch.git
%cd /content/VectorDrugMatch
!git branch --show-current
```

Google Drive was remounted:

``` python
from google.colab import drive
drive.mount('/content/drive')
```

The clone succeeded and the active branch printed `mukul`.

### 8.6 Confirming the saved CSV files

The following folders and CSVs were verified in Drive:

**`multiseed_results_20261111/`** - `seed_wise_metrics.csv` -
`five_seed_summary.csv`

**`error_analysis_20261111/`** - `seed_wise_error_summary.csv` -
`five_seed_error_summary.csv` - `all_prediction_errors.csv` -
`top_10_confident_mistakes_seed42.csv`

**`ranking_evaluation_20261111/`** - `seed_wise_ranking_metrics.csv` -
`five_seed_ranking_summary.csv`

The actual schemas were inspected before regenerating the report.

`seed_wise_metrics.csv`: - 20 rows, 4 columns - `model`, `seed`,
`roc_auc`, `pr_auc`

`seed_wise_error_summary.csv`: - 20 rows, 8 columns - `model`, `seed`,
`n`, `threshold`, `false_positives`, `false_negatives`, `total_errors`,
`error_rate`

`seed_wise_ranking_metrics.csv`: - 20 rows, 23 columns - `model`,
`seed`, `n_pairs`, `n_positives`, `average_precision`, and
precision/recall/NDCG metrics at K = 10, 25, 50, 100, 250, 500.

### 8.7 Rebuilding the report inside the repository

The report was regenerated directly in the cloned repository, not
downloaded from an external ZIP.

Target folder:

`/content/VectorDrugMatch/reports/research_validation_20261111/`

The generation cell:

1.  Loaded the three verified CSVs from Drive.
2.  Aggregated five-seed performance metrics.
3.  Aggregated five-seed error metrics.
4.  Aggregated ranking metrics.
5.  Encoded the previously verified calibration values directly because
    no calibration CSV was available.
6.  Created six Matplotlib visualizations.
7.  Wrote four aggregate CSVs.
8.  Wrote `research_report.md` and `README.md`.
9.  Verified that every expected artifact existed.

The report generator did not rerun model training.

### 8.8 Final report artifact list

The successful verification output showed 12 expected artifacts and no
missing files:

``` text
reports/research_validation_20261111/README.md
reports/research_validation_20261111/research_report.md
reports/research_validation_20261111/five_seed_performance.csv
reports/research_validation_20261111/five_seed_ranking.csv
reports/research_validation_20261111/five_seed_calibration.csv
reports/research_validation_20261111/five_seed_error_analysis.csv
reports/research_validation_20261111/figures/01_model_performance.png
reports/research_validation_20261111/figures/02_ranking_performance.png
reports/research_validation_20261111/figures/03_calibration_comparison.png
reports/research_validation_20261111/figures/04_error_analysis.png
reports/research_validation_20261111/figures/05_seed_stability.png
reports/research_validation_20261111/figures/06_precision_recall_at_k.png
```

The six figure files were:

1.  `01_model_performance.png`
2.  `02_ranking_performance.png`
3.  `03_calibration_comparison.png`
4.  `04_error_analysis.png`
5.  `05_seed_stability.png`
6.  `06_precision_recall_at_k.png`

The generator printed:

``` text
Expected artifacts: 12
Missing: []
SUCCESS: Report and six figures generated inside the repository.
```

## 9. Git staging, identity configuration, and commit

Only the report directory was staged. Other repository changes were
deliberately not staged.

The staging command was:

``` python
%cd /content/VectorDrugMatch
!git add reports/research_validation_20261111/
!git status --short
```

The staged files all appeared with `A` status, indicating newly added
report files.

The first commit attempt failed because Git author identity was not
configured:

``` text
Author identity unknown
Please tell me who you are.
fatal: unable to auto-detect email address
```

Git identity was configured locally for this repository:

``` python
!git config user.name "Mukul Prasad"
!git config user.email "<your e-mail>"
```

Then the report commit succeeded:

``` text
25361b0 docs: add research validation report and six visualizations
```

At that point, the local `mukul` branch contained the new report commit.

## 10. GitHub authentication and publication

The GitHub remote used HTTPS:

`https://github.com/MUKUL-PRASAD-SIGH/VectorDrugMatch`

The earlier push failure was caused by missing credentials in the fresh
Colab runtime. A GitHub Personal Access Token was generated through
GitHub's settings page:

`https://github.com/settings/personal-access-tokens/new`

Recommended fine-grained token settings for this repository:

-   Repository access: only `VectorDrugMatch`
-   Repository permission: `Contents` → `Read and write`

The token was entered into a Colab `getpass` prompt, rather than pasted
into chat or embedded in the notebook command. It was passed to the Git
process through an environment variable and a temporary askpass script.

The push command was:

``` text
git push origin mukul
```

The user subsequently confirmed: **"pushed npow"** (push completed).

The user then confirmed: **"merged to main"**.

The published report locations are:

-   Main branch:
    https://github.com/MUKUL-PRASAD-SIGH/VectorDrugMatch/tree/main/reports/research_validation_20261111
-   `mukul` branch:
    https://github.com/MUKUL-PRASAD-SIGH/VectorDrugMatch/tree/mukul/reports/research_validation_20261111

The user confirmed that the merge into `main` was completed. The exact
merge commit hash was not provided in the conversation.

## 11. Problems encountered and how they were resolved

  ----------------------------------------------------------------------------------------------
  Problem                      Cause                   Resolution
  ---------------------------- ----------------------- -----------------------------------------
  `SyntaxError` on             Shell command entered   Use `!git ...` in a Python cell
  `git status --short`         as Python               

  Push could not read GitHub   No Git credentials in   Use a GitHub token via hidden prompt
  username                     Colab                   

  `/content/VectorDrugMatch`   Colab runtime reset     Reclone repository from GitHub
  missing                                              

  Git reported "not a git      Working                 Clone repository and `%cd` into it
  repository"                  directory/repository    
                               disappeared after reset 

  First report commit landed   Wrong active local      Reclone/switch to `mukul` and create the
  on `main`                    branch                  intended commit there

  Git author identity unknown  `user.name` and         Configure repository-local Git identity
                               `user.email` unset      

  Calibration CSV missing      No standalone           Use previously verified calibration
                               calibration CSV in the  values, clearly documented
                               Drive folder            

  Concern about unrelated      Other files were        Stage only
  changes                      modified/untracked      `reports/research_validation_20261111/`
  ----------------------------------------------------------------------------------------------

## 12. Important research limitations and interpretation

The report should be read with the following qualifications:

1.  Negative examples are sampled negatives, not experimentally
    confirmed non-interactions.
2.  The five seeds share the same saved data split.
3.  Bootstrap intervals resample the fixed test samples.
4.  The structure-covered test set is a subset, not an independent
    external cohort.
5.  Identical XGBoost predictions across seeds explain zero standard
    deviation in this evaluation; this does not establish robustness.
6.  Calibration metrics describe the sampled test distribution and are
    not clinically validated probabilities.
7.  ECE is a ten-bin estimate.
8.  The NTD test subset has only 15 positive examples, so strong
    NTD-specific conclusions are not justified.
9.  Contradictory indication, contraindication, and off-label records
    may exist.
10. External Open Targets positive-evidence assessment is not
    independent clinical validation and does not establish verified
    negative labels.
11. No clinical validity or deployment-readiness claim follows from this
    benchmark.

## 13. What was not done: model deployment

The completed workflow published **research results and
visualizations**. It did not establish any of the following:

-   A running production inference server.
-   A publicly accessible `/predict` API endpoint.
-   A web application for entering drug and disease identifiers.
-   A verified end-to-end inference pipeline that loads the selected
    checkpoint and all required graph/preprocessing assets.
-   Production hosting, uptime monitoring, authentication, or
    operational alerting.

Therefore, the repository's research report should not be described as a
deployed model.

## 14. Recommended next phase: inference and deployment

The next phase should be treated as a separate engineering milestone.

### Phase A --- Audit inference assets

Locate and verify:

-   The selected trained checkpoint.
-   Model architecture and configuration.
-   Graph data and node-ID mappings.
-   Feature construction and preprocessing code.
-   Drug and disease identifier validation.
-   Any required embeddings or auxiliary data.
-   A reproducible inference example.

The private Drive model releases may contain some of these assets.
Inspect them before deciding which files can be published. Model
bundles, datasets, checkpoints, predictions, and derived/restricted data
should remain private unless redistribution rights are confirmed.

### Phase B --- Implement and test inference

Create a reproducible prediction function that accepts supported drug
and disease identifiers and returns a clearly defined model score.
Validate it against known evaluation examples and test invalid or
unsupported identifiers.

Do not assume that a model checkpoint alone is sufficient: graph-based
models may require the exact graph, node mappings, feature pipeline, and
configuration used during training.

### Phase C --- API

Wrap the verified inference function in a service such as FastAPI.
Potential endpoints:

-   `GET /health`
-   `POST /predict`

The request and response schema should be documented, input validation
should be explicit, and model/version metadata should accompany outputs.

### Phase D --- User interface and hosting

Build a simple interface for entering a drug ID and disease ID, then
displaying the model score and appropriate caveats. Deploy the API and
interface only after local end-to-end tests pass. Add authentication,
rate limiting, logging, monitoring, and resource limits as appropriate.

### Phase E --- Safe interpretation

The application should clearly communicate that VectorDrugMatch is a
computational research model. Its score is not a treatment
recommendation, proof of interaction, or substitute for clinical review.

------------------------------------------------------------------------

## 15. Final status

  Deliverable                            Status
  -------------------------------------- ---------------------------------------------
  Five-seed evaluation results           Completed before report publication
  Error and ranking evaluation outputs   Available in Google Drive
  Calibration metrics                    Previously computed and encoded into report
  Six research visualizations            Generated
  Research report and README             Generated
  Four aggregate CSV files               Generated
  Report committed on `mukul`            Confirmed
  Push to GitHub                         User confirmed successful
  Merge into `main`                      User confirmed successful
  Live model inference deployment        Not yet done
  Interactive production prediction UI   Not yet done

**Final conclusion:** The Colab research-validation and GitHub
publication workflow is complete according to the user's confirmations.
The next milestone is to audit the saved model and inference assets,
implement a reproducible prediction path, test it, and then deploy it as
a separate service.
