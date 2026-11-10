"""
scripts/evaluate.py - Final 11-Model Evaluation Consolidation

Merges results from train_baselines.py and train_gnn.py to produce 
the final comprehensive model comparison table used in the research paper.
"""

import sys
from pathlib import Path
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

from src.utils.metrics import format_metrics_table

def main(config_path):
    print("==========================================================")
    print("|   VectorDrugMatch - Comprehensive Model Comparison       |")
    print("==========================================================\n")
    
    config_path = REPO_ROOT / config_path
    import yaml
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    exp_name = config.get("experiment", {}).get("name", "baseline")
    outputs_dir = REPO_ROOT / "outputs" / exp_name
    models_dir = outputs_dir / "models"
    
    base_csv = outputs_dir / "baseline_comparison.csv"
    gnn_csv = outputs_dir / "gnn_comparison.csv"
    
    if not base_csv.exists() or not gnn_csv.exists():
        print("ERROR: Missing evaluation files.")
        print(f"Ensure both scripts have been run:")
        print("  python scripts/train_baselines.py")
        print("  python scripts/train_gnn.py")
        sys.exit(1)
        
    df_base = pd.read_csv(base_csv)
    df_gnn = pd.read_csv(gnn_csv)
    
    # Merge and format
    df_all = pd.concat([df_base, df_gnn], ignore_index=True)
    
    # Sort logically (baselines first, then GNNs, roughly by complexity)
    sort_order = {
        "Random Guess": 0,
        "Majority Class": 1,
        "Logistic Regression": 2,
        "Naive Bayes": 3,
        "Random Forest": 4,
        "XGBoost": 5,
        "MLP (scikit-learn)": 6,
        "GCN": 7,
        "GraphSAGE": 8,
        "GAT": 9,
        "RGCN": 10,
        "HGT": 11
    }
    
    df_all["_sort"] = df_all["name"].map(sort_order).fillna(99)
    df_all = df_all.sort_values("_sort").drop(columns=["_sort"])
    
    # Print the final table
    results = df_all.to_dict(orient="records")
    print(format_metrics_table(results))
    
    # Save final combined CSV
    out_csv = outputs_dir / "model_comparison.csv"
    df_all.to_csv(out_csv, index=False)
    print(f"\nFinal comparison saved to {out_csv}")
    
    print("\n--- Ablation Study ---")
    print("Model\t\t\t\tROC-AUC\t\tPR-AUC\t\tF1")
    
    # Load ablation results if they exist
    ablation_files = list(models_dir.glob("ablation*.json"))
    ablation_results = []
    for f in ablation_files:
        import json
        with open(f, "r") as json_f:
            ablation_results.append(json.load(json_f))
            
    if ablation_results:
        # Sort ablations logically
        ab_order = {
            "Ablation: Morgan Only": 1,
            "Ablation: Morgan + RDKit": 2,
            "Ablation: Morgan + RDKit + Disease": 3
        }
        ablation_results.sort(key=lambda x: ab_order.get(x.get("name", ""), 99))
        
        for ab in ablation_results:
            name = ab.get('name', 'Unknown')
            roc = f"{ab.get('roc_auc',0):.3f}±{ab.get('roc_auc_std',0):.2f}" if "roc_auc_std" in ab else f"{ab.get('roc_auc',0):.3f}"
            pr = f"{ab.get('pr_auc',0):.3f}±{ab.get('pr_auc_std',0):.2f}" if "pr_auc_std" in ab else f"{ab.get('pr_auc',0):.3f}"
            f1 = f"{ab.get('f1',0):.3f}±{ab.get('f1_std',0):.2f}" if "f1_std" in ab else f"{ab.get('f1',0):.3f}"
            print(f"{name:<30}\t{roc:<14}\t{pr:<14}\t{f1:<14}")
    else:
        print("No actual ablation models found. Run scripts/run_ablations.py.")
        
    # Also print GNN and NDPI for context
    hgt_row = df_all[df_all["name"] == "HGT"]
    if not hgt_row.empty:
        hgt = hgt_row.iloc[0]
        roc = f"{hgt.get('roc_auc',0):.3f}±{hgt.get('roc_auc_std',0):.2f}" if "roc_auc_std" in hgt and not pd.isna(hgt["roc_auc_std"]) else f"{hgt.get('roc_auc',0):.3f}"
        pr = f"{hgt.get('pr_auc',0):.3f}±{hgt.get('pr_auc_std',0):.2f}" if "pr_auc_std" in hgt and not pd.isna(hgt["pr_auc_std"]) else f"{hgt.get('pr_auc',0):.3f}"
        f1 = f"{hgt.get('f1',0):.3f}±{hgt.get('f1_std',0):.2f}" if "f1_std" in hgt and not pd.isna(hgt["f1_std"]) else f"{hgt.get('f1',0):.3f}"
        print(f"{'Full GNN (HGT)':<30}\t{roc:<14}\t{pr:<14}\t{f1:<14}")
        
    print(f"{'Full Pipeline (+ NDPI)':<30}\tScore represents final ranking composite, not pure ML metric.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default="configs/baseline_morgan.yaml")
    args = parser.parse_args()
    main(args.config)
