"""
scripts/optuna_gnn.py - Hyperparameter Search using Optuna for HGT
"""

import sys
from pathlib import Path
import yaml
import torch
import torch.nn.functional as F
import optuna
import mlflow
import copy

try:
    import torch_geometric.transforms as T
    PYG_AVAILABLE = True
except ImportError:
    PYG_AVAILABLE = False

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

from src.data.graph_builder import build_hetero_data
from src.models.gnn.hgt import create_hgt_model
from src.utils.metrics import compute_all_metrics
from scripts.train_gnn import GNNLinkPredictionModel, train_epoch, evaluate_model

def objective(trial, config_path):
    # Hyperparameters to tune
    hidden_channels = trial.suggest_categorical("hidden_channels", [32, 64, 128])
    heads = trial.suggest_categorical("heads", [2, 4, 8])
    lr = trial.suggest_float("lr", 1e-4, 1e-2, log=True)
    dropout = trial.suggest_float("dropout", 0.1, 0.5)
    
    config_path = REPO_ROOT / config_path
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    exp_name = config.get("experiment", {}).get("name", "baseline")
    processed_dir = REPO_ROOT / "data" / "processed" / exp_name
    
    # 1. Load Graph
    data = build_hetero_data(processed_dir, include_features=True)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # 2. Split Edges
    transform = T.RandomLinkSplit(
        num_val=0.15,
        num_test=0.15,
        disjoint_train_ratio=0.3,
        neg_sampling_ratio=1.0,
        add_negative_train_samples=True,
        edge_types=[('drug', 'treats', 'disease')],
        rev_edge_types=[('disease', 'rev_treats', 'drug')],
    )
    
    train_data, val_data, test_data = transform(data)
    train_data, val_data, test_data = train_data.to(device), val_data.to(device), test_data.to(device)
    
    # 3. Model Setup
    metadata = data.metadata()
    gnn = create_hgt_model(metadata, hidden_channels=hidden_channels, out_channels=hidden_channels, heads=heads)
    model = GNNLinkPredictionModel(gnn, in_channels=hidden_channels, hidden_channels=hidden_channels // 2).to(device)
    
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scaler = torch.cuda.amp.GradScaler(enabled=device.type == 'cuda')
    
    epochs = 50 # Fixed smaller epochs for tuning
    best_val_auc = 0
    
    with mlflow.start_run(nested=True):
        mlflow.log_params(trial.params)
        
        for epoch in range(1, epochs + 1):
            loss = train_epoch(model, optimizer, train_data, scaler)
            val_metrics = evaluate_model(model, val_data)
            
            val_auc = val_metrics["roc_auc"]
            
            trial.report(val_auc, epoch)
            
            if trial.should_prune():
                raise optuna.TrialPruned()
                
            if val_auc > best_val_auc:
                best_val_auc = val_auc
                
        mlflow.log_metric("val_roc_auc", best_val_auc)
        
    return best_val_auc

def run_optuna(config_path, n_trials=10):
    if not PYG_AVAILABLE:
        print("ERROR: PyTorch Geometric is required.")
        sys.exit(1)
        
    print(f"Starting Optuna hyperparameter search with {n_trials} trials...")
    
    config_path_abs = REPO_ROOT / config_path
    with open(config_path_abs, "r") as f:
        config = yaml.safe_load(f)
    exp_name = config.get("experiment", {}).get("name", "baseline")
    
    mlflow.set_experiment(exp_name)
    with mlflow.start_run(run_name="optuna_hpo"):
        study = optuna.create_study(direction="maximize")
        study.optimize(lambda trial: objective(trial, config_path), n_trials=n_trials)
        
        print("\nBest Trial:")
        print(f"  Value: {study.best_trial.value}")
        print("  Params: ")
        for key, value in study.best_trial.params.items():
            print(f"    {key}: {value}")
            mlflow.log_param(f"best_{key}", value)
        mlflow.log_metric("best_val_roc_auc", study.best_trial.value)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default="configs/baseline_morgan.yaml")
    parser.add_argument("--trials", type=int, default=10)
    args = parser.parse_args()
    
    run_optuna(args.config, args.trials)
