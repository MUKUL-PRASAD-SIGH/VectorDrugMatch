"""
scripts/run_treats_edge_ablation.py - controlled comparison of how the target (treats) edges enter GCN message passing. RUN ON COLAB (GPU); not run locally.

    python scripts/run_treats_edge_ablation.py --config-name A_orig  --seeds 21 42 52 72 100
    python scripts/run_treats_edge_ablation.py --config-name B_k4    --seeds 21 42 52 72 100
    python scripts/run_treats_edge_ablation.py --smoke               # every configuration, seed 42, a few epochs, written to <out>/smoke (never mixed with results)

Configurations (the model, optimiser, head, split, negatives and seeds are identical; only the listed property changes):
  A_orig    code-of-record protocol: no treats edges in message passing, ONE full-batch step per epoch (reproduces the earlier GCN protocol).
  A_k4      no treats edges, but each epoch = k=4 steps over a random stratified partition of the train pairs (the matched control for B).
  B_k{k}    train-positive treats edges (+reverse) in message passing; the positives supervised in a step are REMOVED from the graph in that step (no target
            leakage); evaluation uses all train positives. k = number of folds per epoch (k=2,4,8 selectable; choose k on VALIDATION only).
  B0_naive  DIAGNOSTIC ONLY: all train-positive treats edges in message passing and also supervised (target leakage by construction). Expected to look
            good in training and worse on held-out pairs; included to show why masking is necessary, never reported as a result.
  C_k4      mechanism-only graph (no treats, no contraindication/off-label edges), k=4 steps per epoch.
  D_rgcn_B  B_k4 with the existing RGCN encoder instead of GCN (relation-aware comparison).
  A_k4_L3 / B_k4_L3   the same as A_k4 / B_k4 with 3 message-passing layers instead of 2 (hypothesis: with 2 layers a held-out drug cannot receive
            information that travels drug - gene - train drug - treats - disease, which needs 3 hops; see diagnostics walk coverage).

Held-out (val/test) positives are never in the graph. Validation selects the checkpoint (best validation ROC-AUC, patience 20, <= 100 epochs); the
Youden threshold comes from validation; test is scored once with the selected checkpoint. Split: the saved seed-42 split (configs/primekg_morgan.yaml);
`--seeds` change initialisation and fold assignment only, never the split.

Outputs per run: <out>/<config>/seed<seed>/{metrics.json, predictions.csv, history.csv, model.pth, leakage_audit.json, run_config.json, train.log}
"""
import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml
from sklearn.metrics import roc_auc_score, roc_curve

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import torch.nn.functional as F  # noqa: E402

from src.data.dataset import build_message_passing_graph, build_tabular_dataset, set_seeds  # noqa: E402
from src.data.graph_builder import build_hetero_data  # noqa: E402
from src.data.treats_edges import (TARGET, build_variant_edges, leakage_audit, make_folds, supervision_view, train_positive_pairs)  # noqa: E402
from src.models.gnn.base import GNNLinkPredictionModel  # noqa: E402
from src.models.gnn.gcn import create_gcn_model  # noqa: E402
from src.models.gnn.rgcn import create_rgcn_model  # noqa: E402
from src.utils.eval_extra import bootstrap_ci, classification_calibration, errors_at, precision_recall_ndcg_at_k  # noqa: E402

CONFIGS = {
    "A_orig": dict(variant="original", k=1, mask=False, arch="GCN"),
    "A_k4": dict(variant="original", k=4, mask=False, arch="GCN"),
    "B_k2": dict(variant="train_treats", k=2, mask=True, arch="GCN"),
    "B_k4": dict(variant="train_treats", k=4, mask=True, arch="GCN"),
    "B_k8": dict(variant="train_treats", k=8, mask=True, arch="GCN"),
    "B0_naive": dict(variant="train_treats", k=1, mask=False, arch="GCN"),
    "C_k4": dict(variant="mechanism", k=4, mask=False, arch="GCN"),
    "D_rgcn_B": dict(variant="train_treats", k=4, mask=True, arch="RGCN"),
    "A_k4_L3": dict(variant="original", k=4, mask=False, arch="GCN", layers=3),       # 3 layers: matched control for B_k4_L3
    "B_k4_L3": dict(variant="train_treats", k=4, mask=True, arch="GCN", layers=3),   # a 3-hop receptive field reaches test drug -gene- train drug -treats- disease
}
EMB = 64
HEAD = 32


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    except Exception:
        return None


def make_model(cfg, data, base, splits, x, e_tr, seed, dev):
    """Seeded model whose initial weights depend ONLY on (architecture, layers, seed): the lazy layers are initialised with one canonical forward pass on the
    'original' edge dict for every configuration. (Initialising on each configuration's own edge dict was found to give different initial weights for A and B,
    which would have confounded the comparison; see Docs/TREATS_EDGE_ABLATION_PLAN.md.)"""
    set_seeds(seed)
    gnn = create_gcn_model(data.metadata(), EMB, EMB, num_layers=cfg.get("layers", 2)) if cfg["arch"] == "GCN" else create_rgcn_model(data.metadata(), EMB, EMB)
    model = GNNLinkPredictionModel(gnn, in_channels=EMB, hidden_channels=HEAD).to(dev)
    ed0 = {k: v.to(dev) for k, v in build_variant_edges(base, splits, "original").items()}
    with torch.no_grad():
        model.forward_logits(x, ed0, e_tr[:, :8])
    return model


def forward_logits(model, x, ed, idx):
    return model.forward_logits(x, ed, idx)


def evaluate(model, x, ed, idx, y):
    model.eval()
    with torch.no_grad():
        p = torch.sigmoid(model.forward_logits(x, ed, idx)).float().cpu().numpy()
    return p


def run_one(name, seed, a, ctx, out_root, max_epochs, patience):
    cfg = CONFIGS[name]
    run_dir = out_root / name / f"seed{seed}"
    if (run_dir / "metrics.json").exists():
        if a.resume:
            print(f"[resume] {name} seed {seed} already done")
            return
        if not a.smoke:
            sys.exit(f"{run_dir} already holds results: refusing to overwrite (use --resume to skip finished runs, or a different --out)")
    run_dir.mkdir(parents=True, exist_ok=True)
    log = open(run_dir / "train.log", "w", encoding="utf-8")

    def P(*s):
        msg = " ".join(str(x) for x in s)
        print(msg)
        log.write(msg + "\n")
        log.flush()

    dev, data, base, splits = ctx["dev"], ctx["data"], ctx["base"], ctx["splits"]
    ed_eval = {k: v.to(dev) for k, v in build_variant_edges(base, splits, cfg["variant"]).items()}
    x = {t: data[t].x.float().to(dev) for t in data.node_types}
    n = {t: data[t].num_nodes for t in data.node_types}
    train_pos =torch.as_tensor(train_positive_pairs(splits), dtype=torch.long, device=dev)
    pos_rows = np.where(np.asarray(splits["y_train"]).astype(bool))[0]
    pos_of_row = {int(r): j for j, r in enumerate(pos_rows)}
    e_tr = torch.as_tensor(splits["edges_train"], dtype=torch.long, device=dev)
    y_tr = torch.as_tensor(splits["y_train"], dtype=torch.float32, device=dev)
    e_va, y_va = torch.as_tensor(splits["edges_val"], dtype=torch.long, device=dev), np.asarray(splits["y_val"])
    e_te, y_te = torch.as_tensor(splits["edges_test"], dtype=torch.long, device=dev), np.asarray(splits["y_test"])

    # masking self-check for this run (epoch-1 folds), saved in the audit
    rng_check = np.random.default_rng(seed)
    folds_check = make_folds(train_pos.shape[1], splits["y_train"], cfg["k"], rng_check)
    sup_check = [(train_pos.cpu(), [torch.as_tensor([pos_of_row[int(i)] for i in f if int(i) in pos_of_row], dtype=torch.long) for f in folds_check])] if (cfg["mask"] and cfg["variant"] == "train_treats") else None
    audit = leakage_audit({k: v.cpu() for k, v in ed_eval.items()}, splits, data, n["drug"], n["disease"], cfg["variant"], sup_check=sup_check)
    (run_dir / "leakage_audit.json").write_text(json.dumps(audit, indent=1, default=str), encoding="utf-8")
    if not audit["all_pass"]:
        P("LEAKAGE AUDIT FAILED - not training", json.dumps({k: v for k, v in audit.items() if isinstance(v, dict) and not v.get("pass", True)}, default=str)[:600])
        sys.exit(2)

    model = make_model(cfg, data, base, splits, x, e_tr, seed, dev)
    n_params = int(sum(p.numel() for p in model.parameters()))
    opt = torch.optim.Adam(model.parameters(), lr=0.005, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, mode="max", factor=0.5, patience=10)
    scaler = torch.cuda.amp.GradScaler(enabled=dev.type == "cuda")
    rng = np.random.default_rng(seed)
    best, best_state, best_ep, bad, hist = -1.0, None, 0, 0, []
    t0 = time.time()
    for ep in range(1, max_epochs + 1):
        model.train()
        folds = make_folds(train_pos.shape[1], splits["y_train"], cfg["k"], rng) if cfg["k"] > 1 else [np.arange(len(splits["y_train"]))]
        losses = []
        for f in folds:
            ft = torch.as_tensor(f, dtype=torch.long, device=dev)
            if cfg["mask"]:
                sup = torch.as_tensor([pos_of_row[int(i)] for i in f if int(i) in pos_of_row], dtype=torch.long, device=dev)
                ed = supervision_view(ed_eval, train_pos, sup)
            else:
                ed = ed_eval
            opt.zero_grad()
            with torch.cuda.amp.autocast(enabled=scaler.is_enabled()):
                logits = model.forward_logits(x, ed, e_tr[:, ft])
            loss = F.binary_cross_entropy_with_logits(logits.float(), y_tr[ft])
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            losses.append(float(loss.item()))
        pv = evaluate(model, x, ed_eval, e_va, y_va)
        v_auc = float(roc_auc_score(y_va, pv))
        sched.step(v_auc)
        hist.append({"epoch": ep, "train_loss": float(np.mean(losses)), "val_roc_auc": v_auc})
        if v_auc > best:
            best, best_ep, bad = v_auc, ep, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
        if ep % 10 == 0 or ep == 1:
            P(f"  {name} seed {seed} epoch {ep:>3} loss {hist[-1]['train_loss']:.4f} val ROC-AUC {v_auc:.4f}")
        if bad >= patience:
            P(f"  early stop at epoch {ep}")
            break
    train_s = time.time() - t0
    model.load_state_dict(best_state)
    t1 = time.time()
    pv = evaluate(model, x, ed_eval, e_va, y_va)
    pt = evaluate(model, x, ed_eval, e_te, y_te)
    infer_s = time.time() - t1
    fpr, tpr, thr = roc_curve(y_va, pv)
    threshold = float(thr[np.argmax(tpr - fpr)])
    m = {"config": name, "seed": seed, "arch": cfg["arch"], "variant": cfg["variant"], "k": cfg["k"], "mask_supervised_edges": cfg["mask"],
         "val": classification_calibration(y_va, pv), "test": classification_calibration(y_te, pt), "n_params": n_params, "best_epoch": best_ep, "epochs_run": len(hist),
         "train_seconds": round(train_s, 1), "inference_seconds_val_plus_test": round(infer_s, 3),
         "counts": {"train_pairs": int(len(splits["y_train"])), "train_pos": int(np.sum(splits["y_train"])), "val_pairs": int(len(y_va)), "val_pos": int(y_va.sum()),
                    "test_pairs": int(len(y_te)), "test_pos": int(y_te.sum()), "mp_treats_edges_at_eval": int(ed_eval[TARGET].shape[1]),
                    "mp_edges_total_at_eval": int(sum(v.shape[1] for v in ed_eval.values()))}}
    m["test"].update(precision_recall_ndcg_at_k(y_te, pt))
    err, wfp, wfn = errors_at(y_te, pt, threshold)
    m["test_errors"] = err
    m["test_bootstrap_ci"] = bootstrap_ci(y_te, pt, n=a.bootstrap, seed=seed)
    ids_d = ctx["drug_ids"]
    ids_s = ctx["disease_ids"]
    et = np.asarray(splits["edges_test"])
    pd.DataFrame({"drug_id": [ids_d[i] for i in et[0]], "disease_id": [ids_s[i] for i in et[1]], "label": y_te, "probability": pt}).to_csv(run_dir / "predictions.csv", index=False)
    pd.DataFrame({"drug_id": [ids_d[i] for i in et[0][wfp]], "disease_id": [ids_s[i] for i in et[1][wfp]], "probability": pt[wfp], "kind": "high_conf_false_positive"}).to_csv(run_dir / "high_conf_false_positives.csv", index=False)
    pd.DataFrame({"drug_id": [ids_d[i] for i in et[0][wfn]], "disease_id": [ids_s[i] for i in et[1][wfn]], "probability": pt[wfn], "kind": "high_conf_false_negative"}).to_csv(run_dir / "high_conf_false_negatives.csv", index=False)
    pd.DataFrame(hist).to_csv(run_dir / "history.csv", index=False)
    torch.save(model.state_dict(), run_dir / "model.pth")
    (run_dir / "metrics.json").write_text(json.dumps(m, indent=1, default=float), encoding="utf-8")
    (run_dir / "run_config.json").write_text(json.dumps({
        "config": name, **cfg, "seed": seed, "split": "data/processed/primekg/splits/seed42.npz (fixed)", "optimizer": "Adam lr 0.005 wd 1e-4", "scheduler": "ReduceLROnPlateau(val ROC-AUC, factor .5, patience 10)",
        "early_stopping": f"patience {patience}, max {max_epochs} epochs, checkpoint = best validation ROC-AUC", "emb_dim": EMB, "head_hidden": HEAD, "git_commit": git_commit(),
        "torch": torch.__version__, "cuda": torch.version.cuda, "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None, "python": platform.python_version(),
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=1), encoding="utf-8")
    P(f"DONE {name} seed {seed}: test ROC-AUC {m['test']['roc_auc']:.4f} AP {m['test']['pr_auc_ap']:.4f} | val ROC-AUC {m['val']['roc_auc']:.4f} | best epoch {best_ep} | {train_s:.0f}s | params {n_params:,}")
    log.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config-name", nargs="+", choices=list(CONFIGS))
    ap.add_argument("--seeds", nargs="+", type=int, default=[21, 42, 52, 72, 100])
    ap.add_argument("--out", default="outputs/treats_edge_ablation_20261111")
    ap.add_argument("--smoke", action="store_true", help="all configurations, seed 42, 3 epochs, 20 bootstrap resamples, output under <out>/smoke")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--patience", type=int, default=20)
    ap.add_argument("--bootstrap", type=int, default=3000)
    ap.add_argument("--config", default="configs/primekg_morgan.yaml")
    a = ap.parse_args()
    if not Path(a.out).name.startswith("treats_edge_ablation_"):
        sys.exit("--out must be a treats_edge_ablation_* folder: this script never writes into other result folders")
    if a.smoke:
        a.config_name, a.seeds, a.epochs, a.bootstrap = list(CONFIGS), [42], 3, 20
        out_root = REPO / a.out / "smoke"
    else:
        out_root = REPO / a.out
        if not a.config_name:
            sys.exit("give --config-name or --smoke")
    cfg = yaml.safe_load(open(REPO / a.config, encoding="utf-8"))
    proc = cfg["experiment"].get("processed_name", cfg["experiment"]["name"])
    presplit = cfg["dataset"]["presplit"]
    data = build_hetero_data(REPO / "data" / "processed" / proc, include_features=True)
    raw = np.load(REPO / presplit, allow_pickle=True)         # the saved split itself (edges, labels, drugs, held-out pairs)
    splits = {k: raw[k] for k in raw.files}
    base = build_message_passing_graph(data, presplit)
    ctx = {"dev": torch.device("cuda" if torch.cuda.is_available() else "cpu"), "data": data, "base": base, "splits": splits,
           "drug_ids": data["drug"].node_ids, "disease_ids": data["disease"].node_ids}
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "split_manifest_copy.json").write_text((REPO / "data/processed/primekg/splits/seed42.manifest.json").read_text(encoding="utf-8"), encoding="utf-8")
    for name in a.config_name:
        for s in a.seeds:
            run_one(name, s, a, ctx, out_root, a.epochs, a.patience)


if __name__ == "__main__":
    main()
