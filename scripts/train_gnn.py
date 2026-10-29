"""
scripts/train_gnn.py - Train all 5 Graph Neural Networks

This script evaluates GNN models on the link prediction task 
(predicting Drug-treats-Disease edges).

Pipeline:
1. Load PyTorch Geometric HeteroData (from src.data.graph_builder)
2. Split edges into Train/Val/Test using RandomLinkSplit (negative sampling)
3. Train 5 models:
   - GCN
   - GraphSAGE
   - GAT
   - RGCN
   - HGT
4. Compute metrics and save to outputs/gnn_comparison.csv
"""

import sys
from pathlib import Path
import json
import yaml

import torch
import torch.nn.functional as F
import pandas as pd
import numpy as np
import mlflow

try:
    import torch_geometric.transforms as T
    from torch_geometric.loader import LinkNeighborLoader
    PYG_AVAILABLE = True
except ImportError:
    PYG_AVAILABLE = False

# Add repo root to Python path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

from src.data.graph_builder import build_hetero_data
from src.utils.metrics import compute_all_metrics, format_metrics_table, print_metrics
from src.utils.experiment_logger import log_experiment

from src.models.gnn.gcn import create_gcn_model
from src.models.gnn.graphsage import create_graphsage_model
from src.models.gnn.gat import create_gat_model
from src.models.gnn.rgcn import create_rgcn_model
from src.models.gnn.hgt import create_hgt_model
from src.models.gnn.base import GNNLinkPredictionModel


def train_epoch(model, optimizer, train_data, scaler):
    model.train()
    optimizer.zero_grad()
    
    # We predict on the target relation: ('drug', 'treats', 'disease')
    edge_label_index = train_data['drug', 'treats', 'disease'].edge_label_index
    edge_label = train_data['drug', 'treats', 'disease'].edge_label
    
    # Mixed Precision Autocast
    with torch.cuda.amp.autocast(enabled=scaler.is_enabled()):
        pred = model(train_data.x_dict, train_data.edge_index_dict, edge_label_index)
        loss = F.binary_cross_entropy(pred, edge_label.float())
        
    scaler.scale(loss).backward()
    scaler.unscale_(optimizer)
    
    # Gradient Clipping
    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
    
    scaler.step(optimizer)
    scaler.update()
    
    return loss.item()


@torch.no_grad()
def evaluate_model(model, data):
    model.eval()
    
    edge_label_index = data['drug', 'treats', 'disease'].edge_label_index
    edge_label = data['drug', 'treats', 'disease'].edge_label.cpu().numpy()
    
    pred_proba = model(data.x_dict, data.edge_index_dict, edge_label_index).cpu().numpy()
    
    metrics = compute_all_metrics(edge_label, pred_proba)
    return metrics


def train_evaluate_gnns(config_path: str, epochs: int = 100):
    if not PYG_AVAILABLE:
        print("ERROR: PyTorch Geometric is required to train GNNs.")
        sys.exit(1)
        
    print("==========================================================")
    print("|   VectorDrugMatch - GNN Models Training Pipeline         |")
    print("==========================================================")
    
    config_path = REPO_ROOT / config_path
    if not config_path.exists():
        print(f"ERROR: Config file not found at {config_path}")
        sys.exit(1)
        
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    exp_name = config.get("experiment", {}).get("name", "baseline")
    processed_dir = REPO_ROOT / "data" / "processed" / exp_name
    outputs_dir = REPO_ROOT / "outputs" / exp_name
    outputs_dir.mkdir(parents=True, exist_ok=True)
    models_dir = outputs_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    preds_dir = outputs_dir / "predictions"
    preds_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Load Graph
    print("\nLoading HeteroData...")
    try:
        data = build_hetero_data(processed_dir, include_features=True)
    except FileNotFoundError:
        print("ERROR: Processed data not found. Run scripts/preprocess.py first.")
        sys.exit(1)
        
    # Make sure we have the target relation
    target_edge = ('drug', 'treats', 'disease')
    if target_edge not in data.edge_types:
        print(f"ERROR: Graph does not contain target edge {target_edge}.")
        sys.exit(1)
        
    # To fix potential dimension issues for lazy initialization, pass sample data through initially
    # Ensure all nodes have float32 features
    for node_type in data.node_types:
        if not hasattr(data[node_type], 'x') or data[node_type].x is None:
            data[node_type].x = torch.ones((data[node_type].num_nodes, 1), dtype=torch.float32)
        else:
            data[node_type].x = data[node_type].x.float()
            
    dataset_cfg = config.get("dataset", {})
    neg_ratio = dataset_cfg.get("neg_ratio", 5.0)
    test_size = dataset_cfg.get("test_size", 0.15)
    val_size = dataset_cfg.get("val_size", 0.15)
    
    # 2. Train/Val/Test Split using PyG's RandomLinkSplit
    print(f"\nSplitting graph into Train/Val/Test (negative sampling ratio {neg_ratio})...")
    transform = T.RandomLinkSplit(
        num_val=val_size,
        num_test=test_size,
        disjoint_train_ratio=0.3,
        neg_sampling_ratio=neg_ratio,
        add_negative_train_samples=True,
        edge_types=[target_edge],
        # Remove the reverse of each held-out edge too, otherwise val/test labels leak via message passing
        rev_edge_types=[('disease', 'rev_treats', 'drug')],
    )
    
    train_data, val_data, test_data = transform(data)
    
    train_edges = train_data[target_edge].edge_label.shape[0]
    test_edges = test_data[target_edge].edge_label.shape[0]
    print(f"  Train set: {train_edges:,} edges")
    print(f"  Test set:  {test_edges:,} edges")

    # 3. Define Models
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\nUsing device: {device}")
    
    train_data = train_data.to(device)
    val_data = val_data.to(device)
    test_data = test_data.to(device)
    
    EMB_DIM = 64
    
    gnn_factories = {
        "GCN": lambda: create_gcn_model(data.metadata(), hidden_channels=EMB_DIM, out_channels=EMB_DIM),
        "GraphSAGE": lambda: create_graphsage_model(data.metadata(), hidden_channels=EMB_DIM, out_channels=EMB_DIM),
        "GAT": lambda: create_gat_model(data.metadata(), hidden_channels=32, out_channels=EMB_DIM, heads=2),
        "RGCN": lambda: create_rgcn_model(data.metadata(), hidden_channels=EMB_DIM, out_channels=EMB_DIM),
        "HGT": lambda: create_hgt_model(data.metadata(), hidden_channels=EMB_DIM, out_channels=EMB_DIM, heads=4)
    }
    
    results = []
    
    # 4. Train & Evaluate
    EPOCHS = epochs
    
    for name, factory in gnn_factories.items():
        print(f"\n" + "="*50)
        print(f"Training {name}...")
        print("="*50)
        
        # Build GNN + Predictor
        gnn = factory()
        model = GNNLinkPredictionModel(gnn, in_channels=EMB_DIM, hidden_channels=32).to(device)
        
        # Initialize lazy modules by doing a forward pass with CPU data before passing to optimizer
        with torch.no_grad():
            _ = model(train_data.x_dict, train_data.edge_index_dict, 
                     train_data[target_edge].edge_label_index)
            
        optimizer = torch.optim.Adam(model.parameters(), lr=0.005, weight_decay=1e-4)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='max', factor=0.5, patience=10)
        scaler = torch.cuda.amp.GradScaler(enabled=device.type == 'cuda')
        
        best_val_auc = 0.0
        best_metrics = None
        best_model_state = None
        best_epoch = 0
        patience = 20
        epochs_no_improve = 0
        
        # Training loop
        for epoch in range(1, EPOCHS + 1):
            loss = train_epoch(model, optimizer, train_data, scaler)
            val_metrics = evaluate_model(model, val_data)
            
            scheduler.step(val_metrics["roc_auc"])
            
            # Checkpointing based on Validation ROC-AUC
            if val_metrics["roc_auc"] > best_val_auc:
                best_val_auc = val_metrics["roc_auc"]
                best_model_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
                best_epoch = epoch
                epochs_no_improve = 0
            else:
                epochs_no_improve += 1
                
            if epoch % 10 == 0 or epoch == EPOCHS:
                print(f"  Epoch {epoch:>3}/{EPOCHS} | Loss: {loss:.4f} | "
                      f"Val ROC-AUC: {val_metrics['roc_auc']:.4f} | Val PR-AUC: {val_metrics['pr_auc']:.4f}")
                      
            if epochs_no_improve >= patience:
                print(f"  Early stopping at epoch {epoch}")
                break
        
        if best_model_state is not None:
            model.load_state_dict(best_model_state)
            
        best_metrics = evaluate_model(model, test_data)
            
        best_metrics["name"] = name
        best_metrics["type"] = "gnn"
        
        feature_dim = data['drug'].x.shape[1] if hasattr(data['drug'], 'x') else None
        
        # Save model, metrics, config
        model_path = models_dir / f"gnn_{name}.pth"
        torch.save(model.state_dict(), model_path)
        print(f"  Model saved to {model_path.relative_to(REPO_ROOT)}")
        
        import json
        import shutil
        with open(models_dir / f"gnn_{name}_metrics.json", "w") as f:
            json.dump(best_metrics, f, indent=4, default=float)
        if config_path.exists():
            shutil.copy2(config_path, models_dir / f"gnn_{name}_config.yaml")
            
        mlflow.set_experiment(exp_name)
        with mlflow.start_run(run_name=f"GNN_{name}"):
            mlflow.log_params({
                "model_type": name,
                "epochs": EPOCHS,
                "hidden_channels": EMB_DIM,
                "learning_rate": 0.005,
                "weight_decay": 1e-4,
                "feature_dim": feature_dim,
                "best_epoch": best_epoch
            })
            mlflow.log_metrics({
                "test_roc_auc": best_metrics.get("roc_auc", 0),
                "test_pr_auc": best_metrics.get("pr_auc", 0),
                "test_f1": best_metrics.get("f1", 0)
            })
            mlflow.log_artifact(str(model_path))
            mlflow.log_artifact(str(models_dir / f"gnn_{name}_metrics.json"))
            if config_path.exists():
                mlflow.log_artifact(str(models_dir / f"gnn_{name}_config.yaml"))
        # Save predictions if configured
        if config.get("experiment", {}).get("save_predictions"):
            model.eval()
            with torch.no_grad():
                edge_label_index = test_data['drug', 'treats', 'disease'].edge_label_index
                pred_proba = model(test_data.x_dict, test_data.edge_index_dict, edge_label_index).cpu().numpy()
                y_true = test_data['drug', 'treats', 'disease'].edge_label.cpu().numpy()
                
                pred_df = pd.DataFrame({
                    "drug_id": edge_label_index[0].cpu().numpy(),
                    "disease_id": edge_label_index[1].cpu().numpy(),
                    "label": y_true,
                    "prediction": (pred_proba >= 0.5).astype(int),
                    "probability": pred_proba,
                    "experiment": config.get("experiment", {}).get("name", "baseline"),
                    "model": name
                })
                pred_path = preds_dir / f"gnn_{name}_predictions.csv"
                pred_df.to_csv(pred_path, index=False)
                
        # Save Embeddings
        model.eval()
        with torch.no_grad():
            # Run forward pass on the full graph to extract node embeddings
            node_embeddings = model.gnn(data.x_dict, data.edge_index_dict)
            if 'drug' in node_embeddings and 'disease' in node_embeddings:
                drug_emb = node_embeddings['drug'].cpu().numpy()
                disease_emb = node_embeddings['disease'].cpu().numpy()
                np.save(models_dir / f"gnn_{name}_drug_embeddings.npy", drug_emb)
                np.save(models_dir / f"gnn_{name}_disease_embeddings.npy", disease_emb)
        
        results.append(best_metrics)
        print_metrics(name, best_metrics, "gnn (Test Set)")
        
    # 5. Save Results
    print("\n" + "="*80)
    print("GNN Comparison Summary (Test Set)")
    print("="*80)
    print(format_metrics_table(results))
    
    results_df = pd.DataFrame(results)
    csv_path = outputs_dir / "gnn_comparison.csv"
    results_df.to_csv(csv_path, index=False)
    print(f"\nResults saved to {csv_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="VectorDrugMatch GNN Training")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to experiment config file")
    parser.add_argument("--epochs", type=int, default=100, help="Max training epochs per model")
    args = parser.parse_args()
    
    train_evaluate_gnns(args.config, epochs=args.epochs)
