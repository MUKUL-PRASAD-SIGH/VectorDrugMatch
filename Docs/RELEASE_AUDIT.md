# Release audit (publication to the public GitHub repository)

Audit of 2026-11-11. The repository `https://github.com/MUKUL-PRASAD-SIGH/VectorDrugMatch` is **public** (`gh repo view`: visibility PUBLIC). Nothing has been pushed by this audit; no history was rewritten.

## 1. Repository state and versions
| item | result |
|---|---|
| Working tree | clean after the commits listed in `Docs/PUBLICATION_PLAN.md` |
| Branch | `mukul`; remote branches `main`, `master`, `feat/biomedical-graph-setup`, `feat/data-pipeline`, `mukul` |
| Final code commit (pinned in the notebook) | the value of `PIN` in `notebooks/colab_final_run.ipynb` (commits after it change only `notebooks/` and `Docs/`; checked by `scripts/make_final_docs.py`) |
| Tracked files | 156 (89 Python, docs, 8 configs, 3 notebooks, 14 figure files); no dataset, model, checkpoint or output file |

## 2. Consistency checks (re-run in this audit, evidence in `Docs/COLAB_TRAINING_HANDOFF.md` section 2)
* One saved split (`splits/seed42.npz`) is read by baselines, ablation, Node2Vec and GNNs; the disease-profile variant is tested to keep pairs, labels, negatives and original columns identical.
* Leakage checks: 37 PASS / 0 FAIL on a regenerated copy (drug-disjoint sets, no negative is a known pair of any relation, `treats` and `rev_treats` removed from the message-passing graph, no held-out pair reachable through any drug-disease relation).
* MONDO release `2026-11-03` (`data/external/mondo.obo`, SHA-256 prefix `b5a3d84857`); PrimeKG `kg.csv` SHA-256 prefix `0a5a010fcd`; SMILES cache 6,984 entries. A fresh-clone regeneration from these inputs, including the live lookup for the 996 uncached drugs, reproduced all 20 benchmark files byte-for-byte; the notebook (Step 4b) re-checks this on Colab against `Docs/release/vdm_v1_candidate_manifest.json`.
* 36 tests pass locally.

## 3. Secrets, credentials, personal data, restricted files
| scan | result |
|---|---|
| Credential patterns (API keys, tokens, passwords, AWS/GitHub/OpenAI/Google/Slack key formats) in all tracked files | none found |
| Tracked environment files | only `.env.example` (placeholder `ENTREZ_EMAIL=your_email@example.com`); `.env` is git-ignored |
| Restricted data tracked (DrugBank, IHME, WHO EML list, Open Targets tables) | none in the current tree; IHME example values were removed from `Docs/DATA_DICTIONARY.md` and a code comment (commit `cb41c44`); the data dictionary masks IHME-derived examples |
| Absolute local path with a user name | one occurrence in `Docs/COLAB_PLAYBOOK.md`, replaced by a placeholder in this audit |
| Personal information that remains | (a) names of the four team members in `Docs/MASTER_PLAN.md` and `Docs/CONTRIBUTING.md` (project documents; your decision whether to keep them public); (b) **commit author names and e-mail addresses in the Git history** (cannot be removed without rewriting history, which was not done); (c) the README names the student chapter and institute |
| Other tracked data-like files | small mock fixtures `tests/fixtures/mock_raw/*.csv` (synthetic rows that reuse a few public DrugBank identifiers and structures; 14 identifiers), `Docs/source_evidence/*` (licence-page evidence, not data), `Docs/paper/metrics.json` (aggregate counts) |

## 4. DrugBank-derived blobs in Git history (not rewritten)
Three files that derive from DrugBank/PubChem lookups exist in the history of **`origin/mukul` only**; none is on `main`, `master` or the two `feat/` branches, and none is in the current tree:
| path | blob | size | added | removed |
|---|---|---|---|---|
| `data/external/drugbank_cid_map.json` | `e706a40fe7ee222a38a37d0e60310ea839f29af1` | 30,324 B | `1829752` (2026-10-30) | `522deb3` (2026-11-10) |
| `data/external/drugbank_smiles_cache.json` | `e817bcbf20ae21658acf1782ae282bb8b72cfdc0` | 109,649 B | `1829752` | `522deb3` |
| `data/external/fetch_smiles_missing.csv` (list of DrugBank IDs without SMILES) | `45a240064be6166c09b22180b454cfe31c9cd6a7` | 176 B | `1829752` | `522deb3` |

Facts that matter: removing the files from the latest commit does **not** remove them from history; they are already visible to anyone who can read `origin/mukul` in this public repository, so a new push does not add them. A history rewrite would need a force-push on a shared branch, coordination with the other collaborators, and would still not remove copies that were cloned or forked in the meantime. Nothing was changed. The licence position (DrugBank CC BY-NC 4.0 / academic terms) is an open question for you (`Docs/LICENCE_AUDIT.md` section 4); the options are: leave as is and document (current), or later decide on a coordinated rewrite. Neither is needed to run the training.

## 5. Release-blocking issues and how each is handled
| issue | status |
|---|---|
| Push publishes 24+ unpushed commits to a public branch | **needs your approval** (`Docs/PUBLICATION_PLAN.md`); content reviewed: code, docs, aggregates, figures, notebook; no data |
| No `LICENSE` file; old README claimed MIT | README now says no code licence is chosen; **your decision** before a public release |
| DrugBank-derived blobs in `origin/mukul` history | documented above; no rewrite |
| Personal data in Git history and team documents | documented above; your decision |
| Legal questions (CC0 over NC constituents, ShareAlike on derived tables, ClinicalTrials.gov/AACT/TTD/PMDA terms) | unresolved, documented in `Docs/LICENCE_AUDIT.md`; not needed for training, needed before publishing derived tables or the paper |
| Final results absent | expected; the paper marks results sections `[PENDING]` |
| Stale/misleading documents (`Docs/ARCHITECTURE.md`, `Docs/MASTER_PLAN.md`, `Docs/DEVELOPMENT_SUMMARY.md`, `Docs/API.md`) describe the early plan | not changed in this audit (history documents); the README states that the API/frontend do not exist; consider an "archived plan" banner later |
