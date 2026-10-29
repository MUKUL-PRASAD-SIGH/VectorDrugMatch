"""
scripts/main_pipeline.py - End-to-End Inference & NDPI Ranking Pipeline

1. Loads a trained GNN model and a candidate edges CSV.
2. Predicts probabilities.
3. Filters candidates above the optimal Youden Index threshold.
4. Calculates secondary scores (Similarity, Literature, Equity).
5. Computes final NDPI and ranks candidates.
"""

import sys
import yaml
import torch
from rdkit import Chem
from rdkit.Chem import Descriptors
import pandas as pd
from pathlib import Path
from tqdm import tqdm

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

from src.data.graph_builder import build_hetero_data
from src.models.gnn.gcn import create_gcn_model
from src.models.gnn.graphsage import create_graphsage_model
from src.models.gnn.gat import create_gat_model
from src.models.gnn.rgcn import create_rgcn_model
from src.models.gnn.hgt import create_hgt_model
from src.models.gnn.base import GNNLinkPredictionModel
from src.scoring.ndpi import calculate_ndpi
from src.scoring.similarity import compute_similarity_scores
from src.scoring.literature import compute_literature_score
from src.scoring.equity import compute_equity_score

def run_pipeline(config_path: str, disease: str = None, top_k: int = 50, use_literature: bool = True):
    config_path = REPO_ROOT / config_path
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    exp_name = config.get("experiment", {}).get("name", "baseline")
    processed_dir = REPO_ROOT / "data" / "processed" / exp_name
    outputs_dir = REPO_ROOT / "outputs" / exp_name
    
    # 1. Load Graph (for embeddings and known edges)
    print("Loading Graph Data...")
    data = build_hetero_data(processed_dir, include_features=True)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    data = data.to(device)
    
    # 2. Load Model dynamically from config
    best_model_name = config.get("experiment", {}).get("best_model", "HGT")
    print(f"Loading Trained {best_model_name} Model...")
    
    gnn_factories = {
        "GCN": lambda: create_gcn_model(data.metadata(), hidden_channels=64, out_channels=64),
        "GraphSAGE": lambda: create_graphsage_model(data.metadata(), hidden_channels=64, out_channels=64),
        "GAT": lambda: create_gat_model(data.metadata(), hidden_channels=32, out_channels=64, heads=2),
        "RGCN": lambda: create_rgcn_model(data.metadata(), hidden_channels=64, out_channels=64),
        "HGT": lambda: create_hgt_model(data.metadata(), hidden_channels=64, out_channels=64, heads=4)
    }
    
    if best_model_name not in gnn_factories:
        print(f"ERROR: Unknown best_model {best_model_name}")
        sys.exit(1)
        
    gnn = gnn_factories[best_model_name]()
    model = GNNLinkPredictionModel(gnn, in_channels=64, hidden_channels=32).to(device)
    
    model_path = outputs_dir / "models" / f"gnn_{best_model_name}.pth"
    if not model_path.exists():
        print(f"ERROR: Model weights not found at {model_path}")
        sys.exit(1)
        
    # Lazy init fix before loading state dict
    with torch.no_grad():
        target_edge = ('drug', 'treats', 'disease')
        _ = model(data.x_dict, data.edge_index_dict, data[target_edge].edge_index[:, :1])
        
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()
    
    # 3. Candidate selection: score every drug that is not already a known treatment of the target disease
    drugs = pd.read_csv(processed_dir / "drugs.csv")        # row order == graph node index
    diseases = pd.read_csv(processed_dir / "diseases.csv")
    edges_df = pd.read_csv(processed_dir / "edges.csv", usecols=["source_id", "target_id", "relation"])
    treats = edges_df[edges_df["relation"] == "CtD"]

    if disease:
        mask = (diseases["disease_id"].astype(str) == disease) |                diseases["disease_name"].str.contains(disease, case=False, regex=False)
        if not mask.any():
            sys.exit(f"ERROR: no disease matching '{disease}' in diseases.csv")
        disease_idx = int(diseases[mask].index[0])
    else:
        # default: the disease with the most known treatments
        counts = treats["target_id"].value_counts()
        disease_idx = int(diseases.index[diseases["disease_id"].astype(str) == str(counts.index[0])][0])

    target_disease_id = str(diseases.loc[disease_idx, "disease_id"])
    target_disease_name = diseases.loc[disease_idx, "disease_name"]
    daly_burden = float(diseases.loc[disease_idx].get("daly_rate", 0.0) or 0.0)
    print(f"Targeting Disease: {target_disease_name} ({target_disease_id})")

    known_drug_ids = set(treats[treats["target_id"].astype(str) == target_disease_id]["source_id"].astype(str))
    known_mask = drugs["drug_id"].astype(str).isin(known_drug_ids)
    known_drugs_smiles = drugs[known_mask]["smiles"].dropna().tolist()
    candidate_drugs = drugs[~known_mask & drugs["smiles"].notna()].copy()   # no SMILES -> zero fingerprint, skip
    print(f"{known_mask.sum()} known treatments excluded; {len(candidate_drugs)} candidate drugs to evaluate.")

    drug_node_indices = torch.tensor(candidate_drugs.index.values, dtype=torch.long, device=device)
    disease_node_indices = torch.full((len(drug_node_indices),), disease_idx, dtype=torch.long, device=device)
    inference_edge_index = torch.stack([drug_node_indices, disease_node_indices], dim=0)

    print("Running GNN Inference...")
    with torch.no_grad():
        pred_proba = model(data.x_dict, data.edge_index_dict, inference_edge_index).cpu().numpy()
    candidate_drugs["ml_probability"] = pred_proba

    # Only the top-K by ML probability get the (slow, networked) secondary scores
    filtered_candidates = candidate_drugs.sort_values("ml_probability", ascending=False).head(top_k).copy()
    print(f"Keeping top {len(filtered_candidates)} candidates by ML probability.")

    # Calculate Secondary Scores
    print("Calculating NDPI Scores...")
    results = []
    
    for _, row in tqdm(filtered_candidates.iterrows(), total=len(filtered_candidates)):
        drug_name = row["name"]
        smiles = row.get("smiles", "")
        mol = Chem.MolFromSmiles(smiles) if isinstance(smiles, str) else None
        mw = Descriptors.MolWt(mol) if mol is not None else float("nan")
        atc_code = ""       # no ATC data in the Hetionet pipeline
        is_eml = False      # no WHO EML data wired in yet
        
        # 1. Similarity
        sim_scores = compute_similarity_scores(smiles, known_drugs_smiles, top_k=3)
        sim_score = sim_scores["max_sim"] # Or use mean_sim
        
        # 2. Literature
        lit_score = compute_literature_score(drug_name, target_disease_name) if use_literature else 0.0
        
        # 3. Equity
        equity_score = compute_equity_score(is_eml, daly_burden, mw, atc_code)
        
        # 4. NDPI
        ndpi_weights = config.get("ndpi_weights", None)
        ndpi = calculate_ndpi(row["ml_probability"], sim_score, lit_score, equity_score, weights=ndpi_weights)
        
        results.append({
            "drug_id": row["drug_id"],
            "drug_name": drug_name,
            "disease_name": target_disease_name,
            "ml_probability": round(row["ml_probability"], 4),
            "similarity_score": round(sim_score, 4),
            "literature_score": round(lit_score, 4),
            "equity_score": round(equity_score, 4),
            "ndpi": round(ndpi, 4)
        })
        
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values(by="ndpi", ascending=False)
    
    out_path = outputs_dir / "ndpi_ranked_candidates.csv"
    results_df.to_csv(out_path, index=False)
    
    print(f"\nTop 10 Candidates for {target_disease_name}:")
    print(results_df.head(10).to_string())
    print(f"\nSaved ranked candidates to {out_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run full NDPI Inference Pipeline")
    parser.add_argument("--config", type=str, default="configs/baseline_morgan.yaml", help="Path to config")
    parser.add_argument("--disease", type=str, default=None, help="Disease id or name substring (default: most-treated)")
    parser.add_argument("--top-k", type=int, default=50, help="Candidates that get similarity/literature/equity scores")
    parser.add_argument("--no-literature", action="store_true", help="Skip PubMed lookups (offline / fast)")
    args = parser.parse_args()
    run_pipeline(args.config, disease=args.disease, top_k=args.top_k, use_literature=not args.no_literature)
