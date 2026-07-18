"""
scripts/train_baselines.py - Train Classical ML Baselines

This script evaluates tabular ML models on the link prediction task 
(predicting Drug-treats-Disease edges) using StratifiedKFold Cross-Validation,
MLflow tracking, Probability Calibration, and Threshold Optimization (Youden Index).
"""

import sys
import argparse
from pathlib import Path
import yaml
import json
import shutil

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.model_selection import StratifiedKFold
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_curve, precision_recall_curve
import mlflow
import mlflow.sklearn
import shap

# Add repo root to Python path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

from src.data.graph_builder import build_hetero_data
from src.data.dataset import build_tabular_dataset
from src.utils.metrics import compute_all_metrics, format_metrics_table, print_metrics
from src.utils.experiment_logger import log_experiment

from src.models.baseline.logistic import LogisticRegressionModel
from src.models.baseline.naive_bayes import NaiveBayesModel
from src.models.baseline.random_forest import RandomForestModel
from src.models.baseline.xgboost_model import XGBoostModel, XGB_AVAILABLE
from src.models.baseline.mlp import MLPModel


def get_available_models():
    """Returns a dictionary of available baseline models."""
    models = {
        "logistic": ("Logistic Regression", LogisticRegressionModel),
        "nb": ("Naive Bayes", NaiveBayesModel),
        "rf": ("Random Forest", RandomForestModel),
        "mlp": ("MLP (scikit-learn)", MLPModel),
    }
    if XGB_AVAILABLE:
        models["xgb"] = ("XGBoost", XGBoostModel)
    return models


def train_evaluate_baselines(selected_models, config_path):
    print("==========================================================")
    print("   VectorDrugMatch - Baseline Models Training Pipeline    ")
    print("==========================================================")
    
    # Load Config
    config = {}
    if config_path.exists():
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
            
    exp_name = config.get("experiment", {}).get("name", "baseline")
    processed_dir = REPO_ROOT / "data" / "processed" / exp_name
    
    outputs_dir = REPO_ROOT / "outputs" / exp_name
    models_dir = outputs_dir / "models"
    preds_dir = outputs_dir / "predictions"
    
    outputs_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)
    preds_dir.mkdir(parents=True, exist_ok=True)
            
    dataset_cfg = config.get("dataset", {})
    neg_ratio = dataset_cfg.get("neg_ratio", 5.0)
    test_size = dataset_cfg.get("test_size", 0.15)
    val_size = dataset_cfg.get("val_size", 0.15)
    random_seed = dataset_cfg.get("random_seed", 42)
    
    # 1. Load Graph
    print("\nLoading HeteroData...")
    try:
        data = build_hetero_data(processed_dir, include_features=True)
    except FileNotFoundError:
        print("ERROR: Processed data not found. Run scripts/preprocess.py first.")
        sys.exit(1)
        
    # 2. Build Dataset
    splits = build_tabular_dataset(
        data, 
        neg_ratio=neg_ratio, 
        test_size=test_size, 
        val_size=val_size,
        random_state=random_seed
    )
    
    X_all = np.vstack([splits.get("X_train", np.empty((0,0))), 
                       splits.get("X_val", np.empty((0,0))), 
                       splits.get("X_test", np.empty((0,0)))])
                       
    y_all = np.concatenate([splits.get("y_train", []), 
                            splits.get("y_val", []), 
                            splits.get("y_test", [])])
                            
    # We filter out empty splits from the stack
    valid_idx = [i for i, x in enumerate([splits.get("X_train"), splits.get("X_val"), splits.get("X_test")]) if x is not None and len(x) > 0]
    X_parts = []
    y_parts = []
    if "X_train" in splits: X_parts.append(splits["X_train"]); y_parts.append(splits["y_train"])
    if "X_val" in splits: X_parts.append(splits["X_val"]); y_parts.append(splits["y_val"])
    if "X_test" in splits: X_parts.append(splits["X_test"]); y_parts.append(splits["y_test"])
    
    X_all = np.vstack(X_parts)
    y_all = np.concatenate(y_parts)
    
    results = []
    
    # 4. Train & Evaluate ML Models
    print("\nTraining ML Baselines with 5-Fold Stratified CV...")
    
    available = get_available_models()
    
    mlflow.set_experiment(exp_name)
    
    for key in selected_models:
        if key not in available:
            print(f"[WARNING] Skipping unknown model: {key}")
            continue
            
        name, ModelClass = available[key]
        print(f"\nTraining {name} (K-Fold)...")
        
        model_kwargs = config.get("models", {}).get(key, {})
        
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=random_seed)
        fold_metrics = []
        best_threshold = 0.5
        
        with mlflow.start_run(run_name=f"{name}_CV"):
            mlflow.log_params(model_kwargs)
            
            for fold, (train_idx, test_idx) in enumerate(skf.split(X_all, y_all)):
                X_train, y_train = X_all[train_idx], y_all[train_idx]
                X_test, y_test = X_all[test_idx], y_all[test_idx]
                
                base_model = ModelClass(**model_kwargs)
                
                # We wrap the internal sklearn model in CalibratedClassifierCV
                # using cv=3 internally on X_train to prevent leakage into X_test
                if key in ["rf", "xgb", "logistic"] and hasattr(base_model, "model"):
                    calibrated = CalibratedClassifierCV(estimator=base_model.model, method="sigmoid", cv=3)
                    calibrated.fit(X_train, y_train)
                    base_model.model = calibrated
                else:
                    base_model.train(X_train, y_train)
                    
                y_pred_proba = base_model.predict_proba(X_test)
                
                # Youden index optimization on the fold
                fpr, tpr, thresholds = roc_curve(y_test, y_pred_proba)
                youden_j = tpr - fpr
                best_threshold = thresholds[np.argmax(youden_j)]
                
                metrics = compute_all_metrics(y_test, y_pred_proba, threshold=best_threshold)
                fold_metrics.append(metrics)
                
                mlflow.log_metrics({f"fold_{fold}_{k}": v for k,v in metrics.items()})
                
            # Aggregate fold metrics
            avg_metrics = {k: np.mean([m[k] for m in fold_metrics]) for k in fold_metrics[0].keys()}
            std_metrics = {k: np.std([m[k] for m in fold_metrics]) for k in fold_metrics[0].keys()}
            
            for k in list(avg_metrics.keys()):
                if isinstance(avg_metrics[k], float):
                    avg_metrics[f"{k}_std"] = std_metrics[k]
                    
            avg_metrics["name"] = name
            avg_metrics["type"] = "baseline"
            avg_metrics["best_threshold"] = float(best_threshold)
            
            mlflow.log_metrics({f"avg_{k}": v for k,v in avg_metrics.items() if isinstance(v, (int, float))})
            
            # Save final full model
            final_model = ModelClass(**model_kwargs)
            if key in ["rf", "xgb", "logistic"] and hasattr(final_model, "model"):
                calibrated = CalibratedClassifierCV(estimator=final_model.model, method="sigmoid", cv=5)
                calibrated.fit(X_all, y_all)
                final_model.model = calibrated
            else:
                final_model.train(X_all, y_all)
                
            model_path = models_dir / f"baseline_{key}.pkl"
            final_model.save(model_path)
            mlflow.log_artifact(str(model_path))
            
            # Feature Importance for RF/XGB
            if key in ["rf", "xgb"]:
                if hasattr(final_model.model, "estimator"):
                    # Extract from calibrated classifier
                    fi = final_model.model.estimator.feature_importances_
                    base_estimator = final_model.model.estimator
                else:
                    fi = final_model.model.feature_importances_
                    base_estimator = final_model.model
                    
                fi_df = pd.DataFrame({"Feature_Index": range(len(fi)), "Importance": fi})
                fi_df = fi_df.sort_values("Importance", ascending=False)
                fi_path = outputs_dir / f"{key}_feature_importance.csv"
                fi_df.to_csv(fi_path, index=False)
                mlflow.log_artifact(str(fi_path))
                
                # SHAP Support
                print(f"Computing SHAP values for {name}...")
                try:
                    explainer = shap.TreeExplainer(base_estimator)
                    # Use a random subset of 5000 instances to save time
                    sample_size = min(5000, len(X_all))
                    np.random.seed(random_seed)
                    idx = np.random.choice(len(X_all), sample_size, replace=False)
                    X_sample = X_all[idx]
                    
                    # Save exact indices used
                    idx_path = outputs_dir / f"{key}_shap_indices.npy"
                    np.save(idx_path, idx)
                    mlflow.log_artifact(str(idx_path))
                    
                    shap_values = explainer.shap_values(X_sample)
                    
                    shap_path = outputs_dir / f"{key}_shap_values.npy"
                    np.save(shap_path, shap_values)
                    mlflow.log_artifact(str(shap_path))
                    
                    plt.figure(figsize=(10, 8))
                    shap.summary_plot(shap_values, X_sample, show=False)
                    plot_path = outputs_dir / f"{key}_shap_summary.png"
                    plt.savefig(plot_path, bbox_inches='tight')
                    plt.close()
                    mlflow.log_artifact(str(plot_path))
                    print(f"SHAP values and summary plot saved for {name}.")
                except Exception as e:
                    print(f"SHAP computation failed for {name}: {e}")

                
            with open(models_dir / f"baseline_{key}_metrics.json", "w") as f:
                json.dump(avg_metrics, f, indent=4)
                
            results.append(avg_metrics)
            print_metrics(name, avg_metrics, "baseline")
        
    # 5. Save Results
    print("\n" + "="*80)
    print("Baseline Comparison Summary (5-Fold CV Average)")
    print("="*80)
    print(format_metrics_table(results))
    
    results_df = pd.DataFrame(results)
    csv_path = outputs_dir / "baseline_comparison.csv"
    results_df.to_csv(csv_path, index=False)
    print(f"\nResults saved to {csv_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Baseline Tabular Models")
    parser.add_argument(
        "--model", 
        type=str, 
        nargs="+", 
        choices=["logistic", "nb", "rf", "xgb", "mlp", "all", "default"],
        default=["default"],
        help="Models to train. 'default' runs Logistic, RF, XGB. 'all' runs everything."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to the experiment configuration YAML file."
    )
    
    args = parser.parse_args()
    
    if "all" in args.model:
        selected = list(get_available_models().keys())
    elif "default" in args.model:
        # User requested: stop before MLP to prove tabular pipeline
        selected = ["logistic", "rf", "xgb"]
    else:
        selected = args.model
        
    config_path = REPO_ROOT / args.config
    train_evaluate_baselines(selected, config_path)
