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
  "total": 10
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
      "drug_id": "DB00602",
      "drug_name": "Ivermectin",
      "smiles": "C...",
      "on_who_eml": true,
      "generic_available": true
    }
  ],
  "total": 15
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
      "drug_id": "DB00602",
      "drug_name": "Ivermectin",
      "ndpi_score": 0.847,
      "components": {
        "gnn_score": 0.91,
        "similarity_score": 0.78,
        "literature_score": 0.95,
        "equity_score": 0.72
      },
      "pubmed_count": 482,
      "on_who_eml": true,
      "smiles": "C..."
    }
  ]
}
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `disease_id` | string | ✅ | — | UMLS disease identifier |
| `top_k` | int | ❌ | 10 | Number of candidates to return (max 50) |
| `explain` | bool | ❌ | false | Include NDPI component breakdown |

---

### `GET /health`

Health check endpoint.

**Response:**
```json
{"status": "ok", "model": "gcn_v1", "ndpi_version": "1.0"}
```

---

## NDPI Score Components & External API Integrations

The NDPI score combines multiple metrics. Two of these metrics, `literature_score` and `equity_score`, require integration with external APIs. **It is critical that all component scores are normalized to a `(0, 1)` scale** to prevent raw values (like large DALY numbers) from skewing or overwhelming the underlying Graph Neural Network (GNN) scores.

### 1. Literature Score
* **Base Knowledge**: Measures the volume of existing research linking a specific drug to a specific disease.
* **Detailed Knowledge**: We count the number of PubMed articles that mention both the drug and the disease in their title or abstract. 
* **Integration Steps & Plan**:
  1. Use the `biopython` package to interface with the NCBI Entrez API (`esearch` endpoint).
  2. Construct the search query format: `"(Drug)[Title/Abstract] AND (Disease)[Title/Abstract]"`.
  3. Retrieve the total PubMed evidence count.
  4. Normalize the raw count to a `(0, 1)` scale (e.g., using Min-Max scaling or log transformation) before incorporating it into the final NDPI score.

### 2. Equity Score
* **Base Knowledge**: Evaluates the accessibility and public health impact of the drug, especially for Neglected Tropical Diseases (NTDs).
* **Detailed Knowledge**: Based on WHO Essential Medicines List (EML) status, generic availability, affordability, and the Disability-Adjusted Life Year (DALY) burden of the target NTD.
* **Integration Steps & Plan**:
  1. Hit the WHO Global Health Observatory (GHO) OData API.
  2. Match our target NTDs to their corresponding DALY records in the WHO database.
  3. Pull the DALY burden values.
  4. Normalize the DALY values and combine them with EML status/generic availability to produce a final `equity_score` on a `(0, 1)` scale, ensuring it properly weighs alongside the GNN predictions.

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
