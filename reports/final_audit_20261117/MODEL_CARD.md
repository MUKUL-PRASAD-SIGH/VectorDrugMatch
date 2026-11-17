# Model card - VectorDrugMatch `vdm-1.0.0`

| | |
|---|---|
| Task | Rank candidate drug → disease **indication** hypotheses (PrimeKG node IDs) for research prioritisation |
| Model | Rank average of (a) a heterogeneous GCN, 4 message-passing layers (GraphConv, mean aggregation, BatchNorm, residual), 128-d embeddings, MLP link head (64), dropout 0.4, weight decay 5e-4, Adam lr 5e-3, ReduceLROnPlateau, k = 4 steps/epoch, best validation ROC-AUC checkpoint (patience 20, ≤ 200 epochs); **5 seeds** (21, 42, 52, 72, 100), probabilities averaged; and (b) a HistGradientBoosting classifier on degree, connectivity and drug-cross-fitted fingerprint-profile features |
| Parameters | GCN 3,307,137 per seed (16.5 M over 5 seeds); GBM 300 trees × ≤ 31 leaves |
| Training data | PrimeKG (Harvard Dataverse 10.7910/DVN/IXA7BM): 1,296 training drugs' indications (6,784 positives, 33,920 sampled negatives); 144-drug internal validation for early stopping; graph without indication edges and without held-out drugs' indication pairs |
| Output | `ranking_score` ∈ [0, 1]: mean of the two components' percentiles among reference pairs (internal-validation pairs, 1:5 sampled negatives). **Not a probability.** Component scores, PrimeKG flags (known indication / contraindication / off-label), sparsity flags, warnings and graph-evidence explanations are returned alongside |
| Bundle | 57.6 MB, SHA-256 per file in `manifest.json`; CPU inference (numpy / scipy / scikit-learn 1.7.2); load 3.7 s; 1,000 pairs 0.22 s; one drug vs all diseases 2.1 s; one disease vs all drugs 0.44 s (local CPU) |

## Evaluation (locked holdout: 361 drugs unseen in training and selection, evaluated once)
| Candidate set | ROC-AUC [95% CI] | AP [95% CI] | P@100 |
|---|---|---|---|
| hard negatives (1:5) | 0.907 [0.899, 0.915] | 0.793 [0.778, 0.808] | 1.00 |
| popularity-matched negatives (1:5) | 0.860 [0.849, 0.870] | 0.656 [0.635, 0.677] | 0.89 |
| per-drug ranking of all ~17k diseases | recall@10 0.40, @100 0.59, MRR 0.38, median rank of an indication ~3,000 | | |
| holdout drugs without contraindication/off-label records (165) | 0.862 (hard) / 0.823 (popularity-matched) | | |
| diseases with no training indications | 0.656 (hard) | | |

Development CV (5 drug-grouped folds × 3 seeds): validation AP 0.764 ± 0.025, ROC-AUC 0.901 ± 0.011.

## Intended use
Generating ranked, explainable hypotheses about new indications for drugs that are already in PrimeKG, for review by domain experts, with
literature and safety checks. Research use only.

## Out of scope
Clinical decisions, treatment advice, dosing, patient-level use; claims of efficacy; novel chemical entities without PrimeKG records (expected
performance is materially lower); diseases without training indications (near-chance ranking); any use of `ranking_score` as a probability.

## Known limitations and failure modes
* **Sampled negatives**: unlabelled pairs, not confirmed non-indications; metrics are relative to the sampling scheme (hard negatives reward
  disease popularity; popularity-matched results are lower).
* **Label incompleteness**: PrimeKG misses established uses; many top "novel" candidates are known therapies (evidence review: 4/20 established).
* **Same-source side information**: contraindication / off-label edges come from the same curated label source as indications; drugs without them
  score lower.
* **Class/route over-generalisation**: active-ingredient nodes have no formulation or route; topical/inhaled corticosteroids are proposed for
  systemic diseases.
* **Safety blind spots**: pairs not recorded as contraindications can still be harmful (e.g. stimulant → anxiety, antidepressant → mania).
* **Hub concentration**: the top 500 holdout pairs involve 52 drugs (one drug contributes 116) and favour popular diseases (median training degree
  13.5 vs 6).
* **Seed variability of the GCN component**: top-100 Jaccard between seeds 0.56 (min 0.49), Spearman 0.86; mitigated by averaging 5 seeds.
* **Calibration**: components are roughly calibrated only at the 1:5 sampled prevalence and are over-confident under popularity matching; at the
  prevalence of indications among all pairs (≈ 7e-5) a component probability of 0.9 corresponds to ≈ 0.003.
* Disease nodes include grouped MONDO concepts; ~1/3 of positives have imperfect DOID/MONDO mappings.

## Ethical considerations
Outputs could be misread as treatment suggestions. The API returns a disclaimer, excludes PrimeKG contraindications by default, warns on known
contraindications, requires an API key and is not exposed publicly. Neglected tropical disease coverage is small (18 NTD positive pairs in the
holdout), so no NTD-specific performance claim is made.

## Reproducibility
Code `exp/final-audit-20261117`; GPU runs at commits `3af51fd`/`0b3d225` (identical training code), Tesla T4, torch 2.14.1+cu130; split files and
hashes in `protocol_files/` and `protocol_manifest_committed.json`; selection `FROZEN_SELECTION.json`; holdout lock `HOLDOUT_EVALUATED.lock`;
everything in `EXPERIMENT_MANIFEST.json`.
