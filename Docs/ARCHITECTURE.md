# 🏗️ ARCHITECTURE.md — System Design

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                                │
│  DrugBank  │  ChEMBL  │  Hetionet  │  DisGeNET  │  WHO GHO    │
└────────────────────────┬────────────────────────────────────────┘
                         │ ETL (src/data/)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE GRAPH                               │
│         Nodes: Drugs | Genes | Proteins | Diseases              │
│         Edges: targets | associates | treats | similar_to       │
│         Format: NetworkX → PyTorch Geometric HeteroData         │
└────────────────────────┬────────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
  ┌───────────┐  ┌────────────┐  ┌──────────────┐
  │  GCN/GAT  │  │ Tanimoto   │  │ PubMed       │
  │  Model    │  │ Similarity │  │ Literature   │
  │ (PyG)     │  │ (RDKit)    │  │ (Entrez API) │
  └─────┬─────┘  └─────┬──────┘  └──────┬───────┘
        │              │                │
        └──────────────┼────────────────┘
                       ▼
             ┌─────────────────┐
             │   NDPI Scoring  │  ← + WHO Equity Score
             │  0.35×GNN       │
             │+ 0.20×Sim       │
             │+ 0.20×Lit       │
             │+ 0.25×Equity    │
             └────────┬────────┘
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
   ┌────────────┐          ┌────────────┐
   │ Flask API  │          │  React UI  │
   │ /predict   │          │ (prod)     │
   └────────────┘          └────────────┘
```

## Component Responsibilities

### `src/data/` — Data Engineering
- **loaders.py**: Handles downloads, API calls, raw file reading
- **preprocessing.py**: Cleaning, normalisation, entity resolution
- **graph_builder.py**: Constructs heterogeneous graph from processed CSVs
- **feature_engineering.py**: Encodes node features (drug properties, disease DALY, etc.)

### `src/models/` — Machine Learning
- **baseline.py**: Logistic Regression using concatenated node features
- **gcn.py**: 2-layer Graph Convolutional Network (primary model)
- **gat.py**: Graph Attention Network (attention over neighbourhood)
- **link_predictor.py**: Dot-product scoring head for link prediction
- **ensemble.py**: Combines all models for production inference

### `src/scoring/` — NDPI Engine
- **ndpi.py**: Orchestrates all 4 components into final NDPI score
- **similarity.py**: RDKit Morgan fingerprint Tanimoto similarity
- **literature.py**: PubMed evidence count + normalisation + caching
- **equity.py**: WHO EML + DALY + affordability + generic availability

### `src/explainability/` — Interpretability
- **shap_explainer.py**: SHAP values for the Logistic Regression baseline
- **gnn_explainer.py**: PyG GNNExplainer for graph model predictions

### `api/` — REST Backend
- Flask application factory pattern
- Stateless: loads model once at startup, serves predictions
- Returns JSON with ranked drugs + NDPI component breakdown

### `frontend/` — React UI (Production)
- Connects to Flask API
- Three pages: Rankings, Explore (graph viz), About

### `streamlit_app/` — Legacy Prototype UI
- Deprecated in favor of React for production-ready interface
- Kept for reference or quick prototyping

## Data Flow

```
Raw CSVs
  └─► preprocess_all.py
        └─► processed/*.csv
              └─► graph_builder.py
                    └─► node_features.npy + edge_index.npy
                          └─► train_gcn.py
                                └─► outputs/models/gcn_best.pt
                                      └─► main_pipeline.py
                                            └─► outputs/ndpi_results.csv
                                                  └─► API / React
```

## Key Design Decisions

1. **React UI connects to Flask production API** — Clean API contract for advanced research interface; supports complex visualizations and interactions.
2. **NDPI formula uses fixed weights** — Interpretable to clinicians. Future work: learn weights with meta-learning.
3. **Positive labels from Hetionet CtD edges** — Known, curated drug-treats-disease relationships. 1:1 negative sampling from unconfirmed pairs.
4. **Literature scores are cached** — PubMed API has rate limits (3 req/sec). Cache all lookups to SQLite.
5. **GCN over GraphSAGE** — GCN is simpler for 4-person student team; GAT added in Week 4 for comparison.
