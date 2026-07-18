"""
scripts/run_ablations.py - Actual Feature Ablation Study

Trains Random Forest on systematically reduced feature sets to prove
the value of each feature component.
"""

import sys
from pathlib import Path
import yaml
import json
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_curve
import mlflow

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

from src.data.graph_builder import build_hetero_data
from src.data.dataset import build_tabular_dataset
from src.utils.metrics import compute_all_metrics, print_metrics
from src.models.baseline.random_forest import RandomForestModel

def run_ablation_study(config_path):
    print("==========================================================")
    print("   VectorDrugMatch - Actual Ablation Study (RF)           ")
    print("==========================================================")
    
    config_path = REPO_ROOT / config_path
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    exp_name = config.get("experiment", {}).get("name", "baseline")
    processed_dir = REPO_ROOT / "data" / "processed" / exp_name
    outputs_dir = REPO_ROOT / "outputs" / exp_name
    models_dir = outputs_dir / "models"
    
    dataset_cfg = config.get("dataset", {})
    random_seed = dataset_cfg.get("random_seed", 42)
    
    print("\nLoading Graph and Splitting Dataset...")
    data = build_hetero_data(processed_dir, include_features=True)
    splits = build_tabular_dataset(
        data, 
        neg_ratio=dataset_cfg.get("neg_ratio", 5.0), 
        test_size=dataset_cfg.get("test_size", 0.15), 
        val_size=dataset_cfg.get("val_size", 0.15),
        random_state=random_seed
    )
    
    # We will use cross-validation over the entire dataset for ablation
    X_parts = []
    y_parts = []
    if "X_train" in splits: X_parts.append(splits["X_train"]); y_parts.append(splits["y_train"])
    if "X_val" in splits: X_parts.append(splits["X_val"]); y_parts.append(splits["y_val"])
    if "X_test" in splits: X_parts.append(splits["X_test"]); y_parts.append(splits["y_test"])
    
    X_all = np.vstack(X_parts)
    y_all = np.concatenate(y_parts)
    
    print(f"\nTotal Dataset Shape: {X_all.shape}")
    
    # Dynamic feature boundaries based on config flags
    drug_flags = config.get("features", {}).get("drug", {})
    
    # Calculate dimension offsets based on enabled features in config
    morgan_end = 2048 if drug_flags.get("use_morgan", True) else 0
    
    rdkit_end = morgan_end
    if drug_flags.get("use_rdkit", True):
        rdkit_end += 6
        
    if morgan_end == 0:
        print("WARNING: Morgan fingerprints disabled in config, ablation might be invalid.")
        morgan_end = X_all.shape[1] # fallback to all drug features if somehow morgan is missing
        
    ablations = {
        "Ablation: Morgan Only": X_all[:, :morgan_end],
        "Ablation: Morgan + RDKit": X_all[:, :rdkit_end],
        # The full feature set includes disease features (and any other enabled drug features)
        "Ablation: Full Features": X_all 
    }
    
    mlflow.set_experiment(exp_name)
    model_kwargs = config.get("models", {}).get("rf", {})
    
    results = []
    
    for ab_name, X_subset in ablations.items():
        print(f"\nRunning {ab_name} (Shape: {X_subset.shape})...")
        
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=random_seed)
        fold_metrics = []
        
        with mlflow.start_run(run_name=f"{ab_name.replace(' ', '_')}_CV"):
            mlflow.log_params(model_kwargs)
            mlflow.log_param("num_features", X_subset.shape[1])
            
            for fold, (train_idx, test_idx) in enumerate(skf.split(X_subset, y_all)):
                X_train, y_train = X_subset[train_idx], y_all[train_idx]
                X_test, y_test = X_subset[test_idx], y_all[test_idx]
                
                base_model = RandomForestModel(**model_kwargs)
                
                # INTERNAL CALIBRATION FIX (No Leakage)
                # We wrap with cv=3 so it splits X_train internally and calibrates on hold-outs from X_train
                calibrated = CalibratedClassifierCV(estimator=base_model.model, method="sigmoid", cv=3)
                calibrated.fit(X_train, y_train)
                base_model.model = calibrated
                
                y_pred_proba = base_model.predict_proba(X_test)
                
                # Youden index optimization
                fpr, tpr, thresholds = roc_curve(y_test, y_pred_proba)
                best_threshold = thresholds[np.argmax(tpr - fpr)]
                
                metrics = compute_all_metrics(y_test, y_pred_proba, threshold=best_threshold)
                fold_metrics.append(metrics)
                
            # Aggregate fold metrics
            avg_metrics = {k: np.mean([m[k] for m in fold_metrics]) for k in fold_metrics[0].keys()}
            std_metrics = {k: np.std([m[k] for m in fold_metrics]) for k in fold_metrics[0].keys()}
            
            for k in list(avg_metrics.keys()):
                if isinstance(avg_metrics[k], float):
                    avg_metrics[f"{k}_std"] = std_metrics[k]
                    
            avg_metrics["name"] = ab_name
            avg_metrics["type"] = "ablation"
            
            # Save metrics
            out_name = ab_name.replace(" ", "_").replace(":", "").replace("+", "plus").lower()
            with open(models_dir / f"{out_name}_metrics.json", "w") as f:
                json.dump(avg_metrics, f, indent=4)
                
            results.append(avg_metrics)
            print_metrics(ab_name, avg_metrics, "ablation")

    print("\nAblations complete! Results saved to JSON.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default="configs/baseline_morgan.yaml")
    args = parser.parse_args()
    run_ablation_study(args.config)
