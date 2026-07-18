"""
scripts/preprocess.py - Unified Preprocessing Pipeline for VectorDrugMatch

REPLACES: process_pubchem_bulk.py, featurize_pubchem.py, preprocess_all.py

This single script:
  1. Loads PubChem CID-SMILES → drugs.csv + drug_features.npy (Morgan FP 2048-bit)
  2. Loads DisGeNET → diseases.csv + genes.csv
  3. Loads Hetionet v1.0 → edges.csv (ALL relation types preserved)
  4. Merges, validates, and produces graph_metadata.json

Usage:
    python scripts/preprocess.py
    python scripts/preprocess.py --pubchem-limit 50000   # limit PubChem rows for testing
"""

import argparse
import json
import sys
import time
import os
import requests
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx
import yaml

# Add repo root to Python path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

from src.features.drug import featurize_drugs_df
from src.features.disease import build_disease_feature_matrix

# ---------------------------------------------------------------------------
# Project paths (resolve relative to repo root regardless of cwd)
# ---------------------------------------------------------------------------
DATA_DIR = REPO_ROOT / "data"
RAW = DATA_DIR / "raw"
PROC = DATA_DIR / "processed"
EXTERNAL = DATA_DIR / "external"

# ---------------------------------------------------------------------------
# Hetionet relation types we care about
# ---------------------------------------------------------------------------
HETIONET_RELATIONS = {
    "CtD": ("Compound", "Disease", "Compound treats Disease"),
    "CpD": ("Compound", "Disease", "Compound palliates Disease"),
    "CbG": ("Compound", "Gene", "Compound binds Gene"),
    "CdG": ("Compound", "Gene", "Compound downregulates Gene"),
    "CuG": ("Compound", "Gene", "Compound upregulates Gene"),
    "DaG": ("Disease", "Gene", "Disease associates Gene"),
    "DuG": ("Disease", "Gene", "Disease upregulates Gene"),
    "DdG": ("Disease", "Gene", "Disease downregulates Gene"),
    "GiG": ("Gene", "Gene", "Gene interacts Gene"),
    "GrG": ("Gene", "Gene", "Gene regulates Gene"),
    # Add more as needed - we keep ALL from Hetionet
}


# ============================================================================
# 1. DRUGS - PubChem + Hetionet compounds
# ============================================================================

def _fetch_smiles_pubchem_local(drug_ids: list, raw_dir: Path) -> dict:
    """Fetch SMILES from local PubChem CID-SMILES file using SQLite for fast lookups."""
    smiles_map = {}
    cid_path = raw_dir / "CID-SMILES"
    cid_gz_path = raw_dir / "CID-SMILES.gz"
    db_path = raw_dir / "cid_smiles.db"
    
    import sqlite3
    
    # 1. Build SQLite cache if it doesn't exist
    if not db_path.exists():
        file_path = cid_gz_path if cid_gz_path.exists() else (cid_path if cid_path.exists() else None)
        if not file_path:
            print("  [WARNING] Local PubChem CID-SMILES file not found. Skipping local lookup.")
            return smiles_map
            
        print(f"  Building SQLite database from {file_path.name} (this may take a few minutes)...")
        import gzip
        
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("CREATE TABLE smiles (cid TEXT PRIMARY KEY, smiles TEXT)")
        
        open_func = gzip.open if file_path.suffix == '.gz' else open
        batch = []
        try:
            with open_func(file_path, "rt") as f:
                for line in f:
                    parts = line.strip().split("\t")
                    if len(parts) >= 2:
                        batch.append((parts[0], parts[1]))
                    if len(batch) >= 100000:
                        c.executemany("INSERT OR IGNORE INTO smiles VALUES (?, ?)", batch)
                        batch = []
            if batch:
                c.executemany("INSERT OR IGNORE INTO smiles VALUES (?, ?)", batch)
            conn.commit()
            print("  [DONE] SQLite database built successfully.")
        except Exception as e:
            print(f"  [WARNING] Error building SQLite DB: {e}")
            conn.close()
            if db_path.exists():
                db_path.unlink()
            return smiles_map
        finally:
            conn.close()

    # 2. Query SQLite
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        print(f"  Looking up SMILES in local SQLite database...")
        
        # Clean IDs for querying
        clean_dids = [str(did)[3:] if str(did).startswith("CID") else str(did) for did in drug_ids]
        
        chunk_size = 900
        for i in range(0, len(clean_dids), chunk_size):
            chunk = clean_dids[i:i+chunk_size]
            placeholders = ",".join(["?"] * len(chunk))
            c.execute(f"SELECT cid, smiles FROM smiles WHERE cid IN ({placeholders})", chunk)
            
            for cid, smiles in c.fetchall():
                smiles_map[cid] = smiles
                smiles_map[f"CID{cid}"] = smiles
                    
    except Exception as e:
        print(f"  [WARNING] Error querying SQLite DB: {e}")
    finally:
        if 'conn' in locals():
            conn.close()
            
    return smiles_map

def _fetch_smiles_mychem(drugbank_ids: list, cache_path: Path) -> dict:
    """Fetch SMILES for a list of DrugBank IDs using MyChem.info API with caching."""
    smiles_map = {}
    if cache_path.exists():
        with open(cache_path, "r") as f:
            smiles_map = json.load(f)
            
    to_fetch = [did for did in drugbank_ids if did not in smiles_map]
    if not to_fetch:
        return smiles_map
        
    print(f"  Fetching SMILES for {len(to_fetch)} new DrugBank IDs from MyChem.info...")
    
    # Process in chunks of 100
    chunk_size = 100
    import urllib.parse
    
    for i in range(0, len(to_fetch), chunk_size):
        chunk = to_fetch[i:i+chunk_size]
        q_str = " OR ".join([f"drugbank.id:{did}" for did in chunk])
        
        try:
            resp = requests.post(
                "https://mychem.info/v1/query",
                data={"q": q_str, "fields": "drugbank.id,smiles", "scopes": "drugbank.id"}
            )
            if resp.status_code == 200:
                results = resp.json()
                for res in results:
                    if "drugbank" in res and "id" in res["drugbank"]:
                        db_id = res["drugbank"]["id"]
                        smiles = res.get("smiles")
                        if smiles:
                            smiles_map[db_id] = smiles
            time.sleep(0.2)  # rate limit compliance
        except Exception as e:
            print(f"    [WARNING] API request failed: {e}")
            
    with open(cache_path, "w") as f:
        json.dump(smiles_map, f, indent=2)
        
    return smiles_map


def build_drugs(config_flags: dict, proc_dir: Path, hetionet_nodes: pd.DataFrame | None = None,
                pubchem_limit: int | None = None) -> pd.DataFrame:
    """Build drugs.csv and drug_features.npy."""
    print("\n" + "=" * 60)
    print("1. BUILDING DRUGS")
    print("=" * 60)

    rows = []
    drugbank_ids = []
    
    # 1. Load Hetionet compounds
    hetio_nodes_path = RAW / "hetionet-v1.0-nodes.tsv"
    if hetionet_nodes is not None:
        compounds = hetionet_nodes[hetionet_nodes["kind"] == "Compound"]
    elif hetio_nodes_path.exists():
        nodes_df = pd.read_csv(hetio_nodes_path, sep="\t")
        compounds = nodes_df[nodes_df["kind"] == "Compound"]
    else:
        compounds = pd.DataFrame()

    for _, row in compounds.iterrows():
        node_id = row["id"].split("::")[-1] if "::" in str(row["id"]) else str(row["id"])
        rows.append({
            "drug_id": node_id,
            "name": row.get("name", f"Compound:{node_id}"),
            "node_type": "drug"
        })
        drugbank_ids.append(node_id)
        
    print(f"  Loaded {len(rows)} compounds from Hetionet.")

    if not rows:
        mock_drugs = RAW / "drugs.csv"
        if mock_drugs.exists():
            print("  [WARNING] Falling back to mock data/raw/drugs.csv")
            drugs_df = pd.read_csv(mock_drugs)
            if "node_type" not in drugs_df.columns:
                drugs_df["node_type"] = "drug"
            if "drug_id" not in drugs_df.columns and "id" in drugs_df.columns:
                drugs_df.rename(columns={"id": "drug_id"}, inplace=True)
            if "name" not in drugs_df.columns and "drug_name" in drugs_df.columns:
                drugs_df.rename(columns={"drug_name": "name"}, inplace=True)
            
            print("  Computing config-driven RDKit features...")
            final_df, fp_matrix = featurize_drugs_df(drugs_df, config_flags, smiles_col="smiles")
            final_df.to_csv(proc_dir / "drugs.csv", index=False)
            np.save(proc_dir / "drug_features.npy", fp_matrix)
            print(f"  [OK] drugs.csv: {len(final_df):,} drugs")
            return final_df
        
        print("  [WARNING] No drug sources found. Creating empty files.")
        drugs = pd.DataFrame(columns=["drug_id", "name", "smiles", "node_type"])
        drugs.to_csv(proc_dir / "drugs.csv", index=False)
        np.save(proc_dir / "drug_features.npy", np.zeros((0, 3246), dtype=np.float32))
        return drugs

    # 2. Get SMILES
    EXTERNAL.mkdir(parents=True, exist_ok=True)
    cache_path = EXTERNAL / "drugbank_smiles_cache.json"
    
    # Primary: Local PubChem lookup
    smiles_map = _fetch_smiles_pubchem_local(drugbank_ids, RAW)
    
    # Fallback: MyChem API
    missing_ids = [did for did in drugbank_ids if did not in smiles_map]
    if missing_ids:
        print(f"  {len(missing_ids)} IDs not found locally. Falling back to MyChem API...")
        mychem_map = _fetch_smiles_mychem(missing_ids, cache_path)
        smiles_map.update(mychem_map)
    
    missing_log_rows = []
    for row in rows:
        smi = smiles_map.get(row["drug_id"], "")
        row["smiles"] = smi
        if not smi:
            missing_log_rows.append({
                "drug_id": row["drug_id"],
                "name": row.get("name", "Unknown"),
                "reason": "Not found in local SQLite or MyChem API"
            })
            
    if missing_log_rows:
        missing_df = pd.DataFrame(missing_log_rows)
        missing_df.to_csv(proc_dir / "missing_smiles.csv", index=False)
        print(f"  [WARNING] Logged {len(missing_log_rows)} missing SMILES to missing_smiles.csv")
        
    drugs_df = pd.DataFrame(rows).drop_duplicates("drug_id")
    n_with_smiles = (drugs_df["smiles"] != "").sum()
    print(f"  Resolved SMILES for {n_with_smiles}/{len(drugs_df)} drugs.")

    # 3. Featurize
    print("  Computing config-driven RDKit features...")
    final_df, fp_matrix = featurize_drugs_df(drugs_df, config_flags, smiles_col="smiles")
    
    final_df.to_csv(proc_dir / "drugs.csv", index=False)
    np.save(proc_dir / "drug_features.npy", fp_matrix)

    print(f"  [OK] drugs.csv: {len(final_df):,} drugs")
    print(f"  [OK] drug_features.npy: shape {fp_matrix.shape}")
    return final_df


# ============================================================================
# 2. DISEASES - DisGeNET + Hetionet
# ============================================================================

def build_diseases(config_flags: dict, proc_dir: Path, hetionet_nodes: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build diseases.csv and disease_features.npy from DisGeNET and/or Hetionet."""
    print("\n" + "=" * 60)
    print("2. BUILDING DISEASES")
    print("=" * 60)

    disease_rows = []

    # --- Hetionet disease nodes ---
    hetio_nodes_path = RAW / "hetionet-v1.0-nodes.tsv"
    if hetionet_nodes is not None:
        diseases_het = hetionet_nodes[hetionet_nodes["kind"] == "Disease"]
        for _, row in diseases_het.iterrows():
            node_id = row["id"].split("::")[-1] if "::" in str(row["id"]) else str(row["id"])
            disease_rows.append({
                "disease_id": node_id,
                "disease_name": row.get("name", node_id),
                "source": "hetionet",
            })
        print(f"  Loaded {len(disease_rows)} diseases from Hetionet nodes.")
    elif hetio_nodes_path.exists():
        nodes_df = pd.read_csv(hetio_nodes_path, sep="\t")
        diseases_het = nodes_df[nodes_df["kind"] == "Disease"]
        for _, row in diseases_het.iterrows():
            node_id = row["id"].split("::")[-1] if "::" in str(row["id"]) else str(row["id"])
            disease_rows.append({
                "disease_id": node_id,
                "disease_name": row.get("name", node_id),
                "source": "hetionet",
            })
        print(f"  Loaded {len(disease_rows)} diseases from Hetionet nodes TSV.")

    # --- DisGeNET curated associations ---
    disgenet_paths = [
        RAW / "curated_gene_disease_associations.tsv",
        RAW / "curated_gene_disease_associations.tsv.gz",
    ]
    for dg_path in disgenet_paths:
        if dg_path.exists():
            try:
                compression = "gzip" if str(dg_path).endswith(".gz") else None
                dg = pd.read_csv(dg_path, sep="\t", compression=compression)
                # Find columns flexibly
                id_col = next(c for c in dg.columns if "diseaseid" in c.lower())
                name_col = next(c for c in dg.columns if "diseasename" in c.lower() or
                                ("name" in c.lower() and "disease" in c.lower()))
                dg_diseases = dg[[id_col, name_col]].drop_duplicates(id_col)
                for _, row in dg_diseases.iterrows():
                    disease_rows.append({
                        "disease_id": str(row[id_col]),
                        "disease_name": str(row[name_col]),
                        "source": "disgenet",
                    })
                print(f"  Loaded {len(dg_diseases)} diseases from DisGeNET.")
            except Exception as e:
                print(f"  [WARNING] Error reading DisGeNET: {e}")
            break

    if not disease_rows:
        mock_diseases = RAW / "diseases.csv"
        if mock_diseases.exists():
            print("  [WARNING] Falling back to mock data/raw/diseases.csv")
            diseases = pd.read_csv(mock_diseases)
            if "node_type" not in diseases.columns:
                diseases["node_type"] = "disease"
            if "disease_id" not in diseases.columns and "id" in diseases.columns:
                diseases.rename(columns={"id": "disease_id"}, inplace=True)
            
            print("  Computing config-driven disease features on mock data...")
            disease_features = build_disease_feature_matrix(diseases, config_flags)
            diseases.to_csv(proc_dir / "diseases.csv", index=False)
            np.save(proc_dir / "disease_features.npy", disease_features)
            print(f"  [OK] diseases.csv: {len(diseases):,} diseases")
            return diseases
            
        print("  [WARNING] No disease sources found.")
        diseases = pd.DataFrame(columns=["disease_id", "disease_name", "node_type",
                                          "is_ntd", "daly_rate"])
        diseases.to_csv(proc_dir / "diseases.csv", index=False)
        return diseases

    diseases = pd.DataFrame(disease_rows).drop_duplicates("disease_id")
    diseases = diseases[["disease_id", "disease_name"]].copy()
    diseases["node_type"] = "disease"
    diseases["is_ntd"] = 0
    diseases["daly_rate"] = 0.0

    # Enrich with NTD flags if external file exists
    ntd_path = EXTERNAL / "who_ntd_list.csv"
    if ntd_path.exists():
        ntd_df = pd.read_csv(ntd_path)
        if "disease_id" in ntd_df.columns:
            ntd_ids = set(ntd_df["disease_id"].astype(str))
            diseases["is_ntd"] = diseases["disease_id"].isin(ntd_ids).astype(int)
            print(f"  Enriched with NTD flags: {diseases['is_ntd'].sum()} NTDs.")

    diseases.to_csv(proc_dir / "diseases.csv", index=False)
    
    # Generate feature matrix
    print("  Computing config-driven disease features...")
    disease_features = build_disease_feature_matrix(diseases, config_flags)
    np.save(proc_dir / "disease_features.npy", disease_features)
    
    print(f"  [OK] diseases.csv: {len(diseases):,} diseases")
    print(f"  [OK] disease_features.npy: shape {disease_features.shape}")
    return diseases


# ============================================================================
# 3. GENES - DisGeNET + Hetionet
# ============================================================================

def build_genes(proc_dir: Path, hetionet_nodes: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build genes.csv from DisGeNET and/or Hetionet."""
    print("\n" + "=" * 60)
    print("3. BUILDING GENES")
    print("=" * 60)

    gene_rows = []

    # --- Hetionet gene nodes ---
    hetio_nodes_path = RAW / "hetionet-v1.0-nodes.tsv"
    if hetionet_nodes is not None:
        genes_het = hetionet_nodes[hetionet_nodes["kind"] == "Gene"]
        for _, row in genes_het.iterrows():
            node_id = row["id"].split("::")[-1] if "::" in str(row["id"]) else str(row["id"])
            gene_rows.append({
                "gene_id": node_id,
                "gene_symbol": row.get("name", node_id),
                "source": "hetionet",
            })
        print(f"  Loaded {len(gene_rows)} genes from Hetionet nodes.")
    elif hetio_nodes_path.exists():
        nodes_df = pd.read_csv(hetio_nodes_path, sep="\t")
        genes_het = nodes_df[nodes_df["kind"] == "Gene"]
        for _, row in genes_het.iterrows():
            node_id = row["id"].split("::")[-1] if "::" in str(row["id"]) else str(row["id"])
            gene_rows.append({
                "gene_id": node_id,
                "gene_symbol": row.get("name", node_id),
                "source": "hetionet",
            })
        print(f"  Loaded {len(gene_rows)} genes from Hetionet nodes TSV.")

    # --- DisGeNET genes ---
    disgenet_paths = [
        RAW / "curated_gene_disease_associations.tsv",
        RAW / "curated_gene_disease_associations.tsv.gz",
    ]
    for dg_path in disgenet_paths:
        if dg_path.exists():
            try:
                compression = "gzip" if str(dg_path).endswith(".gz") else None
                dg = pd.read_csv(dg_path, sep="\t", compression=compression)
                gene_id_col = next(c for c in dg.columns if "geneid" in c.lower())
                gene_sym_col = next(c for c in dg.columns if "genesymbol" in c.lower() or
                                    "symbol" in c.lower())
                dg_genes = dg[[gene_id_col, gene_sym_col]].drop_duplicates(gene_id_col)
                for _, row in dg_genes.iterrows():
                    gene_rows.append({
                        "gene_id": str(row[gene_id_col]),
                        "gene_symbol": str(row[gene_sym_col]),
                        "source": "disgenet",
                    })
                print(f"  Loaded {len(dg_genes)} genes from DisGeNET.")
            except Exception as e:
                print(f"  [WARNING] Error reading DisGeNET genes: {e}")
            break

    if not gene_rows:
        mock_genes = RAW / "genes.csv"
        if mock_genes.exists():
            print("  [WARNING] Falling back to mock data/raw/genes.csv")
            genes = pd.read_csv(mock_genes)
            if "node_type" not in genes.columns:
                genes["node_type"] = "gene"
            genes.to_csv(proc_dir / "genes.csv", index=False)
            print(f"  [OK] genes.csv: {len(genes):,} genes")
            return genes
            
        print("  [WARNING] No gene sources found.")
        genes = pd.DataFrame(columns=["gene_id", "gene_symbol", "node_type"])
        genes.to_csv(proc_dir / "genes.csv", index=False)
        return genes

    genes = pd.DataFrame(gene_rows).drop_duplicates("gene_id")
    genes = genes[["gene_id", "gene_symbol"]].copy()
    genes["node_type"] = "gene"

    genes.to_csv(proc_dir / "genes.csv", index=False)
    print(f"  [OK] genes.csv: {len(genes):,} genes")
    return genes


# ============================================================================
# 4. EDGES - Hetionet (ALL types) + DisGeNET
# ============================================================================

def build_edges(proc_dir: Path) -> pd.DataFrame:
    """Build edges.csv preserving ALL heterogeneous relation types.

    ⭐ CRITICAL FIX: The old preprocess_all.py only kept CtD edges (137 rows).
    This version keeps ALL Hetionet relation types + DisGeNET high-confidence
    gene-disease associations, producing 50,000+ edges.
    """
    print("\n" + "=" * 60)
    print("4. BUILDING EDGES (ALL RELATION TYPES)")
    print("=" * 60)

    all_edges = []

    # --- Hetionet edges (ALL types) ---
    hetio_paths = [
        RAW / "hetionet-v1.0-edges.sif",
        RAW / "hetionet-v1.0-edges.sif.gz",
        RAW / "hetionet_edges.tsv",
        RAW / "hetionet-v1.0-edges.sdf",
    ]

    het = None
    for hp in hetio_paths:
        if hp.exists():
            print(f"  Loading Hetionet from: {hp.name}")
            compression = "gzip" if str(hp).endswith(".gz") else None
            try:
                het = pd.read_csv(hp, sep="\t", header=None, compression=compression)
                if het.shape[1] < 3:
                    het = pd.read_csv(hp, sep=r"\s+", header=None, compression=compression)
                het.columns = ["source", "metaedge", "target"][:het.shape[1]]
                break
            except Exception as e:
                print(f"    [WARNING] Failed to read {hp.name}: {e}")
                het = None

    if het is not None:
        het = het.dropna(subset=["source", "metaedge", "target"])

        # Parse source/target IDs and types (format: "Type::ID")
        def parse_node(val):
            s = str(val)
            if "::" in s:
                parts = s.split("::", 1)
                return parts[1], parts[0]
            return s, "Unknown"

        het["source_id"] = het["source"].apply(lambda x: parse_node(x)[0])
        het["source_type"] = het["source"].apply(lambda x: parse_node(x)[1])
        het["target_id"] = het["target"].apply(lambda x: parse_node(x)[0])
        het["target_type"] = het["target"].apply(lambda x: parse_node(x)[1])

        het_edges = het[["source_id", "target_id", "metaedge", "source_type", "target_type"]].copy()
        het_edges = het_edges.rename(columns={"metaedge": "relation"})
        het_edges = het_edges.drop_duplicates()

        all_edges.append(het_edges)
        print(f"  [OK] Hetionet edges: {len(het_edges):,}")
        print("    Relation breakdown:")
        for rel, count in het_edges["relation"].value_counts().items():
            desc = HETIONET_RELATIONS.get(rel, ("?", "?", rel))[2]
            print(f"      {rel}: {count:>8,}  ({desc})")
    else:
        print("  [WARNING] No Hetionet edge file found. Skipping.")

    # --- DisGeNET gene-disease associations (high confidence) ---
    disgenet_paths = [
        RAW / "curated_gene_disease_associations.tsv",
        RAW / "curated_gene_disease_associations.tsv.gz",
    ]
    for dg_path in disgenet_paths:
        if dg_path.exists():
            try:
                compression = "gzip" if str(dg_path).endswith(".gz") else None
                dg = pd.read_csv(dg_path, sep="\t", compression=compression)
                gene_col = next(c for c in dg.columns if "geneid" in c.lower())
                disease_col = next(c for c in dg.columns if "diseaseid" in c.lower())
                score_col = next((c for c in dg.columns if c.lower() == "score"), None)

                gene_disease = dg[[gene_col, disease_col]].copy()
                if score_col:
                    gene_disease["_score"] = dg[score_col]
                    gene_disease = gene_disease[gene_disease["_score"] > 0.3]
                    gene_disease = gene_disease.drop(columns=["_score"])

                gene_disease.columns = ["source_id", "target_id"]
                gene_disease["source_id"] = gene_disease["source_id"].astype(str)
                gene_disease["target_id"] = gene_disease["target_id"].astype(str)
                gene_disease["relation"] = "DaG_disgenet"
                gene_disease["source_type"] = "Gene"
                gene_disease["target_type"] = "Disease"
                gene_disease = gene_disease.drop_duplicates()

                all_edges.append(gene_disease)
                print(f"  [OK] DisGeNET gene-disease edges: {len(gene_disease):,}")
            except Exception as e:
                print(f"  [WARNING] Error reading DisGeNET edges: {e}")
            break

    if not all_edges:
        mock_edges = RAW / "edges.csv"
        if mock_edges.exists():
            print("  [WARNING] Falling back to mock data/raw/edges.csv")
            edges = pd.read_csv(mock_edges)
            if "source" in edges.columns:
                edges.rename(columns={"source": "source_id", "target": "target_id"}, inplace=True)
            if "source_type" not in edges.columns:
                edges["source_type"] = "Drug"
            if "target_type" not in edges.columns:
                edges["target_type"] = "Disease"
            
            # Map mock relations to expected Hetionet metaedges
            if "relation" in edges.columns:
                edges["relation"] = edges["relation"].replace({
                    "treats": "CtD",
                    "drug_targets_gene": "CbG",
                    "gene_associated_with_disease": "DaG_disgenet"
                })
                
            edges.to_csv(proc_dir / "edges.csv", index=False)
            print(f"\n  [OK] edges.csv: {len(edges):,} total edges")
            return edges
            
        print("  [WARNING] No edge sources found. Creating empty edges.csv.")
        edges = pd.DataFrame(columns=["source_id", "target_id", "relation",
                                       "source_type", "target_type"])
        edges.to_csv(proc_dir / "edges.csv", index=False)
        return edges

    edges = pd.concat(all_edges, ignore_index=True)
    edges = edges.drop_duplicates(subset=["source_id", "target_id", "relation"])

    edges.to_csv(proc_dir / "edges.csv", index=False)
    print(f"\n  [OK] edges.csv: {len(edges):,} total edges")
    return edges


# ============================================================================
# 5. VALIDATION & METADATA
# ============================================================================

def validate_and_save_metadata(drugs: pd.DataFrame, diseases: pd.DataFrame,
                                genes: pd.DataFrame, edges: pd.DataFrame) -> dict:
    """Cross-reference outputs and save graph_metadata.json."""
    print("\n" + "=" * 60)
    print("5. VALIDATION & METADATA")
    print("=" * 60)

    # Edge type breakdown
    edge_counts = {}
    if len(edges) > 0 and "relation" in edges.columns:
        edge_counts = edges["relation"].value_counts().to_dict()

    # Positive label count
    n_positive = 0
    if "relation" in edges.columns:
        n_positive = int((edges["relation"] == "CtD").sum())

    # Check for duplicates
    n_dup_drugs = int(drugs.duplicated("drug_id").sum()) if len(drugs) > 0 else 0
    n_dup_edges = int(edges.duplicated(subset=["source_id", "target_id", "relation"]).sum()) if len(edges) > 0 else 0

    # Drug SMILES coverage
    n_with_smiles = 0
    if "smiles" in drugs.columns:
        n_with_smiles = int((drugs["smiles"] != "").sum())

    # Check for disconnected components and isolated nodes
    G = nx.Graph()
    if len(edges) > 0:
        edges_list = list(zip(edges["source_id"].astype(str), edges["target_id"].astype(str)))
        G.add_edges_from(edges_list)
        
    all_nodes = set(drugs["drug_id"].astype(str)) | set(diseases["disease_id"].astype(str)) | set(genes["gene_id"].astype(str))
    isolated_nodes = all_nodes - set(G.nodes)
    
    n_components = nx.number_connected_components(G) if len(G.nodes) > 0 else 0
    isolated_drugs = len(set(drugs["drug_id"].astype(str)).intersection(isolated_nodes))
    isolated_diseases = len(set(diseases["disease_id"].astype(str)).intersection(isolated_nodes))
    isolated_genes = len(set(genes["gene_id"].astype(str)).intersection(isolated_nodes))

    # Calculate averages if descriptors exist
    avg_mw = float(drugs["mw"].mean()) if "mw" in drugs.columns else 0.0
    avg_logp = float(drugs["logp"].mean()) if "logp" in drugs.columns else 0.0

    metadata = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "node_counts": {
            "drugs": int(len(drugs)),
            "diseases": int(len(diseases)),
            "genes": int(len(genes)),
            "total": int(len(drugs) + len(diseases) + len(genes)),
        },
        "edge_counts": {
            "total": int(len(edges)),
            "positive_labels_CtD": n_positive,
            "by_relation": {k: int(v) for k, v in edge_counts.items()},
        },
        "validation": {
            "duplicate_drugs": n_dup_drugs,
            "duplicate_edges": n_dup_edges,
            "drugs_with_smiles": n_with_smiles,
            "drugs_without_smiles": int(len(drugs)) - n_with_smiles,
            "connected_components": n_components,
            "isolated_nodes_total": len(isolated_nodes),
            "isolated_drugs": isolated_drugs,
            "isolated_diseases": isolated_diseases,
            "isolated_genes": isolated_genes,
        },
    }

    # Add SHA256 checksum
    import hashlib
    metadata_str = json.dumps(metadata, sort_keys=True)
    metadata["sha256"] = hashlib.sha256(metadata_str.encode("utf-8")).hexdigest()

    meta_path = PROC / "graph_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)
        
    outputs_dir = REPO_ROOT / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    
    report_data = {
        "drugs": int(len(drugs)),
        "resolved_smiles": n_with_smiles,
        "missing_smiles": int(len(drugs)) - n_with_smiles,
        "avg_mw": round(avg_mw, 2),
        "avg_logp": round(avg_logp, 2)
    }
    
    report_path = outputs_dir / "preprocessing_report.json"
    with open(report_path, "w") as f:
        json.dump(report_data, f, indent=2, default=str)

    # --- Print summary ---
    print(f"\n  {'=' * 40}")
    print(f"  PREPROCESSING SUMMARY")
    print(f"  {'=' * 40}")
    print(f"  Drug nodes:          {metadata['node_counts']['drugs']:>8,}")
    print(f"    with SMILES:       {metadata['validation']['drugs_with_smiles']:>8,}")
    print(f"    without SMILES:    {metadata['validation']['drugs_without_smiles']:>8,}")
    print(f"  Disease nodes:       {metadata['node_counts']['diseases']:>8,}")
    print(f"  Gene nodes:          {metadata['node_counts']['genes']:>8,}")
    print(f"  Total nodes:         {metadata['node_counts']['total']:>8,}")
    print(f"  Total edges:         {metadata['edge_counts']['total']:>8,}")
    print(f"  Positive labels(CtD):{metadata['edge_counts']['positive_labels_CtD']:>8,}")
    print(f"  Duplicate drugs:     {metadata['validation']['duplicate_drugs']:>8}")
    print(f"  Duplicate edges:     {metadata['validation']['duplicate_edges']:>8}")

    # --- Validation warnings ---
    warnings = []
    if metadata["edge_counts"]["total"] < 1000:
        warnings.append(f"[WARNING] Only {metadata['edge_counts']['total']} edges. Expected 50,000+.")
    if metadata["edge_counts"]["positive_labels_CtD"] < 100:
        warnings.append(f"[WARNING] Only {metadata['edge_counts']['positive_labels_CtD']} CtD edges. Expected 750+.")
    if metadata["node_counts"]["genes"] < 100:
        warnings.append(f"[WARNING] Only {metadata['node_counts']['genes']} genes. Expected 20,000+.")
    if metadata["validation"]["duplicate_edges"] > 0:
        warnings.append(f"[WARNING] Found {metadata['validation']['duplicate_edges']} duplicate edges.")
    if metadata["validation"]["isolated_diseases"] > 0:
        warnings.append(f"[WARNING] Found {metadata['validation']['isolated_diseases']} isolated diseases.")
    if metadata["validation"]["isolated_drugs"] > 0:
        warnings.append(f"[WARNING] Found {metadata['validation']['isolated_drugs']} isolated drugs.")
    if metadata["validation"]["connected_components"] > 5:
        warnings.append(f"[WARNING] Graph is highly fragmented ({metadata['validation']['connected_components']} components).")

    if warnings:
        print(f"\n  {'-' * 40}")
        print("  WARNINGS:")
        for w in warnings:
            print(f"    {w}")
    else:
        print(f"\n  [DONE] All validation checks passed.")

    print(f"\n  Metadata saved to: {meta_path}")
    return metadata


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="VectorDrugMatch Unified Preprocessing")
    parser.add_argument("--config", type=str, default="config.yaml",
                        help="Path to experiment config file")
    parser.add_argument("--pubchem-limit", type=int, default=None,
                        help="Limit number of PubChem CID-SMILES rows to load (for testing)")
    args = parser.parse_args()

    print("==========================================================")
    print("   VectorDrugMatch - Unified Preprocessing Pipeline      ")
    print("==========================================================")
    print(f"\n  Raw data dir:       {RAW}")
    print(f"  Processed data dir: {PROC}")

    PROC.mkdir(parents=True, exist_ok=True)

    # Check what raw files exist
    print("\n  Available raw files:")
    if RAW.exists():
        for f in sorted(RAW.iterdir()):
            if f.is_file():
                size_mb = f.stat().st_size / (1024 * 1024)
                print(f"    {f.name} ({size_mb:.1f} MB)")
    else:
        print("    [WARNING] data/raw/ directory not found!")
        RAW.mkdir(parents=True, exist_ok=True)

    # Load Hetionet nodes once (shared by drugs, diseases, genes)
    hetionet_nodes = None
    hetio_nodes_path = RAW / "hetionet-v1.0-nodes.tsv"
    if hetio_nodes_path.exists():
        hetionet_nodes = pd.read_csv(hetio_nodes_path, sep="\t")
        print(f"\n  Hetionet nodes loaded: {len(hetionet_nodes):,} ({hetionet_nodes['kind'].value_counts().to_dict()})")

    # Build each component
    t_start = time.time()

    # Load configuration
    config_path = REPO_ROOT / args.config
    config_dict = {}
    if config_path.exists():
        with open(config_path, "r") as f:
            config_dict = yaml.safe_load(f)
            
    drug_flags = config_dict.get("features", {}).get("drug", {})
    disease_flags = config_dict.get("features", {}).get("disease", {})
    
    exp_name = config_dict.get("experiment", {}).get("name", "baseline")
    proc_exp = PROC / exp_name
    proc_exp.mkdir(parents=True, exist_ok=True)
    
    drugs = build_drugs(drug_flags, proc_exp, hetionet_nodes, pubchem_limit=args.pubchem_limit)
    diseases = build_diseases(disease_flags, proc_exp, hetionet_nodes)
    genes = build_genes(proc_exp, hetionet_nodes)
    edges = build_edges(proc_exp)

    validate_and_save_metadata(drugs, diseases, genes, edges)

    elapsed = time.time() - t_start
    print(f"\n  Total time: {elapsed:.1f}s")
    print("  [DONE] Preprocessing complete.\n")


if __name__ == "__main__":
    main()
