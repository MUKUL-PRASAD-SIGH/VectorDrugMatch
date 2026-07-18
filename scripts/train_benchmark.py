"""
scripts/train_benchmark.py - External Benchmark (Node2Vec + LR)

Implements a standard network embedding baseline for comparison 
against the ML and GNN approaches.
"""

import sys
from pathlib import Path
import json
import yaml

import torch
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.calibration import CalibratedClassifierCV
import mlflow
import mlflow.sklearn

try:
    from torch_geometric.nn import Node2Vec
    PYG_AVAILABLE = True
except ImportError:
    PYG_AVAILABLE = False

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

from src.data.graph_builder import build_hetero_data
from src.data.dataset import build_tabular_dataset
from src.utils.metrics import compute_all_metrics, print_metrics

def train_node2vec_baseline(config_path):
    if not PYG_AVAILABLE:
        print("ERROR: PyTorch Geometric is required for Node2Vec.")
        sys.exit(1)
        
    config_path = REPO_ROOT / config_path
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    exp_name = config.get("experiment", {}).get("name", "baseline")
    processed_dir = REPO_ROOT / "data" / "processed" / exp_name
    
    outputs_dir = REPO_ROOT / "outputs" / exp_name
    models_dir = outputs_dir / "models"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)
    
    dataset_cfg = config.get("dataset", {})
    random_seed = dataset_cfg.get("random_seed", 42)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    print("Loading Graph for Benchmark...")
    # Load HeteroData
    data = build_hetero_data(processed_dir, include_features=False)
    
    # We need a homogeneous graph for standard Node2Vec
    # Just extracting the 'treats' edges and remapping nodes
    num_drugs = data['drug'].num_nodes
    num_diseases = data['disease'].num_nodes
    total_nodes = num_drugs + num_diseases
    
    edge_index = data['drug', 'treats', 'disease'].edge_index.clone()
    # Offset disease indices
    edge_index[1] += num_drugs
    
    # Make undirected
    rev_edge_index = torch.stack([edge_index[1], edge_index[0]], dim=0)
    homo_edge_index = torch.cat([edge_index, rev_edge_index], dim=1)
    
    print("Training Node2Vec Embeddings...")
    n2v = Node2Vec(
        homo_edge_index, 
        embedding_dim=64, 
        walk_length=20, 
        context_size=10, 
        walks_per_node=10,
        num_negative_samples=1, 
        p=1.0, 
        q=1.0, 
        sparse=True
    ).to(device)
    
    loader = n2v.loader(batch_size=128, shuffle=True, num_workers=0)
    optimizer = torch.optim.SparseAdam(list(n2v.parameters()), lr=0.01)
    
    n2v.train()
    for epoch in range(1, 11): # Small epochs for benchmark
        total_loss = 0
        for pos_rw, neg_rw in loader:
            optimizer.zero_grad()
            loss = n2v.loss(pos_rw.to(device), neg_rw.to(device))
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            
    n2v.eval()
    with torch.no_grad():
        z = n2v()
        
    drug_embeddings = z[:num_drugs].cpu().numpy()
    disease_embeddings = z[num_drugs:].cpu().numpy()
    
    # Now build the dataset splits from our regular process, but replace X with these embeddings
    print("Extracting tabular dataset splits...")
    splits = build_tabular_dataset(data, neg_ratio=5.0, test_size=0.15, val_size=0.15, random_state=random_seed)
    
    # We ignore X_train from tabular and build our own from embeddings
    # splits dict has y_train, y_val, etc. but we need the actual edges.
    # Actually, build_tabular_dataset generates features. 
    # To use embeddings, we need the edge indices that it sampled.
    # Wait, `build_tabular_dataset` internally samples edges but doesn't return them by default unless modified.
    # Let's just create a quick custom edge sampling for the benchmark here, 
    # or just use the whole edge index.
    
    # Positive edges
    pos_edge_index = data['drug', 'treats', 'disease'].edge_index.cpu().numpy()
    num_pos = pos_edge_index.shape[1]
    
    # Negative edges (random sampling)
    np.random.seed(random_seed)
    neg_u = np.random.randint(0, num_drugs, num_pos * 5)
    neg_v = np.random.randint(0, num_diseases, num_pos * 5)
    neg_edge_index = np.vstack([neg_u, neg_v])
    
    all_u = np.concatenate([pos_edge_index[0], neg_edge_index[0]])
    all_v = np.concatenate([pos_edge_index[1], neg_edge_index[1]])
    y_all = np.concatenate([np.ones(num_pos), np.zeros(num_pos * 5)])
    
    # Feature for LR is the element-wise product of embeddings (Hadamard)
    X_all = drug_embeddings[all_u] * disease_embeddings[all_v]
    
    print("Training Logistic Regression on Node2Vec features (5-Fold CV)...")
    mlflow.set_experiment(exp_name)
    
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=random_seed)
    fold_metrics = []
    
    with mlflow.start_run(run_name="Node2Vec_Benchmark_CV"):
        for fold, (train_idx, test_idx) in enumerate(skf.split(X_all, y_all)):
            X_train, y_train = X_all[train_idx], y_all[train_idx]
            X_test, y_test = X_all[test_idx], y_all[test_idx]
            
            clf = LogisticRegression(max_iter=1000, class_weight='balanced', random_state=random_seed)
            calibrated = CalibratedClassifierCV(estimator=clf, method="sigmoid", cv="prefit")
            
            clf.fit(X_train, y_train)
            calibrated.fit(X_test, y_test)
            
            y_pred_proba = calibrated.predict_proba(X_test)[:, 1]
            metrics = compute_all_metrics(y_test, y_pred_proba)
            fold_metrics.append(metrics)
            
        avg_metrics = {k: np.mean([m[k] for m in fold_metrics]) for k in fold_metrics[0].keys()}
        std_metrics = {k: np.std([m[k] for m in fold_metrics]) for k in fold_metrics[0].keys()}
        
        for k in list(avg_metrics.keys()):
            if isinstance(avg_metrics[k], float):
                avg_metrics[f"{k}_std"] = std_metrics[k]
                
        avg_metrics["name"] = "Node2Vec + LR (Ext)"
        avg_metrics["type"] = "baseline"
        
        with open(models_dir / "baseline_node2vec_metrics.json", "w") as f:
            json.dump(avg_metrics, f, indent=4)
            
        print_metrics("Node2Vec Benchmark", avg_metrics, "baseline")
        print(f"Benchmark results saved to {models_dir / 'baseline_node2vec_metrics.json'}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default="configs/baseline_morgan.yaml")
    args = parser.parse_args()
    
    train_node2vec_baseline(args.config)
