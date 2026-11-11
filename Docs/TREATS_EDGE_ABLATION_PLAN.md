# Treats-edge ablation: audit, design and safeguards (branch `exp/treats-edge-ablation`)

Status: **code and local checks done; no model has been trained for this experiment.** All training runs on Colab (`notebooks/colab_treats_edge_ablation.ipynb`). Nothing here changes the completed results (`reports/research_validation_20261111/`, Drive bundles). Not pushed.

## 1. Audit of the existing implementation (inspected, not assumed)
| question | finding (source) |
|---|---|
| Where do `treats` edges come from? | PrimeKG indication rows, relation `CtD`/`treats`, loaded by `src/data/graph_builder.py`; `T.ToUndirected()` then adds `rev_treats`. 9,388 pairs = 6,730 train + 1,397 val + 1,261 test positives. |
| Are all treats edges removed in training? | **Yes.** `build_message_passing_graph` (src/data/dataset.py:94) empties `treats` and `rev_treats` for every pair, train included. `scripts/train_gnn.py` uses this one graph for train, validation and test. |
| Are train-positive edges available? | In the data, yes (`edges_train`, `y_train`=1: 6,730); currently unused for message passing. |
| Are val/test positives excluded? | Yes (all treats are excluded). `contraindicated_for` / `offlabel_for` are additionally dropped, both directions, for the 2,658 held-out indication pairs (`heldout_indication_pairs`). |
| Reverse edges? | Yes, created by `ToUndirected`; handled together with the forward edge everywhere above. |
| Other routes for the target? | Drug-disease relations in the graph: `treats`, `contraindicated_for`, `offlabel_for` only. Held-out pairs are removed from the latter two. Node features: disease and gene degrees are computed **without** label relations (`LABEL_RELATIONS`), drug features are fingerprints; no label enters features. |
| Same split for graph and supervision? | Yes: one saved split (`splits/seed42.npz`) feeds both; the five seeds change initialisation only. |
| Transductive or inductive? | Transductive in nodes (all 7,957 drugs, 17,080 diseases, 19,051 genes are in the graph) but **inductive in labels**: split is drug-disjoint, so a validation/test drug has no train-positive `treats` edge by construction. |
| Five-seed experiment code? | **Not in the repository** (the five-seed run was done in an unrecorded Colab session). The new runner is the first versioned multi-seed implementation; `A_orig` re-runs the original protocol under it. |

## 2. Measured graph diagnostics (CPU, `scripts/graph_diagnostics.py`; files in `reports/treats_edge_ablation_20261111/diagnostics/`)
* Original graph (A): 492,286 undirected non-target edges; **1,529 of 7,957 drugs (19%) are isolated**, 29 diseases isolated, 1,567 connected components (largest: 42,511 nodes; 81% of drugs, 99.8% of diseases in it). 44 of 271 test drugs have no gene edge.
* Reachability of test pairs by a walk of length at most 2 / 3: positives 28.3% / 81.1%, negatives 7.0% / 61.6% (original). With train treats edges (B): 28.3% / 88.7% and 7.0% / 70.1%. Mechanism-only (C): 23.5% / 46.3% and 5.6% / 26.2%.
* **Two consequences.** (i) Connectivity itself separates positives from sampled negatives, so part of any graph model's score can be a connectivity/popularity effect. (ii) Train treats edges add **nothing within 2 hops** (28.3% unchanged): a 2-layer GCN can use them only on the disease side (median 11 train-positive drugs per test-positive disease; 91 test positives have none); the path *test drug - gene - similar train drug - treats - disease* needs 3 hops. Hence the controlled 3-layer pair `A_k4_L3` / `B_k4_L3`.
* Hypothesis (not a conclusion): the earlier GCN-versus-RF gap may partly come from the RF receiving a disease-profile block (a label-derived disease signal) that the GCN lacked. Variant B gives the GCN the same kind of training-label information through the graph.

## 3. Design and why it differs slightly from the literal request
Requested: train-positive treats edges available to message passing. **Using the same positives as supervised targets and as graph edges is target leakage in training** (the model reads the label off the edge; held-out pairs have no such edge, so validation/test would look much worse than training and the learned weights would rely on the edge). Therefore, in configuration B each optimisation step hides the pairs it supervises:
* an epoch = `k` steps (default k = 4) over a random, label-stratified partition of the train pairs; in step j the train positives of fold j (and their reverse edges) are **removed** from `treats`/`rev_treats`, the other (k-1)/k of the train positives stay as known indications;
* evaluation (validation, test) uses **all** train positives in the graph; held-out positives and negatives are never inserted;
* training negatives are only supervised targets, never edges.
`B0_naive` (everything present and supervised) is run only as a labelled diagnostic to demonstrate the leakage; it is never reported as a result.

| config | graph | steps per epoch | masking | purpose |
|---|---|---|---|---|
| A_orig | no treats | 1 (full batch) | - | code-of-record protocol (control A) |
| A_k4 | no treats | 4 | - | matched control for B (same step structure) |
| **B_k4** | + train positives | 4 | yes | **primary** (B) |
| B_k2, B_k8 | + train positives | 2, 8 | yes | sensitivity of k, validation only, seed 42 |
| C_k4 | no treats, no contraindication/off-label | 4 | - | mechanism-only ablation (C) |
| A_k4_L3, B_k4_L3 | as A_k4, B_k4 | 4 | yes (B) | 3 layers: reaches drug-gene-drug-disease paths |
| D_rgcn_B | as B_k4, RGCN encoder | 4 | yes | optional relation-aware model (D) |
| B0_naive | + train positives | 1 | **no** | leakage diagnostic only |

Held fixed in every run: model (the code-of-record stabilised GCN, 64-d embeddings, head 128-32-1), Adam lr 0.005 / weight decay 1e-4, plateau scheduler and early stopping on **validation** ROC-AUC (patience 20, <= 100 epochs), identical train/val/test pairs and sampled negatives, identical features, seeds 21, 42, 52, 72, 100, Youden threshold from validation. HGT is not included (not needed for the question). RF/XGBoost are untouched. k = 4 is fixed a priori; the k sweep is sensitivity only.

## 4. Leakage safeguards (automated, saved per run as `leakage_audit.json`; a failing audit stops the run)
Held-out positives absent from `treats`, `contraindicated_for`, `offlabel_for` and every reverse edge; heldout set equals val+test positives; graph treats edges are train positives of train drugs only; drug sets disjoint; reverse is the exact flip; no negative of any split is a known pair of any drug-disease relation or a graph edge; in every masked step the supervised positives are absent from the edges (checked for all folds). Tested: `tests/test_treats_edges.py` plants a test pair and a reverse-only leak and verifies the audit catches them. Result on the real split (local): `all_pass=True` for variants A, B and C.
Label-learning preprocessing: none (fingerprints; degrees without label relations). Test data are used once, for the final evaluation of the validation-selected checkpoint.

## 5. Metrics and outputs
ROC-AUC, PR-AUC as average precision (step-wise) **and** as trapezoidal area (reported separately), Precision@10/50/100/500, Recall@K, NDCG@K (global over the sampled test pairs), Brier, log loss, ECE (10 bins), false positives / negatives, error rate, high-confidence mistakes (listed in CSVs), bootstrap 95% CI per run (3,000 resamples), paired bootstrap against `A_orig`, parameters, train and inference seconds, graph and target-edge counts. Per run: configuration, split manifest copy, leakage audit, predictions, checkpoint, history, log in `outputs/treats_edge_ablation_20261111/<config>/seed<seed>/`; summaries from `scripts/summarize_treats_ablation.py`.
Sampled-negative evaluation is a computational benchmark, not clinical validation.

## 6. Interpretation protocol (decided before results)
After the five-seed runs: compare `B_k4` (and the 3-layer pair) with `A_orig`/`A_k4` by validation and test ROC-AUC/AP (mean ± SD, paired differences) and with the **unchanged** RF/XGBoost numbers. Outcomes: (1) substantial improvement: attribute it to training-positive treats edges only if `B_k4` beats the matched control `A_k4` and `B0_naive` does not explain it; (2) improvement below RF/XGBoost: report both; (3) no improvement: keep the original conclusion. Caveats to state regardless: one fixed split, sampled negatives, the connectivity effect above, drug-disjoint cold start (held-out drugs have no treats edges).

## 7. What has and has not been done
Done locally (no training): audit, diagnostics, leakage audit on the real split, 5 unit tests (42 tests pass in total), a forward-only check of every code path on CPU (parameter count 1,155,649 for the 2-layer GCN, 1,255,105 for 3 layers; masked step 5,047 of 6,730 treats edges visible). **Not done:** any training, any result, the Colab smoke test, the five-seed runs, the paper update. Not pushed: the branch `exp/treats-edge-ablation` exists only locally.

## 8. Pre-run verification (local, CPU, no training; `scripts/verify_ablation_setup.py`, output `reports/treats_edge_ablation_20261111/verification_pre_run.json`)
1. **A_k4 and B_k4 differ only in the edge dict.** Fold sequences are identical for the same seed (the fold generator is the only consumer of the run's random generator), every epoch's folds partition all 40,380 train pairs, supervised targets and labels come from the one saved split (train/val/test pair hashes recorded), negatives are never resampled, evaluation pairs are the saved validation/test pairs. **A bug was found and fixed here:** initialising the lazy layers on each configuration's own edge dict gave A and B *different initial weights*; `make_model()` now initialises on one canonical edge dict, and the initial-weight hashes of A_orig, A_k4 and B_k4 are identical for seeds 21 and 42. Residual non-identity: dropout masks come from the seeded global stream and are not forced equal between configurations.
2. **Supervised edges hidden:** in all 84 checked steps (k = 2, 4, 8; seeds 21 and 42; 3 epochs) every supervised positive and its reverse is absent from that step's graph (0 violations); visible train `treats` edges per step range 3,365 to 5,889 of 6,730.
3. **Held-out absent everywhere:** 0 occurrences of any of the 2,658 held-out (val+test positive) pairs, forward or reverse, in `treats`, `contraindicated_for` or `offlabel_for`, in the evaluation graph and in every masked step graph, for all nine configurations.
4. **Alternate representations:** only `treats`, `contraindicated_for` and `offlabel_for` (and their reverses) join drug and disease nodes; there are no drug-drug edge types; no duplicate drug or disease node ids; no val/test drug has a train `treats` edge. **Residual side information (existing design, identical in A and B, removed only in C):** 7,730 of 30,638 contraindication and 704 of 2,537 off-label edges belong to validation/test drugs and point to *other* diseases; they are not the target pair but are label-like information about a held-out drug. It cannot explain an A-versus-B difference; `C_k4` shows how much the model relies on such edges.
5. **Output safety:** the runner writes only below `outputs/treats_edge_ablation_*` (refuses other `--out`), refuses to overwrite an existing run (`--resume` skips finished runs), and smoke output goes to a separate `smoke/` folder. Existing checkpoints and reports are not touched.
