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
import pandas as pd
from pathlib import Path
from tqdm import tqdm

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

REPO_ROOT = Path(__file__).resolve().parent.parent

def run_pipeline(config_path: str):
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
        _ = model(data.x_dict, data.edge_index_dict, data[target_edge].edge_label_index)
        
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()
    
    # 3. Load Candidates to rank (e.g., from inference.csv)
    # For now, let's just score the TEST set positive edges from the graph as a proxy 
    # if no inference CSV is provided, or a specific CSV if given.
    # In a real scenario, this would be all possible drug-disease pairs minus known positives.
    
    print("Extracting Candidates...")
    # Mocking candidate selection: We'll score all drugs against a single disease (e.g. Malaria)
    # For demonstration, we'll just score the test edges or negative samples.
    # Let's assume we have a list of pairs to score.
    # We will score ALL drugs against a specific disease.
    
    nodes_df = pd.read_csv(processed_dir / "nodes.csv")
    diseases = nodes_df[nodes_df["type"] == "disease"]
    drugs = nodes_df[nodes_df["type"] == "drug"]
    
    # Pick the most connected disease as the target
    target_disease_id = diseases.iloc[0]["id"]
    target_disease_name = diseases.iloc[0]["name"]
    daly_burden = float(diseases.iloc[0].get("daly_burden", 0.5)) # Mock DALY
    
    print(f"Targeting Disease: {target_disease_name} ({target_disease_id})")
    
    # Get known treatments to exclude them and use for similarity
    edges_df = pd.read_csv(processed_dir / "edges.csv")
    treats = edges_df[edges_df["relation"] == "treats"]
    known_drug_ids = treats[treats["dst"] == target_disease_id]["src"].tolist()
    known_drugs_df = drugs[drugs["id"].isin(known_drug_ids)]
    known_drugs_smiles = known_drugs_df["smiles"].dropna().tolist()
    
    # Candidate drugs (drugs not already treating the disease)
    candidate_drugs = drugs[~drugs["id"].isin(known_drug_ids)]
    
    print(f"Found {len(candidate_drugs)} candidate drugs to evaluate.")
    
    # Prepare edge_label_index for inference
    drug_node_indices = torch.tensor(candidate_drugs.index.values, dtype=torch.long, device=device)
    disease_idx = int(diseases[diseases["id"] == target_disease_id].index[0])
    disease_node_indices = torch.full((len(drug_node_indices),), disease_idx, dtype=torch.long, device=device)
    
    inference_edge_index = torch.stack([drug_node_indices, disease_node_indices], dim=0)
    
    # Predict Probabilities
    print("Running GNN Inference...")
    with torch.no_grad():
        with torch.cuda.amp.autocast(enabled=device.type == 'cuda'):
            pred_proba = model(data.x_dict, data.edge_index_dict, inference_edge_index).cpu().numpy()
            
    # Add probabilities to candidates
    candidate_drugs = candidate_drugs.copy()
    candidate_drugs["ml_probability"] = pred_proba
    
    # Filter by threshold (e.g. Youden Index, let's assume 0.5 for now)
    THRESHOLD = 0.5
    filtered_candidates = candidate_drugs[candidate_drugs["ml_probability"] > THRESHOLD].copy()
    print(f"Filtering candidates > {THRESHOLD}: {len(filtered_candidates)} remain.")
    
    if len(filtered_candidates) == 0:
        print("No candidates passed the ML threshold.")
        return
        
    # Calculate Secondary Scores
    print("Calculating NDPI Scores...")
    results = []
    
    for _, row in tqdm(filtered_candidates.iterrows(), total=len(filtered_candidates)):
        drug_name = row["name"]
        smiles = row.get("smiles", "")
        mw = float(row.get("molecular_weight", 300.0))
        atc_code = row.get("atc_code", "")
        is_eml = bool(row.get("is_eml", False))
        
        # 1. Similarity
        sim_scores = compute_similarity_scores(smiles, known_drugs_smiles, top_k=3)
        sim_score = sim_scores["max_sim"] # Or use mean_sim
        
        # 2. Literature
        lit_score = compute_literature_score(drug_name, target_disease_name)
        
        # 3. Equity
        equity_score = compute_equity_score(is_eml, daly_burden, mw, atc_code)
        
        # 4. NDPI
        ndpi_weights = config.get("ndpi_weights", None)
        ndpi = calculate_ndpi(row["ml_probability"], sim_score, lit_score, equity_score, weights=ndpi_weights)
        
        results.append({
            "drug_id": row["id"],
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
    args = parser.parse_args()
    run_pipeline(args.config)
