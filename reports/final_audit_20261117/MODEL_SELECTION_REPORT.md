# Model selection report

## Predeclared procedure (`configs/final_audit_20261117_plan.json`, committed before any final-protocol GCN result)
* Metric: mean validation AP (hard negatives) over the 5 drug-grouped development folds × seeds. Ties: within 0.005 AP → higher popularity-matched
  AP, then fewer parameters / the non-ensemble.
* Stage A: convergence rerun (historical split). Stage B: 13 one-factor configurations around A_k4_L3, 5 folds, seed 42. Stage C: top-3 + a
  combination of every improving factor (≥ +0.005 AP), seeds 21 and 52 added. Final: best GCN on `final_train` (5 seeds).
* Final candidates: best GCN, deg+conn+fp GBM, and their parameter-free rank average.
* The locked holdout is read only after `FROZEN_SELECTION.json` exists.

## Stage B (one factor at a time, seed 42, 5 folds; validation AP)
| Config | Change from A_k4_L3 | val AP | val AUC | popmatch AP |
|---|---|---|---|---|
| L3_drop0.4 | dropout 0.4 | 0.668 | 0.873 | 0.529 |
| L3_wd5e-4 | weight decay 5e-4 | 0.666 | 0.866 | 0.526 |
| L3_emb128 | embedding 128, head 64 | 0.666 | 0.864 | 0.554 |
| L4 | 4 layers | 0.664 | 0.870 | 0.534 |
| **L3_base** | (= A_k4_L3, 200 epochs) | 0.650 | 0.855 | 0.524 |
| L3_wd1e-5 | weight decay 1e-5 | 0.641 | 0.852 | 0.495 |
| L3_lr0.002 | lr 0.002 | 0.639 | 0.849 | 0.503 |
| L3_drop0.1 | dropout 0.1 | 0.638 | 0.850 | 0.519 |
| L2 | 2 layers (≈ A_k4) | 0.624 | 0.841 | 0.500 |
| RGCN_L2_original | relation-aware RGCN, no treats | 0.621 | 0.843 | 0.461 |
| L3_k1 | one full-batch step per epoch | 0.608 | 0.836 | 0.462 |
| L3_mechanism | no contraindication / off-label edges | 0.547 | 0.801 | 0.419 |
| L3_train_treats | training treats edges with masking | 0.510 | 0.779 | 0.346 |

Negative findings: the relation-aware RGCN and treats-edge message passing do not help; removing same-source side information hurts.

## Stage C (3 seeds × 5 folds) and the planning defect
Correct plan from complete Stage B: {L3_drop0.4, L3_wd5e-4, L3_emb128, L3_combo = 4 layers + emb 128/head 64 + dropout 0.4 + wd 5e-4}. On Colab,
Stage C was first started before Stage B had finished and was later re-run; the planner then used means over all seeds present (a bug, now fixed:
it must use Stage B seeds only) and swapped L4 in for L3_emb128. All four correct configurations completed 3 seeds × 5 folds; the extra L4 seeds are
reported but are not candidates. L3_combo's hyper-parameters were identical in both plans.

| Config (3 seeds × 5 folds) | val AP mean ± SD | val AUC | popmatch AP | params |
|---|---|---|---|---|
| **L3_combo** | **0.675 ± 0.032** | 0.875 | 0.521 | 3,307,137 |
| L3_drop0.4 | 0.666 ± 0.038 | 0.870 | 0.518 | 1,255,105 |
| L3_wd5e-4 | 0.664 ± 0.033 | 0.865 | 0.525 | 1,255,105 |
| L3_emb128 | 0.663 ± 0.030 | 0.863 | 0.543 | 2,911,617 |
| (L4, surplus) | 0.659 ± 0.035 | 0.867 | 0.516 | 1,354,561 |

Best GCN: L3_combo (no other config within 0.005 AP).

## Final decision (development data only; frozen 2026-11-17 21:04:53Z)
| Candidate | val AP | val AUC | popmatch AP |
|---|---|---|---|
| **rank-avg(L3_combo, deg+conn+fp GBM)** | **0.764 ± 0.025** | 0.901 | 0.645 |
| deg+conn+fp GBM | 0.733 ± 0.025 | 0.865 | 0.633 |
| L3_combo | 0.675 ± 0.032 | 0.875 | 0.521 |

Selected: **rank-avg(L3_combo, deg+conn+fp GBM)**, with no tie. Frozen: architecture, hyper-parameters, preprocessing, feature schema, checkpoint
policy (best validation ROC-AUC, patience 20, ≤ 200 epochs), final checkpoints (SHA-256 in `FROZEN_SELECTION.json`), GBM model, seeds
21/42/52/72/100. The final GCN seeds trained on `final_train` (1,296 drugs; 144-drug internal validation) reached validation AUC 0.870-0.886 at
best epochs 59-80 (40-50 s each on a T4).

## Holdout confirmation (evaluated once, after freezing)
The ordering on the holdout matches development: rank average > GBM > GCN (AUC 0.907 > 0.880 > 0.870; AP 0.793 > 0.759 > 0.698).
