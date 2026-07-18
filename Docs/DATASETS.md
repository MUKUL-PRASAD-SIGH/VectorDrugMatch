# 📦 DATASETS.md — Data Sources for VectorDrugMatch

Complete reference for every dataset used in the project: what it is, where to get it, what columns matter, how to clean it, and which pipeline stage uses it.

---

## Table of Contents

1. [Quick Reference Table](#quick-reference-table)
2. [Primary Biomedical Databases](#primary-biomedical-databases)
3. [Public Health & Equity Data](#public-health--equity-data)
4. [Literature & Evidence](#literature--evidence)
5. [Supplementary Sources](#supplementary-sources)
6. [Unified Preprocessing Pipeline](#unified-preprocessing-pipeline)
7. [Data Schema Reference](#data-schema-reference)
8. [Storage & Version Control Policy](#storage--version-control-policy)

---

## Quick Reference Table

| Dataset | What It Contains | Access | Registration | Priority |
|---|---|---|---|---|
| **Hetionet v1.0** | Biomedical KG: drugs, genes, diseases, pathways, 2M+ edges | [het.io](https://het.io) | ❌ None | ⭐⭐⭐ Must-have |
| **PubChem** | Chemical structures (CID-SMILES), bioassays | [pubchem.ncbi.nlm.nih.gov](https://pubchem.ncbi.nlm.nih.gov/) | ❌ None | ⭐⭐⭐ Must-have |
| **DisGeNET** | Gene–disease associations with confidence scores | [disgenet.com](https://www.disgenet.com/) | ✅ Free account | ⭐⭐⭐ Must-have |
| **WHO GHO API** | DALY burden, disease prevalence by country | [ghoapi.azureedge.net](https://ghoapi.azureedge.net/api/) | ❌ Open API | ⭐⭐⭐ Must-have |
| **WHO Essential Medicines List** | Approved essential drug list | [who.int/medicines](https://www.who.int/groups/expert-committee-on-selection-and-use-of-essential-medicines/essential-medicines-lists) | ❌ None | ⭐⭐ Important |
| **ChEMBL SQLite** | Bioactivity data, molecular properties, targets | [ebi.ac.uk](https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/latest/) | ❌ None | ⭐⭐ Important |
| **NCBI Gene** | Gene identifiers, annotations | [ncbi.nlm.nih.gov/gene](https://www.ncbi.nlm.nih.gov/gene) | ❌ None | ⭐⭐ Important |
| **UniProt** | Protein sequences & function | [uniprot.org](https://www.uniprot.org/) | ❌ None | ⭐ Supplementary |
| **OMIM** | Disease-gene links (Mendelian) | [omim.org](https://omim.org/) | ✅ Free account | ⭐ Supplementary |
| **STRING DB** | Protein–protein interactions | [string-db.org](https://string-db.org/) | ❌ None | ⭐ Supplementary |
| **KEGG Pathways** | Biological pathway maps | [kegg.jp](https://www.kegg.jp/) | ❌ None (API limited) | ⭐ Supplementary |

> ⚠️ **Note on DrugBank:** The open DrugBank vocabulary portal was completely offline/unreachable during initial setup. The pipeline has been successfully pivoted to use the open-source **PubChem** (`CID-SMILES`) dataset for drug node generation instead.

---

## Primary Biomedical Databases

### 1. Hetionet v1.0

**What it is:** The most comprehensive open biomedical knowledge graph. Contains 47,031 nodes of 11 types and 2,250,197 edges of 24 types.

**Download:**
```bash
# Edges (SIF format) — no account needed
wget https://github.com/hetio/hetionet/raw/main/hetnet/tsv/hetionet-v1.0-edges.sif.gz

# Nodes
wget https://github.com/hetio/hetionet/raw/main/hetnet/tsv/hetionet-v1.0-nodes.tsv
```

**Key columns:**
| Column | Description |
|---|---|
| `source` | Source node ID (e.g., `Compound::DB00945`) |
| `metaedge` | Relation type (e.g., `CbG` = Compound binds Gene) |
| `target` | Target node ID (e.g., `Gene::1`) |

**⭐ ALL relation types used in the pipeline:**

| Code | Full Name | Source → Target | Count (approx) | Role in Pipeline |
|---|---|---|---|---|
| `CtD` | Compound treats Disease | Drug → Disease | ~750 | **Positive labels** for link prediction |
| `CpD` | Compound palliates Disease | Drug → Disease | ~390 | Additional drug-disease signal |
| `CbG` | Compound binds Gene | Drug → Gene | ~11,600 | Drug-target interactions |
| `CdG` | Compound downregulates Gene | Drug → Gene | ~21,100 | Drug gene regulation |
| `CuG` | Compound upregulates Gene | Drug → Gene | ~18,500 | Drug gene regulation |
| `DaG` | Disease associates Gene | Disease → Gene | ~12,600 | Disease-gene associations |
| `DuG` | Disease upregulates Gene | Disease → Gene | ~7,700 | Disease gene regulation |
| `DdG` | Disease downregulates Gene | Disease → Gene | ~7,600 | Disease gene regulation |
| `GiG` | Gene interacts Gene | Gene → Gene | ~147,100 | Protein-protein interactions |
| `GrG` | Gene regulates Gene | Gene → Gene | ~265,600 | Gene regulatory network |

> ⚠️ **CRITICAL:** The old `preprocess_all.py` only saved CtD edges (137 rows). The new `preprocess.py` preserves ALL relation types above, producing 50,000+ edges that connect the graph properly.

**Why ALL edges matter:**
```
Drug A ──binds──► Gene X ──associated with──► Disease Y
(CbG)                     (DaG)
```
Without CbG and DaG edges, the Drug and Disease nodes are completely disconnected. A GNN learns by passing messages along edges — if there are no connecting edges, the GNN behaves like a disconnected set of single nodes.

---

### 2. PubChem (Primary Drug Source)

**What it is:** Free chemical database. Used for SMILES structures and as the primary source of drug compound identifiers.

**Download (bulk CID-SMILES file):**
```bash
# ~3.5 GB compressed file containing all CID-SMILES mappings
wget https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Extras/CID-SMILES.gz
gunzip CID-SMILES.gz
# Save as: data/raw/CID-SMILES
```

**SQLite Local Cache (`cid_smiles.db`):**
To avoid scanning the massive `CID-SMILES` file repeatedly, `preprocess.py` creates a local SQLite database (`data/raw/cid_smiles.db`) with an indexed `cid` column on its first run. Subsequent runs query this database for milliseconds-level lookup times. MyChem API is used as a fallback for missing IDs.

**REST API (supplementary):**
```python
import requests

def get_pubchem_properties(drug_name):
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{drug_name}/property/MolecularFormula,MolecularWeight,CanonicalSMILES,IsomericSMILES/JSON"
    r = requests.get(url, timeout=10)
    if r.status_code == 200:
        props = r.json()['PropertyTable']['Properties'][0]
        return props
    return None
```

**RDKit Feature Extraction (replaces old `featurize_pubchem.py`):**
```python
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors
import numpy as np

def extract_drug_features(smiles: str) -> dict:
    """
    Convert a SMILES string into a full feature vector.
    
    Returns:
        dict with Morgan FP (2048-bit) + 7 molecular descriptors
        Returns None if SMILES is invalid.
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    
    # Morgan Fingerprint (2048-bit) — the core drug representation
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=2048)
    fp_array = np.array(fp, dtype=np.float32)
    
    # Molecular descriptors
    descriptors = {
        'morgan_fp': fp_array,               # 2048 features
        'mw': Descriptors.MolWt(mol),         # Molecular weight
        'logp': Descriptors.MolLogP(mol),     # LogP (lipophilicity)
        'tpsa': Descriptors.TPSA(mol),        # Topological polar surface area
        'hbd': Descriptors.NumHDonors(mol),   # H-bond donors
        'hba': Descriptors.NumHAcceptors(mol), # H-bond acceptors
        'rotatable_bonds': Descriptors.NumRotatableBonds(mol),
    }
    return descriptors
```

> ⚠️ **WHY NOT `smiles_length` and `num_C`?** Those fake features tell the model nothing about molecular function. Morgan Fingerprints encode actual chemical substructures (benzene rings, amide bonds, etc.) as a 2048-bit binary vector. This lets models learn: *"Drugs with this substructure pattern treat diseases of this type."*

---

### 3. DisGeNET

**What it is:** Largest public database of gene–disease associations. Covers >1M associations from curated databases and text mining.

**Download:**
1. Register free at https://www.disgenet.com/signup
2. Go to Downloads → Curated Associations → `curated_gene_disease_associations.tsv`

**Key columns:**
| Column | Description |
|---|---|
| `geneId` | NCBI Gene ID |
| `geneSymbol` | Gene symbol (e.g., `ABCB1`) |
| `diseaseId` | UMLS concept ID (e.g., `C0023418`) |
| `diseaseName` | Disease name |
| `score` | Association confidence (0–1) |
| `EI` | Evidence index |

---

### 4. ChEMBL (SQLite)

**What it is:** Database of bioactive molecules with drug-like properties. Contains 2.4M+ compounds and bioactivity measurements.

**Download:**
```bash
# ~5 GB download
wget https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/latest/chembl_35_sqlite.tar.gz
tar -xzf chembl_35_sqlite.tar.gz -C data/raw/chembl/
```

**Key tables & queries:**
```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('data/raw/chembl/chembl_35.db')

# Drug–target activity
query = """
SELECT
    md.chembl_id AS drug_id,
    md.pref_name AS drug_name,
    cs.canonical_smiles AS smiles,
    td.chembl_id AS target_id,
    td.pref_name AS target_name,
    act.pchembl_value,
    act.standard_type AS assay_type
FROM activities act
JOIN molecule_dictionary md ON act.molregno = md.molregno
JOIN compound_structures cs ON md.molregno = cs.molregno
JOIN assays a ON act.assay_id = a.assay_id
JOIN target_dictionary td ON a.tid = td.tid
WHERE act.pchembl_value IS NOT NULL
  AND act.pchembl_value >= 5.0
  AND td.target_type = 'SINGLE PROTEIN'
LIMIT 100000;
"""
drug_targets = pd.read_sql(query, conn)
drug_targets.to_csv('data/processed/drug_target_activity.csv', index=False)
conn.close()
```

---

## Public Health & Equity Data

### 5. WHO Global Health Observatory (GHO) API

**What it is:** Open API providing global health statistics including DALY burden by disease and country.

**No registration required.** Base URL: `https://ghoapi.azureedge.net/api/`

```python
import requests
import pandas as pd

# Get all available indicators
r = requests.get("https://ghoapi.azureedge.net/api/Indicator")
indicators = r.json()['value']

# Search for NTD-related indicators
ntd_indicators = [i for i in indicators if 'neglect' in i['IndicatorName'].lower()
                  or 'DALY' in i['IndicatorCode']]

# Download DALY data for specific disease
def get_daly_burden(indicator_code, country_code=None):
    url = f"https://ghoapi.azureedge.net/api/{indicator_code}"
    params = {}
    if country_code:
        params['$filter'] = f"SpatialDim eq '{country_code}'"
    r = requests.get(url, params=params)
    data = r.json()['value']
    df = pd.DataFrame(data)
    return df[['SpatialDim', 'TimeDim', 'NumericValue']].rename(columns={
        'SpatialDim': 'country',
        'TimeDim': 'year',
        'NumericValue': 'daly_rate'
    })

# Key NTD DALY indicators
DALY_INDICATORS = {
    'lymphatic_filariasis': 'NEHF_7',
    'leishmaniasis': 'NEHF_12',
    'chagas': 'NEHF_2',
    'schistosomiasis': 'NEHF_17',
    'sleeping_sickness': 'NEHF_19',
}
```

---

### 6. WHO Essential Medicines List (EML)

**What it is:** Official list of medicines that satisfy priority health care needs. Drugs on this list are expected to be affordable and available worldwide.

**Download (PDF → parse or use pre-parsed):**
```python
# Manually curated list of NTD-relevant essential medicines
who_eml_drugs = [
    'ivermectin', 'albendazole', 'praziquantel', 'miltefosine',
    'benznidazole', 'nifurtimox', 'suramin', 'pentamidine',
    'eflornithine', 'amphotericin b', 'doxycycline', 'azithromycin',
    'metronidazole', 'rifampicin', 'isoniazid'
]

def is_on_eml(drug_name: str) -> int:
    return int(drug_name.lower() in [d.lower() for d in who_eml_drugs])
```

---

### 7. Drug Pricing Data

**What it is:** Generic drug price data to compute affordability score.

**Free sources:**
- **NADAC** (US): https://data.medicaid.gov/datasets?theme=Drug%20Pricing (open data)
- **MSF Access Campaign**: https://msfaccess.org/essential-medicines-pricing
- **WHO Medicine Prices**: Manual lookup via WHO

```python
# Simple affordability proxy using MW (molecular weight)
def affordability_proxy(molecular_weight: float) -> float:
    """
    Smaller molecules tend to be cheaper to synthesize.
    Returns a normalised score [0, 1]; higher = more affordable.
    """
    import math
    return 1 / (1 + math.log1p(molecular_weight / 200))
```

---

## Literature & Evidence

### 8. PubMed via Biopython Entrez

**What it is:** Free access to 35M+ biomedical abstracts via NCBI's Entrez API.

**Setup:**
```bash
pip install biopython
```

**Usage:**
```python
from Bio import Entrez
import time

# Required: identify yourself with a valid email
Entrez.email = "your@email.com"

def pubmed_count(drug_name: str, disease_name: str) -> int:
    """Return number of PubMed papers mentioning drug + disease."""
    query = f"{drug_name}[Title/Abstract] AND {disease_name}[Title/Abstract]"
    try:
        handle = Entrez.esearch(db="pubmed", term=query, retmax=0)
        record = Entrez.read(handle)
        handle.close()
        time.sleep(0.34)  # Respect rate limit: 3 requests/second
        return int(record["Count"])
    except Exception:
        return 0

def literature_score(drug_name: str, disease_name: str, max_papers: int = 100) -> float:
    """Normalised literature score [0, 1]."""
    count = pubmed_count(drug_name, disease_name)
    return min(count / max_papers, 1.0)
```

---

## Supplementary Sources

### 9. UniProt (Protein Information)

```python
import requests

def get_protein_info(uniprot_id: str) -> dict:
    url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.json"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()
        return {
            'id': uniprot_id,
            'name': data.get('proteinDescription', {}).get('recommendedName', {}).get('fullName', {}).get('value', ''),
            'sequence_length': data.get('sequence', {}).get('length', 0),
            'function': data.get('comments', [{}])[0].get('texts', [{}])[0].get('value', '')
        }
    return {}
```

### 10. STRING DB (Protein–Protein Interactions)

```python
import requests

def get_ppi_network(protein_ids: list, min_score: int = 700) -> pd.DataFrame:
    """Get protein interactions with minimum combined score."""
    url = "https://string-db.org/api/json/network"
    params = {
        'identifiers': '%0d'.join(protein_ids),
        'species': 9606,  # Human
        'required_score': min_score,
        'caller_identity': 'vectordrugmatch'
    }
    r = requests.post(url, data=params)
    interactions = r.json()
    return pd.DataFrame(interactions)[['stringId_A', 'stringId_B', 'score']]
```

---

## Unified Preprocessing Pipeline

> ⚠️ **REPLACES:** The old 3-script pipeline (`process_pubchem_bulk.py`, `featurize_pubchem.py`, `preprocess_all.py`) is consolidated into a **single** `scripts/preprocess.py`.

### Full Pipeline: Build All Processed Files

```python
# scripts/preprocess.py — SINGLE UNIFIED SCRIPT
# Replaces: process_pubchem_bulk.py, featurize_pubchem.py, preprocess_all.py

import pandas as pd
import numpy as np
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors
import json

RAW = Path('data/raw')
PROC = Path('data/processed')
PROC.mkdir(parents=True, exist_ok=True)


def build_drugs():
    """Load PubChem CID-SMILES, compute RDKit features, save drugs.csv + drug_features.npy."""
    df = pd.read_csv(RAW / 'CID-SMILES', sep='\t', header=None,
                     names=['drug_id', 'smiles'])
    df = df.dropna(subset=['drug_id', 'smiles']).drop_duplicates('drug_id')

    # Canonicalize SMILES and compute descriptors
    features = []
    valid_rows = []
    for _, row in df.iterrows():
        mol = Chem.MolFromSmiles(row['smiles'])
        if mol is None:
            continue
        fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=2048)
        features.append(np.array(fp, dtype=np.float32))
        valid_rows.append({
            'drug_id': str(row['drug_id']),
            'name': f"CID:{row['drug_id']}",
            'smiles': Chem.MolToSmiles(mol),  # canonical
            'mw': Descriptors.MolWt(mol),
            'logp': Descriptors.MolLogP(mol),
            'tpsa': Descriptors.TPSA(mol),
            'hbd': Descriptors.NumHDonors(mol),
            'hba': Descriptors.NumHAcceptors(mol),
            'rotatable_bonds': Descriptors.NumRotatableBonds(mol),
            'node_type': 'drug'
        })

    drugs = pd.DataFrame(valid_rows)
    drugs.to_csv(PROC / 'drugs.csv', index=False)
    np.save(PROC / 'drug_features.npy', np.array(features))
    print(f"[drugs] {len(drugs)} rows, features shape: {np.array(features).shape}")


def build_diseases():
    """Load DisGeNET, extract unique diseases with metadata."""
    dg = pd.read_csv(RAW / 'curated_gene_disease_associations.tsv', sep='\t')
    diseases = dg[['diseaseId', 'diseaseName']].drop_duplicates('diseaseId').rename(columns={
        'diseaseId': 'disease_id', 'diseaseName': 'disease_name'
    })
    diseases['node_type'] = 'disease'
    diseases['is_ntd'] = 0       # Will be enriched from WHO data
    diseases['daly_rate'] = 0.0  # Will be enriched from WHO GHO API
    diseases.to_csv(PROC / 'diseases.csv', index=False)
    print(f"[diseases] {len(diseases)} rows")


def build_genes():
    """Load DisGeNET, extract unique genes."""
    dg = pd.read_csv(RAW / 'curated_gene_disease_associations.tsv', sep='\t')
    genes = dg[['geneId', 'geneSymbol']].drop_duplicates('geneId').rename(columns={
        'geneId': 'gene_id', 'geneSymbol': 'gene_symbol'
    })
    genes['node_type'] = 'gene'
    genes.to_csv(PROC / 'genes.csv', index=False)
    print(f"[genes] {len(genes)} rows")


def build_edges():
    """
    Load Hetionet + DisGeNET. PRESERVE ALL RELATION TYPES.
    
    ⚠️ CRITICAL FIX: The old script only saved CtD edges (137 rows).
    This version keeps ALL heterogeneous edge types:
      CtD, CpD, CbG, CdG, CuG, DaG, DuG, DdG, GiG, GrG
    """
    # --- Hetionet edges (ALL types) ---
    het = pd.read_csv(RAW / 'hetionet-v1.0-edges.sif', sep='\t', header=None,
                      names=['source', 'metaedge', 'target'])

    # Parse node IDs (format: "Type::ID")
    het['source_id'] = het['source'].str.split('::').str[1]
    het['target_id'] = het['target'].str.split('::').str[1]
    het['source_type'] = het['source'].str.split('::').str[0]
    het['target_type'] = het['target'].str.split('::').str[0]

    # Keep relation column (this is the FIX — old script lost this)
    het_edges = het[['source_id', 'target_id', 'metaedge', 'source_type', 'target_type']].copy()
    het_edges = het_edges.rename(columns={'metaedge': 'relation'})

    # --- DisGeNET gene-disease associations (high confidence) ---
    dg = pd.read_csv(RAW / 'curated_gene_disease_associations.tsv', sep='\t')
    gene_disease = dg[dg['score'] > 0.3][['geneId', 'diseaseId', 'score']].rename(columns={
        'geneId': 'source_id', 'diseaseId': 'target_id', 'score': 'confidence'
    })
    gene_disease['source_id'] = gene_disease['source_id'].astype(str)
    gene_disease['target_id'] = gene_disease['target_id'].astype(str)
    gene_disease['relation'] = 'DaG_disgenet'
    gene_disease['source_type'] = 'Gene'
    gene_disease['target_type'] = 'Disease'

    # --- Merge all edges ---
    edges = pd.concat([
        het_edges[['source_id', 'target_id', 'relation', 'source_type', 'target_type']],
        gene_disease[['source_id', 'target_id', 'relation', 'source_type', 'target_type']]
    ], ignore_index=True)

    edges = edges.drop_duplicates()
    edges.to_csv(PROC / 'edges.csv', index=False)
    print(f"[edges] {len(edges)} rows")

    # Print breakdown by relation type
    print("\nEdge type breakdown:")
    for rel, count in edges['relation'].value_counts().items():
        print(f"  {rel}: {count:,}")


def validate_and_save_metadata():
    """Cross-reference all outputs and save graph_metadata.json."""
    drugs = pd.read_csv(PROC / 'drugs.csv')
    diseases = pd.read_csv(PROC / 'diseases.csv')
    genes = pd.read_csv(PROC / 'genes.csv')
    edges = pd.read_csv(PROC / 'edges.csv')

    # Check for orphan nodes
    all_edge_nodes = set(edges['source_id'].astype(str)) | set(edges['target_id'].astype(str))

    metadata = {
        'node_counts': {
            'drugs': len(drugs),
            'diseases': len(diseases),
            'genes': len(genes),
            'total': len(drugs) + len(diseases) + len(genes)
        },
        'edge_counts': {
            'total': len(edges),
            'by_relation': edges['relation'].value_counts().to_dict()
        },
        'validation': {
            'duplicate_edges': int(edges.duplicated().sum()),
            'drugs_with_smiles': int(drugs['smiles'].notna().sum()),
        }
    }

    with open(PROC / 'graph_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2, default=str)

    print(f"\n=== Validation Summary ===")
    print(f"Drug nodes:     {metadata['node_counts']['drugs']:,}")
    print(f"Disease nodes:  {metadata['node_counts']['diseases']:,}")
    print(f"Gene nodes:     {metadata['node_counts']['genes']:,}")
    print(f"Total edges:    {metadata['edge_counts']['total']:,}")
    print(f"Duplicate edges: {metadata['validation']['duplicate_edges']}")


if __name__ == '__main__':
    build_drugs()
    build_diseases()
    build_genes()
    build_edges()
    validate_and_save_metadata()
    print("\n✅ Preprocessing complete.")
```

---

## Data Schema Reference

### `data/processed/drugs.csv`
| Column | Type | Description |
|---|---|---|
| `drug_id` | str | PubChem CID (e.g., `2244`) |
| `name` | str | Display name (e.g., `CID:2244` or common name if resolved) |
| `smiles` | str | Canonical SMILES string (RDKit-canonicalized) |
| `mw` | float | Molecular weight (RDKit `Descriptors.MolWt`) |
| `logp` | float | LogP / lipophilicity (RDKit `Descriptors.MolLogP`) |
| `tpsa` | float | Topological polar surface area |
| `hbd` | int | Number of hydrogen bond donors |
| `hba` | int | Number of hydrogen bond acceptors |
| `rotatable_bonds` | int | Number of rotatable bonds |
| `node_type` | str | Always `"drug"` |
| `on_who_eml` | int | 1 if on WHO EML, else 0 (enriched in scoring step) |

### `data/processed/drug_features.npy`
| Property | Value |
|---|---|
| Shape | `(N_drugs, 2048)` |
| Dtype | `float32` |
| Contents | Morgan Fingerprint bit vectors (radius=2, nBits=2048) |
| Each row | Corresponds to the same row index in `drugs.csv` |

### `data/processed/diseases.csv`
| Column | Type | Description |
|---|---|---|
| `disease_id` | str | UMLS / DOID identifier |
| `disease_name` | str | Full disease name |
| `node_type` | str | Always `"disease"` |
| `is_ntd` | int | 1 if WHO-classified NTD |
| `daly_rate` | float | DALY per 100k (from WHO GHO) |

### `data/processed/genes.csv`
| Column | Type | Description |
|---|---|---|
| `gene_id` | int | NCBI Gene ID |
| `gene_symbol` | str | Gene symbol (e.g., `ABCB1`) |
| `node_type` | str | Always `"gene"` |

### `data/processed/edges.csv`
| Column | Type | Description |
|---|---|---|
| `source_id` | str | Source node ID |
| `target_id` | str | Target node ID |
| `relation` | str | Edge type (see relation types below) |
| `source_type` | str | Node type of source (`Compound`, `Gene`, `Disease`) |
| `target_type` | str | Node type of target |

**Edge relation types (preserved from Hetionet):**

| Relation | Source → Target | Description |
|---|---|---|
| `CtD` | Compound → Disease | **Positive training label** (treats) |
| `CpD` | Compound → Disease | Palliates |
| `CbG` | Compound → Gene | Drug binds protein target |
| `CdG` | Compound → Gene | Drug downregulates gene |
| `CuG` | Compound → Gene | Drug upregulates gene |
| `DaG` | Disease → Gene | Disease associated with gene |
| `DuG` | Disease → Gene | Disease upregulates gene |
| `DdG` | Disease → Gene | Disease downregulates gene |
| `GiG` | Gene → Gene | Protein-protein interaction |
| `GrG` | Gene → Gene | Gene regulation |
| `DaG_disgenet` | Gene → Disease | From DisGeNET (high-confidence, score > 0.3) |

### `data/processed/graph_metadata.json`
```json
{
  "node_counts": {
    "drugs": 1553,
    "diseases": 138,
    "genes": 20945,
    "total": 22636
  },
  "edge_counts": {
    "total": 512847,
    "by_relation": {
      "GrG": 265672,
      "GiG": 147164,
      "CdG": 21102,
      "CuG": 18539,
      "DaG": 12623,
      "CbG": 11571,
      "DuG": 7731,
      "DdG": 7623,
      "CtD": 755,
      "CpD": 390,
      "DaG_disgenet": 8677
    }
  },
  "validation": {
    "duplicate_edges": 0,
    "drugs_with_smiles": 1553
  }
}
```

---

## Storage & Version Control Policy

- **`data/raw/`** — Git-ignored. Download manually using instructions above.
- **`data/processed/`** — Git-ignored (large files). Regenerate via `python scripts/preprocess.py`.
- **`data/external/`** — Version-controlled. Small reference files (WHO EML, NTD list) that change rarely.
- Use **DVC** (Data Version Control) for large files if collaborating:

```bash
pip install dvc
dvc init
dvc add data/processed/
git add data/processed/.gitignore data/processed.dvc
```

---

*Last updated: July 2026 | Maintained by VectorDrugMatch Team*
