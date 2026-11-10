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


def resolve_smiles(ids: list, cache_dir: Path = EXTERNAL) -> dict:
    """Return {drugbank_id: smiles} for `ids`, MERGING into data/external caches (existing entries are kept).

    Only ids missing from the cache are queried (MyChem -> PubChem CID -> PubChem REST). Safe to call for any
    DrugBank id list (Hetionet compounds, PrimeKG drugs, ...).
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    sp, cp = cache_dir / "drugbank_smiles_cache.json", cache_dir / "drugbank_cid_map.json"
    smiles = json.loads(sp.read_text()) if sp.exists() else {}
    cids = json.loads(cp.read_text()) if cp.exists() else {}
    todo = [i for i in dict.fromkeys(ids) if i not in smiles]
    if todo:
        print(f"  resolving {len(todo)} DrugBank ids not in the cache ...")
        new_s, new_c = query_mychem(todo)
        smiles.update(new_s)
        cids.update(new_c)
        need = {d: cids[d] for d in todo if d not in smiles and d in cids}
        print(f"  MyChem: {len(new_s)} SMILES, {len(new_c)} PubChem CIDs; PubChem REST for {len(need)}")
        smiles.update(query_pubchem(need))
        sp.write_text(json.dumps(smiles, indent=2))
        cp.write_text(json.dumps(cids, indent=2))
    return {i: smiles[i] for i in ids if i in smiles}


def main():
    ids = load_compound_ids()
    print(f"{len(ids)} Hetionet compounds")
    got = resolve_smiles(ids)
    missing = [d for d in ids if d not in got]
    print(f"Resolved {len(got)}/{len(ids)}; {len(missing)} missing")
    if missing:
        pd.DataFrame({"drug_id": missing}).to_csv(EXTERNAL / "fetch_smiles_missing.csv", index=False)
        print("Missing IDs written to data/external/fetch_smiles_missing.csv")


if __name__ == "__main__":
    sys.exit(main())
