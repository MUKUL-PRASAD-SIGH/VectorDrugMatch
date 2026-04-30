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

## Running the API

```bash
# Development
python api/app.py

# Production (gunicorn)
gunicorn -w 4 -b 0.0.0.0:5000 "api.app:create_app()"

# Docker
docker-compose up api
```
