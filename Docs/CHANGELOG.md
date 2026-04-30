# 📋 CHANGELOG

All notable changes to VectorDrugMatch are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

---

## [Unreleased]

### Added
- Initial project structure
- README, MASTER_PLAN, DATASETS, ARCHITECTURE, API, CONTRIBUTING documentation
- Sample dataset: 15 drugs, 10 NTDs, 48 edges

---

## [0.1.0] — Week 2 Target

### Added
- Data preprocessing pipeline (`src/data/preprocessing.py`)
- Knowledge graph construction with NetworkX (`src/data/graph_builder.py`)
- Logistic Regression baseline (`src/models/baseline.py`)
- React production UI (`frontend/`)
- WHO EML and NTD flag columns in drugs/diseases CSVs

---

## [0.2.0] — Week 4 Target

### Added
- 2-layer GCN model (`src/models/gcn.py`)
- Graph Attention Network (`src/models/gat.py`)
- RDKit Tanimoto similarity scoring (`src/scoring/similarity.py`)
- PubMed literature scoring with caching (`src/scoring/literature.py`)
- Full NDPI formula with all 4 components (`src/scoring/ndpi.py`)
- WHO GHO API integration for DALY data

---

## [0.3.0] — Week 6 Target

### Added
- SHAP explainability for baseline model (`src/explainability/shap_explainer.py`)
- GNNExplainer for graph model (`src/explainability/gnn_explainer.py`)
- Flask REST API (`api/`)
- Unit tests for all modules (`tests/`)
- Model ensemble (`src/models/ensemble.py`)

---

## [1.0.0] — Week 8 Target

### Added
- React production frontend (`frontend/`)
- Docker + docker-compose deployment
- GitHub Actions CI/CD
- Scaled dataset: 100+ drugs, all 10 NTDs
- 5 documented case studies
- Paper draft complete
