# Final release readiness

Generated 2026-11-11 02:40 by `scripts/make_final_docs.py`. Statuses: DONE AND VALIDATED, IMPLEMENTED BUT NOT VALIDATED, BLOCKED ON MY INPUT, NOT STARTED, NOT APPLICABLE.

## Task registry
| area | task | status | evidence / note |
|---|---|---|---|
| PrimeKG | Full benchmark built (7,957 drugs, 17,080 diseases, 9,388 indications) and leakage-validated | DONE AND VALIDATED | validate_primekg_dataset.py: all hard checks passed |
| PrimeKG | Drug-disjoint split; held-out and reverse-edge leakage checks | DONE AND VALIDATED | same validator; message-passing graph has 0 treats edges |
| PrimeKG | Negatives audited (sampled only; none curated; no negative is a known indication/contraindication/off-label pair) | DONE AND VALIDATED | split manifest negatives_in_known_pairs = 0 |
| PrimeKG | Structure-covered variant built with its own validation | DONE AND VALIDATED | make_structure_covered_variant.py built-in checks; loaders audited |
| PrimeKG | SMILES / fingerprint coverage and zero-fingerprint handling documented | DONE AND VALIDATED | 996 no SMILES, 997 zero fingerprints; with/no_structure subsets |
| PrimeKG | Disease representation for classical baselines: optional leak-free disease-profile variant (configs/*_dp.yaml) | IMPLEMENTED BUT NOT VALIDATED | tests/test_disease_profile.py (8 passed incl. real-split identity); no model trained; effect on results unknown until Colab |
| NTD | Official WHO list read directly (21 groupings, 25 fact sheets) | DONE AND VALIDATED | evidence log; build_ntd_mapping.py asserts |
| NTD | Reconciliation with the 22 frozen groups; frozen labels unchanged | DONE AND VALIDATED | ntd_group_reconciliation.csv; flag nodes 68 = union of groups |
| NTD | Nested-root / double-counting audit | DONE AND VALIDATED | ntd_group_overlaps.csv: 2 overlaps; 85 vs 82 unique pairs |
| NTD | Candidate extensions kept separate from the frozen flag | DONE AND VALIDATED | scope column in ntd_disease_mapping.csv |
| HAI | Raw preserved, parsed and numerically audited | DONE AND VALIDATED | audit_hai_parsing.py: 0 FAIL, 3 documented WARN |
| HAI | Medicine -> DrugBank mapping tiers (55/60; 5 unmapped combinations/biologic-like) | DONE AND VALIDATED | hai_medicines.csv |
| Open Targets | Release identified (26.09) by byte identity; same-release files obtained | DONE AND VALIDATED | SHA-256 equality in evidence log |
| Open Targets | Every report reference attributed to a provider/source | DONE AND VALIDATED | 100% of 321,785 references resolved |
| Open Targets | Mapping coverage, tiers and loader validation | DONE AND VALIDATED | validate_open_targets.py all hard checks passed |
| Open Targets | Quality-flag (UNVALIDATED_INDICATION) semantics | IMPLEMENTED BUT NOT VALIDATED | filter implemented; meaning unresolved (H9) |
| Open Targets | Independent external-validation claim | NOT APPLICABLE | no independence claim is made |
| Licensing | Source-by-source audit with evidence log | DONE AND VALIDATED | 29 pages hashed; statuses VERIFIED / PARTIAL / NOT VERIFIED |
| Licensing | Legal conclusions (ShareAlike, CC0 over NC constituents, redistribution) | BLOCKED ON MY INPUT | legal judgement: H5/H6 |
| Licensing | Git history inspected for DrugBank-derived files | DONE AND VALIDATED | 3 blobs, 2 commits, on origin/mukul |
| Models | Baseline implementations audited statically; defects fixed | DONE AND VALIDATED | cold-start checkpoints now saved; SHAP class slice; seeds documented |
| Models | GNN implementations audited; eval-mode dropout bug fixed; regression tests | DONE AND VALIDATED | tests/test_gnn_eval_determinism.py (5 passed) |
| Models | Loaders / splits consistent across all models | DONE AND VALIDATED | audit_models.py loaders + validator |
| Models | Cold-start ablation script | IMPLEMENTED BUT NOT VALIDATED | compiles; not run |
| Models | Results exporter (tables + figures) | IMPLEMENTED BUT NOT VALIDATED | run on one real baseline file only; multi-model / GNN figures untested |
| Models | Explainability (SHAP trees, GNNExplainer) | IMPLEMENTED BUT NOT VALIDATED | synthetic API tests pass (tests/test_explainability.py); real models need Colab |
| Models | Trained-model performance | NOT STARTED | Colab by design |
| Equity | IHME file inspected | DONE AND VALIDATED | 17 causes, one row each, DALYs/Rate/Global/Both/All ages/2023, no missing values; ZIP and CSV hashes match |
| Equity | IHME DALY processing | DONE AND VALIDATED | process_ihme_daly.py: 15 groups complete, 7 missing; mapping reconciliation documented; unit of 'Rate' not verified against IHME documentation |
| Equity | WHO EML extracted from the official PDF and mapped | IMPLEMENTED BUT NOT VALIDATED | automated structure checks + tests only; NOT manually validated entry by entry (spot checks on a few entries only); corrections in Docs/EML_EXTRACTION_CORRECTIONS.md |
| Equity | Equity table + NDPI code | DONE AND VALIDATED | EML + HAI + DALY; burden-aware only for 50 NTD pairs (DALY missing for 32 NTD pairs and all non-NTD pairs); missing never 0 (tests) |
| Equity | NDPI evaluation and sensitivity | IMPLEMENTED BUT NOT VALIDATED | computed on real EML + HAI + DALY inputs; weights are an unvalidated proposal; on 49 burden-aware pairs the ranking is weight-sensitive (Spearman -0.42 to 0.87 median); NDPI has no external validation |
| Paper | Bibliography metadata verified (15 references) | DONE AND VALIDATED | Crossref / arXiv / WHO page |
| Paper | Claim-to-reference support | IMPLEMENTED BUT NOT VALIDATED | abstract/documentation-level; full text pending (H7) |
| Paper | Structure, citation order, figures, tables, numbers vs metrics.json | DONE AND VALIDATED | scripts/check_paper.py passed |
| Paper | Results, ablation and NDPI sections | NOT STARTED | need Colab results and H1 |
| Release | Clean-clone check (compile, paths, imports) | DONE AND VALIDATED | 75 files compile; 24 referenced paths exist; imports ok |
| Release | Dependencies documented | IMPLEMENTED BUT NOT VALIDATED | requirements.txt completed; local versions recorded; Colab versions recorded at run time (not pinned) |
| Release | Commits, notebook pin and release manifest reconciled | DONE AND VALIDATED | see section 3 below |
| Release | Push to GitHub | BLOCKED ON MY INPUT | H3 |

Counts: {'DONE AND VALIDATED': 26, 'IMPLEMENTED BUT NOT VALIDATED': 9, 'BLOCKED ON MY INPUT': 2, 'NOT STARTED': 2, 'NOT APPLICABLE': 1}.

## Questions answered explicitly
**A. Percentage complete and how it was calculated.** 66.7% of applicable preparation tasks are DONE AND VALIDATED (26 of 39; NOT APPLICABLE items excluded); 89.7% are at least implemented. Method: equal weighting of the 40 registry tasks above, so the figure is crude. It excludes Colab results and the paper's results sections by design, and a high percentage does **not** mean the research is finished.

**B. Datasets.** Complete: PrimeKG full benchmark, structure-covered variant, NTD mapping tables, HAI tables (regional pilot), Open Targets tables (with provenance), WHO EML flags. IHME DALY export (15 of 22 NTD groups). Incomplete by nature: burden exists for 50 of 82 NTD pairs only; seven groups have no GBD cause.

**C. Mappings.** Complete: WHO->MONDO->PrimeKG (with documented differences, nested roots and 6 WHO entries without indications); Open Targets drug (tier 1: 5,494 ChEMBL ids) and disease mapping; HAI medicines 55/60; EML 497/590 single entries. Ambiguous or missing: 93 EML single entries unmapped; 5 HAI medicines unmapped; ~470 Open Targets disease ids without a MONDO xref and 479 phenotype/GO ids; MONDO->DOID unmapped for 9,089 PrimeKG disease nodes.

**D. Scripts implemented and validated.** Validated: dataset build/split/validation, structure variant, NTD mapping, HAI parser + audit, Open Targets loader/validator/attribution, EML extraction + tests, GNN determinism tests, explainability API tests (synthetic), paper checks, freeze/verify, clean-clone check. Implemented but not validated on real trained models: training scripts for Node2Vec and the five GNNs on GPU, cold-start ablation, results exporter beyond one baseline, explanation CLI.

**E. Paper tables and figures the final pipeline can generate** (from actual outputs): dataset statistics, split statistics, model comparison, cold-start metrics, ablation, structure sensitivity, NTD-specific performance, NDPI prioritisation and equity coverage (needs DALY for a meaningful NDPI), ROC/PR, confusion matrices, calibration, training curves, embedding PCA, SHAP and GNN-explanation tables. Figures 1-7 already exist from real data. **Not yet generated by any script:** a drug-disease candidate network figure, a molecular-feature analysis figure, an NDPI ranking figure and an equity-component contribution figure (they need DALY/EML-based NDPI and, for the network, final model outputs); no synthetic figure is presented as a result.

**F. Unresolved issues.** `Docs/DATA_AND_PIPELINE_READINESS.md` section 6 lists 24; the main ones: burden missing for 7 NTD groups and for all non-NTD pairs; weight-sensitivity of NDPI; the effect of the disease-profile baseline variant (known only after Colab); legal questions (`Docs/LICENCE_AUDIT.md` section 4); Open Targets flag semantics; small NTD test set (15 positives); full-text reference checks; unvalidated trained behaviour.

**G. What you must provide or approve.** See `Docs/HUMAN_ACTION_CHECKLIST.md`: H3 (push approval), H4 (Drive upload), H5-H7 before release/submission.

**H. Is human-dependent work still pending?** Not for the preparation phase (H1, H2 done); H3-H4 at Colab time; H5-H7 before release/submission.

**I. Can you freeze and move to Colab?** Yes, once H3 (push) and H4 (Drive upload) are done. The IHME data are in place; the NDPI is burden-aware for 50 NTD pairs only.

**J. Single next action.** Approve the push (**H3**) and upload the git-ignored inputs to Drive (**H4**), then run the Colab notebook.

## Colab commands (do not run yet; the notebook `notebooks/colab_final_run.ipynb` contains them)
```
!git clone https://github.com/MUKUL-PRASAD-SIGH/VectorDrugMatch && %cd VectorDrugMatch && git checkout <pinned SHA>
!pip install -q rdkit mlflow optuna shap xgboost lightgbm loguru pyyaml torch-geometric tabulate scikit-learn lxml matplotlib pymupdf pyarrow
!pip install -q pyg_lib torch_scatter torch_sparse torch_cluster -f https://data.pyg.org/whl/torch-<torch>+cu<cuda>.html
!python scripts/run_full_pipeline.py --stage prepare
!python scripts/run_full_pipeline.py --stage external
!python scripts/run_full_pipeline.py --stage smoke
!python scripts/run_full_pipeline.py --stage train --variant full
!python scripts/run_full_pipeline.py --stage report --variant full
!python scripts/run_full_pipeline.py --stage explain --variant full
!python scripts/run_full_pipeline.py --stage train --variant structcov
!python scripts/run_full_pipeline.py --stage report --variant structcov
!python scripts/freeze_release.py --tag vdm_v1
```

## 3. Commit / pin / manifest reconciliation (state at generation)
HEAD `f4ecebe5d0`; local commits ahead of `origin/mukul`: 28; working tree has uncommitted changes. The notebook pins code commit `b87801a4f5`. Test: after the pinned commit only `notebooks/` and `Docs/` may change. Result: **PASS**. The release manifest `Docs/release/vdm_v1_candidate_manifest.json` records the data checksums, versions and the commit at freeze time; rename it `vdm_v1` after H1 data arrive.

## Final Colab-readiness gate
| gate | status |
|---|---|
| required raw/processed datasets exist locally | yes |
| mandatory mappings validated | yes |
| both benchmark variants reproducible (config + split files + scripts) | yes |
| model, evaluation, ablation, exporter, explainability scripts implemented | yes (see D) |
| configurations consistent | yes (two configs: full and structcov) |
| dependencies documented | partly (versions pinned only as validated-local; Colab recorded at run time) |
| paths work in a clean clone | yes (clean-clone check) |
| no untracked local-only dependency silently required | the external stage needs Drive uploads (H4) and says so |
| no restricted raw data in git | yes (`data/` ignored; DrugBank-derived blobs remain in history: H5) |
| notebook pins a commit containing all code | yes; it can only be cloned on Colab after the push (H3) |
