# VectorDrugMatch — Complete Development Summary

---

## 🎯 Overall Goal
Build a **production-grade, reproducible drug repurposing framework** that is significantly more than a GNN classifier.

**Final Objective:** Predict novel Drug–Disease associations using heterogeneous graph learning, then rank candidates using a biologically informed **Novel Drug Prioritization Index (NDPI)** combining ML predictions with similarity, literature evidence, and disease burden.

**The Pipeline:**
`Raw Biomedical Data` → `Unified Preprocessing` → `Feature Engineering` → `Graph Construction` → `Baseline ML` → `External Benchmark` → `Five Heterogeneous GNNs` → `Evaluation` → `Feature Ablation` → `Hyperparameter Search` → `Inference` → `NDPI Ranking`

---

## 🏆 Development Phases & Accomplishments

### Phase 1 — Data Engineering
- **Unified Preprocessing**: Redesigned preprocessing to use a single `scripts/preprocess.py` instead of multiple fragmented scripts (`process_pubchem_bulk.py`, `featurize_pubchem.py`, etc.).
- **Raw Datasets Integrated**: PubChem (Morgan fingerprints, MACCS, Avalon, ECFP3, FCFP3, RDKit descriptors), Hetionet v1.0 (Compound, Disease, Gene nodes and ALL relations: CtD, CpD, CbG, CdG, CuG, DaG, DuG, DdG, GiG, GrG), DisGeNET (metadata, associations, names).
- **SQLite Optimization**: Built `cid_smiles.db` to prevent rescanning large gz archives. Future runs take milliseconds instead of hours.
- **MyChem Fallback**: Failed PubChem SMILES are fetched via MyChem API and cached in `drugbank_smiles_cache.json` to prevent repeated API calls.
- **Missing SMILES Logging**: Non-resolvable SMILES are logged to `missing_smiles.csv` rather than silently failing.
- **Robust Validation**: Preprocessing validates drug/disease counts, feature matrices, edge consistency, and metadata.
- **Experiment-Aware Outputs**: Outputs are cleanly versioned into subdirectories (e.g., `baseline_morgan/`, `baseline_avalon/`) based on the experiment configuration.

### Phase 2 — Feature Engineering
- **Configurable Drug Features**: Switched via `config.yaml` (Morgan, MACCS, Avalon, ECFP3, FCFP3, RDKit descriptors, Scaffold) without needing code edits.
- **Disease Features**: Features include DALY, WHO NTD flag, disease category (scaled using `RobustScaler`), with future support for 768-dimensional SapBERT embeddings.

### Phase 3 — Graph Construction
- Constructed PyTorch Geometric `HeteroData` encompassing the entire biomedical graph (Drug, Disease, Gene nodes and all heterogeneous relations).

### Phase 4 — Dataset Builder
- **`build_tabular_dataset()`**: Handles positive edges, negative sampling, feature concatenation, and Train/Val/Test splits.
- **Hard Negative Sampling**: Forces the model to learn meaningful relationships rather than just degree memorization.
- **Cold-Start Split**: Added `cold_start_drug` split for strong experimental protocol to generalize to unseen drugs.

### Phase 5 — Classical Baselines
- **Models Implemented**: Logistic Regression, Naive Bayes, Random Forest, XGBoost, MLP.
- **Standardized Interface**: Wrapped inside `BaseModel` (`train()`, `predict()`, `predict_proba()`, `save()`, `load()`, `get_params()`).
- **DEFAULTS Pattern**: Every model now leverages a `DEFAULTS={}` pattern merged with config parameters for a cleaner architecture.

### Phase 6 — Configuration System
- All features, hyperparameters, experiment names, negative ratios, random seeds, and flags are driven by `.yaml` configs (`baseline_morgan.yaml`, etc.).

### Phase 7 — Baseline Training Pipeline
- Rewritten flow: `Load graph` → `Build dataset` → `Train models` → `Evaluate` → `Save` → `Log experiment` → `Save predictions`.
- **Artifacts Saved**: Model serialization (`baseline_rf.pkl`), metrics JSON, copied config, predictions CSV (`drug_id, disease_id, label, prediction, probability, experiment, model`).
- **Experiment Logging**: Records timestamp, model, feature dimension, metrics, git commit, and config for absolute reproducibility.

### Phase 8 — Unified Metrics
- **`metrics.py`**: Ensures all models use identical evaluation metrics (ROC-AUC, PR-AUC, F1, Precision, Recall, MCC, Accuracy, Brier score) and outputs formatted comparison tables.

### Phase 9 — GNN Framework
- **Models Implemented**: GCN, GraphSAGE, GAT, RGCN, HGT.
- **Wrapper**: Unified under `GNNLinkPredictionModel` separating encoder and link predictor. Features gradient clipping, mixed precision, and validation.

### Phase 10 — Evaluation
- **`evaluate.py`**: Combines Baseline and GNN results into a single research-grade table `model_comparison.csv`.

### Phase 11 — Feature Ablation
- **`run_ablations.py`**: Evaluates different feature combinations (Morgan, RDKit, Disease) using 5-fold CV, probability calibration, and MLflow logging.

### Phase 12 — Hyperparameter Search
- **`optuna_gnn.py`**: Tunes hidden size, heads, learning rate, weight decay, dropout, optimizer, scheduler, and epochs with MLflow logging.

### Phase 13 — External Benchmark
- **Node2Vec Integration**: Added Node2Vec embeddings + Logistic Regression as a rigorous external ML baseline.

### Phase 14 & 15 — Main Inference Pipeline & NDPI
- **`main_pipeline.py`**: Flow: `Load trained model` → `Generate candidate pairs` → `Predict probabilities` → `Threshold optimization` → `Similarity score` → `Literature score` → `Equity score` → `NDPI` → `Rank candidates`.
- **NDPI**: Final ranking prioritizes drugs by combining ML predictions with similarity, literature evidence, and disease burden.

### Phase 16 — Experiment Infrastructure
- Experiment versioning, MLflow, config snapshots, metrics JSON, model snapshots, and prediction CSVs ensure complete reproducibility.

### Phase 17 — Codebase Export
- **`export_codebase.py`**: Condenses the repository into a single `codebase.md` to feed into LLMs for code reviews and analysis.

### Phase 18 — Major Improvements Made During Review
- [x] SQLite PubChem lookup
- [x] Config-based preprocessing
- [x] Versioned outputs & Prediction CSVs
- [x] Metadata logger & Experiment logger
- [x] Feature dimension validation
- [x] DEFAULTS pattern & BaseModel cleanup
- [x] Unified metrics
- [x] Node2Vec benchmark
- [x] MLflow & Optuna integration
- [x] Calibration & Threshold optimization
- [x] SHAP integration
- [x] Hard negatives & Cold-start evaluation
- [x] 5-fold Stratified Cross Validation
- [x] Config snapshots & Metrics snapshots
- [x] Model serialization
- [x] Missing SMILES logging
- [x] Flexible feature engineering
- [x] Graph-wide heterogeneous edges
- [x] Unified preprocessing & unified evaluation

---

## 🚀 Remaining Improvements Identified (Future Work)
1. Load best inference model from config instead of hardcoding HGT.
2. Remove hardcoded feature dimensions from ablation scripts.
3. Add statistical significance testing (DeLong/bootstrap confidence intervals).
4. Add external validation datasets (DrugBank, RepoDB, Open Targets).
5. Include ranking metrics: Precision@K, Recall@K, Hits@K, MRR, NDCG.
6. Save learned drug and disease embeddings for downstream analysis.
7. Make NDPI weights configurable in YAML.
8. Log environment metadata (Python, CUDA, package versions) for full reproducibility.

---

## 🏗️ Final Architecture Flow
```
Raw Biomedical Datasets (PubChem, Hetionet, DisGeNET)
│
▼
scripts/preprocess.py
│
▼
Feature Engineering (Morgan/MACCS/Avalon/RDKit/ECFP/FCFP/SapBERT)
│
▼
PyTorch Geometric HeteroData
│
▼
Dataset Builder (Hard Negatives + Cold Start)
│
├─────────────────────────────┐
▼                             ▼
Baseline ML                   Node2Vec Benchmark
(LogReg, NB, RF, XGB, MLP)    (External Baseline)
│                             │
└──────────────┬──────────────┘
               ▼
Five Heterogeneous GNNs (GCN, GraphSAGE, GAT, RGCN, HGT)
               │
               ▼
Cross-Validation + Calibration
               │
               ▼
Unified Evaluation
               │
               ▼
Feature Ablation Study
               │
               ▼
Optuna Hyperparameter Search
               │
               ▼
Trained Best Model
               │
               ▼
Inference Pipeline
               │
               ▼
Probability Prediction → Similarity Score → Literature Score → Equity/Burden Score
               │
               ▼
Novel Drug Prioritization Index (NDPI)
               │
               ▼
Ranked Drug Repurposing Candidates
```
