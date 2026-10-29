"""
scripts/fetch_smiles.py - Resolve SMILES for Hetionet compounds (DrugBank IDs).

Step 1: MyChem.info maps DrugBank ID -> PubChem CID (+ ChEMBL / PubChem SMILES when present).
Step 2: Compounds still without SMILES are looked up by CID in the PubChem PUG REST API.

Writes data/external/drugbank_smiles_cache.json ({drugbank_id: smiles}), which
scripts/preprocess.py reads before calling the MyChem fallback, and
data/external/drugbank_cid_map.json ({drugbank_id: cid}).

Usage:
    python scripts/fetch_smiles.py
"""

import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW = REPO_ROOT / "data" / "raw"
EXTERNAL = REPO_ROOT / "data" / "external"

MYCHEM_URL = "https://mychem.info/v1/query"
PUBCHEM_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cids}/property/CanonicalSMILES/JSON"


def load_compound_ids() -> list:
    nodes = pd.read_csv(RAW / "hetionet-v1.0-nodes.tsv", sep="\t")
    comp = nodes[nodes["kind"] == "Compound"]
    return [i.split("::")[-1] for i in comp["id"]]


def _first(value):
    """MyChem fields can be a scalar, a dict, or a list of either."""
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        value = value.get("absolute") or value.get("connectivity")
    return value


def _field(hit: dict, source: str, name: str):
    """Fetch hit[source][name]; MyChem may return the source as a list of dicts."""
    block = hit.get(source) or {}
    if isinstance(block, list):
        for b in block:
            val = _first((b or {}).get(name))
            if val:
                return val
        return None
    return _first(block.get(name))


def query_mychem(ids: list, chunk: int = 100):
    smiles, cids = {}, {}
    for i in range(0, len(ids), chunk):
        batch = ids[i:i + chunk]
        resp = requests.post(
            MYCHEM_URL,
            data={
                "q": ",".join(batch),
                "scopes": "drugbank.id",
                "fields": "drugbank.id,pubchem.cid,pubchem.smiles,chembl.smiles",
            },
            timeout=60,
        )
        resp.raise_for_status()
        for hit in resp.json():
            if hit.get("notfound"):
                continue
            db_id = hit["query"]
            cid = _field(hit, "pubchem", "cid")
            if cid:
                cids[db_id] = int(cid)
            smi = _field(hit, "chembl", "smiles") or _field(hit, "pubchem", "smiles")
            if smi and db_id not in smiles:
                smiles[db_id] = smi
        time.sleep(0.2)
    return smiles, cids


def query_pubchem(cid_by_db: dict, chunk: int = 100) -> dict:
    out = {}
    items = list(cid_by_db.items())
    for i in range(0, len(items), chunk):
        batch = items[i:i + chunk]
        url = PUBCHEM_URL.format(cids=",".join(str(c) for _, c in batch))
        resp = requests.get(url, timeout=60)
        if resp.status_code != 200:
            print(f"  [WARNING] PubChem batch {i} returned {resp.status_code}")
            continue
        by_cid = {p["CID"]: p.get("CanonicalSMILES") or p.get("ConnectivitySMILES")
                  for p in resp.json()["PropertyTable"]["Properties"]}
        for db_id, cid in batch:
            if by_cid.get(cid):
                out[db_id] = by_cid[cid]
        time.sleep(0.25)
    return out


def main():
    ids = load_compound_ids()
    print(f"{len(ids)} Hetionet compounds")

    smiles, cids = query_mychem(ids)
    print(f"MyChem: {len(cids)} with PubChem CID, {len(smiles)} with SMILES")

    need = {d: c for d, c in cids.items() if d not in smiles}
    print(f"PubChem REST lookup for {len(need)} compounds")
    smiles.update(query_pubchem(need))

    missing = [d for d in ids if d not in smiles]
    print(f"Resolved {len(smiles)}/{len(ids)}; {len(missing)} missing")

    EXTERNAL.mkdir(parents=True, exist_ok=True)
    (EXTERNAL / "drugbank_smiles_cache.json").write_text(json.dumps(smiles, indent=2))
    (EXTERNAL / "drugbank_cid_map.json").write_text(json.dumps(cids, indent=2))
    if missing:
        pd.DataFrame({"drug_id": missing}).to_csv(EXTERNAL / "fetch_smiles_missing.csv", index=False)
        print("Missing IDs written to data/external/fetch_smiles_missing.csv")


if __name__ == "__main__":
    sys.exit(main())
