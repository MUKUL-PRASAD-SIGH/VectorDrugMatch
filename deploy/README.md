# VectorDrugMatch research inference API - deployment

Research-grade candidate prioritisation only. Not a clinical decision system. Only a bundle with `"status": "FROZEN"` (exported from
`reports/final_audit_*/FROZEN_SELECTION.json` after the one-time holdout evaluation) may go to staging; `PROVISIONAL` bundles are for local testing.

## Components
| Piece | Path |
|---|---|
| API (FastAPI) | `src/serving/app.py` - `GET /health`, `GET /model-info`, `POST /score`, `POST /rank` |
| Scoring (numpy/scipy/sklearn, CPU, no torch) | `src/serving/scoring.py` |
| Bundle exporter (checksummed, immutable) | `scripts/final_audit/export_bundle.py` |
| Image | `deploy/Dockerfile`, built by `deploy/build_image.sh <bundle_dir>` |
| Locked serving dependencies | `requirements-serving.lock` (exact versions; scikit-learn must equal the training version 1.7.2 for the joblib GBM) |
| Config template | `deploy/.env.example` |
| Tests | `tests/test_serving.py` (API, auth, limits, unknown IDs, tamper refusal, training/serving parity) |

## Run locally
```bash
bash deploy/build_image.sh outputs/final_audit_20261117/bundles/<version>
cp deploy/.env.example deploy/.env   # set VDM_API_KEY to a long random secret
docker run -d --name vdm -p 127.0.0.1:8000:8000 --env-file deploy/.env vectordrugmatch-api:<version>
curl -s localhost:8000/health
curl -s -X POST localhost:8000/rank -H "X-API-Key: $VDM_API_KEY" -H 'Content-Type: application/json' -d '{"disease_id":"MONDO:0005044","top_k":20}'
```
Without Docker: `pip install -r requirements-serving.lock` then
`VDM_BUNDLE_DIR=<bundle> VDM_API_KEY=<secret> uvicorn src.serving.app:app --port 8000`.

## Request / response
* `POST /score` `{"pairs": [{"drug_id": "DB00945", "disease_id": "MONDO:0005044"}], "explain": true}` (<= `VDM_MAX_PAIRS`, default 1000).
  IDs are PrimeKG node IDs (DrugBank `DB…`, MONDO / `MONDO_GROUP:` disease IDs). Unknown IDs are returned under `unknown`, never guessed.
* `POST /rank` `{"drug_id": …}` (diseases for a drug) or `{"disease_id": …}` (drugs for a disease), `top_k` <= 500. Known PrimeKG indications and
  contraindications are excluded by default (`include_known`, `include_contraindicated`).
* Each result: `ranking_score` (mean component percentile vs the reference pairs - a relative score, not a probability), `component_scores`,
  `flags` (known indication / contraindication / off-label in PrimeKG, sparse-data indicators, NTD), `warnings`, optional `explanation`
  (shared gene targets, structurally similar training drugs with the indication, target-sharing drugs, relations to related diseases - descriptive
  evidence, not mechanisms), `model` (bundle version and status), `disclaimer`.

## Security and operations
* Startup verifies every bundle file's SHA-256 against `manifest.json`; on mismatch, missing key or missing bundle the service reports
  `503 unhealthy` and serves nothing. The model is never trained or modified at startup.
* `X-API-Key` (constant-time compare) on all endpoints except `/health`. Secrets come from the environment only; `deploy/.env` is git-ignored.
* Logs: one JSON line per request (request id, path, status, latency) and model-load events. No identifiers, request bodies or keys are logged.
* Container runs as non-root uid 10001, `HEALTHCHECK` on `/health`, single worker (the model is ~100 MB in memory; scale out with replicas).
* Monitoring: alert on `/health` != 200, 5xx rate, p95 latency (`ms` field; local CPU smoke test: /rank by drug ~1.7 s, by disease ~0.35 s),
  and on the `model_load_failed` event.

## Versioning and rollback
One immutable bundle per image; the image tag is the bundle version (`vectordrugmatch-api:vdm-<x.y.z>`). Bundles are never overwritten
(`export_bundle.py` refuses an existing version). Roll back by redeploying the previous tag (Cloud Run: route traffic to the previous revision).
`/model-info` reports the bundle version, status, components, export commit and holdout metrics.

## Staging on Google Cloud Run (prepared; run only with authorisation, FROZEN bundle only)
```bash
PROJECT=<gcp-project>; REGION=<region>; VER=<bundle version>
gcloud artifacts repositories create vdm --repository-format=docker --location=$REGION --project=$PROJECT   # once
docker tag vectordrugmatch-api:$VER $REGION-docker.pkg.dev/$PROJECT/vdm/api:$VER
gcloud auth configure-docker $REGION-docker.pkg.dev
docker push $REGION-docker.pkg.dev/$PROJECT/vdm/api:$VER
printf '%s' "<long random key>" | gcloud secrets create vdm-api-key --data-file=- --project=$PROJECT                 # once
gcloud run deploy vdm-api-staging --image=$REGION-docker.pkg.dev/$PROJECT/vdm/api:$VER --region=$REGION --project=$PROJECT \
  --no-allow-unauthenticated --memory=1Gi --cpu=1 --concurrency=4 --max-instances=2 --set-secrets=VDM_API_KEY=vdm-api-key:latest
```
`--no-allow-unauthenticated` keeps the service private (Google IAM in front of the API key). Do not expose it publicly.
