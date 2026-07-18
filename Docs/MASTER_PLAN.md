# 🗺️ MASTER_PLAN.md — Complete Research & Engineering Roadmap

**Project:** VectorDrugMatch  
**Duration:** 8 Weeks (IAM Pro CS Internship 2026)  
**Team:** Nikita Ravindra · Arpit Pandey · Mukul Prasad · Swastik R Phadke

---

## 📋 Overview

This document is the single source of truth for the entire project execution plan. Every task, deliverable, and milestone is listed here. Each team member should read their section in full before starting.

The pipeline follows a **research-grade progressive model comparison** structure:

```
Phase 1 — Data Engineering       → Unified preprocessing, heterogeneous graph
Phase 2 — Feature Engineering    → RDKit Morgan FP, WHO/DALY, PubMed features
Phase 3 — Classical ML Baselines → 6 models (Random Guess → MLP)
Phase 4 — Graph Neural Networks  → 5 models (GCN → HGT)
Phase 5 — Explainability         → SHAP + GNNExplainer
Phase 6 — NDPI Integration       → HGT + Similarity + Literature + Equity
```

---

## 🎯 Project Goals

| Goal | Success Metric |
|---|---|
| Build working drug repurposing system | NDPI scores for all drug–disease pairs |
| Progressive model comparison (research-grade) | 6 baselines + 5 GNN models evaluated side-by-side |
| Best GNN outperforms best baseline | HGT ROC-AUC > best baseline ROC-AUC |
| Overall model quality | Final model ROC-AUC > 0.80 |
| Equity-aware ranking | NDPI includes 4 independent components |
| Explainable predictions | SHAP plots (baselines) + GNNExplainer (HGT) |
| Production-ready code | Dockerised, tested, CI passing |
| Research contribution | Full paper with progressive results table |

**Evaluation Metrics (applied to ALL models):**

| Metric | Purpose |
|---|---|
| ROC-AUC | Overall discrimination ability |
| PR-AUC | Performance under class imbalance |
| F1-score | Harmonic mean of precision & recall |
| Precision | Fraction of predicted positives that are correct |
| Recall | Fraction of actual positives that are found |
| MCC | Matthews Correlation Coefficient (balanced metric) |

---

## 👤 Team Roles & Ownership

| Member | Primary Role | Owns |
|---|---|---|
| **Nikita Ravindra** (Lead) | Data Engineering + Equity Scoring | `scripts/preprocess.py`, `src/data/`, `src/scoring/equity.py`, coordination |
| **Arpit Pandey** | ML Modelling (Baselines + GNNs) | `src/models/`, `scripts/train_baselines.py`, `scripts/train_gnn.py`, `scripts/evaluate.py` |
| **Mukul Prasad** | NDPI + Literature + Features | `src/scoring/ndpi.py`, `src/scoring/literature.py`, `src/features/` |
| **Swastik R Phadke** | Frontend + Integration | `frontend/`, `api/`, `docker-compose.yml` |

---

## 🔄 Distributed Team Workflow
Since the team is operating across 4 devices, strict adherence to this sequence is required. When a step says **[PUSH]**, you must commit and push your code so the next person can pull it. **NEVER push raw data or large processed files** to GitHub.

### 🤖 AI Agent Delegation
- **Human (Manual) Tasks:** Creating accounts, downloading gated datasets, running commands locally, testing the UI, reviewing results.
- **AI Agent Tasks:** Writing Python scripts, debugging runtime errors, writing React components, drafting documentation, formatting data, writing tests.

---

## 📁 Target Folder Structure

```
scripts/
    preprocess.py              ← Single unified preprocessing script
    train_baselines.py         ← Train all 6 baseline models
    train_gnn.py               ← Train all 5 GNN models
    evaluate.py                ← Unified evaluation across all models

src/
    data/
        graph_builder.py       ← Processed CSVs → PyTorch Geometric HeteroData

    features/
        drug.py                ← RDKit Morgan FP + molecular descriptors
        disease.py             ← DALY + WHO + NTD + ontology features
        graph.py               ← Node degree, centrality, Node2Vec embeddings

    models/
        baseline/
            logistic.py        ← Logistic Regression
            naive_bayes.py     ← Gaussian Naive Bayes
            random_forest.py   ← Random Forest
            xgboost_model.py   ← XGBoost / LightGBM
            mlp.py             ← Multi-Layer Perceptron (PyTorch)
        gnn/
            gcn.py             ← Graph Convolutional Network
            graphsage.py       ← GraphSAGE (inductive)
            gat.py             ← Graph Attention Network
            rgcn.py            ← Relational GCN (multi-relation)
            hgt.py             ← Heterogeneous Graph Transformer (final model)

    scoring/
        similarity.py          ← RDKit Tanimoto similarity
        literature.py          ← PubMed evidence scoring
        equity.py              ← WHO equity scoring
        ndpi.py                ← Final NDPI formula

    explainability/
        shap_explainer.py      ← SHAP for baseline models
        gnn_explainer.py       ← GNNExplainer for HGT

    utils/
        logging.py
        metrics.py             ← ROC-AUC, PR-AUC, F1, MCC, etc.
        visualisation.py
```

---

### Step 1: Initial Environment Setup (All Members)
*Every team member must do this independently on their own device.*

**Manual Tasks (Humans):**
- [x] Fork the repo and clone locally.
- [x] Create Python 3.10+ virtual environment.
- [x] Install dependencies: `pip install -r requirements.txt`.
- [ ] Verify PyTorch: `python -c "import torch; print(torch.__version__)"`.
- [ ] Verify RDKit: `python -c "from rdkit import Chem; print('RDKit OK')"`.
- [ ] Pull latest `main` branch to ensure you are up to date.

**AI Assistance:** 
- The AI agent can help debug environment/CUDA installation errors if you paste the logs.

---

### Step 2: Data Engineering — Unified Preprocessing (Nikita)
*Nikita builds the foundation. Others wait or work on standalone components.*

#### Step 2.1: Data Download (Manual)
- [x] **Nikita:** Pivot to PubChem (Instead of DrugBank).
- [ ] **Nikita:** Download the raw PubChem `CID-SMILES` compound mapping file.
- [ ] **Nikita:** Download DisGeNET curated associations TSV and Hetionet edges/nodes manually.
- [ ] **Nikita:** Place all files exactly in `data/raw/` (e.g., `data/raw/CID-SMILES`, `data/raw/hetionet-v1.0-edges.sif`).

#### Step 2.2: Unified Preprocessing Script (AI + Nikita)

> ⚠️ **CRITICAL CHANGE:** The old 3-script pipeline (`process_pubchem_bulk.py`, `featurize_pubchem.py`, `preprocess_all.py`) is replaced by a **single** `scripts/preprocess.py`. The old scripts are deprecated and should be deleted.

- [x] **AI Agent:** Write `scripts/preprocess.py` that does **ALL** of the following in one script:

**PubChem Processing:**
```
PubChem CID-SMILES
    │
    ├── Read CID + SMILES
    ├── Canonicalize SMILES (via RDKit)
    ├── Compute RDKit descriptors (MW, LogP, TPSA, HBD, HBA, rotatable bonds)
    ├── Compute Morgan Fingerprints (2048-bit)
    │
    └── Save: drugs.csv + drug_features.npy
```

**DisGeNET Processing:**
```
DisGeNET curated TSV
    │
    ├── Extract diseases (ID, name)
    ├── Extract genes (ID, symbol)
    ├── Extract gene-disease associations (with confidence scores)
    ├── Merge DALY / WHO flags
    │
    └── Save: diseases.csv, genes.csv
```

**Hetionet Processing (⭐ MOST CRITICAL FIX):**
```
Hetionet v1.0 edges
    │
    ├── Read ALL edges
    ├── KEEP ALL relation types:
    │     CtD  — Compound treats Disease          (positive labels)
    │     CpD  — Compound palliates Disease
    │     CbG  — Compound binds Gene
    │     CdG  — Compound downregulates Gene
    │     CuG  — Compound upregulates Gene
    │     DaG  — Disease associates Gene
    │     DuG  — Disease upregulates Gene
    │     DdG  — Disease downregulates Gene
    │     GiG  — Gene interacts Gene
    │     GrG  — Gene regulates Gene
    │
    ├── Parse source/target IDs (split on '::')
    ├── Assign node_type (Drug, Gene, Disease)
    │
    └── Save: edges.csv (with source, target, relation columns)
```

**Merge & Validate:**
```
All sources
    │
    ├── Cross-reference IDs between datasets
    ├── Remove orphan nodes (nodes with zero edges)
    ├── Check for duplicates
    ├── Verify edge references point to valid nodes
    │
    └── Save: graph_metadata.json (node counts, edge counts per type, statistics)
```

**Expected output files:**
| File | Contents |
|---|---|
| `data/processed/drugs.csv` | drug_id, name, smiles, mw, logp, tpsa, hbd, hba, rotatable_bonds, node_type |
| `data/processed/diseases.csv` | disease_id, name, daly_rate, daly_normalized, is_ntd, who_category, node_type |
| `data/processed/genes.csv` | gene_id, symbol, description, degree, node_type |
| `data/processed/edges.csv` | source_id, target_id, relation, source_type, target_type, confidence |
| `data/processed/drug_features.npy` | NumPy array (N_drugs × 2048) Morgan fingerprints |
| `data/processed/graph_metadata.json` | Summary statistics, node/edge counts by type |

- [x] **Nikita:** Run `python scripts/preprocess.py` locally.
- [x] **Nikita:** Verify output files exist and validate using metadata JSON.
- [x] **Nikita:** Delete old scripts: `process_pubchem_bulk.py`, `featurize_pubchem.py`.

**Expected validation targets:**
| Check | Expected |
|---|---|
| Drug nodes | 1,500+ (Hetionet compounds) |
| Disease nodes | 130+ (Hetionet diseases) |
| Gene nodes | 20,000+ (Hetionet genes) |
| Total edges | 50,000+ (across all relation types) |
| CtD edges (positive labels) | 750+ |
| CbG + CdG + CuG edges | 30,000+ |
| DaG edges | 12,000+ |
| Orphan nodes | 0 |
| Duplicate edges | 0 |

#### Step 2.3: Graph Construction (AI + Nikita)
- [x] **AI Agent:** Write `src/data/graph_builder.py` to convert processed CSVs into a PyTorch Geometric `HeteroData` object with proper node types and edge types.
- [x] **Nikita:** Run graph builder locally. Generate `HeteroData` object.
- [ ] **Nikita:** **[PUSH]** Commit and push `scripts/preprocess.py`, `src/data/`, and `data/external/` to GitHub. *(⚠️ Add `data/processed/` and `data/raw/` to `.gitignore`)*.

---

### Step 3: Feature Engineering (Mukul)
*Can happen in parallel with Step 2.*

#### Step 3.1: Drug Features — RDKit Pipeline (AI + Mukul)

> ⚠️ **WHY RDKit IS CRITICAL:** Without RDKit, every drug is just an ID number. The model memorises IDs instead of learning chemistry. RDKit converts SMILES strings into 2048-bit Morgan Fingerprints where each bit represents a chemical substructure (e.g., benzene ring, sulfur bond). This lets BOTH the baseline and the GNN learn: *"Drugs with this molecular substructure are more likely to treat diseases of this type."*

- [x] **AI Agent:** Write `src/features/drug.py`:
  - Morgan Fingerprint (2048-bit) via `AllChem.GetMorganFingerprintAsBitVect`
  - Molecular Weight (`Descriptors.MolWt`)
  - LogP (`Descriptors.MolLogP`)
  - TPSA (`Descriptors.TPSA`)
  - H-bond donors (`Descriptors.NumHDonors`)
  - H-bond acceptors (`Descriptors.NumHAcceptors`)
  - Rotatable bonds (`Descriptors.NumRotatableBonds`)
  - **Total: ~2055 features per drug**

#### Step 3.2: Disease Features (AI + Mukul)
- [x] **AI Agent:** Write `src/features/disease.py`:
  - DALY burden (normalised [0,1])
  - WHO NTD classification flag
  - Disease category / ontology embedding (optional)

#### Step 3.3: Graph Features (AI + Mukul)
- [x] **AI Agent:** Write `src/features/graph.py`:
  - Node degree per type
  - Betweenness centrality
  - Node2Vec embeddings (optional, for baselines)

#### Step 3.4: Scoring Functions (AI + Mukul)
- [x] **Mukul:** Test WHO GHO API & PubMed Entrez API.
- [x] **Mukul:** Install RDKit locally.
- [x] **AI Agent:** Write `src/scoring/literature.py` (Biopython Entrez caching & normalization).
- [x] **AI Agent:** Write `src/scoring/equity.py` (WHO GHO parsing & normalization).
- [x] **AI Agent:** Write `src/scoring/similarity.py` (RDKit Morgan fingerprint Tanimoto similarity — **NOT** molecular weight proxy).
- [ ] **Mukul:** Test these scripts independently with mock data.
- [ ] **Mukul:** **[PUSH]** Commit and push `src/features/` and `src/scoring/` to GitHub.

---

### Step 4: Classical ML Baselines — 6 Models (Arpit)
*Requires Nikita to finish Step 2 and Mukul to finish Step 3.*

> ⚠️ **WHY 6 BASELINES?** A research paper with only one baseline (Logistic Regression) is weak. Reviewers will ask: *"Maybe XGBoost already solves this — why do you need a GNN?"* By training 6 progressively complex baselines, you prove that the GNN's graph structure provides genuine improvement beyond what any flat feature model can achieve.

#### Step 4.1: Local Data Sync
- [ ] **Arpit:** Pull `main` branch to get preprocessing and feature scripts.
- [ ] **Arpit:** Run `python scripts/preprocess.py` locally to generate data files.

#### Step 4.2: Training Data Preparation
For each drug-disease pair, the training row is:

```
Drug RDKit Features (2048 Morgan FP + 7 descriptors = 2055)
    +
Disease Features (DALY + WHO + NTD = ~5)
    +
Pair Features (Literature score + Similarity score + Equity score)
    ↓
~2063 features per (drug, disease) pair
    ↓
Label: 1 (treats) or 0 (does not treat)
```

#### Step 4.3: Baseline Model Training (AI + Arpit)

| # | Model | Script | Purpose |
|---|---|---|---|
| 0 | Random Guess | `scripts/train_baselines.py` | Sanity check (ROC-AUC ≈ 0.50) |
| 1 | Majority Class | `scripts/train_baselines.py` | Sanity check (always predicts majority class) |
| 2 | Logistic Regression | `src/models/baseline/logistic.py` | Linear baseline |
| 3 | Naive Bayes | `src/models/baseline/naive_bayes.py` | Probabilistic baseline |
| 4 | Random Forest | `src/models/baseline/random_forest.py` | Tree ensemble |
| 5 | XGBoost / LightGBM | `src/models/baseline/xgboost_model.py` | Gradient boosting (expected strongest baseline) |
| 6 | MLP | `src/models/baseline/mlp.py` | Neural network baseline (PyTorch) |

- [x] **AI Agent:** Write `src/models/baseline/logistic.py`.
- [x] **AI Agent:** Write `src/models/baseline/naive_bayes.py`.
- [x] **AI Agent:** Write `src/models/baseline/random_forest.py`.
- [x] **AI Agent:** Write `src/models/baseline/xgboost_model.py`.
- [x] **AI Agent:** Write `src/models/baseline/mlp.py`.
- [x] **AI Agent:** Write `scripts/train_baselines.py` (trains all 6, saves metrics).
- [ ] **Arpit:** Train all baselines **locally** (or on Colab if MLP is too slow). Record metrics (ROC-AUC, PR-AUC, F1, MCC).
- [ ] **Arpit:** **[PUSH]** Commit `src/models/baseline/` and `scripts/train_baselines.py`.

**Expected results range:**

| Model | Expected ROC-AUC |
|---|---|
| Random Guess | ~0.50 |
| Majority Class | ~0.50 |
| Logistic Regression | 0.65–0.75 |
| Naive Bayes | 0.60–0.70 |
| Random Forest | 0.70–0.80 |
| XGBoost | 0.75–0.85 |
| MLP | 0.72–0.82 |

---

### Step 5: Graph Neural Networks — 5 Models (Arpit)
*Builds on Step 4. Only start after baselines are stable.*

> ⚠️ **WHY 5 GNNs?** Each model adds a capability: GCN proves graph helps → GraphSAGE adds inductive learning → GAT adds attention → RGCN adds relation awareness → HGT combines everything for heterogeneous graphs. This progression tells a clear story in the paper.

#### Step 5.1: Graph Baseline — GCN

| # | Model | What It Adds | File |
|---|---|---|---|
| 1 | GCN | Proves graph structure helps | `src/models/gnn/gcn.py` |
| 2 | GraphSAGE | Inductive learning (generalises to unseen nodes) | `src/models/gnn/graphsage.py` |
| 3 | GAT | Attention over neighbourhood (learns edge importance) | `src/models/gnn/gat.py` |
| 4 | RGCN | Multi-relation awareness (CbG ≠ CdG ≠ DaG) | `src/models/gnn/rgcn.py` |
| 5 | HGT | Heterogeneous Graph Transformer (**final proposed model**) | `src/models/gnn/hgt.py` |

- [x] **AI Agent:** Write `src/models/gnn/gcn.py` (PyTorch Geometric 2-layer GCN).
- [x] **AI Agent:** Write `src/models/gnn/graphsage.py`.
- [x] **AI Agent:** Write `src/models/gnn/gat.py`.
- [x] **AI Agent:** Write `src/models/gnn/rgcn.py` (uses `RGCNConv` — relation-type-aware message passing).
- [x] **AI Agent:** Write `src/models/gnn/hgt.py` (uses `HGTConv` — heterogeneous attention across node/edge types).
- [x] **AI Agent:** Write `scripts/train_gnn.py` (trains all 5, saves metrics + model weights).
- [ ] **Arpit:** Upload `data/processed/` files to **Google Colab**.
- [ ] **Arpit:** Train all GNN models on **Google Colab (using GPU)**. Tune hyperparameters.
- [ ] **Arpit:** Download and save best model weights to `outputs/models/` locally.
- [ ] **Arpit:** **[PUSH]** Commit `src/models/gnn/` and `scripts/train_gnn.py` along with downloaded weights.

**Why RGCN and HGT matter:**

The same RDKit fingerprints are reused as drug node features. The difference:

```
Logistic Regression:
    RDKit Features → Flat prediction (each drug treated independently)

GCN:
    RDKit Features → Drug Node → Homogeneous graph → Message passing → Prediction

RGCN:
    RDKit Features → Drug Node → Heterogeneous graph (relation-aware) → Prediction
    (CbG edges pass different messages than DaG edges)

HGT:
    RDKit Features → Drug Node → Heterogeneous graph + Transformer attention → Prediction
    (Learns WHICH relations and WHICH neighbours matter most)
```

**Expected results (GNNs should beat baselines):**

| Model | Expected ROC-AUC |
|---|---|
| GCN | 0.78–0.85 |
| GraphSAGE | 0.79–0.86 |
| GAT | 0.80–0.87 |
| RGCN | 0.83–0.89 |
| **HGT** | **0.85–0.92** |

---

### Step 6: NDPI Integration & Full Pipeline (Nikita & Mukul)
*Requires Steps 3, 4 & 5.*

#### Step 6.1: Unified Evaluation (AI + Arpit)
- [x] **AI Agent:** Write `scripts/evaluate.py` that produces a single comparison table across ALL 11 models.

**Expected output format:**
```
┌──────────────────────┬──────────┬──────────┬────────┬───────┬──────┐
│ Model                │ ROC-AUC  │ PR-AUC   │ F1     │ MCC   │ Type │
├──────────────────────┼──────────┼──────────┼────────┼───────┼──────┤
│ Random Guess         │ 0.500    │ 0.xxx    │ 0.xxx  │ 0.xxx │ Base │
│ Majority Class       │ 0.500    │ 0.xxx    │ 0.xxx  │ 0.xxx │ Base │
│ Logistic Regression  │ 0.7xx    │ 0.xxx    │ 0.xxx  │ 0.xxx │ Base │
│ Naive Bayes          │ 0.6xx    │ 0.xxx    │ 0.xxx  │ 0.xxx │ Base │
│ Random Forest        │ 0.7xx    │ 0.xxx    │ 0.xxx  │ 0.xxx │ Base │
│ XGBoost              │ 0.8xx    │ 0.xxx    │ 0.xxx  │ 0.xxx │ Base │
│ MLP                  │ 0.7xx    │ 0.xxx    │ 0.xxx  │ 0.xxx │ Base │
│ GCN                  │ 0.8xx    │ 0.xxx    │ 0.xxx  │ 0.xxx │ GNN  │
│ GraphSAGE            │ 0.8xx    │ 0.xxx    │ 0.xxx  │ 0.xxx │ GNN  │
│ GAT                  │ 0.8xx    │ 0.xxx    │ 0.xxx  │ 0.xxx │ GNN  │
│ RGCN                 │ 0.8xx    │ 0.xxx    │ 0.xxx  │ 0.xxx │ GNN  │
│ HGT ★               │ 0.9xx    │ 0.xxx    │ 0.xxx  │ 0.xxx │ GNN  │
└──────────────────────┴──────────┴──────────┴────────┴───────┴──────┘
```

#### Step 6.2: Full Pipeline Assembly
- [ ] **Nikita & Mukul:** Pull `main` branch (to get Arpit's models and Mukul's scoring functions).
- [ ] **AI Agent:** Write `src/scoring/ndpi.py` to combine **HGT** prediction, Similarity, Literature, and Equity scores.

**Updated NDPI Formula (uses HGT as the ML component):**
```
NDPI = 0.35 × HGT_score
     + 0.20 × Similarity_score   (Tanimoto on Morgan FP)
     + 0.20 × Literature_score   (PubMed evidence, normalised)
     + 0.25 × Equity_score       (WHO DALY + EML + affordability)
```

- [ ] **AI Agent:** Write `main_pipeline.py` as a single master script.
- [ ] **Nikita:** Run `main_pipeline.py` to generate `outputs/ndpi_results.csv`.
- [ ] **Nikita/Mukul:** **[PUSH]** Commit `main_pipeline.py` and the final `ndpi_results.csv`.

---

### Step 7: Flask API Development (Swastik)
*Requires Step 6.*

#### Step 7.1: API Backend
- [ ] **Swastik:** Pull `main` branch (to get the final CSV results).
- [ ] **AI Agent:** Write `api/app.py` (Flask backend) to serve the contents of `ndpi_results.csv`.
- [ ] **Swastik:** Run Flask locally (`python api/app.py`) and test the endpoints (`/diseases`, `/predict`).
- [ ] **Swastik:** **[PUSH]** Commit `api/` folder.

---

### Step 8: React Frontend & Docker (Swastik)
*Builds on Step 7.*

#### Step 8.1: Frontend UI
- [ ] **AI Agent:** Write React components (`frontend/src/`) for the ranking tables, NDPI breakdown charts, and model comparison view.
- [ ] **Swastik:** Run React locally and verify connection to Flask.

#### Step 8.2: Dockerization
- [ ] **AI Agent:** Write `docker-compose.yml` to spin up both React and Flask together.
- [ ] **Swastik:** Run `docker-compose up` to verify production deployment.
- [ ] **Swastik:** **[PUSH]** Commit `frontend/` and `docker-compose.yml`.

---

### Step 9: Explainability (Arpit & Mukul)
*Parallel to Step 8.*

#### Step 9.1: SHAP for Baseline Models
- [ ] **Mukul:** Have AI write SHAP explainers for **all baseline models** (not just Logistic Regression).
- [ ] **AI Agent:** Write `src/explainability/shap_explainer.py` — generates SHAP summary plots for Logistic Regression, Random Forest, XGBoost, and MLP.

#### Step 9.2: GNNExplainer for HGT
- [ ] **Arpit:** Pull `main` branch.
- [ ] **AI Agent:** Write `src/explainability/gnn_explainer.py` — uses PyG's GNNExplainer on the HGT model to generate subgraph visualisations showing which Drug→Gene→Disease paths drive each prediction.
- [ ] **Arpit:** Run GNNExplainer to generate subgraph visualisations. **[PUSH]**
- [ ] **Mukul:** **[PUSH]**

---

### Step 10: Research Paper & Case Studies (All)
- [ ] **Nikita:** Draft abstract and introduction based on AI summaries.
- [ ] **Arpit:** Write methodology for GNN progression (GCN → HGT) — include mathematical formulas for each architecture.
- [ ] **Arpit:** Write results section with the full 11-model comparison table.
- [ ] **Mukul:** Write methodology for NDPI components (Similarity, Literature, Equity).
- [ ] **Mukul:** Write discussion on RDKit feature importance (SHAP analysis).
- [ ] **Swastik:** Capture screenshots of the UI for the paper.
- [ ] **AI Agent:** Can help proofread, format citations in BibTeX, and generate markdown tables.

**Paper results table structure:**

| Stage | Models |
|---|---|
| **Sanity Check** | Random Guess, Majority Class |
| **Classical ML Baselines** | Logistic Regression, Naive Bayes, Random Forest, XGBoost, MLP |
| **Graph Baselines** | GCN, GraphSAGE, GAT |
| **Relation-aware Graph Models** | RGCN |
| **Final Proposed Model** | **HGT + NDPI** |

---

## ⚠️ Common Mistakes to Avoid (Across Devices)

| Mistake | Prevention |
|---|---|
| **Git Merge Conflicts** | Always pull before you start working. Only edit files owned by your role. |
| **Pushing Data** | NEVER commit `data/raw/` or `data/processed/`. The repo will freeze. |
| **Environment Mismatch** | Always use the `requirements.txt`. If you add a library, tell everyone to reinstall. |
| **Hardcoding Paths** | Use `pathlib.Path` so code runs on both Mac (Swastik) and Windows (Nikita/Arpit). |
| **Using fake chemistry features** | NEVER use `smiles_length`, `num_C`, `num_O` etc. Use RDKit Morgan Fingerprints (2048-bit). |
| **Losing relation types** | NEVER flatten edges to just `source → target`. Always keep the `relation` column. |
| **Single baseline** | NEVER submit with only Logistic Regression. Train all 6 baselines for a fair comparison. |
| **Training GNN on bad data** | NEVER start GNN training until preprocessing produces 50,000+ edges with proper relation types. |

---

## 🔑 Key Design Decisions

| Decision | Rationale |
|---|---|
| **Single `preprocess.py`** | Eliminates data inconsistencies from scattered scripts. One script = one source of truth for data. |
| **RDKit Morgan FP shared across ALL models** | Fair comparison: baselines and GNNs use the same drug features. The only difference is graph structure. |
| **6 baselines before any GNN** | Proves the GNN's improvement comes from graph structure, not just better hyperparameters. |
| **RGCN before HGT** | RGCN proves relation types matter. HGT adds transformer attention on top. Progressive evidence. |
| **HGT as final model** | Best fit for heterogeneous biomedical graphs with multiple node/edge types. |
| **No HAN** | HGT subsumes HAN's capabilities. HGT is a better fit for this graph structure. |

---

*This document should be reviewed at every weekly team standup. Update task checkboxes as you go.*
