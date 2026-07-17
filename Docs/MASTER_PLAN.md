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

## 🔄 Distributed Team Workflow
Since the team is operating across 4 devices, strict adherence to this sequence is required. When a step says **[PUSH]**, you must commit and push your code so the next person can pull it. **NEVER push raw data or large processed files** to GitHub.

### 🤖 AI Agent Delegation
- **Human (Manual) Tasks:** Creating accounts, downloading gated datasets, running commands locally, testing the UI, reviewing results.
- **AI Agent Tasks:** Writing Python scripts, debugging runtime errors, writing React components, drafting documentation, formatting data, writing tests.

---

### Step 1: Initial Environment Setup (All Members)
*Every team member must do this independently on their own device.*

**Manual Tasks (Humans):**
- [x] Fork the repo and clone locally.
- [x] Create Python 3.10+ virtual environment.
- [x] Install dependencies: `pip install -r requirements.txt`.
- [ ] Verify PyTorch: `python -c "import torch; print(torch.__version__)"`.
- [ ] Pull latest `main` branch to ensure you are up to date.

**AI Assistance:** 
- The AI agent can help debug environment/CUDA installation errors if you paste the logs.

---

### Step 2: Data Acquisition & Preprocessing (Nikita)
*Nikita builds the foundation. Others wait or work on standalone components.*

#### Step 2.1: Data Download (Manual)
- [x] **Nikita:** Pivot to PubChem (Instead of DrugBank).
- [ ] **Nikita:** Download the raw PubChem `CID-SMILES` compound mapping file.
- [ ] **Nikita:** Download DisGeNET curated associations TSV and Hetionet edges/nodes manually.
- [ ] **Nikita:** Place all of these files exactly in the `data/raw/` folder (e.g., `data/raw/CID-SMILES`). 

#### Step 2.2: Preprocessing Script Generation (AI + Nikita)
- [ ] **AI Agent:** Write/refine `scripts/preprocess_all.py` to clean and merge PubChem, DisGeNET, and Hetionet into processed CSVs.
- [ ] **Nikita:** Run the script locally. Verify output files (`drugs.csv`, `diseases.csv`, `edges.csv`) exist in `data/processed/`.

#### Step 2.3: Graph Construction (AI + Nikita)
- [ ] **AI Agent:** Write `src/data/graph_builder.py` to convert processed CSVs into a PyTorch Geometric `HeteroData` object.
- [ ] **Nikita:** Run graph builder locally. Generate `node_features.npy` and `edge_index.npy`.
- [ ] **Nikita:** **[PUSH]** Commit and push `scripts/`, `src/data/`, and `data/external/` to GitHub. *(⚠️ Add `data/processed/` and `data/raw/` to `.gitignore`)*.

---

### Step 3: Scoring Functions Setup (Mukul)
*Can happen in parallel with Step 2.*

#### Step 3.1: APIs & Infrastructure
- [x] **Mukul:** Test WHO GHO API & PubMed Entrez API.
- [x] **Mukul:** Install RDKit locally.

#### Step 3.2: Scoring Implementations (AI + Mukul)
- [ ] **AI Agent:** Write `src/scoring/literature.py` (Biopython Entrez caching & normalization).
- [ ] **AI Agent:** Write `src/scoring/equity.py` (WHO GHO parsing & normalization).
- [ ] **AI Agent:** Write `src/scoring/similarity.py` (RDKit Morgan fingerprints).
- [ ] **Mukul:** Test these scripts independently with mock data on your device.
- [ ] **Mukul:** **[PUSH]** Commit and push `src/scoring/` to GitHub.

---

### Step 4: Baseline Model Training (Arpit)
*Requires Nikita to finish Step 2.*

#### Step 4.1: Local Data Sync
- [ ] **Arpit:** Pull `main` branch to get Nikita's scripts.
- [ ] **Arpit:** Run `scripts/preprocess_all.py` locally to generate the data files on your machine.

#### Step 4.2: Logistic Regression Baseline (AI + Arpit)
- [ ] **AI Agent:** Write `src/models/baseline.py`.
- [ ] **Arpit:** Train baseline model locally. Record ROC-AUC score.
- [ ] **Arpit:** **[PUSH]** Commit and push `src/models/baseline.py`.

---

### Step 5: Advanced GNN Training (Arpit)
*Builds on Step 4.*

#### Step 5.1: GCN Implementation
- [ ] **AI Agent:** Write `src/models/gcn.py` (PyTorch Geometric 2-layer GCN).
- [ ] **Arpit:** Train GCN locally. Tune hyperparameters.
- [ ] **Arpit:** Save the best model weights to `outputs/models/gcn_best.pt`.
- [ ] **Arpit:** **[PUSH]** Commit `gcn.py` and the best model weights.

---

### Step 6: NDPI Integration & Full Pipeline (Nikita & Mukul)
*Requires Steps 3 & 5.*

#### Step 6.1: Full Pipeline Assembly
- [ ] **Nikita & Mukul:** Pull `main` branch (to get Arpit's model and Mukul's scoring functions).
- [ ] **AI Agent:** Write `src/scoring/ndpi.py` to combine GNN, Similarity, Literature, and Equity scores.
- [ ] **AI Agent:** Write `main_pipeline.py` as a single master script.
- [ ] **Nikita:** Run `main_pipeline.py` on your machine to generate `outputs/ndpi_results.csv`.
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
- [ ] **AI Agent:** Write React components (`frontend/src/`) for the ranking tables and NDPI breakdown charts.
- [ ] **Swastik:** Run React locally and verify connection to Flask.

#### Step 8.2: Dockerization
- [ ] **AI Agent:** Write `docker-compose.yml` to spin up both React and Flask together.
- [ ] **Swastik:** Run `docker-compose up` to verify production deployment.
- [ ] **Swastik:** **[PUSH]** Commit `frontend/` and `docker-compose.yml`.

---

### Step 9: Explainability (Arpit & Mukul)
*Parallel to Step 8.*

- [ ] **Arpit:** Pull `main` branch. 
- [ ] **AI Agent:** Write `src/explainability/gnn_explainer.py`.
- [ ] **Arpit:** Run GNNExplainer to generate subgraph visualisations. **[PUSH]**
- [ ] **Mukul:** Have AI write SHAP explainers for the baseline model. **[PUSH]**

---

### Step 10: Research Paper & Case Studies (All)
- [ ] **Nikita:** Draft abstract and introduction based on AI summaries.
- [ ] **Arpit:** Write methodology for GNN (use AI to format mathematical formulas).
- [ ] **Mukul:** Write methodology for NDPI components.
- [ ] **Swastik:** Capture screenshots of the UI for the paper.
- [ ] **AI Agent:** Can help proofread, format citations in BibTeX, and generate markdown tables.

---

## ⚠️ Common Mistakes to Avoid (Across Devices)

| Mistake | Prevention |
|---|---|
| **Git Merge Conflicts** | Always pull before you start working. Only edit files owned by your role. |
| **Pushing Data** | NEVER commit `data/raw/` or `data/processed/`. The repo will freeze. |
| **Environment Mismatch** | Always use the `requirements.txt`. If you add a library, tell everyone to reinstall. |
| **Hardcoding Paths** | Use `pathlib.Path` so code runs on both Mac (Swastik) and Windows (Nikita/Arpit). |

---

*This document should be reviewed at every weekly team standup. Update task checkboxes as you go.*
