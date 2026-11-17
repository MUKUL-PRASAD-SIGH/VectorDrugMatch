# Deployment readiness

## Status
| Item | State | Evidence |
|---|---|---|
| Frozen, holdout-evaluated model bundle | DONE | `outputs/final_audit_20261117/bundles/vdm-1.0.0` (FROZEN, SHA-256 per file; holdout metrics attached to its manifest) |
| Inference API (`/health`, `/model-info`, `/score`, `/rank`) | DONE | `src/serving/app.py`, `src/serving/scoring.py` |
| Input validation, unknown-ID reporting, request limits, API-key auth, JSON logs without identifiers, checksum verification, CPU-only | DONE | `tests/test_serving.py` (9 tests) |
| Training/serving parity | DONE | GBM identical to 1e-9; GCN CPU vs GPU ≤ 9e-7 with identical AUC |
| Dockerfile, minimal-context build, lock file, env template | DONE | `deploy/`, `requirements-serving.lock` |
| Local container smoke test | DONE for `vectordrugmatch-api:vdm-1.0.0` (2026-11-17 21:38Z): Docker health `healthy`, `/health` ok (FROZEN), 401 without key, `/model-info` reports holdout AUC 0.9066, `/rank` works, 0 identifiers / 0 key occurrences in logs; provisional bundle also tested (unknown-ID reporting, latency) |
| Full test suite | 59 passed | `python -m pytest -q tests` |
| Staging deployment | **NOT DONE** - requires your authorisation (gcloud is logged in with a default project; Cloud Run commands prepared, private service only) |
| Production deployment | Not planned; not appropriate without further validation (see model card) |

## Build and smoke-test the frozen image
```bash
bash deploy/build_image.sh outputs/final_audit_20261117/bundles/vdm-1.0.0          # -> vectordrugmatch-api:vdm-1.0.0
docker run -d --name vdm -p 127.0.0.1:8000:8000 -e VDM_API_KEY=<secret> vectordrugmatch-api:vdm-1.0.0
curl -s localhost:8000/health
```

## Exact staging command (Google Cloud Run; private)
```bash
PROJECT=<gcp-project>; REGION=<region>; VER=vdm-1.0.0
gcloud artifacts repositories create vdm --repository-format=docker --location=$REGION --project=$PROJECT
gcloud auth configure-docker $REGION-docker.pkg.dev
docker tag vectordrugmatch-api:$VER $REGION-docker.pkg.dev/$PROJECT/vdm/api:$VER && docker push $REGION-docker.pkg.dev/$PROJECT/vdm/api:$VER
printf '%s' "<long random key>" | gcloud secrets create vdm-api-key --data-file=- --project=$PROJECT
gcloud run deploy vdm-api-staging --image=$REGION-docker.pkg.dev/$PROJECT/vdm/api:$VER --region=$REGION --project=$PROJECT \
  --no-allow-unauthenticated --memory=1Gi --cpu=1 --concurrency=4 --max-instances=2 --set-secrets=VDM_API_KEY=vdm-api-key:latest
```
Required: a GCP project with billing, Artifact Registry and Secret Manager enabled, and the Cloud Run Admin role. The service stays private
(IAM + API key). Monitoring: `/health`, 5xx rate, p95 latency, `model_load_failed` log events. Rollback: redeploy the previous image tag / revision.
Model versioning: one immutable bundle per image tag; the exporter refuses to overwrite a version.
