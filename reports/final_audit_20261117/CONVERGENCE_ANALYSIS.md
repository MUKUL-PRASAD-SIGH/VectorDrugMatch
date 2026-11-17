# Convergence analysis (A_k4_L3, 200-epoch budget)

Question: seed 72 of the historical A_k4_L3 run selected its final (100th) epoch. Does the model need more training?

Setup: identical to the historical runs (historical seed-42 split, Adam 5e-3 / wd 1e-4, ReduceLROnPlateau on validation ROC-AUC, k = 4 steps per
epoch, checkpoint = best validation ROC-AUC) except max epochs 200 with early-stopping patience 20. Five seeds, Tesla T4.
Output: `outputs/final_audit_20261117/convergence/` (checkpoints kept), `convergence/convergence_seedwise.csv`, `figures/fig_convergence.png`.
The original 100-epoch results are unchanged and used as the reference.

| Seed | 100-epoch budget: best / run | 200-epoch budget: best / run | val AUC 100 → 200 | historical test AUC 100 → 200 | test AP 100 → 200 |
|---|---|---|---|---|---|
| 21 | 73 / 93 | 72 / 92 | 0.889 → 0.880 | 0.855 → 0.854 | 0.657 → 0.650 |
| 42 | 79 / 99 | 62 / 82 | 0.881 → 0.876 | 0.844 → 0.839 | 0.629 → 0.624 |
| 52 | 90 / 100 | 96 / 116 | 0.873 → 0.877 | 0.864 → 0.859 | 0.662 → 0.646 |
| 72 | 100 / 100 | 96 / 116 | 0.878 → 0.885 | 0.859 → 0.851 | 0.658 → 0.658 |
| 100 | 77 / 97 | 67 / 87 | 0.868 → 0.871 | 0.841 → 0.837 | 0.634 → 0.631 |

Paired hierarchical bootstrap (200 − 100 budget): ΔAUC −0.0044 [−0.0089, −0.0003], ΔAP −0.0063 [−0.0152, +0.0027].

Findings
* Every seed early-stopped under the 200-epoch budget (by epoch 116); the cap was not binding. Seed 72 peaked at epoch 96 and stopped at 116.
* Validation AUC is unchanged on average (0.8777 vs 0.8780).
* Seeds 21, 42 and 100 stopped before epoch 100 under both budgets, so the budget cannot have influenced them; their differences (best epoch shifted by up to 17
  epochs, test AUC by up to 0.005) show the magnitude of GPU run-to-run non-determinism. The small negative ΔAUC is therefore not attributable to the budget.
* Conclusion: A_k4_L3 was converged; extended training gives no improvement. All final-protocol runs used 200 epochs / patience 20; none of the
  130 runs reached the 200-epoch cap (the latest stop was epoch 194).
