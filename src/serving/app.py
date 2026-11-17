"""
src/serving/app.py - VectorDrugMatch research inference API (FastAPI).

    VDM_BUNDLE_DIR=outputs/final_audit_20261117/bundles/<version> VDM_API_KEY=... uvicorn src.serving.app:app --host 0.0.0.0 --port 8000

Endpoints: GET /health, GET /model-info, POST /score, POST /rank. All but /health require the X-API-Key header unless VDM_ALLOW_NO_AUTH=1 (local
development only). The model is loaded once at startup (checksums verified; no training, no modification). Logs are JSON lines with request id,
endpoint, item counts, status and latency - never identifiers or request bodies.

Research use only: outputs are relative ranking scores for hypothesis prioritisation, not clinical recommendations.
"""
from __future__ import annotations

import hmac
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import List, Optional

import numpy as np
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from src.serving.scoring import BundleError, Scorer

MAX_PAIRS = int(os.environ.get("VDM_MAX_PAIRS", "1000"))
MAX_TOP_K = int(os.environ.get("VDM_MAX_TOP_K", "500"))
DISCLAIMER = ("Research use only. ranking_score is a relative prioritisation score from a model trained on PrimeKG indications with sampled "
              "unlabelled negatives; it is not a probability of efficacy and not a clinical recommendation.")

log = logging.getLogger("vdm")
if not log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(h)
log.setLevel(os.environ.get("VDM_LOG_LEVEL", "INFO"))


def jlog(**kw):
    log.info(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **kw}))


STATE = {"scorer": None, "error": None, "loaded_at": None, "load_seconds": None}


@asynccontextmanager
async def lifespan(app):
    bundle = os.environ.get("VDM_BUNDLE_DIR")
    t0 = time.time()
    try:
        if not bundle:
            raise BundleError("VDM_BUNDLE_DIR is not set")
        if not os.environ.get("VDM_API_KEY") and os.environ.get("VDM_ALLOW_NO_AUTH") != "1":
            raise BundleError("VDM_API_KEY is not set (set VDM_ALLOW_NO_AUTH=1 only for local development)")
        STATE["scorer"] = Scorer(bundle, verify=True)
        STATE["loaded_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        STATE["load_seconds"] = round(time.time() - t0, 2)
        m = STATE["scorer"].manifest
        jlog(event="model_loaded", version=m["bundle_version"], status=m["status"], kind=m["kind"], seconds=STATE["load_seconds"])
    except Exception as e:                                   # the service starts and reports unhealthy; it never serves an unverified model
        STATE["error"] = f"{type(e).__name__}: {e}"
        jlog(event="model_load_failed", error=STATE["error"])
    yield


app = FastAPI(title="VectorDrugMatch research inference API", version="1.0", lifespan=lifespan)


@app.middleware("http")
async def access_log(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    t0 = time.time()
    try:
        resp = await call_next(request)
    except Exception:
        jlog(event="request", rid=rid, path=request.url.path, status=500, ms=round((time.time() - t0) * 1000, 1))
        return JSONResponse({"detail": "internal error", "request_id": rid}, status_code=500)
    resp.headers["X-Request-ID"] = rid
    jlog(event="request", rid=rid, path=request.url.path, method=request.method, status=resp.status_code, ms=round((time.time() - t0) * 1000, 1))
    return resp


def require_key(x_api_key: Optional[str] = Header(default=None)):
    key = os.environ.get("VDM_API_KEY")
    if not key and os.environ.get("VDM_ALLOW_NO_AUTH") == "1":
        return
    if not key or not x_api_key or not hmac.compare_digest(x_api_key, key):
        raise HTTPException(status_code=401, detail="missing or invalid X-API-Key")


def scorer() -> Scorer:
    s = STATE["scorer"]
    if s is None:
        raise HTTPException(status_code=503, detail=f"model not loaded: {STATE['error']}")
    return s


class Pair(BaseModel):
    drug_id: str = Field(min_length=1, max_length=64)
    disease_id: str = Field(min_length=1, max_length=128)


class ScoreRequest(BaseModel):
    pairs: List[Pair] = Field(min_length=1)
    explain: bool = False

    @field_validator("pairs")
    @classmethod
    def _limit(cls, v):
        if len(v) > MAX_PAIRS:
            raise ValueError(f"at most {MAX_PAIRS} pairs per request")
        return v


class RankRequest(BaseModel):
    drug_id: Optional[str] = Field(default=None, max_length=64)
    disease_id: Optional[str] = Field(default=None, max_length=128)
    top_k: int = Field(default=50, ge=1)
    include_known: bool = False
    include_contraindicated: bool = False
    explain: bool = False

    @field_validator("top_k")
    @classmethod
    def _k(cls, v):
        if v > MAX_TOP_K:
            raise ValueError(f"top_k must be <= {MAX_TOP_K}")
        return v


def model_meta(s: Scorer):
    m = s.manifest
    return {"bundle_version": m["bundle_version"], "status": m["status"], "kind": m["kind"]}


def item(s, d, t, rs, comp, pct, fl, i, explain):
    out = {"drug_id": str(s.drug_ids[d]), "drug_name": str(s.drug_names[d]), "disease_id": str(s.disease_ids[t]), "disease_name": str(s.disease_names[t]),
           "ranking_score": round(float(rs[i]), 6), "component_scores": {k: round(float(v[i]), 6) for k, v in comp.items()},
           "component_percentiles": {k: round(float(v[i]), 6) for k, v in pct.items()},
           "flags": {k: (bool(v[i]) if v.dtype == bool else int(v[i])) for k, v in fl.items()}, "warnings": s.warnings_for(fl, i)}
    if explain:
        out["explanation"] = s.explain(d, t)
    return out


@app.get("/health")
def health():
    s = STATE["scorer"]
    if s is None:
        return JSONResponse({"status": "unhealthy", "error": STATE["error"]}, status_code=503)
    return {"status": "ok", "model": model_meta(s), "loaded_at": STATE["loaded_at"]}


@app.get("/model-info", dependencies=[Depends(require_key)])
def model_info():
    s = scorer()
    m = s.manifest
    return {**model_meta(s), "created_utc": m["created_utc"], "selected_model": m.get("selected_model"), "export_git_commit": m["export_git_commit"],
            "components": [{k: c.get(k) for k in ("type", "seed", "hp", "split", "group", "numpy_vs_torch_max_abs_diff")} for c in m["components"]],
            "score_definition": m["score_definition"], "intended_use": m["intended_use"], "holdout_metrics": m.get("holdout_metrics"),
            "warning": m.get("warning"), "n_drugs": s.n_drug, "n_diseases": s.n_dis, "limits": {"max_pairs": MAX_PAIRS, "max_top_k": MAX_TOP_K},
            "disclaimer": DISCLAIMER}


@app.post("/score", dependencies=[Depends(require_key)])
def score(req: ScoreRequest):
    s = scorer()
    unknown, d, t = [], [], []
    for p in req.pairs:
        di, si = s.drug_index.get(p.drug_id), s.disease_index.get(p.disease_id)
        if di is None or si is None:
            unknown.append({"drug_id": p.drug_id, "disease_id": p.disease_id,
                            "reason": "unknown drug_id" if di is None else "unknown disease_id"})
        else:
            d.append(di)
            t.append(si)
    results = []
    if d:
        rs, comp, pct = s.score(d, t)
        fl = s.flags(d, t)
        results = [item(s, d[i], t[i], rs, comp, pct, fl, i, req.explain) for i in range(len(d))]
    return {"model": model_meta(s), "results": results, "unknown": unknown, "disclaimer": DISCLAIMER}


@app.post("/rank", dependencies=[Depends(require_key)])
def rank(req: RankRequest):
    s = scorer()
    if (req.drug_id is None) == (req.disease_id is None):
        raise HTTPException(status_code=422, detail="give exactly one of drug_id or disease_id")
    if req.drug_id is not None:
        q = s.drug_index.get(req.drug_id)
        if q is None:
            raise HTTPException(status_code=404, detail="unknown drug_id")
        t = np.arange(s.n_dis)
        d = np.full(s.n_dis, q)
    else:
        q = s.disease_index.get(req.disease_id)
        if q is None:
            raise HTTPException(status_code=404, detail="unknown disease_id")
        d = np.arange(s.n_drug)
        t = np.full(s.n_drug, q)
    rs, comp, pct = s.score(d, t)
    fl = s.flags(d, t)
    keep = np.ones(len(d), bool)
    if not req.include_known:
        keep &= ~fl["known_indication_in_primekg"]
    if not req.include_contraindicated:
        keep &= ~fl["contraindication_in_primekg"]
    idx = np.where(keep)[0]
    order = idx[np.argsort(-rs[idx], kind="stable")][: req.top_k]
    res = []
    for r, i in enumerate(order, 1):
        it = item(s, int(d[i]), int(t[i]), rs, comp, pct, fl, int(i), req.explain)
        it["rank"] = r
        res.append(it)
    return {"model": model_meta(s), "query": {"drug_id": req.drug_id, "disease_id": req.disease_id}, "n_candidates": int(keep.sum()),
            "excluded": {"known_indications": not req.include_known, "contraindications": not req.include_contraindicated}, "results": res,
            "disclaimer": DISCLAIMER}
