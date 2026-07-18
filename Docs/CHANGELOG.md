# 📋 CHANGELOG

All notable changes to VectorDrugMatch are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

---

## [Unreleased]

### Added
- Initial project structure
- README, MASTER_PLAN, DATASETS, ARCHITECTURE, API, CONTRIBUTING documentation
- Sample dataset: 15 drugs, 10 NTDs, 48 edges

### Changed
- Restructured documentation for research-grade progressive model comparison
- Pivoted from DrugBank to PubChem as primary drug source
- Consolidated 3 preprocessing scripts into single `scripts/preprocess.py`
- Split `src/models/` into `baseline/` and `gnn/` subdirectories
- Added `src/features/` directory for drug, disease, and graph feature engineering
- Expanded from 1 baseline (Logistic Regression) to 6 baselines
- Expanded from 1 GNN (GCN) to 5 GNN models (GCN → HGT)
- Updated NDPI formula to use HGT prediction instead of basic GCN

### Deprecated
- `process_pubchem_bulk.py` — functionality moved to `scripts/preprocess.py`
- `featurize_pubchem.py` — replaced by RDKit Morgan FP in `src/features/drug.py`
- Old `scripts/preprocess_all.py` — replaced by `scripts/preprocess.py`

---

## [0.1.0] — Phase 1+2: Data & Feature Engineering

### Added
- Unified preprocessing pipeline (`scripts/preprocess.py`)
  - Merges PubChem + DisGeNET + Hetionet in one script
  - Preserves ALL Hetionet edge types (CtD, CbG, CdG, CuG, DaG, GiG, GrG, etc.)
  - Produces `drugs.csv`, `diseases.csv`, `genes.csv`, `edges.csv`, `drug_features.npy`, `graph_metadata.json`
- RDKit drug features (`src/features/drug.py`)
  - Morgan Fingerprints (2048-bit)
  - Molecular descriptors: MW, LogP, TPSA, HBD, HBA, rotatable bonds
- Disease features (`src/features/disease.py`) — DALY, WHO NTD flags
- Graph features (`src/features/graph.py`) — node degree, centrality
- Knowledge graph construction with PyTorch Geometric HeteroData (`src/data/graph_builder.py`)
- WHO EML and NTD flag columns in drugs/diseases CSVs

### Removed
- `process_pubchem_bulk.py`, `featurize_pubchem.py` (consolidated into `preprocess.py`)

---

## [0.2.0] — Phase 3: Classical ML Baselines

### Added
- 6 baseline models (`src/models/baseline/`):
  - Random Guess (sanity check)
  - Majority Class (sanity check)
  - Logistic Regression (`logistic.py`)
  - Naive Bayes (`naive_bayes.py`)
  - Random Forest (`random_forest.py`)
  - XGBoost / LightGBM (`xgboost_model.py`)
  - MLP (`mlp.py`)
- Unified baseline training script (`scripts/train_baselines.py`)
- RDKit Tanimoto similarity scoring (`src/scoring/similarity.py`)
- PubMed literature scoring with caching (`src/scoring/literature.py`)
- WHO GHO API integration for DALY data (`src/scoring/equity.py`)
- Evaluation metrics: ROC-AUC, PR-AUC, F1, Precision, Recall, MCC

---

## [0.3.0] — Phase 4: Graph Neural Networks

### Added
- 5 GNN models (`src/models/gnn/`):
  - GCN — 2-layer Graph Convolutional Network (`gcn.py`)
  - GraphSAGE — inductive learning (`graphsage.py`)
  - GAT — Graph Attention Network (`gat.py`)
  - RGCN — Relational GCN for multi-relation edges (`rgcn.py`)
  - HGT — Heterogeneous Graph Transformer, **final proposed model** (`hgt.py`)
- Unified GNN training script (`scripts/train_gnn.py`)
- Unified evaluation script (`scripts/evaluate.py`) — 11-model comparison table
- Full NDPI formula with HGT as ML component (`src/scoring/ndpi.py`)

---

## [0.4.0] — Phase 5: Explainability & Integration

### Added
- SHAP explainability for all baseline models (`src/explainability/shap_explainer.py`)
- GNNExplainer for HGT model (`src/explainability/gnn_explainer.py`)
- Flask REST API (`api/`)
- Unit tests for all modules (`tests/`)
- 11-model comparison results table for paper

---

## [1.0.0] — Phase 6: Deployment & Paper

### Added
- React production frontend (`frontend/`) with model comparison view
- Docker + docker-compose deployment
- GitHub Actions CI/CD
- Full heterogeneous graph: 1,500+ drugs, 130+ diseases, 20,000+ genes, 500,000+ edges
- 5 documented case studies
- Research paper draft with progressive results table:
  - Sanity checks → Classical baselines → Graph baselines → Relation-aware GNNs → HGT + NDPI
