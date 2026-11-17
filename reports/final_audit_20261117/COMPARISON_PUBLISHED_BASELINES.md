# Comparison against published baseline methods

**Status: partially complete.** The parts that do not need a GPU are finished and reported below. The GPU parts (the KG-embedding baselines, and
VectorDrugMatch under the disease-disjoint protocol) are prepared and pinned in `notebooks/colab_comparison_20261118.ipynb`; their results will be
filled in from `make_comparison_tables.py` once that notebook has run. Nothing here changes the frozen selection or the deployed model: the model was
selected and frozen (`FROZEN_SELECTION.json`), and the holdout evaluated once, **before** any of this comparison work began.

## 1. Can TxGNN itself be run? No - and why that matters
TxGNN (Huang et al., *Nature Medicine* 2024) is the PrimeKG authors' own drug-repurposing model and the most relevant published method.
It could **not** be run, for two independent reasons:

1. **Dependencies.** TxGNN pins `dgl==0.5.2` (September 2020) with Python 3.8. No DGL build of that version exists for Python 3.9+; this machine has
   Python 3.10/3.11/3.12 and no conda, and `pip download dgl==0.5.2` resolves to nothing (available versions jump 0.1.3 → 0.9.0). The `TxGNN` PyPI
   package (0.0.3) declares no dependencies, so it installs but cannot import a working DGL. Porting its code to DGL 2.x is a reimplementation, not
   a reproduction.
2. **Protocol mismatch - the deeper problem.** Every split TxGNN supports holds out whole **diseases** (`complex_disease`, the nine disease-area
   splits, `disease_eval`) or shuffles pairs at random. VectorDrugMatch holds out **drugs**. There is no supported way to give TxGNN a drug-disjoint
   split; its evaluation entry point is disease-centric as well.

Consequence: **no head-to-head claim against TxGNN is made in this project.** Quoting its published numbers next to ours would compare different
splits, different negative sampling and different candidate universes. Two defensible comparisons are made instead:
* **A.** The standard KG-embedding baselines (TransE, DistMult, ComplEx, RotatE) - the model class this literature benchmarks against - trained and
  evaluated on **identical** data, splits, graph and candidate pairs (section 3).
* **B.** VectorDrugMatch measured on a **disease-disjoint** split built to mirror the published protocol, so its behaviour in that setting is
  measured directly rather than argued about (section 4).

## 2. Method
* KG embeddings: `src/models/kge.py`, trained by `scripts/final_audit/train_kge.py`. Training triples = the same leakage-safe message-passing graph
  used by the GCN (no indication edges; contraindication / off-label edges of held-out pairs removed) **plus** the split's training indication edges,
  which a KGE model needs in order to learn the target relation. Held-out positives are never training triples - asserted by a per-run audit.
  Self-adversarial negative sampling (RotatE paper), type-correct corruption, target-relation negatives filtered against all known drug-disease pairs.
  Identical a-priori hyper-parameters for all four models (dim 128 = the deployed GCN's width, gamma 12, 64 negatives, Adam lr 2e-3, batch 8192,
  12,000 steps ≈ 200 passes, checkpoint = best validation ROC-AUC, patience 4 evaluations) - the same checkpoint policy as the GCN.
* Budget justification: a CPU pilot (DistMult, cv_fold0, batch 1024) was still improving at 1,500 steps (validation ROC-AUC 0.505 → 0.633), i.e. these
  models need far more optimisation steps than the GCN. Log: `comparison/kge_cpu_pilot_DistMult_cv_fold0.log`.
* **Known asymmetry, stated up front:** KG-embedding models are structure-only; they see no chemical fingerprints, whereas VectorDrugMatch uses Morgan
  fingerprints. This is inherent to the model class (TxGNN does not use fingerprints either). The matched structure-only comparator inside
  VectorDrugMatch is `connectivity_gbm`, which is reported alongside.
* Disease-disjoint protocol: `scripts/final_audit/make_disease_split.py` (committed files + SHA-256 in `disease_protocol_files/`). 1,226 training
  diseases, 68 validation, 69 test (442 test positives, 2,210 sampled negatives), stratified on NTD status and indication count, 1:5 negatives plus a
  popularity-matched set. Drug sets overlap by construction, so **these numbers must never be mixed with the drug-disjoint results.**

## 3. KG-embedding baselines on identical data - PENDING GPU
To be filled from `COMPARISON_BASELINES.csv` / `comparison/paired_vs_kge_holdout.csv` after `notebooks/colab_comparison_20261118.ipynb` runs:
locked-holdout ROC-AUC and AP for TransE / DistMult / ComplEx / RotatE against the deployed model (paired hierarchical bootstrap, identical pairs),
and fold-to-fold values on the 5 development folds.

## 4. The zero-shot-disease protocol
### 4.1 Feature baselines (complete, CPU)
Test set of the disease-disjoint split (442 positives / 2,210 sampled negatives; a random ranker scores AP = 1/6 = 0.167):

| Method | test ROC-AUC | test AP | popularity-matched AUC | popularity-matched AP |
|---|---|---|---|---|
| connectivity GBM (structure-only) | 0.754 | 0.403 | 0.712 | 0.326 |
| degree GBM | 0.725 | 0.354 | 0.683 | 0.293 |
| deg+conn+fp GBM (deployed component) | 0.681 | 0.358 | 0.649 | 0.300 |
| fingerprint-profile GBM | **0.500** | **0.167** | 0.500 | 0.167 |
| max Tanimoto | **0.500** | **0.167** | 0.500 | 0.167 |
| disease popularity | **0.500** | **0.167** | 0.500 | 0.167 |

**Finding - a genuine limitation of the deployed model.** Every disease-profile and chemistry feature is *exactly* at chance, because all of them are
defined relative to "the training drugs known to treat this disease" and a held-out disease has none: the features are identically zero, so the models
emit a constant. The deployed GBM component therefore contributes nothing in the zero-shot-disease setting, and adding those dead features even hurts
slightly relative to the structure-only connectivity model (AP 0.358 vs 0.403). VectorDrugMatch as deployed is a **new-indication-for-a-known-drug**
system; it is not a zero-shot-disease system, which is precisely what TxGNN was designed to be.

### 4.2 VectorDrugMatch GCN under this protocol - PENDING GPU
The GCN propagates over disease-gene and disease-disease edges, so unlike the feature baselines it is not structurally blind to an unseen disease; its
numbers here (3 seeds) will show how much of the gap it closes. Run on the T4 for device consistency with every other GCN number in this project.

## 5. What this comparison can and cannot establish
* It **can** establish whether VectorDrugMatch outperforms standard KG-embedding methods under identical conditions, and how it behaves under the
  published disease-held-out protocol.
* It **cannot** establish that VectorDrugMatch is better or worse than TxGNN. That claim would need TxGNN executed on these splits (blocked by
  dependencies and by its disease-centric design) or VectorDrugMatch executed inside TxGNN's own harness on its own splits.
* No "state of the art" claim is made anywhere in this project.
