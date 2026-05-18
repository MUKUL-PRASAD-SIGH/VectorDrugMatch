# 🗺️ MASTER_PLAN.md — Complete Research & Engineering Roadmap

**Project:** VectorDrugMatch  
**Duration:** 8 Weeks (IAM Pro CS Internship 2026)  
**Team:** Nikita Ravindra · Arpit Pandey · Mukul Prasad · Swastik R Phadke

---

## 📋 Overview

This document is the single source of truth for the entire project execution plan. Every task, deliverable, and milestone is listed here. Each team member should read their section in full before starting.

---

## 🎯 Project Goals

| Goal | Success Metric |
|---|---|
| Build working drug repurposing system | NDPI scores for all drug–disease pairs |
| Outperform random baseline | GNN ROC-AUC > 0.80 |
| Equity-aware ranking | NDPI includes 4 independent components |
| Explainable predictions | SHAP plots + GNNExplainer output |
| Production-ready code | Dockerised, tested, CI passing |
| Research contribution | Abstract/methods section written |

---

## 👤 Team Roles & Ownership

| Member | Primary Role | Owns |
|---|---|---|
| **Nikita Ravindra** (Lead) | Data Engineering + Equity Scoring | `src/data/`, `src/scoring/equity.py`, coordination |
| **Arpit Pandey** | GNN Modelling | `src/models/`, training scripts, evaluation |
| **Mukul Prasad** | NDPI + Literature | `src/scoring/ndpi.py`, `src/scoring/literature.py` |
| **Swastik R Phadke** | Frontend + Integration | `frontend/`, `api/`, `docker-compose.yml` |

---

## 📅 Week-by-Week Roadmap

---

### WEEK 1 — Environment Setup & Raw Data

**Goal:** Everyone has a working dev environment and all data downloaded.

#### All Team Members (Day 1)
- [ ] Fork the repo and clone locally
- [ ] Create Python 3.10+ virtual environment
- [ ] Install all requirements: `pip install -r requirements.txt`
- [ ] Verify PyTorch and PyTorch Geometric installed correctly:
  ```bash
  python -c "import torch; import torch_geometric; print('OK')"
  ```
- [ ] Register free accounts: DrugBank, DisGeNET

#### Nikita (Data Lead)
- [ ] Download DrugBank vocabulary CSV
- [ ] Download DisGeNET curated associations TSV
- [ ] Download Hetionet edges and nodes TSVs
- [ ] Run `python scripts/preprocess_all.py`
- [ ] Verify row counts:
  - `drugs.csv` → at least 14,000 rows
  - `diseases.csv` → at least 20,000 rows
  - `edges.csv` → at least 100,000 rows

#### Arpit (Model Lead)
- [ ] Download ChEMBL SQLite (5 GB, start download early)
- [ ] Run notebook `01_data_exploration.ipynb`
- [ ] Document data statistics (node/edge counts, class balance)

#### Mukul (Scoring Lead)
- [ ] Test WHO GHO API — fetch DALY data for 5 NTDs
- [ ] Verify PubMed Entrez access: run `pubmed_count("ivermectin", "lymphatic filariasis")`
- [ ] Install RDKit: `conda install -c conda-forge rdkit` or `pip install rdkit`

#### Swastik (Frontend Lead)
- [ ] Install Node.js 18+ and verify: `node --version`
- [ ] Set up React development environment: Install Node.js, npm
- [ ] Create React app: `npx create-react-app frontend`
- [ ] Set up React project: `cd frontend && npm install`

**Week 1 Deliverable:** All tools installed, raw data downloaded, first notebook run.

---

### WEEK 2 — Knowledge Graph + Baseline Model

**Goal:** Working knowledge graph and first ML predictions.

#### Nikita
- [ ] Clean all CSVs: remove nulls, deduplicate, normalise
- [ ] Add `on_who_eml`, `generic_available`, `affordability_score` to drugs.csv
- [ ] Add `is_ntd`, `daly_rate` columns to diseases.csv
- [ ] Produce summary statistics report (mean, std, missing %)

#### Arpit
- [ ] Implement `src/data/graph_builder.py`
  - Use NetworkX to build the heterogeneous graph
  - Convert to PyG `HeteroData` object
  - Save as `edge_index.npy` and `node_features.npy`
- [ ] Run graph visualisation (`notebooks/02_graph_construction.ipynb`)
- [ ] Implement `src/models/baseline.py` (Logistic Regression)
  - Feature vector: concatenate drug + disease features + element-wise product
  - Train/test split: 80/20
  - Report: ROC-AUC, Precision, Recall, F1
- [ ] **Target: ROC-AUC > 0.65**

#### Mukul
- [ ] Implement `src/scoring/equity.py` — manual equity score for 10 drugs
  ```python
  equity = (0.30 * who_eml_flag
           + 0.20 * generic_available
           + 0.20 * affordability
           + 0.20 * daly_burden_norm
           + 0.10 * who_ntd_flag)
  ```
- [ ] Implement basic `src/scoring/ndpi.py` with placeholder GNN score

#### Swastik
- [ ] Build React UI that connects to Flask API for NDPI results
- [ ] Disease dropdown → filter table → show top-10 drugs
- [ ] Add basic bar chart

**Week 2 Deliverable:**
- 4 clean CSV files
- NetworkX graph with 1000+ nodes visualised
- Logistic Regression ROC-AUC > 0.65 reported
- Streamlit showing NDPI table

---

### WEEK 3 — Graph Neural Network

**Goal:** Train GCN, beat the baseline.

#### Arpit
- [ ] Implement `src/models/gcn.py` using PyTorch Geometric:
  ```python
  class DrugDiseaseGCN(torch.nn.Module):
      def __init__(self, in_channels, hidden_channels, out_channels):
          super().__init__()
          self.conv1 = GCNConv(in_channels, hidden_channels)
          self.conv2 = GCNConv(hidden_channels, out_channels)

      def forward(self, x, edge_index):
          x = F.relu(self.conv1(x, edge_index))
          x = F.dropout(x, p=0.5, training=self.training)
          return self.conv2(x, edge_index)
  ```
- [ ] Implement `src/models/link_predictor.py` (dot product scoring)
- [ ] Train GCN with Adam optimizer, lr=0.01, 200 epochs
- [ ] Try hidden dimensions: 8, 16, 32 — report best
- [ ] **Target: ROC-AUC > 0.80**
- [ ] Save best model: `outputs/models/gcn_best.pt`

#### Nikita
- [ ] Integrate WHO GHO API into equity scoring
- [ ] Pull DALY rates for all 10 NTDs, normalise [0,1]
- [ ] Update diseases.csv with real DALY values

#### Mukul
- [ ] Wire GCN scores into NDPI formula
- [ ] Compute NDPI for all drug–disease pairs
- [ ] Generate `outputs/ndpi_results.csv`

#### Swastik
- [ ] Add NDPI bar chart to React UI (top-5 drugs per disease)
- [ ] Display GCN score vs NDPI score side by side

**Week 3 Deliverable:**
- GCN trained, ROC-AUC > 0.80
- NDPI computed for all pairs
- React UI showing NDPI scores

---

### WEEK 4 — Molecular Similarity + Literature Scoring

**Goal:** Complete all 4 NDPI components.

#### Mukul
- [ ] Implement `src/scoring/similarity.py`:
  ```python
  from rdkit import Chem
  from rdkit.Chem import AllChem, DataStructs

  def tanimoto_similarity(smiles1: str, smiles2: str) -> float:
      mol1 = Chem.MolFromSmiles(smiles1)
      mol2 = Chem.MolFromSmiles(smiles2)
      if mol1 is None or mol2 is None:
          return 0.0
      fp1 = AllChem.GetMorganFingerprintAsBitVect(mol1, radius=2, nBits=2048)
      fp2 = AllChem.GetMorganFingerprintAsBitVect(mol2, radius=2, nBits=2048)
      return DataStructs.TanimotoSimilarity(fp1, fp2)
  ```
- [ ] For each drug, compute max Tanimoto similarity to known NTD drugs
- [ ] Implement `src/scoring/literature.py` with PubMed Entrez
- [ ] Cache literature scores to avoid repeated API calls

#### Arpit
- [ ] Implement `src/models/gat.py` — Graph Attention Network
  ```python
  from torch_geometric.nn import GATConv
  class DrugDiseaseGAT(torch.nn.Module):
      def __init__(self, in_channels, hidden_channels, out_channels, heads=4):
          super().__init__()
          self.conv1 = GATConv(in_channels, hidden_channels, heads=heads, dropout=0.6)
          self.conv2 = GATConv(hidden_channels * heads, out_channels, heads=1)
  ```
- [ ] Compare GCN vs GAT on same dataset
- [ ] Run 5-fold cross-validation on best model

#### Nikita
- [ ] Implement `src/scoring/equity.py` with all 5 sub-components
- [ ] Fetch real drug price proxies from NADAC or MSF data
- [ ] Write equity score unit tests (`tests/test_ndpi.py`)

#### Swastik
- [ ] Add "NDPI Component Breakdown" tab to React UI
  - Stacked bar: GNN / Similarity / Literature / Equity contributions
- [ ] Add drug detail popup with SMILES visualisation

**Week 4 Deliverable:**
- All 4 NDPI components working with real data
- RDKit Tanimoto running
- PubMed API literature scores cached
- NDPI component breakdown chart in React UI

---

### WEEK 5 — Explainability (XAI)

**Goal:** Understand WHY the model makes its predictions.

#### Arpit
- [ ] Implement `src/explainability/gnn_explainer.py`:
  ```python
  from torch_geometric.explain import Explainer, GNNExplainer

  explainer = Explainer(
      model=model,
      algorithm=GNNExplainer(epochs=200),
      explanation_type='model',
      node_mask_type='attributes',
      edge_mask_type='object',
  )

  explanation = explainer(x, edge_index, index=node_idx)
  print(f"Generated explanations in {explanation.available_explanations}")
  ```
- [ ] Generate top-5 important edges for 10 drug-disease predictions
- [ ] Visualise explanation subgraph

#### Mukul
- [ ] Implement SHAP for Logistic Regression baseline:
  ```python
  import shap

  explainer = shap.LinearExplainer(model, X_train, feature_perturbation="interventional")
  shap_values = explainer.shap_values(X_test)
  shap.summary_plot(shap_values, X_test, feature_names=feature_names)
  ```
- [ ] Identify top features driving predictions per disease
- [ ] Write explainability section for paper

#### Swastik
- [ ] Add "Explainability" tab to React UI:
  - SHAP bar chart per prediction
  - NDPI component radar chart
- [ ] Add hover tooltips showing evidence supporting each prediction

#### Nikita
- [ ] Run 5 full case studies (one per major NTD)
- [ ] Document: what drug did the model find? what is the NDPI? is it clinically plausible?
- [ ] Cross-reference with published clinical trials on ClinicalTrials.gov

**Week 5 Deliverable:**
- SHAP plots for baseline
- GNNExplainer subgraphs for top predictions
- Explainability tab live in React UI
- 5 case studies documented

---

### WEEK 6 — Integration Testing + Pipeline Cleanup

**Goal:** Everything works end-to-end, code is clean and tested.

#### All Members
- [ ] Write/update docstrings for all functions
- [ ] Write unit tests for your modules (target: 80% coverage)
- [ ] Run `pytest tests/ -v` and fix all failures

#### Arpit
- [ ] Implement `src/models/ensemble.py`:
  - Combine GCN + Logistic Regression + Similarity score
  - Use weighted average or stacking
- [ ] Evaluate ensemble vs individual models
- [ ] Produce final model comparison table

#### Nikita
- [ ] Finalise `main_pipeline.py` — single entry point that:
  1. Loads data
  2. Builds KG
  3. Trains GCN (or loads saved model)
  4. Computes all NDPI components
  5. Outputs ranked CSV
- [ ] Add CLI arguments: `--disease`, `--top-k`, `--skip-training`

#### Mukul
- [ ] Run full pipeline on all 10 NTDs
- [ ] Produce final ranked results table
- [ ] Validate: do top predictions match known repurposed drugs from literature?

#### Swastik
- [ ] Build Flask REST API (`api/`)
  - `GET /diseases` — list all diseases
  - `GET /drugs` — list all drugs
  - `POST /predict` — accepts `{"disease_id": "...", "top_k": 10}` → returns ranked drugs
- [ ] Write API documentation (`API.md`)
- [ ] Run integration tests with `tests/test_api.py`

**Week 6 Deliverable:**
- Full pipeline runs: `python main_pipeline.py`
- All tests passing
- Flask API with 3 endpoints
- Clean, documented codebase

---

### WEEK 7 — Production Frontend + Docker

**Goal:** Production-quality UI and containerised deployment.

#### Swastik
- [ ] Build React frontend (`frontend/src/`):
  - Page 1: **Rankings** — disease selector + drug ranking table + NDPI bar chart
  - Page 2: **Explore** — graph visualisation of drug–gene–disease connections
  - Page 3: **About** — project description, team, methodology
- [ ] Connect React to Flask API
- [ ] Write `docker-compose.yml`:
  ```yaml
  version: '3.8'
  services:
    api:
      build: .
      ports: ["5000:5000"]
      volumes: ["./data:/app/data", "./outputs:/app/outputs"]
    frontend:
      build: ./frontend
      ports: ["3000:3000"]
      depends_on: [api]
  ```
- [ ] Test full Docker build: `docker-compose up --build`

#### Arpit
- [ ] Scale up data: expand from 15 drugs to full NTD-relevant set (100+ drugs)
- [ ] Retrain GCN on expanded graph, report updated AUC
- [ ] Add hyperparameter config file: `config/model_config.yaml`

#### Nikita
- [ ] Add GitHub Actions CI: `.github/workflows/test.yml`
  - Run `pytest` on every push
  - Check code formatting with `black`
- [ ] Set up environment variables properly (`.env.example`)

#### Mukul
- [ ] Scale up literature scoring to all drug–disease pairs
- [ ] Export results to `outputs/ndpi_results_full.csv`
- [ ] Produce ROC curve plots and confusion matrix figures

**Week 7 Deliverable:**
- React frontend live at localhost:3000
- Docker-compose builds and runs
- CI/CD pipeline active on GitHub

---

### WEEK 8 — Paper Draft + Final Polish

**Goal:** Submit internship report, prepare for publication.

#### All Members
- [ ] Write paper sections (target: IEEE CS conference format):
  - Abstract (150 words) — Nikita
  - Introduction (1 page) — Nikita
  - Related Work (1 page) — Mukul
  - Methodology — NDPI, KG construction, GNN (2 pages) — Arpit + Mukul
  - Experiments & Results (1.5 pages) — Arpit
  - Case Studies (1 page) — Nikita
  - Discussion & Future Work (0.5 page) — Mukul
  - Conclusion (0.25 page) — All

#### Swastik
- [ ] Create project demo video (3–5 minutes)
- [ ] Polish README with badges, screenshots, demo GIF
- [ ] Publish to GitHub with public visibility

#### Final Checklist (All)
- [ ] `python main_pipeline.py` runs cleanly from scratch
- [ ] `docker-compose up` builds and serves UI
- [ ] All 5 case studies in `notebooks/07_case_studies.ipynb`
- [ ] Paper draft ready for advisor review
- [ ] GitHub repo public with complete README

---

## ✅ Milestone Checklist Summary

### End of Week 2
- [ ] 4 clean CSV files created
- [ ] NetworkX graph with 1000+ nodes visualised
- [ ] Logistic Regression ROC-AUC > 0.65
- [ ] React UI showing NDPI table

### End of Week 4
- [ ] GCN ROC-AUC > 0.80
- [ ] All 4 NDPI components computed
- [ ] WHO GHO equity data integrated
- [ ] RDKit Tanimoto similarity working

### End of Week 6
- [ ] PubMed literature scoring working
- [ ] SHAP explainability in Streamlit
- [ ] Flask API with 3 endpoints
- [ ] All tests passing

### End of Week 8
- [ ] Full pipeline: `python main_pipeline.py`
- [ ] Docker-compose running
- [ ] React frontend with 3 tabs
- [ ] 5 case studies documented
- [ ] Paper draft complete

---

## ⚠️ Common Mistakes to Avoid

| Mistake | Prevention |
|---|---|
| Data leakage | Never include `label` column as a feature — only as target |
| Wrong edge direction | `Drug→Gene` ≠ `Gene→Drug`. Always verify source/target |
| NDPI weights not summing to 1 | Add assertion: `assert abs(sum(weights) - 1.0) < 1e-6` |
| Training on test data | Always use `cross_val_predict`, never `.fit()` then `.predict()` on same set |
| PubMed rate limiting | Add `time.sleep(0.34)` between calls (max 3 req/sec) |
| Too many negative samples | Maintain 1:1 positive:negative ratio |
| Downloading huge datasets first | Start with the sample 15-drug dataset, scale in Week 7 |
| Hardcoding file paths | Use `pathlib.Path` + config file |
| Not caching API calls | Cache PubMed and WHO GHO results locally |

---

## 🔮 Production Extensions (Post-Internship)

These are stretch goals and future research directions:

1. **Multi-omics integration** — add transcriptomic data (Gene Expression Omnibus)
2. **Side effect prediction** — integrate SIDER database to flag toxic repurposings
3. **Federated learning** — allow hospitals to contribute data without sharing patient records
4. **Active learning** — prioritise uncertain drug–disease pairs for wet lab validation
5. **Time-series DALY** — track NDPI changes as disease burden evolves
6. **Drug combination** — predict synergistic drug pairs for complex NTDs
7. **Geographic targeting** — country-level NDPI adjusted for local drug availability
8. **Clinical trial matching** — link top predictions to open ClinicalTrials.gov entries

---

*This document should be reviewed at every weekly team standup. Update task checkboxes as you go.*
