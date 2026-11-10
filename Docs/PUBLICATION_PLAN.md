# Publication plan (nothing has been pushed; awaiting your approval)

## Destination
* Remote `origin` = `https://github.com/MUKUL-PRASAD-SIGH/VectorDrugMatch` (**public**), branch **`mukul`**.
* Command that would be run after your approval: `git push origin mukul` (a plain fast-forward: `origin/mukul` is an ancestor of HEAD; **no force, no rebase, no amend, no reset**). Nothing is pushed to `main`, `master` or the `feat/` branches. Merging `mukul` into `main` (a pull request) is a separate decision.

## What cannot be reorganised, and what can
Git history is preserved as you instructed. The 26 unpushed commits below already exist locally; re-splitting them would require rewriting history, so they are published **as they are**. Several are small "re-pin / refresh manifest" commits that were needed to keep the notebook pin consistent. The commits made in this session (marked NEW) are separate, focused commits.

## Commits that would be published (oldest first)
| # | commit | message |
|---|---|---|
| 1 | `ad2b215` | Ignore data/external/downloads; track HAI/Open Targets/IHME download manifest |
| 2 | `fc5a67e` | Add Open Targets indication loader and validator (separate from the PrimeKG benchmark) |
| 3 | `323b590` | Add IEEE-format paper draft, reproducible figures and metrics.json |
| 4 | `204f91b` | Paper: add in-text citations, verified bibliography, citation audit and paper checks |
| 5 | `afd03fc` | Data/pipeline layer: variants, NTD mapping, HAI parser, equity features, results package, readiness report |
| 6 | `c742a7d` | Orchestrator: separate required vs optional external steps (inputs only the user can supply) |
| 7 | `a95798d` | Add colab_final_run.ipynb: final Colab run driven by run_full_pipeline.py, pinned to c742a7d |
| 8 | `c3deddc` | Source audit: official WHO NTD groupings, Open Targets licence/provenance, evidence log |
| 9 | `3586a3c` | Re-pin colab_final_run.ipynb to c3deddc (includes the WHO reconciliation outputs) |
| 10 | `aec76c1` | Final preparation pass: EML extraction, OT release/source attribution, licence audit, explainability, fixes |
| 11 | `8ea7f49` | Pin colab_final_run.ipynb to aec76c1; regenerate final readiness documents |
| 12 | `b4d6c39` | EML status: separate confirmed positives, unresolved and no-candidate zeros; regenerate docs |
| 13 | `632b537` | Re-pin colab_final_run.ipynb to b4d6c39 |
| 14 | `a745cd3` | EML: classifier module + tests, synonym fixes, unmapped reasons, denominators in equity report |
| 15 | `94261bc` | Re-pin colab_final_run.ipynb to a745cd3 |
| 16 | `6550e62` | Refresh candidate release manifest after EML/equity rebuild |
| 17 | `d26a77f` | Optional leak-free disease-profile baseline variant (configs *_dp, tests); EML co-pack and footnote-mark extraction fixe |
| 18 | `5cf428f` | Re-pin colab_final_run.ipynb to d26a77f; refresh manifest |
| 19 | `4384957` | requirements: declare markdown and joblib |
| 20 | `9784375` | Final handoff document; refresh readiness docs and manifest |
| 21 | `7e70d3c` | IHME GBD 2023 export processed (15/22 groups); equity/NDPI rebuilt with burden-aware subset sensitivity; docs and paper  |
| 22 | `ff9b1b1` | Re-pin colab_final_run.ipynb to 7e70d3c; refresh manifest and handoff |
| 23 | `cb41c44` | Do not republish IHME values in tracked docs/scripts (public repo); examples masked |
| 24 | `956c9a9` | Colab training handoff; notebook Step 3/4b (frozen-data check); refreshed manifest |
| 25 | `67b23f7` | feat(pipeline): resumable per-model training and merged comparison tables |
| 26 | `b87801a` | docs(readme): rewrite README to match the actual project (benchmark, models, leakage controls, NDPI limits) |

The first table was generated before the last three commits of this release pass existed; the authoritative list is always `git log --oneline origin/mukul..HEAD`.

## NEW focused commits made in this release pass (in addition to the table above where already listed)
| commit group | what |
|---|---|
| `feat(pipeline): resumable per-model training and merged comparison tables` | `scripts/run_full_pipeline.py`, `train_gnn.py`, `train_baselines.py`, `src/utils/results_io.py`, `tests/test_resume_and_merge.py` |
| `docs(readme): rewrite README ...` | `README.md` |
| `docs(release): release audit and path scrub` | `Docs/RELEASE_AUDIT.md`, `Docs/COLAB_PLAYBOOK.md` |
| `docs(colab): beginner handbook, training handoff and publication plan` | `Docs/COLAB_BEGINNER_HANDBOOK.md`, `Docs/COLAB_TRAINING_HANDOFF.md`, `Docs/PUBLICATION_PLAN.md` |
| `feat(colab): Drive-persistent outputs, environment record, resume; re-pin` | `notebooks/colab_final_run.ipynb`, refreshed `Docs/FINAL_*`, `Docs/release/vdm_v1_candidate_manifest.json` |

## Honest mapping to your suggested logical stages
Present in the history (as committed): data ingestion/provenance, dataset preprocessing and validation, features, graph construction, classical baselines, Node2Vec, GNNs, drug-disjoint evaluation and leakage prevention, disease-profile variant, ablations, explainability, NTD/EML/HAI/IHME evidence integration with NDPI and its sensitivity, tests, paper, documentation and the Colab notebook. **No commit exists for "API and application components"**: the repository contains no API or front-end code (only a design note, `Docs/API.md`); none was invented.

## What becomes public with the push
Source code, tests, configs, documentation, the paper draft and 7 figures (aggregate counts), the release manifest (file names, sizes, SHA-256 of local data, no data), the notebook. **Not** public: any dataset, IHME values, the WHO EML list, Open Targets tables, DrugBank files, checkpoints, outputs, keys. Already public and unchanged by this push: the three DrugBank-derived blobs in the history of `origin/mukul` (`Docs/RELEASE_AUDIT.md` section 4). Commit author names and e-mail addresses are part of the published history.

## Approval requested
Reply **"approve push to origin/mukul"** to publish exactly the commits above. Before that, decide (none blocks training): a code licence file, whether team names stay in `MASTER_PLAN.md`/`CONTRIBUTING.md`, and what to do about the DrugBank blobs.
