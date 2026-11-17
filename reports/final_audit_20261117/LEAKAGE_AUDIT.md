# Leakage audit

**Conclusion: no target leakage was identified in the final pipeline.** Two issues were found and handled: a leave-one-out train/test shift in
label-derived baseline features (fixed), and same-source side information (contraindication / off-label) that is legitimate for the intended
deployment but inflates performance relative to novel compounds (quantified, documented, flagged at inference time).

## Message passing
* Treats (indication) edges are never in the message-passing graph of the deployed GCN (`variant = original`).
* Every held-out indication pair (CV-validation fold + locked holdout during development; final_train internal-validation + holdout for the final
  model) is removed from `contraindicated_for` / `offlabel_for` in both directions before training (`train_gcn_protocol.mp_graph`).
* Automated audit before every run (`train_gcn_protocol.audit`): excluded pairs absent from every drug-disease relation and its reverse; treats edges
  are training positives only; reverse treats = flip; drug sets disjoint; training pairs use training drugs; negatives are not known pairs.
  **130/130 GPU runs pass; 42/42 historical runs pass** (re-verified from the archive).
* Treats-in-graph variants (masking each step's supervised positives) were evaluated: historical B_k4 / B_k4_L3 / D_rgcn_B and final-protocol
  L3_train_treats are all worse than the no-treats controls (e.g. dev AP 0.510 vs 0.650). B0_naive (unmasked) is a leakage diagnostic only.

## Label-derived features (defect found and fixed)
The historical disease-profile features use leave-one-out for training rows: a training positive sees the disease's training-indication count
minus itself, while negatives of the same disease see the full count. A tree model learns this one-count offset, which never occurs for held-out
drugs. Evidence: a degree-only GBM with leave-one-out features scored ROC-AUC 0.57 on the historical test set, below the raw popularity score (0.65);
with drug-grouped **cross-fitting** (training rows of fold j use only other folds' positives) it scores 0.71. The historical RF + disease profile
recipe keeps the leave-one-out construction and is reproduced as-is for comparison (it is weaker: holdout AUC 0.835 vs 0.880 for the cross-fitted GBM).
All new baselines and the deployed GBM use cross-fitting (`src/features/simple_baselines.py`).

## Same-source side information (contraindication / off-label)
* Source: in PrimeKG, indications, contraindications and off-label uses are all drug-disease relations derived from the same curated drug-label
  resource (DrugCentral, per the PrimeKG documentation; not re-verified here). They are therefore **not independent** of the target labels.
* They are not the label and contain no held-out indication pair, but they place a drug in a therapeutic area (e.g. contraindicated for a disease
  related to its indications).
* Influence: removing them (mechanism-only graph) lowers dev-CV AP from 0.650 to 0.547 (L3_base vs L3_mechanism; historical C_k4 vs A_k4: AUC
  0.771 vs 0.827). On the locked holdout, drugs with no such edges (165/361) score AUC 0.862 vs 0.921 for drugs with them
  (`analysis/holdout_by_side_information.csv`).
* Appropriateness: the deployment setting is "new indications for drugs already in PrimeKG", where these records exist at prediction time, so their
  use is legitimate there. For new chemical entities they do not exist; expected performance is closer to the no-side-information stratum.
  The API reports `drug_gene_targets` and other sparsity flags; this limitation is in the model card.

## Evaluation hygiene
* The historical seed-42 test set has been examined by many experiments; it is reported only as "historical".
* The final holdout (361 drugs) was written once (seed 20261117), hashed, committed, never read by training or selection code (the trainer refuses
  any split named holdout), and evaluated exactly once after `FROZEN_SELECTION.json` existed (`HOLDOUT_EVALUATED.lock`, started 21:08:39Z,
  finished 21:17:51Z on 2026-11-17, selection sha256 `e8cb89dc…`, holdout sha256 `b54367ad…`).
* 53 holdout drugs were among the historical seed-42 validation/test drugs (independent re-partition). Their historical scores were seen in earlier
  work, but no final-protocol model or selection used holdout labels.
* Selection used validation folds only; the CV validation fold also drove early stopping (equal optimism for every candidate; documented).
