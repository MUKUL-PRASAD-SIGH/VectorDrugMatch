"""
scripts/final_audit/train_gcn_protocol.py - GCN/RGCN trainer for the final protocol (development CV, final training) and the convergence rerun.

    # development CV (validation only; the locked holdout is never read here)
    python scripts/final_audit/train_gcn_protocol.py --name L3_base --splits cv_fold0 cv_fold1 cv_fold2 cv_fold3 cv_fold4 --seeds 42 --layers 3 \
        --out outputs/final_audit_20261117/dev_cv
    # convergence experiment on the HISTORICAL split (200 epochs, patience 20)
    python scripts/final_audit/train_gcn_protocol.py --name A_k4_L3_e200 --splits historical --seeds 21 42 52 72 100 --layers 3 --epochs 200 \
        --out outputs/final_audit_20261117/convergence

Training logic is that of scripts/run_treats_edge_ablation.py (same canonical initialisation, k-step stratified fold epochs, Adam + ReduceLROnPlateau
on validation ROC-AUC, gradient clipping 1.0, AMP on GPU only, checkpoint = best validation ROC-AUC, early stopping patience). With the historical
split, --layers 3 --k 4 --epochs 100 reproduces A_k4_L3. Everything that differs is a command-line hyper-parameter recorded in run_config.json.

Graph: all treats edges removed; contraindicated_for / offlabel_for edges on `exclude_from_graph_pairs` (every non-training drug's indication pairs,
incl. the locked holdout's) removed in both directions; variant 'mechanism' removes contra/off-label entirely; 'train_treats' adds TRAIN positives with
per-step masking (as B_k4). An automated leakage audit runs before training and the run stops if any check fails.

Per run: <out>/<name>/<split>/seed<seed>/{metrics.json, val_predictions.csv, val_popmatch_predictions.csv, [test_predictions.csv for 'historical'],
history.csv, model.pth, leakage_audit.json, run_config.json, train.log}
"""
import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from src.data.dataset import _drop_pairs, build_message_passing_graph, set_seeds  # noqa: E402
from src.data.graph_builder import build_hetero_data  # noqa: E402
from src.data.treats_edges import LABEL_REL, REV, TARGET, build_variant_edges, make_folds, supervision_view, train_positive_pairs  # noqa: E402
from src.models.gnn.base import GNNLinkPredictionModel  # noqa: E402
from src.models.gnn.gcn import create_gcn_model  # noqa: E402
from src.models.gnn.rgcn import create_rgcn_model  # noqa: E402
from src.utils.final_metrics import all_metrics  # noqa: E402

FINAL_DIR = "data/processed/primekg/splits_final_20261117"
DISEASE_DIR = "data/processed/primekg/splits_disease_20261118"   # comparison protocol: diseases are the held-out unit
HIST = "data/processed/primekg/splits/seed42.npz"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    except Exception:
        return None


def load_split(name):
    """-> (dict of arrays, path). 'historical' = the saved seed-42 split (its val/test pairs are excluded from the graph)."""
    if name == "historical":
        p = REPO / HIST
        z = dict(np.load(p))
        z["exclude_from_graph_pairs"] = z["heldout_indication_pairs"]
        return z, p
    if "holdout" in name.lower():
        sys.exit("the locked holdout is never a training/validation split (use scripts/final_audit/evaluate_final_holdout.py)")
    p = (REPO / DISEASE_DIR / f"{name}.npz") if name == "disease_split" else (REPO / FINAL_DIR / f"{name}.npz")
    return dict(np.load(p)), p


def mp_graph(data, splits):
    """Leakage-safe message-passing HeteroData for this split (no treats; excluded pairs removed from contra/off-label, both directions)."""
    mp = build_message_passing_graph(data, None)                     # removes treats / rev_treats
    ex = np.asarray(splits["exclude_from_graph_pairs"]).astype(np.int64)
    n_dis, n_dr = mp["disease"].num_nodes, mp["drug"].num_nodes
    for rel in LABEL_REL:
        fwd, rev = ("drug", rel, "disease"), ("disease", f"rev_{rel}", "drug")
        if fwd in mp.edge_types:
            mp[fwd].edge_index = _drop_pairs(mp[fwd].edge_index, ex, n_dis)
        if rev in mp.edge_types:
            mp[rev].edge_index = _drop_pairs(mp[rev].edge_index, ex[::-1], n_dr)
    return mp


def graph_edges(data, splits, variant):
    """Leakage-safe message-passing edge dict for this split and graph variant."""
    return build_variant_edges(mp_graph(data, splits), splits, variant)


def audit(ed, splits, data, variant):
    n2 = data["disease"].num_nodes
    key = lambda e: np.asarray(e[0], np.int64) * n2 + np.asarray(e[1], np.int64)  # noqa: E731
    ex = key(splits["exclude_from_graph_pairs"])
    out = {}
    per, ok = {}, True
    for rel in ("treats",) + LABEL_REL:
        f, r = ("drug", rel, "disease"), ("disease", f"rev_{rel}", "drug")
        nf = int(np.isin(key(ed[f].cpu().numpy()), ex).sum()) if f in ed and ed[f].numel() else 0
        nr = int(np.isin(key(ed[r].flip(0).cpu().numpy()), ex).sum()) if r in ed and ed[r].numel() else 0
        per[rel] = {"excluded_in_forward": nf, "excluded_in_reverse": nr}
        ok &= nf == 0 and nr == 0
    out["no_excluded_pair_in_any_drug_disease_edge_or_reverse"] = {"pass": bool(ok), "detail": per}
    vpos = np.asarray(splits["edges_val"])[:, np.asarray(splits["y_val"]).astype(bool)]
    out["val_positives_are_excluded"] = {"pass": bool(np.isin(key(vpos), ex).all())}
    if "edges_test" in splits:
        tpos = np.asarray(splits["edges_test"])[:, np.asarray(splits["y_test"]).astype(bool)]
        out["test_positives_are_excluded"] = {"pass": bool(np.isin(key(tpos), ex).all())}
    trk = key(train_positive_pairs(splits))
    tk = key(ed[TARGET].cpu().numpy()) if ed[TARGET].numel() else np.zeros(0, np.int64)
    out["treats_edges_are_train_positives_only"] = {"pass": bool(np.isin(tk, trk).all() and (tk.size == (trk.size if variant == "train_treats" else 0))),
                                                   "n_treats_edges": int(tk.size)}
    out["rev_treats_is_flip"] = {"pass": bool(set(key(ed[REV].flip(0).cpu().numpy()).tolist()) == set(tk.tolist()))}
    unit = "diseases" if "diseases_train" in splits else "drugs"     # held-out unit: drugs (main protocol) or diseases (comparison protocol)
    row = 1 if unit == "diseases" else 0
    utr, uva = set(np.asarray(splits[f"{unit}_train"]).tolist()), set(np.asarray(splits[f"{unit}_val"]).tolist())
    ute = set(np.asarray(splits[f"{unit}_test"]).tolist()) if f"{unit}_test" in splits else set()
    out[f"{unit[:-1]}_sets_disjoint"] = {"pass": bool(not (utr & uva) and not (utr & ute) and not (uva & ute)), "held_out_unit": unit}
    out[f"train_pair_{unit}_are_train_{unit}"] = {"pass": bool(set(np.asarray(splits["edges_train"])[row].tolist()) <= utr)}
    known = np.unique(np.concatenate([key(data[("drug", r, "disease")].edge_index.numpy()) for r in ("treats",) + LABEL_REL if ("drug", r, "disease") in data.edge_types]))
    neg = {}
    nok = True
    for nm in [k[6:] for k in splits if k.startswith("edges_")]:
        y = np.asarray(splits[f"y_{nm}"]).astype(bool)
        hit = int(np.isin(key(np.asarray(splits[f"edges_{nm}"])[:, ~y]), known).sum())
        neg[nm] = hit
        nok &= hit == 0
    out["negatives_are_not_known_pairs"] = {"pass": bool(nok), "known_pairs_among_negatives": neg}
    out["all_pass"] = bool(all(v["pass"] for v in out.values()))
    return out


def make_model(hp, data, base_ed, x, e_tr, seed, dev):
    set_seeds(seed)
    if hp["arch"] == "GCN":
        gnn = create_gcn_model(data.metadata(), hp["emb"], hp["emb"], num_layers=hp["layers"], dropout=hp["dropout"])
    else:
        gnn = create_rgcn_model(data.metadata(), hp["emb"], hp["emb"], num_layers=hp["layers"])
    model = GNNLinkPredictionModel(gnn, in_channels=hp["emb"], hidden_channels=hp["head"]).to(dev)
    with torch.no_grad():                                           # canonical lazy initialisation on the 'original'-type edge dict
        model.forward_logits(x, base_ed, e_tr[:, :8])
    return model


def predict(model, x, ed, e):
    model.eval()
    with torch.no_grad():
        return torch.sigmoid(model.forward_logits(x, ed, torch.as_tensor(e, dtype=torch.long, device=x["drug"].device))).float().cpu().numpy()


def run_one(hp, split_name, seed, ctx, out_root, resume):
    run_dir = out_root / hp["name"] / split_name / f"seed{seed}"
    if (run_dir / "metrics.json").exists():
        if resume:
            print(f"[resume] {hp['name']} {split_name} seed {seed} done")
            return
        sys.exit(f"{run_dir} already holds results; refusing to overwrite (use --resume)")
    run_dir.mkdir(parents=True, exist_ok=True)
    log = open(run_dir / "train.log", "w", encoding="utf-8")

    def P(*s):
        m = " ".join(str(v) for v in s)
        print(m)
        log.write(m + "\n")
        log.flush()

    dev, data = ctx["dev"], ctx["data"]
    splits, sp_path = load_split(split_name)
    ed_eval = {k: v.to(dev) for k, v in graph_edges(data, splits, hp["variant"]).items()}
    ed_init = {k: v.to(dev) for k, v in graph_edges(data, splits, "original").items()}
    au = audit({k: v.cpu() for k, v in ed_eval.items()}, splits, data, hp["variant"])
    (run_dir / "leakage_audit.json").write_text(json.dumps(au, indent=1), encoding="utf-8")
    if not au["all_pass"]:
        P("LEAKAGE AUDIT FAILED - not training", json.dumps(au)[:800])
        sys.exit(2)
    x = {t: data[t].x.float().to(dev) for t in data.node_types}
    train_pos = torch.as_tensor(train_positive_pairs(splits), dtype=torch.long, device=dev)
    pos_rows = np.where(np.asarray(splits["y_train"]).astype(bool))[0]
    pos_of_row = {int(r): j for j, r in enumerate(pos_rows)}
    e_tr = torch.as_tensor(splits["edges_train"], dtype=torch.long, device=dev)
    y_tr = torch.as_tensor(splits["y_train"], dtype=torch.float32, device=dev)
    y_va = np.asarray(splits["y_val"]).astype(int)
    model = make_model(hp, data, ed_init, x, e_tr, seed, dev)
    n_params = int(sum(p.numel() for p in model.parameters()))
    opt = torch.optim.Adam(model.parameters(), lr=hp["lr"], weight_decay=hp["wd"])
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, mode="max", factor=0.5, patience=hp["sched_patience"])
    use_amp = dev.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    rng = np.random.default_rng(seed)
    best, best_state, best_ep, bad, hist = -1.0, None, 0, 0, []
    mask = hp["variant"] == "train_treats"
    t0 = time.time()
    for ep in range(1, hp["epochs"] + 1):
        model.train()
        folds = make_folds(train_pos.shape[1], splits["y_train"], hp["k"], rng) if hp["k"] > 1 else [np.arange(len(splits["y_train"]))]
        losses = []
        for f in folds:
            ft = torch.as_tensor(f, dtype=torch.long, device=dev)
            if mask:
                sup = torch.as_tensor([pos_of_row[int(i)] for i in f if int(i) in pos_of_row], dtype=torch.long, device=dev)
                ed = supervision_view(ed_eval, train_pos, sup)
            else:
                ed = ed_eval
            opt.zero_grad()
            with torch.autocast(device_type=dev.type, enabled=use_amp):
                logits = model.forward_logits(x, ed, e_tr[:, ft])
            loss = F.binary_cross_entropy_with_logits(logits.float(), y_tr[ft])
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            losses.append(float(loss.item()))
        pv = predict(model, x, ed_eval, splits["edges_val"])
        v_auc = float(roc_auc_score(y_va, pv))
        sched.step(v_auc)
        hist.append({"epoch": ep, "train_loss": float(np.mean(losses)), "val_roc_auc": v_auc, "val_ap": float(average_precision_score(y_va, pv)),
                     "lr": opt.param_groups[0]["lr"]})
        if v_auc > best:
            best, best_ep, bad = v_auc, ep, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
        if ep % 10 == 0 or ep == 1:
            P(f"  {hp['name']} {split_name} s{seed} ep {ep:>3} loss {hist[-1]['train_loss']:.4f} val AUC {v_auc:.4f} lr {hist[-1]['lr']:.2e}")
        if bad >= hp["patience"]:
            P(f"  early stop at epoch {ep}")
            break
    train_s = time.time() - t0
    model.load_state_dict(best_state)
    t1 = time.time()
    pv = predict(model, x, ed_eval, splits["edges_val"])
    infer_s = time.time() - t1
    fpr, tpr, thr = roc_curve(y_va, pv)
    threshold = float(thr[np.argmax(tpr - fpr)])
    ids_d, ids_s = ctx["drug_ids"], ctx["disease_ids"]
    m = {"name": hp["name"], "split": split_name, "seed": seed, "hp": hp, "n_params": n_params, "best_epoch": best_ep, "epochs_run": len(hist),
         "stopped_early": len(hist) < hp["epochs"], "best_epoch_at_budget": best_ep == hp["epochs"], "train_seconds": round(train_s, 1),
         "val_inference_seconds": round(infer_s, 3), "val_threshold_youden": threshold, "val": all_metrics(y_va, pv)}
    sets = [("val", "edges_val", "y_val", pv)]
    if "edges_val_popmatch" in splits:
        pp = predict(model, x, ed_eval, splits["edges_val_popmatch"])
        m["val_popmatch"] = all_metrics(splits["y_val_popmatch"], pp)
        sets.append(("val_popmatch", "edges_val_popmatch", "y_val_popmatch", pp))
    if "edges_test" in splits:            # historical split (already-seen test set) or the disease-disjoint comparison split
        tk = "historical_test" if split_name == "historical" else "test"
        pt = predict(model, x, ed_eval, splits["edges_test"])
        m[tk] = all_metrics(splits["y_test"], pt)
        sets.append(("test", "edges_test", "y_test", pt))
        if "edges_test_popmatch" in splits:
            pp2 = predict(model, x, ed_eval, splits["edges_test_popmatch"])
            m["test_popmatch"] = all_metrics(splits["y_test_popmatch"], pp2)
            sets.append(("test_popmatch", "edges_test_popmatch", "y_test_popmatch", pp2))
    for nm, ek, yk, p in sets:
        e = np.asarray(splits[ek])
        pd.DataFrame({"drug_id": ids_d[e[0]], "disease_id": ids_s[e[1]], "label": np.asarray(splits[yk]).astype(int), "probability": p}).to_csv(
            run_dir / f"{nm}_predictions.csv", index=False)
    pd.DataFrame(hist).to_csv(run_dir / "history.csv", index=False)
    torch.save(model.state_dict(), run_dir / "model.pth")
    (run_dir / "metrics.json").write_text(json.dumps(m, indent=1, default=float), encoding="utf-8")
    (run_dir / "run_config.json").write_text(json.dumps({
        **hp, "split": split_name, "split_file": str(sp_path.relative_to(REPO)), "split_sha256": sha(sp_path), "seed": seed, "git_commit": git_commit(),
        "torch": torch.__version__, "cuda": torch.version.cuda, "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "python": platform.python_version(), "platform": platform.platform(), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model_sha256": sha(run_dir / "model.pth")}, indent=1), encoding="utf-8")
    P(f"DONE {hp['name']} {split_name} s{seed}: val AUC {m['val']['roc_auc']:.4f} AP {m['val']['pr_auc_ap']:.4f}"
      + (f" | popmatch AUC {m['val_popmatch']['roc_auc']:.4f}" if "val_popmatch" in m else "")
      + (f" | test AUC {m.get('historical_test', m.get('test', {})).get('roc_auc', float('nan')):.4f}" if ("historical_test" in m or "test" in m) else "") + f" | best ep {best_ep}/{len(hist)} | {train_s:.0f}s")
    log.close()


def parse():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--splits", nargs="+", required=True)
    ap.add_argument("--seeds", nargs="+", type=int, default=[42])
    ap.add_argument("--out", required=True)
    ap.add_argument("--arch", default="GCN", choices=["GCN", "RGCN"])
    ap.add_argument("--variant", default="original", choices=["original", "mechanism", "train_treats"])
    ap.add_argument("--layers", type=int, default=3)
    ap.add_argument("--emb", type=int, default=64)
    ap.add_argument("--head", type=int, default=32)
    ap.add_argument("--dropout", type=float, default=0.2)
    ap.add_argument("--lr", type=float, default=0.005)
    ap.add_argument("--wd", type=float, default=1e-4)
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--patience", type=int, default=20)
    ap.add_argument("--sched-patience", type=int, default=10)
    ap.add_argument("--resume", action="store_true")
    return ap.parse_args()


def main():
    a = parse()
    if not Path(a.out).parts[0] == "outputs" or "final_audit" not in a.out:
        sys.exit("--out must be under outputs/final_audit_*")
    hp = {k: getattr(a, k) for k in ("name", "arch", "variant", "layers", "emb", "head", "dropout", "lr", "wd", "k", "epochs", "patience", "sched_patience")}
    data = build_hetero_data(REPO / "data/processed/primekg", include_features=True)
    ctx = {"dev": torch.device("cuda" if torch.cuda.is_available() else "cpu"), "data": data,
           "drug_ids": np.asarray(data["drug"].node_ids), "disease_ids": np.asarray(data["disease"].node_ids)}
    out_root = REPO / a.out
    for sp_ in a.splits:
        for s in a.seeds:
            run_one(hp, sp_, s, ctx, out_root, a.resume)


if __name__ == "__main__":
    main()
