# 🚀 FINAL EXECUTION & COLAB WORKFLOW PLAN

This document outlines the final steps to transition the VectorDrugMatch project from local development to cloud execution (Google Colab), assign team responsibilities, and execute the post-Colab deployment and research paper preparation.

---

## 1. 🎯 What is Left (The Remaining 8 Tasks)

Before declaring the project 100% complete, the following scientific and engineering tasks remain:
1. **Dynamic Best Model Loading**: Load the best inference model from `config.yaml` instead of hardcoding `hgt_best.pt` in `main_pipeline.py`.
2. **Configurable Feature Dimensions**: Remove hardcoded feature dimensions (e.g., 2048 for Morgan) from `run_ablations.py` to allow seamless dynamic feature switching.
3. **Statistical Significance**: Add DeLong's test and bootstrap confidence intervals to mathematically prove the GNN's superiority isn't due to random chance.
4. **External Validation**: Test the trained HGT model on external, unseen datasets (e.g., DrugBank, RepoDB, Open Targets) to prove out-of-distribution generalization.
5. **Ranking Metrics**: Implement Precision@K, Recall@K, Hits@K, MRR, and NDCG for the final NDPI ranked list.
6. **Embeddings Export**: Save the learned drug and disease embeddings from the final GNN layer for downstream clustering and visualizations (e.g., UMAP, t-SNE).
7. **Configurable NDPI Weights**: Make the NDPI component weights (0.35, 0.20, 0.20, 0.25) configurable in `config.yaml`.
8. **Reproducibility Metadata**: Enhance `evaluate.py` to dump `pip freeze`, Python/CUDA versions, and RNG seeds into MLflow artifacts.

---

## 2. ☁️ Google Colab Execution: From 0 to End (Step-by-Step)

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
4. **Upload Data**: Local preprocessing (`scripts/preprocess.py`) should already be done. Upload your `data/processed/` folder to Google Drive (e.g., `My Drive/VDM_Data/processed/`), then copy it to the Colab workspace:
   ```bash
   !cp -r /content/drive/MyDrive/VDM_Data/processed/ data/
   ```

### Phase 1: Environment Setup
1. **Install Dependencies**: Colab has pre-installed PyTorch, but PyTorch Geometric (PyG) and RDKit must be installed carefully.
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

## 3. 👥 Task Delegation (Colab & Research)

To maximize efficiency, the heavy lifting is divided among 3 distinct roles:

### 👤 Person 1: Colab Core Engineer (
**Focus:** Core Training & Environment Stability
- **Tasks:**
  - Execute Phase 0, 1, and 2 in Colab.
  - Monitor GPU RAM usage to prevent CUDA Out Of Memory (OOM) errors.
  - Download all baseline `.pkl` files and GNN `.pt` files to Google Drive.
- **Potential Mistakes:** Not mounting Google Drive before starting, losing hours of training when the runtime disconnects.

### 👤 Person 2: Colab Optimization Engineer
**Focus:** Tuning, Ablations, and MLflow
- **Tasks:**
  - Execute Phase 3 in Colab (`optuna_gnn.py` and `run_ablations.py`).
  - Track the MLflow metrics. Identify the absolute best hyperparameters for HGT.
  - Ensure config files properly trigger different feature dimensions.
- **Potential Mistakes:** Overwriting MLflow runs by not setting unique experiment names for each Optuna trial.

### 👤 Person 3: Research & Visualisation Engineer 
**Focus:** Scripts, Paper Visuals, and Mathematics (Done Locally)
- **Tasks:**
  - **Generate Visualisation Scripts:**
    - `plot_metrics.py`: ROC-AUC and PR-AUC curves comparing all 11 models on one graph.
    - `plot_loss.py`: Training/Validation loss curves for the GNNs to prove no overfitting.
    - `plot_ablations.py`: Bar charts showing performance drops when removing RDKit or Disease features.
  - **Explainability:** Write scripts to export SHAP summary plots and GNNExplainer subgraph PNGs.
  - **Mathematics for Paper:** Formulate the LaTeX equations for:
    1. **NDPI Formula**: Mathematical representation of the weightings and normalizations.
    2. **HGT Attention Mechanism**: The math behind how HGT weights different relation types.
    3. **RDKit Tanimoto**: The Jaccard similarity equivalent for Morgan fingerprints.

---

## 4. 🚀 Post-Colab: What Next? (Step-by-Step)

Once Colab training is finished and `hgt_best.pt` (plus all metrics) is downloaded to your local machines, here is exactly what happens next.

### Step 1: Inference Pipeline & NDPI Generation
- **Action:** Run `python main_pipeline.py` locally.
- **What it does:** Loads the best model weights, predicts on all unknown Drug-Disease pairs, fetches PubMed and WHO equity data, and computes the NDPI score.
- **Testing:** Verify `outputs/ndpi_results.csv` is populated with sorted, ranked candidates.
- **Possible Mistakes:** 
  - **RDKit Version Mismatch:** If Colab used a different RDKit version than local, the Morgan fingerprints might differ slightly, crashing the model dimension check. Ensure versions match or just rerun `preprocess.py` locally.
  - **Hardcoded Paths:** Forgetting to update `config.yaml` to point to the downloaded Colab model path.

### Step 2: External Validation (The Remaining Improvement #4)
- **Action:** Download RepoDB or Open Targets datasets. Map their IDs to DisGeNET/PubChem IDs. Feed them into the loaded HGT model to see if it correctly predicts these known repurposing successes.
- **Testing:** Calculate Recall@100 for the external dataset.
- **Possible Mistakes:** ID mismatch. A drug in RepoDB might use a DrugBank ID, while your model uses PubChem CID. You must map them perfectly.

### Step 3: Statistical Significance (The Remaining Improvement #3)
- **Action:** Run DeLong's test comparing HGT vs. XGBoost ROC-AUC.
- **Testing:** If p < 0.05, the GNN is statistically significantly better.
- **Possible Mistakes:** Running DeLong's on train data instead of the test split. Always use test probabilities.

### Step 4: Extract Embeddings (The Remaining Improvement #6)
- **Action:** Pass the graph through the trained HGT encoder but skip the link predictor. Save the node embeddings to a CSV/Numpy file. Use `UMAP` or `t-SNE` to plot them in 2D.
- **Testing:** Diseases of the same category (e.g., viral vs. parasitic) should naturally cluster together in the visual plot.

### Step 5: API & Frontend Integration (Swastik)
- **Action:** Place `ndpi_results.csv` and the UMAP coordinates into the `api/` folder. Flask serves these endpoints. React fetches and displays the rankings and model comparison charts.
- **Testing:** Run `docker-compose up` and verify the UI loads instantly.
- **Possible Mistakes:** 
  - Loading a massive CSV into RAM on every API request. **Fix:** Load the CSV once in Pandas at Flask startup, or dump it to a local SQLite DB for querying.
  - CORS errors between React and Flask. **Fix:** Ensure `flask-cors` is configured.

### Step 6: Final Paper Assembly
- Compile the ROC-AUC graphs, NDPI formulas, UMAP clusters, and statistical p-values into the IEEE format paper. 
- Highlight the top 5 novel drug candidates predicted for a specific NTD (e.g., Chagas Disease) as the main case study.
