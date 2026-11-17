# Baseline comparison - does the GCN add signal beyond degree, connectivity and chemistry?

All baselines are trained on the same training pairs and evaluated on the identical candidate pairs as the model they are compared with.
Label-derived features are cross-fitted by drug (see `LEAKAGE_AUDIT.md`). Hyper-parameters were fixed before any final-protocol result
(HistGradientBoosting: 300 iterations, lr 0.05, 31 leaves, L2 1.0). Definitions: `src/features/simple_baselines.py`.

| Baseline | Features |
|---|---|
| disease popularity | number of training drugs indicated for the disease (unsupervised score) |
| degree GBM | graph degrees of drug and disease per relation + disease training-indication count |
| connectivity GBM | + path counts (shared genes, drug-gene-gene-disease, drug-contra/off-label-related disease, drug-gene-training drug-indication) and 2/3-hop reachability |
| max Tanimoto | maximum Morgan similarity of the drug to the disease's training drugs (unsupervised) |
| fingerprint-profile GBM | max / mean Tanimoto to the disease's training drugs + profile flag + disease training degree |
| deg+conn+fp GBM | all of the above |
| RF + disease profile | historical recipe (Morgan bits + leave-one-out disease profile, RF 100×depth 10, sigmoid-calibrated) |

## Results
| Model | Historical test AUC / AP | Dev CV val AP (5 folds) | **Holdout AUC / AP (hard)** | **Holdout AUC / AP (popularity-matched)** |
|---|---|---|---|---|
| disease popularity | 0.648 / 0.294 | 0.301 | 0.679 / 0.329 | 0.534 / 0.187 |
| degree GBM | 0.711 / 0.432 | 0.468 | 0.769 / 0.540 | 0.632 / 0.308 |
| connectivity GBM | 0.800 / 0.581 | 0.580 | 0.827 / 0.657 | 0.738 / 0.475 |
| max Tanimoto | 0.764 / 0.630 | 0.665 | 0.811 / 0.686 | 0.772 / 0.603 |
| fingerprint-profile GBM | 0.790 / 0.624 | 0.652 | 0.829 / 0.690 | 0.795 / 0.598 |
| RF + disease profile | 0.805 / 0.611 | 0.629 | 0.835 / 0.678 | 0.758 / 0.543 |
| **deg+conn+fp GBM** | 0.843 / 0.707 | 0.733 | 0.880 / 0.759 | 0.837 / 0.648 |
| GCN A_k4_L3 (historical) / L3_combo (final) | 0.853 / 0.648 | 0.675 | 0.870 / 0.698 | 0.823 / 0.536 |
| **Selected: rank-avg(GCN, deg+conn+fp GBM)** | - | 0.764 | **0.907 / 0.793** | **0.860 / 0.656** |

## Answers
* **Popularity and connectivity explain a large share but not all of the signal.** Disease popularity alone reaches AUC 0.68 on the holdout (hard
  negatives) and falls to chance (0.53) once negatives are popularity-matched: the hard-negative benchmark rewards popularity. The degree GBM
  (0.77) and connectivity GBM (0.83) explain more; the full feature GBM reaches 0.88.
* **Reachability gap (historical test):** 28% of positives vs 7% of sampled negatives are within 2 hops in the message-passing graph, and 81% vs 62%
  within 3 hops (reachability flag alone AUC 0.60). The GCN still ranks well within reachable (AUC 0.87) and within 3-hop-unreachable pairs (0.76).
* **The GCN alone does not beat the strongest simple baseline.** On the holdout the deg+conn+fp GBM is better than the GCN (AUC 0.880 vs 0.870;
  AP 0.759 vs 0.698), and on the historical split it ties on AUC and wins on AP (Δ −0.059 for the GCN, significant).
* **The GCN adds complementary signal.** Averaging ranks of the GCN and the GBM is significantly better than the GBM alone on the holdout
  (ΔAUC +0.027 [0.022, 0.032], ΔAP +0.034 [0.026, 0.042]); with popularity-matched negatives the AUC gain remains (+0.023) but the AP gain is not
  significant (+0.008, pHolm 0.08). The gain is largest for sparse drugs (1-2 gene targets: AUC 0.878 vs GBM 0.832).
* **The GCN is less robust than the GBM to popularity matching** (AP 0.698 → 0.536 vs 0.759 → 0.648) and much weaker for drugs without
  contraindication/off-label records (AUC 0.800 vs GBM 0.844).
* **Fingerprint similarity is a strong, cheap baseline** (holdout AP 0.686 unsupervised), close to the GCN alone.
