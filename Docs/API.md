# 🔌 API.md — REST API Reference

Base URL: `http://localhost:5000` (development) | `https://api.vectordrugmatch.io` (production)

All responses are JSON. All errors return `{"error": "message"}` with appropriate HTTP status.

---

## Endpoints

### `GET /diseases`

Returns all diseases in the knowledge graph.

**Response:**
```json
{
  "diseases": [
    {
      "disease_id": "C0023418",
      "disease_name": "Lymphatic Filariasis",
      "is_ntd": true,
      "daly_rate": 5.2
    }
  ],
  "total": 138
}
```

---

### `GET /drugs`

Returns all drugs in the knowledge graph.

**Response:**
```json
{
  "drugs": [
    {
      "drug_id": "2244",
      "drug_name": "Aspirin",
      "smiles": "CC(=O)Oc1ccccc1C(=O)O",
      "mw": 180.16,
      "logp": 1.31,
      "on_who_eml": false,
      "generic_available": true
    }
  ],
  "total": 1553
}
```

---

### `POST /predict`

Returns top drug candidates for a given disease, ranked by NDPI.

**Request:**
```json
{
  "disease_id": "C0023418",
  "top_k": 10,
  "explain": true
}
```

**Response:**
```json
{
  "disease_id": "C0023418",
  "disease_name": "Lymphatic Filariasis",
  "predictions": [
    {
      "rank": 1,
      "drug_id": "2244",
      "drug_name": "Aspirin",
      "ndpi_score": 0.847,
      "components": {
        "hgt_score": 0.91,
        "similarity_score": 0.78,
        "literature_score": 0.95,
        "equity_score": 0.72
      },
      "model_comparison": {
        "logistic_regression": 0.68,
        "random_forest": 0.72,
        "xgboost": 0.79,
        "gcn": 0.83,
        "rgcn": 0.87,
        "hgt": 0.91
      },
      "pubmed_count": 482,
      "on_who_eml": true,
      "smiles": "CC(=O)Oc1ccccc1C(=O)O"
    }
  ]
}
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `disease_id` | string | ✅ | — | UMLS disease identifier |
| `top_k` | int | ❌ | 10 | Number of candidates to return (max 50) |
| `explain` | bool | ❌ | false | Include NDPI component breakdown + model comparison |

---

### `GET /models`

Returns the performance comparison of all trained models.

**Response:**
```json
{
  "models": [
    {
      "name": "Random Guess",
      "type": "baseline",
      "roc_auc": 0.500,
      "pr_auc": 0.312,
      "f1": 0.000,
      "mcc": 0.000
    },
    {
      "name": "Logistic Regression",
      "type": "baseline",
      "roc_auc": 0.730,
      "pr_auc": 0.645,
      "f1": 0.672,
      "mcc": 0.389
    },
    {
      "name": "XGBoost",
      "type": "baseline",
      "roc_auc": 0.815,
      "pr_auc": 0.761,
      "f1": 0.743,
      "mcc": 0.521
    },
    {
      "name": "HGT",
      "type": "gnn",
      "roc_auc": 0.910,
      "pr_auc": 0.872,
      "f1": 0.845,
      "mcc": 0.702,
      "is_primary": true
    }
  ],
  "primary_model": "HGT",
  "total_models": 11
}
```

---

### `GET /health`

Health check endpoint.

**Response:**
```json
{"status": "ok", "model": "hgt_v1", "ndpi_version": "2.0", "total_models": 11}
```

---

## NDPI Score Components & External API Integrations

The NDPI score combines multiple metrics. Two of these metrics, `literature_score` and `equity_score`, require integration with external APIs. **It is critical that all component scores are normalized to a `(0, 1)` scale** to prevent raw values (like large DALY numbers) from skewing or overwhelming the underlying model scores.

**Updated NDPI Formula (uses HGT as the ML component):**
```
NDPI = 0.35 × HGT_score
     + 0.20 × Similarity_score
     + 0.20 × Literature_score
     + 0.25 × Equity_score
```

### 1. HGT Score (replaces generic "GNN score")
* **What it is**: The link prediction probability from the Heterogeneous Graph Transformer (HGT) — the best-performing model in the pipeline.
* **Why HGT**: It outperforms GCN, GraphSAGE, GAT, and RGCN by leveraging multi-head attention across different node and edge types in the heterogeneous biomedical graph.

### 2. Similarity Score
* **Base Knowledge**: Chemical similarity between the candidate drug and drugs known to treat the target disease.
* **Method**: Tanimoto coefficient on 2048-bit Morgan Fingerprints (RDKit). NOT molecular weight proxy.

### 3. Literature Score
* **Base Knowledge**: Measures the volume of existing research linking a specific drug to a specific disease.
* **Detailed Knowledge**: We count the number of PubMed articles that mention both the drug and the disease in their title or abstract. 
* **Integration Steps & Plan**:
  1. Use the `biopython` package to interface with the NCBI Entrez API (`esearch` endpoint).
  2. Construct the search query format: `"(Drug)[Title/Abstract] AND (Disease)[Title/Abstract]"`.
  3. Retrieve the total PubMed evidence count.
  4. Normalize the raw count to a `(0, 1)` scale (e.g., using Min-Max scaling or log transformation) before incorporating it into the final NDPI score.

### 4. Equity Score
* **Base Knowledge**: Evaluates the accessibility and public health impact of the drug, especially for Neglected Tropical Diseases (NTDs).
* **Detailed Knowledge**: Based on WHO Essential Medicines List (EML) status, generic availability, affordability, and the Disability-Adjusted Life Year (DALY) burden of the target NTD.
* **Integration Steps & Plan**:
  1. Hit the WHO Global Health Observatory (GHO) OData API.
  2. Match our target NTDs to their corresponding DALY records in the WHO database.
  3. Pull the DALY burden values.
  4. Normalize the DALY values and combine them with EML status/generic availability to produce a final `equity_score` on a `(0, 1)` scale, ensuring it properly weighs alongside the model predictions.

---

## Running the API

```bash
# Development
python api/app.py

# Production (gunicorn)
gunicorn -w 4 -b 0.0.0.0:5000 "api.app:create_app()"

# Docker
docker-compose up api
```
