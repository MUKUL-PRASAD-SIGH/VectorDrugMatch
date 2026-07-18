# 🚀 FINAL EXECUTION & COLAB WORKFLOW PLAN

*This document acts as a step-by-step continuation of [MASTER_PLAN.md](MASTER_PLAN.md). It details the cloud execution (Google Colab) phase, the exact division of labor, immediate post-Colab integration (API, Frontend, Explainability, Paper), and clearly separates out Future Tasks.*

---

## 1. ☁️ Google Colab Execution: From 0 to End (Step-by-Step)

Google Colab will be used exclusively for heavy compute (Training, Hyperparameter Tuning, Ablations). Do **not** use Colab for writing code or frontend work.

### Phase 0: Setup & Data Mounting (Colab Notebook)
1. **Create Notebook**: Open a new Colab Notebook. Go to **Runtime > Change runtime type > T4 GPU** (or A100 if available).
2. **Mount Google Drive**: 
   ```python
   from google.colab import drive
   drive.mount('/content/drive')
   ```
3. **Clone Repository**: 
   ```bash
   !git clone https://github.com/your-org/vectordrugmatch.git
   %cd vectordrugmatch
   ```
4. **Upload Data**: Upload your local `data/raw/` folder (which contains your `drugs.csv`, `diseases.csv`, `genes.csv`, and `edges.csv` files) to Google Drive (e.g., `My Drive/VDM_Data/raw/`), then copy it to the Colab workspace:
   ```bash
   !mkdir -p data/raw/
   !cp -r /content/drive/MyDrive/VDM_Data/raw/* data/raw/
   ```
5. **Run Preprocessing**: Since you made recent changes, re-run the preprocessing inside Colab to generate the fresh `data/processed/` features:
   ```bash
   !python scripts/preprocess.py
   ```

### Phase 1: Environment Setup
1. **Install Dependencies**: Colab has pre-installed PyTorch, but PyTorch Geometric (PyG) and RDKit must be installed manually.
   ```bash
   !pip install rdkit-pypi
   !pip install torch-geometric
   !pip install pyg_lib torch_scatter torch_sparse torch_cluster -f https://data.pyg.org/whl/torch-2.x.x+cu118.html
   !pip install mlflow optuna shap
   ```

### Phase 2: Baselines & GNN Training
1. **Train Baselines (CPU/GPU)**:
   ```bash
   !python scripts/train_baselines.py
   ```
2. **Train GNNs (GPU Required)**:
   ```bash
   !python scripts/train_gnn.py
   ```

### Phase 3: Ablations & Hyperparameter Tuning
1. **Run Feature Ablations**:
   ```bash
   !python scripts/run_ablations.py
   ```
2. **Run Optuna Search (for HGT)**:
   ```bash
   !python scripts/optuna_gnn.py
   ```

### Phase 4: Artifact Extraction (CRITICAL)
If Colab disconnects, you lose everything. You must copy the `outputs/` folder back to Google Drive immediately after training.
```python
!cp -r outputs/ /content/drive/MyDrive/VDM_Outputs_Backup/
```

---

## 2. 👥 Task Delegation (Colab & Research Phase)

To maximize efficiency, the workload runs simultaneously across team members.

### 👤 P1: Colab Core Engineer (Simultaneous Colab Work)
**Focus:** Core Training & Environment Stability
- Execute Phase 0, 1, and 2 in Colab.
- Monitor GPU RAM usage to prevent CUDA Out Of Memory (OOM) errors.
- Train all Baselines and all 5 GNNs (GCN, GraphSAGE, GAT, RGCN, HGT).
- Download all baseline `.pkl` files and GNN `.pt` files to Google Drive.

### 👤 P2: Colab Optimization Engineer (Simultaneous Colab Work)
**Focus:** Tuning, Ablations, and MLflow
- Execute Phase 3 in a separate Colab instance/account (`optuna_gnn.py` and `run_ablations.py`).
- Track the MLflow metrics. Identify the absolute best hyperparameters for HGT.

### 👤 P3: Research & Visualisation Engineer (Local Work)
**Focus:** Scripts, Paper Visuals, and Mathematics
- **Generate Visualisation Scripts:** `plot_metrics.py`, `plot_loss.py`, `plot_ablations.py`.
- **Explainability:** Write scripts to export SHAP summary plots and GNNExplainer subgraph PNGs.
- **Mathematics for Paper:** Formulate the LaTeX equations for NDPI, HGT attention, and Tanimoto similarity.

---

## 3. 💻 Immediate Integration Steps (Post-Colab Local Work)

Once the Colab training is finished and you have downloaded your `outputs/` folder locally, the remaining Master Plan tasks must be executed. 

*(Note: The AI Agent has **already written** the true `scripts/main_pipeline.py` and the `src/scoring/` modules which dynamically load the best model and NDPI weights!)*

### Step A: Final Inference & Ranking (P1 & P2)
- [ ] **Configurable Feature Dimensions**: Ensure `run_ablations.py` and `main_pipeline.py` load dimensions dynamically from `graph_metadata.json` so embeddings can be swapped seamlessly.
- [ ] **Embeddings Export**: Update `scripts/main_pipeline.py` to save the final layer embeddings of drugs/diseases to CSV/Numpy for downstream analysis (e.g., UMAP plotting).
- [ ] **Ranking Metrics (IR Metrics)**: Implement Precision@K, Recall@K, Hits@K, MRR, and NDCG to evaluate the final NDPI ranked list.
- [ ] **Run Pipeline**: P1 runs `scripts/main_pipeline.py` using the weights downloaded from Colab to generate the true, final `outputs/ndpi_ranked_candidates.csv`. Commit the results to GitHub.

### Step B: Explainability (P3 & P2)
- [ ] **SHAP for Baseline Models (P2 / AI Agent):** Write `src/explainability/shap_explainer.py` to generate SHAP summary plots for Logistic Regression, Random Forest, XGBoost, and MLP.
- [ ] **GNNExplainer for HGT (P3 / AI Agent):** Write `src/explainability/gnn_explainer.py` to use PyG's GNNExplainer on the trained HGT model to generate subgraph visualisations showing which Drug→Gene→Disease paths drive each prediction.

### Step C: Flask API & React Frontend / Docker (P3)
- [ ] **Action:** Place `outputs/ndpi_ranked_candidates.csv` and the UMAP coordinate files into the `api/` folder. Flask serves these endpoints. React fetches and displays the rankings and model comparison charts.
- [ ] **Flask API (`api/app.py`):** AI writes and P3 tests the backend to serve the contents of the CSV and the UMAP coordinates.
- [ ] **React Frontend (`frontend/src/`):** AI writes and P3 tests components for ranking tables, NDPI breakdowns, and the model comparison view.
- [ ] **Dockerization:** AI writes `docker-compose.yml`. P3 runs `docker-compose up` to verify both React and Flask run together perfectly. Commit the UI code.

### Step D: Research Paper Assembly (All)
- [ ] **P1:** Draft abstract and introduction.
- [ ] **P3:** Write methodology for GNN progression (GCN → HGT), including math for architectures. Write results section with the 11-model comparison table.
- [ ] **P2:** Write methodology for NDPI components. Formulate LaTeX for NDPI, HGT attention, and Tanimoto similarity. Write discussion on RDKit feature importance via SHAP.
- [ ] **P3:** Capture screenshots of the UI.
- [ ] **AI Agent:** Generate Python plotting scripts (`plot_metrics.py` for ROC-AUC, `plot_loss.py` for loss curves, `plot_ablations.py` for feature drop bars). Proofread and format citations.

---

## 4. 🔮 Future Tasks (Final Scientific Validation)

These tasks are explicitly reserved for future work. They should be done **only** after the core API and application are fully operational.

1. **Statistical Significance**: Add DeLong's test and paired bootstrap confidence intervals to mathematically prove the GNN's superiority isn't due to random chance.
2. **External Validation**: Test the trained HGT model on external, unseen datasets (e.g., DrugBank, RepoDB, Open Targets) to prove out-of-distribution generalization.
3. **Reproducibility Metadata**: Enhance `evaluate.py` to dump `pip freeze`, Python/CUDA versions, and exact RNG seeds into the MLflow artifacts for open-science journal submission.
