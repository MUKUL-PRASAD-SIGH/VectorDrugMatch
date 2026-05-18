# 🧬 VectorDrugMatch

> **AI-Driven Drug Repurposing Engine for Neglected Disease Patients**  
> IEEE Computer Society Student Chapter — IAM Pro CS Internship 2026  
> Ramaiah Institute of Technology, Bangalore

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.x-orange.svg)](https://pytorch.org/)
[![PyG](https://img.shields.io/badge/PyTorch_Geometric-2.x-red.svg)](https://pyg.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production_Ready_Research_System-brightgreen.svg)]()

---

## 📖 Overview

VectorDrugMatch is an open-source, AI-powered drug repurposing platform that identifies clinically viable and affordable treatment candidates for **neglected tropical diseases (NTDs)**. Unlike existing systems that focus on commercially profitable conditions, VectorDrugMatch explicitly prioritises diseases affecting low-resource, underserved populations.

The system combines:
- **Biomedical Knowledge Graph** built from DrugBank, ChEMBL, Hetionet, and DisGeNET
- **Graph Neural Network (GCN/GAT)** for drug–disease association prediction
- **Molecular Similarity Analysis** via RDKit Tanimoto fingerprints
- **Automated Literature Mining** via PubMed Entrez API
- **Neglected Disease Priority Index (NDPI)** — our core scoring innovation that folds in equity, affordability, and disease burden
- **Advanced Interactive Web UI** (Flask + React for production-ready research interface)

---

## 🗂️ Repository Structure

```
vectordrugmatch/
│
├── README.md                        ← You are here
├── DATASETS.md                      ← All data sources, download links, cleaning steps
├── MASTER_PLAN.md                   ← Full 8-week research & engineering roadmap
├── CONTRIBUTING.md                  ← How to contribute
├── ARCHITECTURE.md                  ← System design & component diagram
├── API.md                           ← REST API reference
├── CHANGELOG.md                     ← Version history
├── LICENSE
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── .env.example
│
├── data/
│   ├── raw/                         ← Original downloads (git-ignored)
│   │   ├── drugbank/
│   │   ├── chembl/
│   │   ├── hetionet/
│   │   ├── disgenet/
│   │   └── who_gho/
│   ├── processed/
│   │   ├── drugs.csv                ← Cleaned drug entities
│   │   ├── diseases.csv             ← Disease entities (NTD-focused)
│   │   ├── genes.csv                ← Gene/protein entities
│   │   ├── edges.csv                ← All graph edges with relation types
│   │   ├── node_features.npy        ← Feature matrix (N × D)
│   │   └── edge_index.npy           ← Graph connectivity (PyG format)
│   └── external/
│       ├── who_eml.csv              ← WHO Essential Medicines List
│       ├── who_ntd_list.csv         ← Official WHO NTD disease list
│       └── daly_burden.csv          ← WHO GHO DALY data by disease
│
├── src/
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── loaders.py               ← Dataset download & ingestion
│   │   ├── preprocessing.py         ← Cleaning, normalisation, deduplication
│   │   ├── graph_builder.py         ← NetworkX → PyG knowledge graph
│   │   └── feature_engineering.py  ← Node feature construction
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── baseline.py              ← Logistic Regression baseline
│   │   ├── gcn.py                   ← 2-layer Graph Convolutional Network
│   │   ├── gat.py                   ← Graph Attention Network (advanced)
│   │   ├── link_predictor.py        ← Drug–disease link scoring head
│   │   └── ensemble.py              ← Model ensemble (production)
│   │
│   ├── scoring/
│   │   ├── __init__.py
│   │   ├── ndpi.py                  ← Neglected Disease Priority Index
│   │   ├── similarity.py            ← RDKit Tanimoto molecular similarity
│   │   ├── literature.py            ← PubMed API literature evidence scoring
│   │   └── equity.py                ← WHO equity & affordability scoring
│   │
│   ├── explainability/
│   │   ├── __init__.py
│   │   ├── shap_explainer.py        ← SHAP values for baseline model
│   │   └── gnn_explainer.py         ← GNNExplainer for graph model
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logging.py
│       ├── metrics.py               ← ROC-AUC, AUPRC, MRR, Hit@K
│       └── visualisation.py         ← Graph & result plots
│
├── api/
│   ├── __init__.py
│   ├── app.py                       ← Flask application factory
│   ├── routes/
│   │   ├── predict.py               ← POST /predict
│   │   ├── diseases.py              ← GET /diseases
│   │   └── drugs.py                 ← GET /drugs
│   └── schemas.py                   ← Pydantic request/response models
│
├── frontend/
│   ├── package.json
│   ├── public/
│   └── src/
│       ├── App.jsx
│       ├── components/
│       │   ├── DiseaseSelector.jsx
│       │   ├── DrugRankingTable.jsx
│       │   ├── NDPIBreakdownChart.jsx
│       │   └── ExplainabilityPanel.jsx
│       └── pages/
│           ├── Rankings.jsx
│           ├── Explore.jsx
│           └── About.jsx
│
├── streamlit_app/
│   └── app.py                       ← Legacy prototype UI (deprecated in favor of React)
│
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_graph_construction.ipynb
│   ├── 03_baseline_model.ipynb
│   ├── 04_gcn_training.ipynb
│   ├── 05_ndpi_scoring.ipynb
│   ├── 06_explainability.ipynb
│   └── 07_case_studies.ipynb
│
├── scripts/
│   ├── download_data.sh
│   ├── preprocess_all.py
│   └── evaluate_all.py
│
├── tests/
│   ├── test_preprocessing.py
│   ├── test_models.py
│   ├── test_ndpi.py
│   └── test_api.py
│
├── outputs/
│   ├── ndpi_results.csv             ← Final NDPI rankings (git-ignored)
│   ├── models/                      ← Saved model checkpoints
│   └── figures/                     ← Plots for paper
│
├── main_pipeline.py                 ← Single entry point: runs everything
└── docker-compose.yml
```

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/your-org/vectordrugmatch.git
cd vectordrugmatch

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env — add your ENTREZ_EMAIL (free, required for PubMed API)
```

### 3. Download Data

```bash
bash scripts/download_data.sh
# Follow prompts for DrugBank & DisGeNET (free account required)
```

### 4. Run Full Pipeline

```bash
python main_pipeline.py
# Builds KG → trains GCN → computes NDPI → outputs ranked results
```

### 5. Launch Advanced Research UI

```bash
docker-compose up
# API: http://localhost:5000
# Frontend: http://localhost:3000
```

---

## 🧠 Core Innovation: NDPI

The **Neglected Disease Priority Index** is our primary contribution. Unlike pure ML scores, NDPI explicitly weights real-world deployability:

```
NDPI = 0.35 × GNN_score
     + 0.20 × Similarity_score
     + 0.20 × Literature_score
     + 0.25 × Equity_score
```

| Component | What It Measures | Method |
|---|---|---|
| **GNN_score** | ML-predicted drug–disease association | 2-layer GCN / GAT |
| **Similarity_score** | Chemical similarity to known NTD drugs | RDKit Tanimoto (Morgan FP) |
| **Literature_score** | PubMed evidence count (normalised) | Biopython Entrez API |
| **Equity_score** | WHO EML status + generic availability + affordability + DALY burden | WHO GHO API |

---

## 📊 Results (Current Prototype)

| Model | ROC-AUC | AUPRC | Notes |
|---|---|---|---|
| Logistic Regression (baseline) | 0.730 | — | Feature concatenation |
| 2-layer GCN | **0.830** | — | PyTorch Geometric |
| GAT (planned Week 5) | TBD | TBD | Attention mechanism |
| Ensemble (planned Week 7) | TBD | TBD | GCN + LR + Similarity |

---

## 🏥 Target Diseases

VectorDrugMatch focuses on **WHO-classified Neglected Tropical Diseases**:

- Lymphatic Filariasis
- Leishmaniasis (Cutaneous & Visceral)
- Chagas Disease
- African Trypanosomiasis (Sleeping Sickness)
- Schistosomiasis
- Onchocerciasis (River Blindness)
- Buruli Ulcer
- Dengue Fever
- Rabies
- Soil-transmitted Helminthiases

---

## 🔬 Tech Stack

| Layer | Technology |
|---|---|
| Core ML | PyTorch 2.x, PyTorch Geometric |
| Cheminformatics | RDKit |
| Graph Processing | NetworkX |
| Data | Pandas, NumPy, SQLite |
| Literature Mining | Biopython (Entrez) |
| Explainability | SHAP, PyG GNNExplainer |
| Backend API | Flask, Pydantic |
| Frontend | React 18, Recharts (production-ready research interface) |
| Containerisation | Docker, docker-compose |
| Testing | pytest |
| CI/CD | GitHub Actions |

---

## 👥 Team

| Name | Role | IEEE Member ID | Email |
|---|---|---|---|
| Nikita Ravindra | Team Lead, Data & Equity Scoring | 102191349 | ravindranikita21@gmail.com |
| Arpit Pandey | GNN Modelling | 102199062 | 1ms24ci023@msrit.edu |
| Mukul Prasad | Literature Mining & NDPI | 10177317 | mukulprasad958@gmail.com |
| Swastik R Phadke | Frontend & Integration | 102192683 | swastikphadke098@gmail.com |

**Faculty Advisor:** Dr. Parkavi A, Department of Computer Science, Ramaiah Institute of Technology  
**Program:** CS (AIML) — Semester 4

---

## 📄 Citation

If you use VectorDrugMatch in your research, please cite:

```bibtex
@misc{vectordrugmatch2026,
  title        = {VectorDrugMatch: Vector-Based Drug Repurposing Engine for Neglected Disease Patients},
  author       = {Ravindra, Nikita and Pandey, Arpit and Prasad, Mukul and Phadke, Swastik R},
  year         = {2026},
  institution  = {Ramaiah Institute of Technology, Bangalore},
  note         = {IEEE Computer Society Student Chapter, IAM Pro CS Internship}
}
```

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

*Built with ❤️ for patients who deserve better treatment options.*
