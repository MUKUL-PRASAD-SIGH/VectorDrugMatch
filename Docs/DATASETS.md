# 📦 DATASETS.md — Data Sources for VectorDrugMatch

Complete reference for every dataset used in the project: what it is, where to get it, what columns matter, how to clean it, and which pipeline stage uses it.

---

## Table of Contents

1. [Quick Reference Table](#quick-reference-table)
2. [Primary Biomedical Databases](#primary-biomedical-databases)
3. [Public Health & Equity Data](#public-health--equity-data)
4. [Literature & Evidence](#literature--evidence)
5. [Supplementary Sources](#supplementary-sources)
6. [Cleaning Code Snippets](#cleaning-code-snippets)
7. [Data Schema Reference](#data-schema-reference)
8. [Storage & Version Control Policy](#storage--version-control-policy)

---

## Quick Reference Table

| Dataset | What It Contains | Access | Registration | Priority |
|---|---|---|---|---|
| **Hetionet v1.0** | Biomedical KG: drugs, genes, diseases, pathways, 2M+ edges | [het.io](https://het.io) | ❌ None | ⭐⭐⭐ Must-have |
| **DrugBank Vocabulary** | Drug names, SMILES, identifiers | [drugbank.com](https://go.drugbank.com/releases/latest) | ✅ Free account | ⭐⭐⭐ Must-have |
| **DisGeNET** | Gene–disease associations with confidence scores | [disgenet.com](https://www.disgenet.com/) | ✅ Free account | ⭐⭐⭐ Must-have |
| **ChEMBL SQLite** | Bioactivity data, molecular properties, targets | [ebi.ac.uk](https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/latest/) | ❌ None | ⭐⭐⭐ Must-have |
| **WHO GHO API** | DALY burden, disease prevalence by country | [ghoapi.azureedge.net](https://ghoapi.azureedge.net/api/) | ❌ Open API | ⭐⭐⭐ Must-have |
| **WHO Essential Medicines List** | Approved essential drug list | [who.int/medicines](https://www.who.int/groups/expert-committee-on-selection-and-use-of-essential-medicines/essential-medicines-lists) | ❌ None | ⭐⭐ Important |
| **PubChem** | Chemical structures, bioassays | [pubchem.ncbi.nlm.nih.gov](https://pubchem.ncbi.nlm.nih.gov/) | ❌ None | ⭐⭐ Important |
| **NCBI Gene** | Gene identifiers, annotations | [ncbi.nlm.nih.gov/gene](https://www.ncbi.nlm.nih.gov/gene) | ❌ None | ⭐⭐ Important |
| **UniProt** | Protein sequences & function | [uniprot.org](https://www.uniprot.org/) | ❌ None | ⭐ Supplementary |
| **OMIM** | Disease-gene links (Mendelian) | [omim.org](https://omim.org/) | ✅ Free account | ⭐ Supplementary |
| **STRING DB** | Protein–protein interactions | [string-db.org](https://string-db.org/) | ❌ None | ⭐ Supplementary |
| **KEGG Pathways** | Biological pathway maps | [kegg.jp](https://www.kegg.jp/) | ❌ None (API limited) | ⭐ Supplementary |

---

## Primary Biomedical Databases

### 1. Hetionet v1.0

**What it is:** The most comprehensive open biomedical knowledge graph. Contains 47,031 nodes of 11 types and 2,250,197 edges of 24 types.

**Download:**
```bash
# Edges (TSV) — no account needed
wget https://github.com/hetio/hetionet/raw/main/hetnet/tsv/hetionet-v1.0-edges.sdf

# Nodes
wget https://github.com/hetio/hetionet/raw/main/hetnet/tsv/hetionet-v1.0-nodes.tsv
```

**Key columns:**
| Column | Description |
|---|---|
| `source` | Source node ID (e.g., `Compound::DB00945`) |
| `metaedge` | Relation type (e.g., `CbG` = Compound binds Gene) |
| `target` | Target node ID (e.g., `Gene::1`) |

**Relation types used:**
- `CbG` — Compound binds Gene
- `CdG` — Compound downregulates Gene
- `CuG` — Compound upregulates Gene
- `CtD` — Compound treats Disease ← **positive labels**
- `CpD` — Compound palliates Disease
- `DaG` — Disease associates Gene
- `DuG` — Disease upregulates Gene

**Cleaning:**
```python
import pandas as pd

edges = pd.read_csv('hetionet-v1.0-edges.sdf', sep='\t')

# Extract drug-treats-disease edges (positive labels)
treats = edges[edges['metaedge'] == 'CtD'].copy()
treats['drug_id'] = treats['source'].str.split('::').str[1]
treats['disease_id'] = treats['target'].str.split('::').str[1]
treats['label'] = 1
```

---

### 2. DrugBank

**What it is:** Gold-standard drug database. Use the **vocabulary CSV** (no parsing required) for basic info. The full XML requires a data access agreement.

**Download:**
1. Register free at https://go.drugbank.com/users/sign_up
2. Go to Downloads → All Drugs → DrugBank Vocabulary (CSV)
3. Save as `data/raw/drugbank/drugbank_vocabulary.csv`

**Key columns:**
| Column | Description |
|---|---|
| `DrugBank ID` | Unique ID (e.g., `DB00945`) |
| `Common name` | Drug name |
| `SMILES` | Chemical structure (SMILES string) |
| `InChIKey` | Standardised chemical identifier |
| `CAS Number` | Chemical Abstracts Service number |

**Cleaning:**
```python
drugbank = pd.read_csv('data/raw/drugbank/drugbank_vocabulary.csv')

drugs = drugbank[['DrugBank ID', 'Common name', 'SMILES', 'InChIKey']].rename(columns={
    'DrugBank ID': 'drug_id',
    'Common name': 'drug_name',
    'SMILES': 'smiles',
    'InChIKey': 'inchikey'
})

drugs = drugs.dropna(subset=['drug_id', 'drug_name'])
drugs = drugs.drop_duplicates('drug_id')
drugs = drugs[drugs['drug_id'].str.startswith('DB')]  # keep approved drugs only

print(f"Drugs loaded: {len(drugs)}")
drugs.to_csv('data/processed/drugs.csv', index=False)
```

**NTD-relevant drugs to prioritise:**
- Ivermectin (DB00602) — Lymphatic filariasis, River blindness
- Albendazole (DB00518) — Helminthiases
- Praziquantel (DB01058) — Schistosomiasis
- Miltefosine (DB12165) — Leishmaniasis
- Benznidazole (DB12499) — Chagas disease
- Nifurtimox (DB08820) — Chagas, Sleeping sickness
- Suramin (DB04786) — Sleeping sickness
- Pentamidine (DB00738) — Sleeping sickness, Leishmaniasis
- Eflornithine (DB00839) — Sleeping sickness
- Amphotericin B (DB00681) — Visceral leishmaniasis

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

**Cleaning:**
```python
disgenet = pd.read_csv('data/raw/disgenet/curated_gene_disease_associations.tsv', sep='\t')

# Keep only high-confidence associations
gene_disease = disgenet[['geneId', 'geneSymbol', 'diseaseId', 'diseaseName', 'score']].copy()
gene_disease = gene_disease[gene_disease['score'] > 0.3]
gene_disease = gene_disease.dropna()
gene_disease.columns = ['gene_id', 'gene_symbol', 'disease_id', 'disease_name', 'confidence']

gene_disease.to_csv('data/processed/gene_disease_edges.csv', index=False)
```

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

### 5. PubChem

**What it is:** Free chemical database. Use for SMILES, molecular properties, and bioassay results.

**Access via REST API (no download needed):**
```python
import requests

def get_pubchem_properties(drug_name):
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{drug_name}/property/MolecularFormula,MolecularWeight,CanonicalSMILES,IsomericSMILES/JSON"
    r = requests.get(url, timeout=10)
    if r.status_code == 200:
        props = r.json()['PropertyTable']['Properties'][0]
        return props
    return None

# Example
props = get_pubchem_properties("ivermectin")
print(props)
# {'CID': 6321424, 'MolecularFormula': 'C48H74O14', 'MolecularWeight': 875.1, ...}
```

---

## Public Health & Equity Data

### 6. WHO Global Health Observatory (GHO) API

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

### 7. WHO Essential Medicines List (EML)

**What it is:** Official list of medicines that satisfy priority health care needs. Drugs on this list are expected to be affordable and available worldwide.

**Download (PDF → parse or use pre-parsed):**
```python
# Pre-parsed CSV available at:
# https://raw.githubusercontent.com/samayo/country-json/master/src/country-who-eml.json

import requests

# Or manually create from WHO website
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

### 8. Drug Pricing Data

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

### 9. PubMed via Biopython Entrez

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

### 10. UniProt (Protein Information)

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

### 11. STRING DB (Protein–Protein Interactions)

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

## Cleaning Code Snippets

### Full Pipeline: Build All Processed Files

```python
# scripts/preprocess_all.py

import pandas as pd
import numpy as np
from pathlib import Path

RAW = Path('data/raw')
PROC = Path('data/processed')
PROC.mkdir(parents=True, exist_ok=True)


def build_drugs():
    db = pd.read_csv(RAW / 'drugbank/drugbank_vocabulary.csv')
    drugs = db[['DrugBank ID', 'Common name', 'SMILES']].rename(columns={
        'DrugBank ID': 'drug_id',
        'Common name': 'drug_name',
        'SMILES': 'smiles'
    })
    drugs = drugs.dropna(subset=['drug_id', 'drug_name']).drop_duplicates('drug_id')
    drugs['node_type'] = 'drug'
    drugs.to_csv(PROC / 'drugs.csv', index=False)
    print(f"[drugs] {len(drugs)} rows")


def build_diseases():
    dg = pd.read_csv(RAW / 'disgenet/curated_gene_disease_associations.tsv', sep='\t')
    diseases = dg[['diseaseId', 'diseaseName']].drop_duplicates('diseaseId').rename(columns={
        'diseaseId': 'disease_id', 'diseaseName': 'disease_name'
    })
    diseases['node_type'] = 'disease'
    diseases.to_csv(PROC / 'diseases.csv', index=False)
    print(f"[diseases] {len(diseases)} rows")


def build_genes():
    dg = pd.read_csv(RAW / 'disgenet/curated_gene_disease_associations.tsv', sep='\t')
    genes = dg[['geneId', 'geneSymbol']].drop_duplicates('geneId').rename(columns={
        'geneId': 'gene_id', 'geneSymbol': 'gene_name'
    })
    genes['node_type'] = 'gene'
    genes.to_csv(PROC / 'genes.csv', index=False)
    print(f"[genes] {len(genes)} rows")


def build_edges():
    het = pd.read_csv(RAW / 'hetionet/hetionet-v1.0-edges.sdf', sep='\t')
    dg = pd.read_csv(RAW / 'disgenet/curated_gene_disease_associations.tsv', sep='\t')

    # Drug-targets-Gene (from Hetionet CbG)
    drug_gene = het[het['metaedge'].isin(['CbG', 'CdG', 'CuG'])].copy()
    drug_gene['source_id'] = drug_gene['source'].str.split('::').str[1]
    drug_gene['target_id'] = drug_gene['target'].str.split('::').str[1]
    drug_gene['relation'] = 'drug_targets_gene'

    # Gene-associated-Disease (from DisGeNET)
    gene_disease = dg[dg['score'] > 0.3][['geneId', 'diseaseId', 'score']].rename(columns={
        'geneId': 'source_id', 'diseaseId': 'target_id'
    })
    gene_disease['relation'] = 'gene_associated_with_disease'

    # Drug-treats-Disease (positive labels from Hetionet CtD)
    treats = het[het['metaedge'] == 'CtD'].copy()
    treats['source_id'] = treats['source'].str.split('::').str[1]
    treats['target_id'] = treats['target'].str.split('::').str[1]
    treats['relation'] = 'treats'
    treats['label'] = 1

    edges = pd.concat([
        drug_gene[['source_id', 'target_id', 'relation']],
        gene_disease[['source_id', 'target_id', 'relation']],
        treats[['source_id', 'target_id', 'relation']]
    ], ignore_index=True)

    edges.to_csv(PROC / 'edges.csv', index=False)
    print(f"[edges] {len(edges)} rows")


if __name__ == '__main__':
    build_drugs()
    build_diseases()
    build_genes()
    build_edges()
    print("Done.")
```

---

## Data Schema Reference

### `data/processed/drugs.csv`
| Column | Type | Description |
|---|---|---|
| `drug_id` | str | DrugBank ID (e.g., `DB00602`) |
| `drug_name` | str | Common name |
| `smiles` | str | SMILES string (nullable) |
| `inchikey` | str | InChI key (nullable) |
| `node_type` | str | Always `"drug"` |
| `on_who_eml` | int | 1 if on WHO EML, else 0 |
| `generic_available` | int | 1 if generic exists |
| `affordability_score` | float | [0, 1] computed from MW proxy |

### `data/processed/diseases.csv`
| Column | Type | Description |
|---|---|---|
| `disease_id` | str | UMLS / DOID identifier |
| `disease_name` | str | Full disease name |
| `node_type` | str | Always `"disease"` |
| `is_ntd` | int | 1 if WHO-classified NTD |
| `daly_rate` | float | DALY per 100k (from WHO GHO) |
| `daly_normalized` | float | [0, 1] normalised DALY burden |

### `data/processed/genes.csv`
| Column | Type | Description |
|---|---|---|
| `gene_id` | int | NCBI Gene ID |
| `gene_name` | str | Gene symbol (e.g., `ABCB1`) |
| `node_type` | str | Always `"gene"` |

### `data/processed/edges.csv`
| Column | Type | Description |
|---|---|---|
| `source_id` | str | Source node ID |
| `target_id` | str | Target node ID |
| `relation` | str | Edge type (see relation types below) |
| `confidence` | float | Evidence score (0–1, nullable) |
| `label` | int | 1 = treats (positive), 0 = unknown |

**Edge relation types:**
- `drug_targets_gene`
- `gene_associated_with_disease`
- `treats` ← positive training label
- `drug_similar_to_drug` ← added by similarity module

---

## Storage & Version Control Policy

- **`data/raw/`** — Git-ignored. Download manually using `scripts/download_data.sh`.
- **`data/processed/`** — Git-ignored (large files). Regenerate via `python scripts/preprocess_all.py`.
- **`data/external/`** — Version-controlled. Small reference files (WHO EML, NTD list) that change rarely.
- Use **DVC** (Data Version Control) for large files if collaborating:

```bash
pip install dvc
dvc init
dvc add data/processed/
git add data/processed/.gitignore data/processed.dvc
```

---

*Last updated: March 2026 | Maintained by VectorDrugMatch Team*
