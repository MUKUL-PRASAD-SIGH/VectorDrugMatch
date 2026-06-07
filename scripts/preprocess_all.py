import pandas as pd
import os

print("Starting biomedical graph preprocessing pipeline...")

os.makedirs("data/processed", exist_ok=True)

# ==========================================
# 1. PROCESS PUBCHEM (Replaced Broken DrugBank)
# ==========================================
print("Processing PubChem data...")
try:
    # Added nrows=50000 to prevent your Mac from freezing on the massive file
    df_pubchem = pd.read_csv("data/raw/CID-SMILES", sep="\t", header=None, nrows=50000)
    
    df_drugs = df_pubchem.iloc[:, [0]].dropna().drop_duplicates()
    df_drugs.columns = ['drug_id']
    df_drugs['name'] = "CID:" + df_drugs['drug_id'].astype(str)
    
    df_drugs.to_csv("data/processed/drugs.csv", index=False)
    print(f"Created drugs.csv with {len(df_drugs)} rows.")
except Exception as e:
    print(f"Error processing PubChem: {e}")

# ==========================================
# 2. PROCESS DISGENET 
# ==========================================
print("Processing DisGeNET data...")
try:
    df_disgenet = pd.read_csv("data/raw/curated_gene_disease_associations.tsv", sep="\t", compression="gzip", header=0)
    id_col = [c for c in df_disgenet.columns if 'diseaseid' in c.lower()][0]
    name_col = [c for c in df_disgenet.columns if 'diseasename' in c.lower() or 'name' in c.lower()][0]
    df_diseases = df_disgenet[[id_col, name_col]].dropna().drop_duplicates()
    df_diseases.columns = ['disease_id', 'name']
    df_diseases.to_csv("data/processed/diseases.csv", index=False)
    print(f"Created diseases.csv with {len(df_diseases)} rows.")
except Exception as e:
    try:
        df_disgenet = pd.read_csv("data/raw/curated_gene_disease_associations.tsv", sep="\t")
        id_col = [c for c in df_disgenet.columns if 'diseaseid' in c.lower()][0]
        name_col = [c for c in df_disgenet.columns if 'diseasename' in c.lower() or 'name' in c.lower()][0]
        df_diseases = df_disgenet[[id_col, name_col]].dropna().drop_duplicates()
        df_diseases.columns = ['disease_id', 'name']
        df_diseases.to_csv("data/processed/diseases.csv", index=False)
        print(f"Created diseases.csv with {len(df_diseases)} rows.")
    except Exception as e2:
        print(f"Error processing DisGeNET: {e2}")

# ==========================================
# 3. PROCESS HETIONET EDGES 
# ==========================================
print("Processing Hetionet edges data...")
try:
    df_hetio = pd.read_csv("data/raw/hetionet_edges.tsv", sep="\t", header=None)
    if df_hetio.shape[1] < 3:
        df_hetio = pd.read_csv("data/raw/hetionet_edges.tsv", sep=r"\s+", header=None)
        
    df_edges = df_hetio.iloc[:, :3].dropna().drop_duplicates()
    df_edges.columns = ['source', 'metaedge', 'target']
    df_edges.to_csv("data/processed/edges.csv", index=False)
    print(f"Created edges.csv with {len(df_edges)} rows.")
except Exception as e:
    print(f"Error processing Hetionet: {e}")

# ==========================================
# 4. FINAL VALIDATION VERIFICATION
# ==========================================
print("Running final validation checks...")

all_passed = True

if os.path.exists("data/processed/drugs.csv"):
    count = len(pd.read_csv("data/processed/drugs.csv"))
    status = "PASSED" if count >= 14000 else "FAILED"
    print(f"Drugs count: {count} (Target: >= 14000) -> {status}")
    if count < 14000: all_passed = False
else:
    print("Drugs file missing.")
    all_passed = False

if os.path.exists("data/processed/diseases.csv"):
    count = len(pd.read_csv("data/processed/diseases.csv"))
    status = "PASSED" if count >= 20000 else "FAILED"
    print(f"Diseases count: {count} (Target: >= 20000) -> {status}")
    if count < 20000: all_passed = False
else:
    print("Diseases file missing.")
    all_passed = False

if os.path.exists("data/processed/edges.csv"):
    count = len(pd.read_csv("data/processed/edges.csv"))
    status = "PASSED" if count >= 100000 else "FAILED"
    print(f"Edges count: {count} (Target: >= 100000) -> {status}")
    if count < 100000: all_passed = False
else:
    print("Edges file missing.")
    all_passed = False

if all_passed:
    print("Verification complete: All targets met.")
else:
    print("Warning: Some datasets failed to meet minimum row requirements.")