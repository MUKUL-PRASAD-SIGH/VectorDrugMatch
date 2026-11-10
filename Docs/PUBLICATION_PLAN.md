# Publication plan and status

## Status (read first)
* Commits 1-29 below were **pushed on 2026-11-11** to `origin/mukul` (fast-forward `b05a6ff..59b05d5`) and merged into `origin/main` (merge commit `308d009`, clean, no force, no rebase) after your message "approve push to origin/mukul THEN MERGE TO MAIN". The repository is **public**.
* Commit 30 (`--coldstart-only`) and the commit that re-pins the notebook and updates the docs are **local only**. **Nothing further has been pushed. A second push needs your separate approval.** It would be `git push origin mukul` (fast-forward) and, if you want it, `git push origin main` after a merge.

## What can and cannot be reorganised
History is preserved as instructed. Commits are published as they are; several are small "re-pin / refresh manifest" commits needed to keep the notebook pin consistent with the data manifest.

## All commits since the previous `origin/mukul` (`b05a6ff`), oldest first
| # | commit | subject | file changes | state |
|---|---|---|---|---|
| 1 | `ad2b215` | Ignore data/external/downloads; track HAI/Open Targets/IHME download manifest | 2 files changed, 31 insertions(+) | pushed |
| 2 | `fc5a67e` | Add Open Targets indication loader and validator (separate from the PrimeKG benchmark) | 2 files changed, 412 insertions(+) | pushed |
| 3 | `323b590` | Add IEEE-format paper draft, reproducible figures and metrics.json | 17 files changed, 595 insertions(+) | pushed |
| 4 | `204f91b` | Paper: add in-text citations, verified bibliography, citation audit and paper checks | 5 files changed, 177 insertions(+), 21 deletions(-) | pushed |
| 5 | `afd03fc` | Data/pipeline layer: variants, NTD mapping, HAI parser, equity features, results package, readiness report | 18 files changed, 2594 insertions(+), 1 deletion(-) | pushed |
| 6 | `c742a7d` | Orchestrator: separate required vs optional external steps (inputs only the user can supply) | 3 files changed, 50 insertions(+), 40 deletions(-) | pushed |
| 7 | `a95798d` | Add colab_final_run.ipynb: final Colab run driven by run_full_pipeline.py, pinned to c742a7d | 1 file changed, 237 insertions(+) | pushed |
| 8 | `c3deddc` | Source audit: official WHO NTD groupings, Open Targets licence/provenance, evidence log | 13 files changed, 520 insertions(+), 19 deletions(-) | pushed |
| 9 | `3586a3c` | Re-pin colab_final_run.ipynb to c3deddc (includes the WHO reconciliation outputs) | 1 file changed, 2 insertions(+), 2 deletions(-) | pushed |
| 10 | `aec76c1` | Final preparation pass: EML extraction, OT release/source attribution, licence audit, explainability, fixes | 35 files changed, 2115 insertions(+), 242 deletions(-) | pushed |
| 11 | `8ea7f49` | Pin colab_final_run.ipynb to aec76c1; regenerate final readiness documents | 2 files changed, 37 insertions(+), 9 deletions(-) | pushed |
| 12 | `b4d6c39` | EML status: separate confirmed positives, unresolved and no-candidate zeros; regenerate docs | 11 files changed, 44 insertions(+), 27 deletions(-) | pushed |
| 13 | `632b537` | Re-pin colab_final_run.ipynb to b4d6c39 | 2 files changed, 4 insertions(+), 4 deletions(-) | pushed |
| 14 | `a745cd3` | EML: classifier module + tests, synonym fixes, unmapped reasons, denominators in equity report | 11 files changed, 186 insertions(+), 50 deletions(-) | pushed |
| 15 | `94261bc` | Re-pin colab_final_run.ipynb to a745cd3 | 2 files changed, 4 insertions(+), 4 deletions(-) | pushed |
| 16 | `6550e62` | Refresh candidate release manifest after EML/equity rebuild | 1 file changed, 23 insertions(+), 23 deletions(-) | pushed |
| 17 | `d26a77f` | Optional leak-free disease-profile baseline variant (configs *_dp, tests); EML co-pack and footnote-mark extraction fixes; docs | 25 files changed, 396 insertions(+), 75 deletions(-) | pushed |
| 18 | `5cf428f` | Re-pin colab_final_run.ipynb to d26a77f; refresh manifest | 3 files changed, 11 insertions(+), 11 deletions(-) | pushed |
| 19 | `4384957` | requirements: declare markdown and joblib | 1 file changed, 2 insertions(+) | pushed |
| 20 | `9784375` | Final handoff document; refresh readiness docs and manifest | 5 files changed, 175 insertions(+), 7 deletions(-) | pushed |
| 21 | `7e70d3c` | IHME GBD 2023 export processed (15/22 groups); equity/NDPI rebuilt with burden-aware subset sensitivity; docs and paper updated | 13 files changed, 183 insertions(+), 121 deletions(-) | pushed |
| 22 | `ff9b1b1` | Re-pin colab_final_run.ipynb to 7e70d3c; refresh manifest and handoff | 4 files changed, 36 insertions(+), 18 deletions(-) | pushed |
| 23 | `cb41c44` | Do not republish IHME values in tracked docs/scripts (public repo); examples masked | 5 files changed, 25 insertions(+), 23 deletions(-) | pushed |
| 24 | `956c9a9` | Colab training handoff; notebook Step 3/4b (frozen-data check); refreshed manifest | 5 files changed, 192 insertions(+), 20 deletions(-) | pushed |
| 25 | `67b23f7` | feat(pipeline): resumable per-model training and merged comparison tables | 5 files changed, 112 insertions(+), 8 deletions(-) | pushed |
| 26 | `b87801a` | docs(readme): rewrite README to match the actual project (benchmark, models, leakage controls, NDPI limits) | 1 file changed, 109 insertions(+), 392 deletions(-) | pushed |
| 27 | `eb8a9f5` | docs(release): release audit (secrets, personal data, DrugBank blobs in history) and scrub a local path | 2 files changed, 49 insertions(+), 1 deletion(-) | pushed |
| 28 | `f4ecebe` | docs(colab): beginner handbook, training handoff (resume, CV/calibration analysis) and publication plan | 3 files changed, 258 insertions(+), 28 deletions(-) | pushed |
| 29 | `59b05d5` | feat(colab): Drive-persistent outputs, environment record and resume in the final notebook; re-pin to b87801a | 4 files changed, 55 insertions(+), 17 deletions(-) | pushed |
| 30 | `6008aed` | feat(baselines): opt-in --coldstart-only (skip pooled CV and pooled all-data model); used by the final pipeline | 3 files changed, 35 insertions(+), 9 deletions(-) | LOCAL ONLY |

## Files changed per commit (name-status; first 12 files per commit)
**1. `ad2b215` Ignore data/external/downloads; track HAI/Open Targets/IHME download manifest**

```
M	.gitignore
A	Docs/HAI_DOWNLOAD_MANIFEST.md
```

**2. `fc5a67e` Add Open Targets indication loader and validator (separate from the PrimeKG benchmark)**

```
A	scripts/open_targets_indications.py
A	scripts/validate_open_targets.py
```

**3. `323b590` Add IEEE-format paper draft, reproducible figures and metrics.json**

```
A	Docs/paper/PAPER_DRAFT_IEEE.md
A	Docs/paper/figures/fig1_split_composition.pdf
A	Docs/paper/figures/fig1_split_composition.png
A	Docs/paper/figures/fig2_disease_mapping.pdf
A	Docs/paper/figures/fig2_disease_mapping.png
A	Docs/paper/figures/fig3_structure_shortcut.pdf
A	Docs/paper/figures/fig3_structure_shortcut.png
A	Docs/paper/figures/fig4_ntd_coverage.pdf
A	Docs/paper/figures/fig4_ntd_coverage.png
A	Docs/paper/figures/fig5_graph_relations.pdf
A	Docs/paper/figures/fig5_graph_relations.png
A	Docs/paper/figures/fig6_open_targets_funnel.pdf
... and 5 more files
```

**4. `204f91b` Paper: add in-text citations, verified bibliography, citation audit and paper checks**

```
M	.gitignore
A	Docs/paper/CITATION_AUDIT.md
M	Docs/paper/PAPER_DRAFT_IEEE.md
A	scripts/check_paper.py
A	scripts/render_paper.py
```

**5. `afd03fc` Data/pipeline layer: variants, NTD mapping, HAI parser, equity features, results package, readiness report**

```
A	Docs/DATA_AND_PIPELINE_READINESS.md
A	Docs/DATA_DICTIONARY.md
A	Docs/EQUITY_DATA_SPECS.md
M	Docs/HAI_DOWNLOAD_MANIFEST.md
A	Docs/release/vdm_v1_candidate_manifest.json
A	configs/primekg_morgan_structcov.yaml
A	scripts/audit_models.py
A	scripts/build_equity_features.py
A	scripts/build_ntd_mapping.py
A	scripts/freeze_release.py
A	scripts/make_readiness_report.py
A	scripts/make_results_package.py
... and 6 more files
```

**6. `c742a7d` Orchestrator: separate required vs optional external steps (inputs only the user can supply)**

```
M	Docs/DATA_AND_PIPELINE_READINESS.md
M	scripts/make_readiness_report.py
M	scripts/run_full_pipeline.py
```

**7. `a95798d` Add colab_final_run.ipynb: final Colab run driven by run_full_pipeline.py, pinned to c742a7d**

```
A	notebooks/colab_final_run.ipynb
```

**8. `c3deddc` Source audit: official WHO NTD groupings, Open Targets licence/provenance, evidence log**

```
M	Docs/DATA_AND_PIPELINE_READINESS.md
M	Docs/DATA_DICTIONARY.md
A	Docs/LICENCE_AUDIT.md
A	Docs/NTD_MAPPING.md
A	Docs/OPEN_TARGETS_PROVENANCE.md
M	Docs/paper/CITATION_AUDIT.md
M	Docs/paper/PAPER_DRAFT_IEEE.md
M	Docs/release/vdm_v1_candidate_manifest.json
A	Docs/source_evidence/fetch_log_2026-11-10.json
A	Docs/source_evidence/ot_licence_table_2026-11-10.csv
M	scripts/build_ntd_mapping.py
M	scripts/make_readiness_report.py
... and 1 more files
```

**9. `3586a3c` Re-pin colab_final_run.ipynb to c3deddc (includes the WHO reconciliation outputs)**

```
M	notebooks/colab_final_run.ipynb
```

**10. `aec76c1` Final preparation pass: EML extraction, OT release/source attribution, licence audit, explainability, fixes**

```
M	Docs/DATA_AND_PIPELINE_READINESS.md
M	Docs/DATA_DICTIONARY.md
A	Docs/DATA_PROVENANCE.md
M	Docs/EQUITY_DATA_SPECS.md
A	Docs/FINAL_RELEASE_READINESS.md
A	Docs/HAI_AUDIT.md
A	Docs/HUMAN_ACTION_CHECKLIST.md
M	Docs/LICENCE_AUDIT.md
M	Docs/OPEN_TARGETS_PROVENANCE.md
M	Docs/paper/PAPER_DRAFT_IEEE.md
M	Docs/release/vdm_v1_candidate_manifest.json
M	Docs/source_evidence/fetch_log_2026-11-10.json
... and 23 more files
```

**11. `8ea7f49` Pin colab_final_run.ipynb to aec76c1; regenerate final readiness documents**

```
M	Docs/FINAL_RELEASE_READINESS.md
M	notebooks/colab_final_run.ipynb
```

**12. `b4d6c39` EML status: separate confirmed positives, unresolved and no-candidate zeros; regenerate docs**

```
M	Docs/DATA_AND_PIPELINE_READINESS.md
M	Docs/DATA_DICTIONARY.md
M	Docs/DATA_PROVENANCE.md
M	Docs/EQUITY_DATA_SPECS.md
M	Docs/FINAL_RELEASE_READINESS.md
M	Docs/HUMAN_ACTION_CHECKLIST.md
M	Docs/LICENCE_AUDIT.md
M	Docs/OPEN_TARGETS_PROVENANCE.md
M	scripts/build_equity_features.py
M	scripts/make_final_docs.py
M	scripts/make_readiness_report.py
```

**13. `632b537` Re-pin colab_final_run.ipynb to b4d6c39**

```
M	Docs/FINAL_RELEASE_READINESS.md
M	notebooks/colab_final_run.ipynb
```

**14. `a745cd3` EML: classifier module + tests, synonym fixes, unmapped reasons, denominators in equity report**

```
M	Docs/DATA_AND_PIPELINE_READINESS.md
M	Docs/DATA_DICTIONARY.md
M	Docs/DATA_PROVENANCE.md
M	Docs/EQUITY_DATA_SPECS.md
M	Docs/FINAL_RELEASE_READINESS.md
M	Docs/paper/PAPER_DRAFT_IEEE.md
M	scripts/build_equity_features.py
M	scripts/make_readiness_report.py
M	scripts/process_who_eml.py
A	src/scoring/eml_status.py
A	tests/test_eml_status.py
```

**15. `94261bc` Re-pin colab_final_run.ipynb to a745cd3**

```
M	Docs/FINAL_RELEASE_READINESS.md
M	notebooks/colab_final_run.ipynb
```

**16. `6550e62` Refresh candidate release manifest after EML/equity rebuild**

```
M	Docs/release/vdm_v1_candidate_manifest.json
```

**17. `d26a77f` Optional leak-free disease-profile baseline variant (configs *_dp, tests); EML co-pack and footnote-mark extraction fixes; docs**

```
M	Docs/DATA_AND_PIPELINE_READINESS.md
M	Docs/DATA_DICTIONARY.md
M	Docs/DATA_PROVENANCE.md
A	Docs/EML_EXTRACTION_CORRECTIONS.md
M	Docs/EQUITY_DATA_SPECS.md
M	Docs/FINAL_RELEASE_READINESS.md
M	Docs/HUMAN_ACTION_CHECKLIST.md
M	Docs/paper/PAPER_DRAFT_IEEE.md
M	Docs/release/vdm_v1_candidate_manifest.json
A	configs/primekg_morgan_dp.yaml
A	configs/primekg_morgan_structcov_dp.yaml
M	scripts/evaluate_primekg.py
... and 13 more files
```

**18. `5cf428f` Re-pin colab_final_run.ipynb to d26a77f; refresh manifest**

```
M	Docs/FINAL_RELEASE_READINESS.md
M	Docs/release/vdm_v1_candidate_manifest.json
M	notebooks/colab_final_run.ipynb
```

**19. `4384957` requirements: declare markdown and joblib**

```
M	requirements.txt
```

**20. `9784375` Final handoff document; refresh readiness docs and manifest**

```
M	Docs/DATA_AND_PIPELINE_READINESS.md
A	Docs/FINAL_PROJECT_HANDOFF.md
M	Docs/FINAL_RELEASE_READINESS.md
M	Docs/release/vdm_v1_candidate_manifest.json
M	notebooks/colab_final_run.ipynb
```

**21. `7e70d3c` IHME GBD 2023 export processed (15/22 groups); equity/NDPI rebuilt with burden-aware subset sensitivity; docs and paper updated**

```
M	Docs/DATA_AND_PIPELINE_READINESS.md
M	Docs/DATA_DICTIONARY.md
M	Docs/DATA_PROVENANCE.md
M	Docs/EQUITY_DATA_SPECS.md
M	Docs/FINAL_PROJECT_HANDOFF.md
M	Docs/FINAL_RELEASE_READINESS.md
M	Docs/HUMAN_ACTION_CHECKLIST.md
M	Docs/paper/PAPER_DRAFT_IEEE.md
M	scripts/build_equity_features.py
M	scripts/make_final_docs.py
M	scripts/make_readiness_report.py
M	scripts/process_ihme_daly.py
... and 1 more files
```

**22. `ff9b1b1` Re-pin colab_final_run.ipynb to 7e70d3c; refresh manifest and handoff**

```
M	Docs/FINAL_PROJECT_HANDOFF.md
M	Docs/FINAL_RELEASE_READINESS.md
M	Docs/release/vdm_v1_candidate_manifest.json
M	notebooks/colab_final_run.ipynb
```

**23. `cb41c44` Do not republish IHME values in tracked docs/scripts (public repo); examples masked**

```
M	Docs/DATA_AND_PIPELINE_READINESS.md
M	Docs/DATA_DICTIONARY.md
M	Docs/FINAL_RELEASE_READINESS.md
M	scripts/make_readiness_report.py
M	scripts/process_ihme_daly.py
```

**24. `956c9a9` Colab training handoff; notebook Step 3/4b (frozen-data check); refreshed manifest**

```
A	Docs/COLAB_TRAINING_HANDOFF.md
M	Docs/FINAL_PROJECT_HANDOFF.md
M	Docs/FINAL_RELEASE_READINESS.md
M	Docs/release/vdm_v1_candidate_manifest.json
M	notebooks/colab_final_run.ipynb
```

**25. `67b23f7` feat(pipeline): resumable per-model training and merged comparison tables**

```
M	scripts/run_full_pipeline.py
M	scripts/train_baselines.py
M	scripts/train_gnn.py
A	src/utils/results_io.py
A	tests/test_resume_and_merge.py
```

**26. `b87801a` docs(readme): rewrite README to match the actual project (benchmark, models, leakage controls, NDPI limits)**

```
M	README.md
```

**27. `eb8a9f5` docs(release): release audit (secrets, personal data, DrugBank blobs in history) and scrub a local path**

```
M	Docs/COLAB_PLAYBOOK.md
A	Docs/RELEASE_AUDIT.md
```

**28. `f4ecebe` docs(colab): beginner handbook, training handoff (resume, CV/calibration analysis) and publication plan**

```
A	Docs/COLAB_BEGINNER_HANDBOOK.md
M	Docs/COLAB_TRAINING_HANDOFF.md
A	Docs/PUBLICATION_PLAN.md
```

**29. `59b05d5` feat(colab): Drive-persistent outputs, environment record and resume in the final notebook; re-pin to b87801a**

```
M	Docs/DATA_AND_PIPELINE_READINESS.md
M	Docs/FINAL_RELEASE_READINESS.md
M	Docs/release/vdm_v1_candidate_manifest.json
M	notebooks/colab_final_run.ipynb
```

**30. `6008aed` feat(baselines): opt-in --coldstart-only (skip pooled CV and pooled all-data model); used by the final pipeline**

```
M	scripts/run_full_pipeline.py
M	scripts/train_baselines.py
M	tests/test_resume_and_merge.py
```

## What is public after the first push, and what the pending commits add
Already public: source code, tests, configs, documentation, the paper draft and 7 figures (aggregate counts), the release manifest (file names, sizes, SHA-256 of local data, no data), the notebook at the old pin. The pending commits add: the `--coldstart-only` flag (code), the re-pinned notebook and updated handoff/handbook text. No data. **Not public (never committed):** datasets, IHME values, the WHO EML list, Open Targets tables, DrugBank files, checkpoints, outputs, keys. Already public and unchanged: the three DrugBank-derived blobs in `origin/mukul` history (`Docs/RELEASE_AUDIT.md` section 4); commit author names and e-mail addresses are part of the history; `main` now also contains that history.

## Honest mapping to the logical stages
Present: data ingestion/provenance, preprocessing and validation, features, graph construction, classical baselines, Node2Vec, GNNs, drug-disjoint evaluation and leakage prevention, disease-profile variant, ablations, explainability, NTD/EML/HAI/IHME evidence with NDPI and sensitivity, tests, paper, documentation, Colab notebook. **No commit exists for "API and application components"**: the repository contains no API or front-end code (only the design note `Docs/API.md`).

## Open decisions (none blocks training)
Code licence file; whether team names stay in `MASTER_PLAN.md`/`CONTRIBUTING.md`; DrugBank blobs in history; the legal questions in `Docs/LICENCE_AUDIT.md`.
