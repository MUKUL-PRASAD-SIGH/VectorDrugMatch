# Statistical comparisons

## Method
Paired **hierarchical bootstrap** (`src/utils/final_metrics.py::hierarchical_paired_bootstrap`), B = 2,000, RNG seed 20261117. Each replicate resamples
(1) training seeds with replacement and (2) test pairs with replacement **stratified by class** (original positive/negative counts kept); the same
pair resample is applied to both models; the statistic is the mean over resampled seeds of metric(model 1) − metric(model 2). Seeds of two GCN
configurations are paired (identical initial weights per seed); a single-run model is broadcast. Five seeds are not treated as five test populations.
95% percentile CIs; two-sided bootstrap p-values (+1 correction; resolution 1/1,000) with **Holm** correction over each family (14 historical tests;
8 holdout tests per candidate set). Weighted AUC/AP equal sklearn with sample weights (tested, ties included).

These intervals cover seed variability and resampling of pairs like the fixed test set. They are not evidence about other drug populations or other
splits. The minimum Holm-adjusted p for the 14-test family is 0.014 (bootstrap resolution), so "pHolm = 0.014" means "smallest attainable".

## Historical seed-42 test set (already examined; 7,566 pairs, 1,261 positives / 6,305 sampled negatives)
| Comparison (model 1 − model 2) | ROC-AUC 1 / 2 | ΔAUC [95% CI] | ΔAP [95% CI] | pHolm (AUC / AP) | seeds favouring 1 (AUC/AP) |
|---|---|---|---|---|---|
| A_k4 − B_k4 | 0.827 / 0.732 | +0.095 [0.079, 0.114] | +0.148 [0.123, 0.177] | 0.014 / 0.014 | 5/5 |
| A_k4_L3 − B_k4_L3 | 0.853 / 0.734 | +0.118 [0.099, 0.139] | +0.188 [0.161, 0.215] | 0.014 / 0.014 | 5/5 |
| A_k4_L3 − A_k4 | 0.853 / 0.827 | +0.025 [0.012, 0.043] | +0.049 [0.024, 0.076] | 0.014 / 0.014 | 5/5 |
| A_k4_L3 − A_orig | 0.853 / 0.792 | +0.061 [0.044, 0.079] | +0.121 [0.090, 0.150] | 0.014 / 0.014 | 5/5 |
| A_k4_L3 − RF + disease profile (5 seeds) | 0.853 / 0.805 | +0.048 [0.032, 0.063] | +0.037 [0.014, 0.059] | 0.014 / 0.014 | 5/5 |
| A_k4_L3 − XGB + disease profile (1 run) | 0.853 / 0.764 | +0.089 [0.074, 0.104] | +0.311 [0.282, 0.336] | 0.014 / 0.014 | 5/5 |
| A_k4_L3 − logistic + disease profile | 0.853 / 0.752 | +0.101 [0.083, 0.119] | +0.069 [0.044, 0.094] | 0.014 / 0.014 | 5/5 |
| A_k4_L3 − MLP + disease profile | 0.853 / 0.767 | +0.085 [0.069, 0.101] | +0.183 [0.153, 0.213] | 0.014 / 0.014 | 5/5 |
| A_k4_L3 − degree GBM (cross-fitted) | 0.853 / 0.711 | +0.142 [0.124, 0.159] | +0.216 [0.188, 0.243] | 0.014 / 0.014 | 5/5 |
| A_k4_L3 − connectivity GBM | 0.853 / 0.800 | +0.052 [0.037, 0.069] | +0.067 [0.041, 0.093] | 0.014 / 0.014 | 5/5 |
| A_k4_L3 − fingerprint-profile GBM | 0.853 / 0.790 | +0.062 [0.047, 0.078] | +0.024 [−0.001, 0.049] | 0.014 / **0.066** | 5/5 |
| A_k4_L3 − deg+conn+fp GBM | 0.853 / 0.843 | +0.009 [−0.004, 0.023] | **−0.059 [−0.080, −0.037]** | **0.191** / 0.014 | 4/0 |
| A_k4_L3 − C_k4 (mechanism-only graph) | 0.853 / 0.771 | +0.081 [0.066, 0.097] | +0.145 [0.113, 0.178] | 0.014 / 0.014 | 5/5 |
| RF + disease profile − deg+conn+fp GBM | 0.805 / 0.843 | −0.039 [−0.049, −0.027] | −0.095 [−0.110, −0.080] | 0.014 / 0.014 | 0/0 |

Candidate universes: all rows use the identical 7,566 ordered test pairs (verified row-by-row). The structure-covered XGBoost (0.8433 / 0.6979 in
earlier reports) uses a different candidate subset and is **not** compared here.

## Locked final holdout (361 unseen drugs; evaluated once)
Hard negatives: 11,514 pairs, 1,919 positives / 9,595 sampled negatives. Selected = rank-average(GCN L3_combo, 5 seeds; deg+conn+fp GBM).

| Selected − comparator | hard: ΔAUC [CI] | hard: ΔAP [CI] | popularity-matched: ΔAUC [CI] | popularity-matched: ΔAP [CI] |
|---|---|---|---|---|
| GCN L3_combo alone | +0.036 [0.030, 0.044] | +0.095 [0.084, 0.107] | +0.037 [0.030, 0.044] | +0.120 [0.106, 0.135] |
| deg+conn+fp GBM alone | +0.027 [0.022, 0.032] | +0.034 [0.026, 0.042] | +0.023 [0.018, 0.028] | +0.008 [−0.001, 0.016] (pHolm 0.079, n.s.) |
| RF + disease profile | +0.072 [0.063, 0.081] | +0.116 [0.103, 0.128] | +0.102 [0.093, 0.112] | +0.113 [0.098, 0.129] |
| fingerprint-profile GBM | +0.077 [0.068, 0.087] | +0.103 [0.089, 0.116] | +0.065 [0.055, 0.074] | +0.058 [0.043, 0.073] |
| max Tanimoto (unsupervised) | +0.096 [0.084, 0.108] | +0.107 [0.093, 0.121] | +0.088 [0.077, 0.101] | +0.053 [0.036, 0.069] |
| connectivity GBM | +0.080 [0.071, 0.088] | +0.136 [0.122, 0.150] | +0.122 [0.113, 0.131] | +0.181 [0.166, 0.197] |
| degree GBM | +0.138 [0.127, 0.149] | +0.253 [0.235, 0.270] | +0.228 [0.217, 0.239] | +0.348 [0.329, 0.365] |
| disease popularity | +0.228 [0.216, 0.241] | +0.464 [0.444, 0.484] | +0.326 [0.314, 0.339] | +0.469 [0.448, 0.489] |
All other pHolm = 0.008 (attainable minimum for 8 tests).

## Additional metrics (holdout, selected model, hard set)
ROC-AUC 0.9066 [0.8986, 0.9146]; AP 0.7930 [0.7780, 0.8077]; trapezoidal PR-AUC 0.7930; P@10 = P@50 = P@100 = 1.000, P@500 = 0.996;
R@500 0.260; NDCG@500 0.997. Brier 0.206, log loss 0.593, ECE 0.337 **for the ranking score, which is a percentile and not a probability**;
the components are better calibrated at the sampled 1:5 prevalence (GCN Brier 0.085 / ECE 0.035; GBM 0.074 / 0.021).
Confusion at the cut that flags as many pairs as there are positives (score ≥ 0.775): TP 1,362, FP 558, FN 557, TN 9,037.
Per-drug full ranking (all ~17k diseases per holdout drug): recall@10 0.398, @50 0.550, @100 0.594, MRR 0.381, mean per-drug AP 0.305.
Full numbers: `FINAL_METRICS.csv`, `PAIRED_COMPARISONS.csv`, `final_holdout/HOLDOUT_RESULTS.json`.
