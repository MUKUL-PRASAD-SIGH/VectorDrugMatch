"""
scripts/primekg_dataset.py - Track B step 1: turn PrimeKG kg.csv into the processed-CSV layout the
rest of the pipeline already reads (drugs/diseases/genes/edges.csv + features), with provenance.

    python scripts/primekg_dataset.py --config configs/primekg_morgan.yaml          # real run
    python scripts/primekg_dataset.py --config configs/primekg_morgan.yaml --no-smiles   # quick test

Inputs  (data/external/): primekg_kg.csv, mondo.obo   [fetch with scripts/fetch_public_data.py --primekg]
Output  data/processed/<experiment.name>/ : drugs.csv diseases.csv genes.csv edges.csv drug_features.npy
        disease_features.npy primekg_provenance.json graph_metadata.json

Label semantics (never merged):
    indication         -> relation CtD         (the ONLY prediction target)
    contraindication   -> relation PK_contra   (graph relation / diagnostic only, NOT a negative label)
    off-label use      -> relation PK_offlabel (graph relation / diagnostic only, NOT a negative label)
Other kept relations: drug_protein->CbG, disease_protein->DaG, protein_protein->GiG,
    disease_disease->PK_DisDis, (optional --include-ddi) drug_drug->PK_DDI.
Nothing is silently dropped: every disease node is kept with its DOID mapping status; edges whose
endpoint cannot be resolved are counted and reported.
"""
import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
from src.data.mondo import (build_children, map_disease_nodes, mondo_version,  # noqa: E402
                            ntd_node_groups, pad, parse_mondo)
from src.features.disease import build_disease_feature_matrix  # noqa: E402

EXT = REPO / "data" / "external"
COLS = ["relation", "display_relation", "x_id", "x_type", "x_name", "x_source",
        "y_id", "y_type", "y_name", "y_source"]
TYPE = {"drug": "drug", "disease": "disease", "gene/protein": "gene"}
CAP = {"drug": "Drug", "disease": "Disease", "gene": "Gene"}       # graph_builder degree code expects these
# primekg relation -> (our relation, source type, target type, symmetric)
RELMAP = {
    "indication": ("CtD", "drug", "disease", False),
    "contraindication": ("PK_contra", "drug", "disease", False),
    "off-label use": ("PK_offlabel", "drug", "disease", False),
    "drug_protein": ("CbG", "drug", "gene", False),
    "disease_protein": ("DaG", "disease", "gene", False),
    "protein_protein": ("GiG", "gene", "gene", True),
    "disease_disease": ("PK_DisDis", "disease", "disease", True),
    "drug_drug": ("PK_DDI", "drug", "drug", True),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest()


def read_kg(path: Path, keep_rel: set):
    """Chunked read: returns (kept edge rows, drug nodes, disease nodes, gene nodes seen in kept rows)."""
    kept, nodes = [], []
    for ch in pd.read_csv(path, usecols=COLS, dtype=str, chunksize=1_000_000):
        for s in ("x", "y"):
            m = ch[f"{s}_type"].isin(["drug", "disease"])
            nodes.append(ch.loc[m, [f"{s}_id", f"{s}_type", f"{s}_name", f"{s}_source"]]
                         .set_axis(["id", "type", "name", "source"], axis=1).drop_duplicates())
        kept.append(ch[ch.relation.isin(keep_rel)])
    kept = pd.concat(kept, ignore_index=True)
    nodes = pd.concat(nodes).drop_duplicates(["id", "type"]).reset_index(drop=True)
    return kept, nodes


def build_edges(kept: pd.DataFrame, disease_id_of: dict, include_ddi: bool):
    out, stats = [], {}
    for prel, (rel, st, tt, sym) in RELMAP.items():
        if prel == "drug_drug" and not include_ddi:
            continue
        sub = kept[kept.relation == prel]
        if sub.empty:
            continue
        x_t, y_t = sub.x_type.map(TYPE), sub.y_type.map(TYPE)
        fwd = (x_t == st) & (y_t == tt)
        rev = (x_t == tt) & (y_t == st) & ~fwd
        a = pd.concat([
            pd.DataFrame({"s": sub.x_id[fwd], "t": sub.y_id[fwd]}),
            pd.DataFrame({"s": sub.y_id[rev], "t": sub.x_id[rev]})])
        a["disp"] = pd.concat([sub.display_relation[fwd], sub.display_relation[rev]])
        n_in = len(sub)
        if sym:                                    # undirected: canonical order, one row per pair
            lo = np.where(a.s <= a.t, a.s, a.t)
            hi = np.where(a.s <= a.t, a.t, a.s)
            a["s"], a["t"] = lo, hi
        a = a.drop_duplicates(["s", "t"])
        if st == "disease":
            a["s"] = a.s.map(disease_id_of)
        if tt == "disease":
            a["t"] = a.t.map(disease_id_of)
        unresolved = int(a.s.isna().sum() + a.t.isna().sum())
        a = a.dropna(subset=["s", "t"])
        e = pd.DataFrame({"source_id": a.s.values, "target_id": a.t.values, "relation": rel,
                          "source_type": CAP[st], "target_type": CAP[tt],
                          "primekg_relation": prel, "primekg_display_relation": a.disp.values})
        out.append(e)
        stats[rel] = {"primekg_relation": prel, "rows_in_kg": n_in, "edges_kept": len(e),
                      "unresolved_endpoints": unresolved}
    return pd.concat(out, ignore_index=True), stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/primekg_morgan.yaml")
    ap.add_argument("--kg", default=str(EXT / "primekg_kg.csv"))
    ap.add_argument("--mondo", default=str(EXT / "mondo.obo"))
    ap.add_argument("--include-ddi", action="store_true", help="also keep drug-drug interactions (2.7M edges, heavy)")
    ap.add_argument("--skip-relations", nargs="*", default=[],
                    help="PrimeKG relations to leave out for a lighter graph, e.g. protein_protein disease_disease")
    ap.add_argument("--no-smiles", action="store_true", help="skip SMILES/fingerprints (zero features) - quick test only")
    ap.add_argument("--no-fetch", action="store_true", help="use cached SMILES only, do not call MyChem")
    a = ap.parse_args()

    cfg = yaml.safe_load(open(REPO / a.config))
    exp = cfg["experiment"]["name"]
    out = REPO / "data" / "processed" / exp
    out.mkdir(parents=True, exist_ok=True)
    flags = cfg.get("features", {})
    for p in (a.kg, a.mondo):
        if not Path(p).exists():
            sys.exit(f"missing {p} - run: python scripts/fetch_public_data.py --primekg")

    print("[1/6] reading PrimeKG (chunked) ...")
    keep = {k for k in RELMAP if a.include_ddi or k != "drug_drug"} - set(a.skip_relations)
    if not {"indication", "contraindication", "off-label use"} <= keep:
        sys.exit("indication / contraindication / off-label use cannot be skipped")
    kept, nodes = read_kg(Path(a.kg), keep)
    print(f"      kept relation rows: {kept.relation.value_counts().to_dict()}")

    print("[2/6] disease nodes: MONDO -> DOID mapping (no node dropped) ...")
    terms = parse_mondo(Path(a.mondo))
    children = build_children(terms)
    dis = nodes[nodes.type == "disease"][["id", "name", "source"]].reset_index(drop=True)
    nm = map_disease_nodes(dis, terms)
    ntd = ntd_node_groups(nm, terms, children)
    nm["disease_id"] = [("MONDO_GROUP:" + r.primekg_id) if r.grouped else pad(r.primekg_id) for r in nm.itertuples()]
    diseases = pd.DataFrame({
        "disease_id": nm.disease_id, "disease_name": nm.name, "node_type": "disease",
        "is_ntd": nm.primekg_id.map(lambda i: int(i in ntd)),
        "ntd_groups": nm.primekg_id.map(lambda i: "|".join(ntd.get(i, []))),
        "daly_rate": np.nan,                         # real DALY data joins later; unknown stays NaN
        "primekg_id": nm.primekg_id, "mapping_status": nm.status, "doid_exact": nm.doid_exact,
        "mondo_resolved": nm.mondo_resolved, "obsolete_status": nm.obsolete_status,
    })
    disease_id_of = dict(zip(nm.primekg_id, nm.disease_id))

    print("[3/6] edges ...")
    edges, estats = build_edges(kept, disease_id_of, a.include_ddi)

    print("[4/6] drugs + SMILES + fingerprints ...")
    drugs = nodes[nodes.type == "drug"][["id", "name"]].rename(columns={"id": "drug_id"}).reset_index(drop=True)
    drugs["node_type"] = "drug"
    smiles = {}
    cache = EXT / "drugbank_smiles_cache.json"
    if cache.exists():
        smiles = json.loads(cache.read_text())
    if not a.no_smiles and not a.no_fetch:
        from fetch_smiles import resolve_smiles          # MyChem -> PubChem; merges into the cache
        smiles = resolve_smiles(drugs.drug_id.tolist())
    drugs["smiles"] = drugs.drug_id.map(smiles).fillna("")
    drugs["has_smiles"] = (drugs.smiles != "").astype(int)
    if a.no_smiles:
        feats = np.zeros((len(drugs), 2048), dtype=np.float32)
    else:
        from src.features.drug import featurize_drugs_df
        drugs, feats = featurize_drugs_df(drugs, flags.get("drug", {}), smiles_col="smiles")
        assert len(drugs) == len(feats)
    print(f"      SMILES coverage: {int(drugs.has_smiles.sum())}/{len(drugs)}")

    print("[5/6] genes + disease features ...")
    gids = pd.unique(pd.concat([edges.loc[edges.source_type == "Gene", "source_id"],
                                edges.loc[edges.target_type == "Gene", "target_id"]]))
    gname = {}
    for s in ("x", "y"):                              # symbols from the kept rows
        m = kept[f"{s}_type"] == "gene/protein"
        gname.update(dict(zip(kept.loc[m, f"{s}_id"], kept.loc[m, f"{s}_name"])))
    genes = pd.DataFrame({"gene_id": gids, "gene_symbol": [gname.get(g, g) for g in gids], "node_type": "gene"})
    dfeat = build_disease_feature_matrix(diseases, flags.get("disease", {}))

    print("[6/6] writing ...")
    drugs.to_csv(out / "drugs.csv", index=False)
    diseases.to_csv(out / "diseases.csv", index=False)
    genes.to_csv(out / "genes.csv", index=False)
    edges.to_csv(out / "edges.csv", index=False)
    np.save(out / "drug_features.npy", feats)
    np.save(out / "disease_features.npy", dfeat)
    prov = {
        "created_utc": datetime.datetime.utcnow().isoformat(timespec="seconds"),
        "source": {"primekg_kg_csv": str(a.kg), "sha256": sha256(Path(a.kg)),
                   "doi": "10.7910/DVN/IXA7BM (Harvard Dataverse, CC0 1.0 per Dataverse metadata)",
                   "mondo": mondo_version(Path(a.mondo))},
        "relation_map": {k: v[0] for k, v in RELMAP.items()},
        "label_semantics": {"target": "indication (CtD)",
                            "contraindication": "PK_contra - graph relation / diagnostic, not a negative",
                            "off-label use": "PK_offlabel - graph relation / diagnostic, not a negative"},
        "edge_stats": estats,
        "nodes": {"drugs": len(drugs), "diseases": len(diseases), "genes": len(genes)},
        "drug_smiles_coverage": int(drugs.has_smiles.sum()),
        "disease_mapping_status": diseases.mapping_status.value_counts().to_dict(),
        "ntd_disease_nodes": int(diseases.is_ntd.sum()),
        "notes": ["Every edge row carries primekg_relation/primekg_display_relation as provenance.",
                  "Upstream DrugBank/DrugCentral terms apply to derived label files; check before redistributing.",
                  "Drug-protein etc. edges are not in any held-out label set; see primekg_split.py for leakage rules."],
    }
    (out / "primekg_provenance.json").write_text(json.dumps(prov, indent=2))
    (out / "graph_metadata.json").write_text(json.dumps(
        {"nodes": prov["nodes"], "edges": {k: v["edges_kept"] for k, v in estats.items()}}, indent=2))
    print(json.dumps({"nodes": prov["nodes"], "edge_stats": estats}, indent=2))
    print(f"\nDONE -> {out}")


if __name__ == "__main__":
    main()
