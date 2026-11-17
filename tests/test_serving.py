"""Inference API: model loading, checksum verification, auth, validation, unknown IDs, batch limits, ranking, and training/serving parity.
Uses the bundle in $VDM_TEST_BUNDLE (default: the provisional test bundle); skipped when it is absent."""
import importlib
import json
import os
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
BUNDLE = Path(os.environ.get("VDM_TEST_BUNDLE", REPO / "outputs/final_audit_20261117/bundles/vdm-0.0.1-provisional"))
pytestmark = pytest.mark.skipif(not (BUNDLE / "manifest.json").exists(), reason="no serving bundle")
KEY = "test-key-123"


def client_for(bundle, key=KEY, monkeypatch=None):
    from fastapi.testclient import TestClient
    monkeypatch.setenv("VDM_BUNDLE_DIR", str(bundle))
    monkeypatch.delenv("VDM_ALLOW_NO_AUTH", raising=False)
    if key:
        monkeypatch.setenv("VDM_API_KEY", key)
    else:
        monkeypatch.delenv("VDM_API_KEY", raising=False)
    import src.serving.app as appmod
    importlib.reload(appmod)
    return TestClient(appmod.app)


@pytest.fixture(scope="module")
def client():
    mp = pytest.MonkeyPatch()
    with client_for(BUNDLE, monkeypatch=mp) as c:
        yield c
    mp.undo()


H = {"X-API-Key": KEY}


def known_pair():
    kp = np.load(BUNDLE / "known_pairs.npz")["treats"]
    ids = np.load(BUNDLE / "ids.npz")
    return str(ids["drug_id"][kp[0, 0]]), str(ids["disease_id"][kp[1, 0]])


def test_health_and_model_info(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert client.get("/model-info").status_code == 401
    m = client.get("/model-info", headers=H).json()
    assert m["bundle_version"] == BUNDLE.name and m["n_drugs"] == 7957 and "not a probability" in m["score_definition"].lower()


def test_auth_rejects_wrong_key(client):
    assert client.post("/score", json={"pairs": [{"drug_id": "x", "disease_id": "y"}]}, headers={"X-API-Key": "wrong"}).status_code == 401


def test_score_known_pair_flags_and_explanation(client):
    d, s = known_pair()
    r = client.post("/score", json={"pairs": [{"drug_id": d, "disease_id": s}], "explain": True}, headers=H).json()
    it = r["results"][0]
    assert 0 <= it["ranking_score"] <= 1 and it["flags"]["known_indication_in_primekg"] is True
    assert any("known indication" in w for w in it["warnings"]) and "explanation" in it and r["disclaimer"]


def test_unknown_ids_reported_not_invented(client):
    d, s = known_pair()
    r = client.post("/score", json={"pairs": [{"drug_id": "DB_NOT_REAL", "disease_id": s}, {"drug_id": d, "disease_id": "MONDO:NOPE"}]}, headers=H).json()
    assert r["results"] == [] and {u["reason"] for u in r["unknown"]} == {"unknown drug_id", "unknown disease_id"}


def test_input_validation_and_limits(client):
    assert client.post("/score", json={"pairs": []}, headers=H).status_code == 422
    big = [{"drug_id": "DB00001", "disease_id": "MONDO:0005044"}] * 1001
    assert client.post("/score", json={"pairs": big}, headers=H).status_code == 422
    assert client.post("/rank", json={"top_k": 10}, headers=H).status_code == 422
    assert client.post("/rank", json={"drug_id": "DB00001", "disease_id": "MONDO:0005044"}, headers=H).status_code == 422
    assert client.post("/rank", json={"drug_id": "DB00001", "top_k": 501}, headers=H).status_code == 422
    assert client.post("/rank", json={"drug_id": "DB_NOT_REAL"}, headers=H).status_code == 404


def test_rank_by_drug_and_by_disease(client):
    d, s = known_pair()
    r = client.post("/rank", json={"drug_id": d, "top_k": 20}, headers=H).json()
    sc = [x["ranking_score"] for x in r["results"]]
    assert len(sc) == 20 and sc == sorted(sc, reverse=True) and [x["rank"] for x in r["results"]] == list(range(1, 21))
    assert not any(x["flags"]["known_indication_in_primekg"] or x["flags"]["contraindication_in_primekg"] for x in r["results"])
    r2 = client.post("/rank", json={"disease_id": s, "top_k": 10, "include_known": True}, headers=H).json()
    assert len(r2["results"]) == 10 and all(x["disease_id"] == s for x in r2["results"])


def test_training_serving_parity():
    """The API's component scores reproduce the predictions written at training/evaluation time for the same pairs."""
    from src.serving.scoring import Scorer
    s = Scorer(BUNDLE)
    man = json.loads((BUNDLE / "manifest.json").read_text())
    for c in man["components"]:
        if c["type"] == "gcn":
            ref = pd.read_csv(REPO / c["run_dir"] / "val_predictions.csv", dtype={"drug_id": str, "disease_id": str})
        else:
            ref = pd.read_csv(REPO / Path(c["source"]).parent / "val_predictions.csv", dtype={"drug_id": str, "disease_id": str})
        ref = ref.iloc[:2000]
        d = [s.drug_index[x] for x in ref.drug_id]
        t = [s.disease_index[x] for x in ref.disease_id]
        got = s.component_scores(d, t)[c["type"]]
        tol = 2e-4 if c["type"] == "gcn" else 1e-9          # gcn: per-seed probability, float32 embeddings
        if c["type"] == "gcn" and len([x for x in man["components"] if x["type"] == "gcn"]) > 1:
            continue                                           # multi-seed mean: checked per seed at export (numpy vs torch parity)
        assert np.abs(got - ref.probability.values).max() < tol, c["type"]


def test_tampered_bundle_refused(tmp_path, monkeypatch):
    b = tmp_path / BUNDLE.name
    shutil.copytree(BUNDLE, b)
    with open(b / "reference.npz", "ab") as f:
        f.write(b"tamper")
    with client_for(b, monkeypatch=monkeypatch) as c:
        r = c.get("/health")
        assert r.status_code == 503 and "checksum" in r.json()["error"]
        assert c.post("/score", json={"pairs": [{"drug_id": "a", "disease_id": "b"}]}, headers=H).status_code == 503


def test_missing_api_key_refuses_to_serve(monkeypatch):
    with client_for(BUNDLE, key=None, monkeypatch=monkeypatch) as c:
        assert c.get("/health").status_code == 503
