# Data integrity audit - VectorDrugMatch final audit (2026-11-17/18)

Scope: PrimeKG-derived graph (`data/processed/primekg/`), the historical seed-42 split, the new final-protocol split
(`data/processed/primekg/splits_final_20261117/`, committed byte-for-byte under `protocol_files/`), and every feature used by the final model.
Nothing in the frozen benchmark or earlier reports was modified.

## Provenance
| Item | Value |
|---|---|
| Source | PrimeKG `kg.csv`, Harvard Dataverse 10.7910/DVN/IXA7BM, sha256 `0a5a010f…`, MONDO release 2026-11-03 |
| Nodes | 7,957 drugs, 17,080 diseases (MONDO / grouped MONDO), 19,051 genes |
| Drug-disease relations | indication 9,388 pairs (target), contraindication 30,675, off-label 2,568 (kg.csv lists each pair twice, one per direction; collapsed) |
| Other relations | drug-gene 25,468, disease-gene 80,411, gene-gene 321,075 (642,150 directed), disease-disease 32,194 |
| Processed-file hashes | `edges.csv`, `drugs.csv`, `diseases.csv`, `drug_features.npy` sha256 recorded in `protocol_manifest_committed.json`; the 7 frozen benchmark files verified against `Docs/release/vdm_v1_candidate_manifest.json` locally and on Colab |
| Drug features | Morgan fingerprint, 2,048 bits, from SMILES (no label information) |
| Disease features | `[is_ntd, daly_rate (0 = unknown for all), degree]`; degree counts only non-label relations (`LABEL_RELATIONS` excluded in `src/data/graph_builder.py`) |
| Gene features | degree over non-label relations |

## ID mappings and contradictions
* All indication / contraindication / off-label endpoints resolve to node IDs (0 unresolved; `primekg_provenance.json`).
* Contradictory pairs in PrimeKG: indication ∩ contraindication **87**, indication ∩ off-label **125**, contraindication ∩ off-label **37**.
  Handling: an indication stays a positive label. Held-out (validation, CV-validation and holdout) indication pairs are removed from the
  contraindication / off-label graph edges in both directions; training positives that are also contraindication/off-label edges remain in the
  graph (≤212 pairs; a small training-time shortcut, not a held-out leak). Negatives never include any known pair of any relation.
* Disease mapping quality of positives (historical manifest): ~67% `mapped`, the rest partial / ambiguous / unmapped-no-DOID (grouped MONDO IDs).
  This affects interpretation (some "diseases" are grouped concepts), not leakage.

## Negative sampling (finding)
Hard negatives = drug uniform over the partition's positive drugs × disease uniform over the partition's **unique** positive diseases. Positives are
frequency-weighted, so popular diseases are over-represented among positives: disease popularity alone reaches ROC-AUC 0.65-0.68 and
a degree-only model 0.71-0.77. To measure the effect, the final protocol adds a **popularity-matched** negative set (drug and disease drawn from the
positive pairs' marginals). On the locked holdout the selected model drops from AUC 0.907 (hard) to 0.860 (popularity-matched); the popularity-only
baseline drops to 0.53 (chance). Sampled negatives are unlabelled pairs, never confirmed non-indications.

## Integrity checks performed
| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Validation/test/holdout positives absent from message-passing edges | PASS | 42/42 historical + 130/130 final-protocol `leakage_audit.json` |
| 2 | Reverse edges cannot leak | PASS | audits check forward and reverse of treats / contraindication / off-label |
| 3 | Negatives are not known pairs of any relation | PASS | audits; split manifests `negatives_in_known_pairs = 0`; `tests/test_final_protocol.py` |
| 4 | Drug-disjointness | PASS | split asserts, audits, tests (CV folds partition the 1,440 development drugs; holdout 361 drugs disjoint) |
| 5 | Features use no held-out labels | PASS | fingerprints; degrees exclude label relations; GBM label features from training positives only |
| 6 | Disease-profile features train-only | PASS, with a defect fixed | `tests/test_disease_profile.py`; the historical leave-one-out construction creates a train/test shift (see `LEAKAGE_AUDIT.md`) - replaced by drug-cross-fitting for all new baselines and the deployed GBM |
| 7 | Degree features exclude target relations | PASS | `graph_builder.LABEL_RELATIONS` |
| 8 | Duplicates / contradictions handled explicitly | PASS | see above |
| 9 | Reproducible from saved artifacts | PASS, with a finding | frozen data hashes verified on two machines; **regenerating** the final protocol on Colab produced different arrays (library versions), so the exact files are committed and copied with SHA-256 checks |
| 10 | Inference uses the training transformations | PASS | `tests/test_serving.py` parity (GBM to 1e-9 on the same pairs; GCN CPU vs GPU ≤ 9e-7, identical AUC) |

## Residual side information
Kept in the graph by design (non-target relations of held-out drugs): historical split 7,730 contraindication + 704 off-label edges of
validation/test drugs; final protocol 4,792 + 464 edges of holdout drugs (196 of 361 holdout drugs have at least one). Their source and effect are
analysed in `LEAKAGE_AUDIT.md`.
