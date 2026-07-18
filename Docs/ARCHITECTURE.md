# 🏗️ ARCHITECTURE.md — System Design

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCES                                    │
│  PubChem (CID-SMILES)  │  Hetionet v1.0  │  DisGeNET  │  WHO GHO API    │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    UNIFIED PREPROCESSING                                  │
│                     scripts/preprocess.py                                 │
│                                                                           │
│  PubChem → drugs.csv + drug_features.npy (RDKit Morgan FP 2048)          │
│  DisGeNET → diseases.csv + genes.csv                                      │
│  Hetionet → edges.csv (ALL relation types: CtD, CbG, CdG, CuG,          │
│             CpD, DaG, DuG, DdG, GiG, GrG)                                │
│  Merge → graph_metadata.json                                              │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     HETEROGENEOUS KNOWLEDGE GRAPH                         │
│                                                                           │
│  Node Types:  Drug (1,500+)  │  Gene (20,000+)  │  Disease (130+)        │
│                                                                           │
│  Edge Types:  CtD (treats)      │  CbG (binds)        │  GiG (interacts)  │
│               CpD (palliates)   │  CdG (downregulates) │  GrG (regulates) │
│               DaG (associates)  │  CuG (upregulates)   │  DuG/DdG         │
│                                                                           │
│  Format: PyTorch Geometric HeteroData                                     │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   FEATURE ENG   │  │  CLASSICAL ML    │  │   GRAPH NEURAL   │
│   src/features/ │  │  BASELINES (6)   │  │   NETWORKS (5)   │
│                 │  │                  │  │                  │
│  Drug:          │  │  Random Guess    │  │  GCN             │
│   Morgan FP     │  │  Majority Class  │  │  GraphSAGE       │
│   MW/LogP/TPSA  │  │  Logistic Reg    │  │  GAT             │
│   HBD/HBA       │  │  Naive Bayes    │  │  RGCN            │
│                 │  │  Random Forest   │  │  HGT ★ (final)   │
│  Disease:       │  │  XGBoost         │  │                  │
│   DALY/WHO/NTD  │  │  MLP             │  │                  │
│                 │  │                  │  │                  │
│  Graph:         │  │  Uses: flat      │  │  Uses: graph     │
│   Degree        │  │  feature vectors │  │  message passing │
│   Centrality    │  │                  │  │  + HeteroData    │
│   Node2Vec      │  │                  │  │                  │
└────────┬────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                    │                      │
         └────────────────────┼──────────────────────┘
                              ▼
              ┌──────────────────────────────┐
              │     UNIFIED EVALUATION       │
              │     scripts/evaluate.py      │
              │                              │
              │  ROC-AUC, PR-AUC, F1,        │
              │  Precision, Recall, MCC      │
              │                              │
              │  11-model comparison table   │
              └──────────────┬───────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌──────────────┐  ┌───────────────────┐  ┌──────────────┐
│  Tanimoto    │  │  PubMed           │  │  WHO GHO     │
│  Similarity  │  │  Literature       │  │  Equity      │
│  (RDKit)     │  │  (Entrez API)     │  │  (DALY+EML)  │
└──────┬───────┘  └────────┬──────────┘  └──────┬───────┘
       │                   │                     │
       └───────────────────┼─────────────────────┘
                           ▼
                ┌─────────────────────┐
                │   NDPI Scoring      │  ← Best model (HGT) + 3 scoring components
                │                     │
                │  0.35 × HGT_score   │
                │+ 0.20 × Similarity  │
                │+ 0.20 × Literature  │
                │+ 0.25 × Equity      │
                └──────────┬──────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
       ┌────────────┐           ┌────────────┐
       │ Flask API  │           │  React UI  │
       │ /predict   │           │ (prod)     │
       └────────────┘           └────────────┘
```

---

## Component Responsibilities

### `scripts/` — Pipeline Entry Points

| Script | Purpose |
|---|---|
| `preprocess.py` | **Single unified preprocessing.** Merges PubChem + DisGeNET + Hetionet → processed CSVs + features. Replaces the old scripts. Now driven by `--config`. |
| `train_baselines.py` | Trains all classical ML baselines, saves metrics + models to versioned `outputs/<exp>`. |
| `train_gnn.py` | Trains all GNN models on `HeteroData`, saves metrics + model weights to versioned `outputs/<exp>`. |
| `evaluate.py` | Loads all trained models, produces the unified comparison table. |

### `configs/` — Config-Driven Ablations
- **YAML Configs**: All experiments are defined declaratively in `.yaml` files (e.g. `baseline_morgan.yaml`, `baseline_avalon.yaml`).
- Defines features to extract (e.g., MACCS, Avalon, continuous descriptors, SapBERT), dataset split sizes, negative sampling ratio, and model hyperparameters.

### `src/data/` — Data Engineering
- **graph_builder.py**: Converts processed CSVs into a PyTorch Geometric `HeteroData` object with typed nodes (`Drug`, `Gene`, `Disease`) and typed edges (`CbG`, `CdG`, `CuG`, `DaG`, `GiG`, `GrG`, `CtD`, etc.)

### `src/features/` — Feature Engineering
- **drug.py**: RDKit Morgan fingerprints (2048-bit) + molecular descriptors (MW, LogP, TPSA, HBD, HBA, rotatable bonds). Produces ~2055 features per drug.
- **disease.py**: DALY burden (normalised), WHO NTD flag, disease category.
- **graph.py**: Node degree, betweenness centrality, Node2Vec embeddings (optional).

### `src/models/baseline/` — Classical ML Models

| File | Model | Purpose |
|---|---|---|
| `logistic.py` | Logistic Regression | Linear baseline; feature importance via coefficients |
| `naive_bayes.py` | Gaussian Naive Bayes | Probabilistic baseline |
| `random_forest.py` | Random Forest | Tree ensemble; feature importance via impurity |
| `xgboost_model.py` | XGBoost / LightGBM | Gradient boosting (expected strongest baseline) |
| `mlp.py` | Multi-Layer Perceptron | Neural network baseline (PyTorch); proves that simply adding layers without graph structure doesn't match GNN performance |

All baselines use concatenated feature vectors: `[drug_features ∥ disease_features ∥ pair_features]`.

### `src/models/gnn/` — Graph Neural Networks

| File | Model | What It Adds |
|---|---|---|
| `gcn.py` | GCN (2-layer) | Proves graph structure provides signal beyond flat features |
| `graphsage.py` | GraphSAGE | Inductive learning; can generalise to unseen drugs/diseases |
| `gat.py` | GAT | Attention over neighbourhood; learns which neighbours matter most |
| `rgcn.py` | RGCN | Relation-type-aware message passing (CbG ≠ CdG ≠ DaG); uses `RGCNConv` |
| `hgt.py` | HGT (**final model**) | Heterogeneous Graph Transformer; multi-head attention across different node and edge types; uses `HGTConv` |

All GNN models reuse the **same RDKit features** as node features. The only difference is how the graph structure is exploited.

### `src/scoring/` — NDPI Engine
- **ndpi.py**: Orchestrates all 4 components into final NDPI score (all inputs normalised to [0,1])
- **similarity.py**: RDKit Morgan fingerprint Tanimoto similarity (NOT molecular weight proxy)
- **literature.py**: PubMed evidence count + normalisation [0,1] + caching via Biopython Entrez API
- **equity.py**: WHO EML + DALY + affordability + generic availability + normalisation [0,1] via WHO GHO OData API

### `src/explainability/` — Interpretability
- **shap_explainer.py**: SHAP values for all baseline models (Logistic Regression, Random Forest, XGBoost, MLP)
- **gnn_explainer.py**: PyG GNNExplainer for the HGT model; generates subgraph visualisations showing Drug→Gene→Disease prediction paths

### `api/` — REST Backend
- Flask application factory pattern
- Stateless: loads HGT model once at startup, serves predictions
- Returns JSON with ranked drugs + NDPI component breakdown + model comparison data

### `frontend/` — React UI (Production)
- Connects to Flask API
- Pages: Rankings, Explore (graph viz), Model Comparison, About

### `streamlit_app/` — Legacy Prototype UI
- Deprecated in favor of React for production-ready interface
- Kept for reference or quick prototyping

---

## Data Flow

```
Raw Data Sources
  │
  └─► scripts/preprocess.py  (SINGLE ENTRY POINT)
        │
        ├─► data/processed/drugs.csv           (drug_id, smiles, descriptors, node_type)
        ├─► data/processed/diseases.csv        (disease_id, name, DALY, WHO, node_type)
        ├─► data/processed/genes.csv           (gene_id, symbol, node_type)
        ├─► data/processed/edges.csv           (source, target, relation, types)
        ├─► data/processed/drug_features.npy   (N_drugs × 2048 Morgan FP)
        └─► data/processed/graph_metadata.json (statistics, counts)
              │
              └─► src/data/graph_builder.py
                    │
                    └─► PyTorch Geometric HeteroData
                          │
                          ├─► scripts/train_baselines.py
                          │     └─► outputs/models/baseline_*.pkl
                          │
                          ├─► scripts/train_gnn.py
                          │     └─► outputs/models/hgt_best.pt (+ gcn, graphsage, gat, rgcn)
                          │
                          └─► scripts/evaluate.py
                                └─► outputs/model_comparison.csv (11-model table)
                                      │
                                      └─► main_pipeline.py
                                            │
                                            ├─► src/scoring/ndpi.py (HGT + Sim + Lit + Equity)
                                            └─► outputs/ndpi_results.csv
                                                  │
                                                  └─► API / React
```

---

## Key Design Decisions

1. **Single `preprocess.py` replaces 3 scattered scripts** — Eliminates data inconsistency. One script = one source of truth. Old scripts (`process_pubchem_bulk.py`, `featurize_pubchem.py`, `preprocess_all.py`) are deprecated.

2. **RDKit Morgan FP shared across ALL models** — Both baselines and GNNs use the same 2048-bit drug features. This ensures a fair comparison: the only variable is model architecture.

3. **HGT as the final proposed model** — Hetionet has multiple node types (Drug, Gene, Disease) and edge types (10+ relations). HGT is purpose-built for heterogeneous graphs with multi-head attention over different relation types.

4. **RGCN before HGT** — RGCN proves that relation-type awareness (CbG ≠ DaG) matters. HGT then adds transformer attention on top of that foundation.

5. **6 baselines before 5 GNNs** — Progressive evidence that graph structure provides genuine improvement. Prevents the reviewer objection: "Maybe XGBoost already solves this."

6. **NDPI formula uses fixed weights** — Interpretable to clinicians. Future work: learn weights with meta-learning.

7. **Positive labels from Hetionet CtD edges** — Known, curated drug-treats-disease relationships. 1:1 negative sampling from unconfirmed pairs.

8. **Literature scores are cached** — PubMed API has rate limits (3 req/sec). Cache all lookups to SQLite.

9. **No HAN implementation** — HGT subsumes HAN's capabilities and is a better fit for this graph topology. Avoids unnecessary model proliferation.
