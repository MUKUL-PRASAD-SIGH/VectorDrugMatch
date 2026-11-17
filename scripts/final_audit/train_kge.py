"""
scripts/final_audit/train_kge.py - published-baseline comparison: KG-embedding models (TransE, DistMult, ComplEx, RotatE) on the SAME splits,
the SAME leakage-safe graph and the SAME candidate pairs as VectorDrugMatch.

    python scripts/final_audit/train_kge.py --models TransE DistMult ComplEx RotatE --splits cv_fold0 ... --seeds 42 --out outputs/final_audit_20261117/kge
    python scripts/final_audit/train_kge.py --models RotatE --splits final_train --seeds 21 42 52 --eval-holdout --out outputs/final_audit_20261117/kge

POST-HOC COMPARISON. The VectorDrugMatch model was selected and frozen before these runs (reports/.../FROZEN_SELECTION.json); nothing here changes
that selection, and no KGE result is used to pick a deployed model.

Protocol
  * Training triples = the leakage-safe message-passing graph (no indication edges; contraindication / off-label edges of held-out pairs removed,
    exactly as for the GCN) PLUS the split's TRAINING indication edges, which KGE needs in order to learn the target relation embedding.
    Held-out (validation / holdout) indication pairs are never training triples - asserted by the audit written with every run.
  * Negatives during training are type-correct (a disease is corrupted by a disease, etc.); for the indication relation they are additionally
    filtered against every known drug-disease pair of any relation, matching the split protocol.
  * Checkpoint selection: best validation ROC-AUC on the split's validation pairs, patience in evaluations - the same policy as the GCN.
    Hyper-parameters are fixed a priori and identical for the four models (dim 128 = the deployed GCN's width, gamma 12, 64 negatives,
    self-adversarial alpha 1.0, Adam lr 2e-3, batch 8192, budget 12,000 steps = about 200 passes over the training triples, with early
    stopping on validation ROC-AUC). The budget was set from a CPU pilot (DistMult, cv_fold0) in which validation ROC-AUC was still rising at
    1,000 steps of batch 1024, i.e. these models need far more optimisation than the GCN; the pilot log is in the comparison report.
  * Structure-only by construction: no chemical fingerprints (unlike the GCN), which is inherent to this model class.

Outputs per run: <out>/<model>/<split>/seed<seed>/{metrics.json, val_predictions.csv, val_popmatch_predictions.csv,
[holdout_predictions.csv, holdout_popmatch_predictions.csv], history.csv, leakage_audit.json, run_config.json, model.pt}
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
from sklearn.metrics import roc_auc_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "final_audit"))
from src.data.graph_builder import build_hetero_data  # noqa: E402
from src.models.kge import MODELS, KGEModel  # noqa: E402
from src.utils.final_metrics import all_metrics  # noqa: E402
from train_gcn_protocol import load_split, mp_graph  # noqa: E402

TARGET_REL = "indication"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    except Exception:
        return None


def build_triples(data, splits):
    """-> (triples (N,3) int64, relation names, type ranges, n_entity). Entity ids: drugs | diseases | genes."""
    mp = mp_graph(data, splits)
    n_dr, n_di, n_ge = data["drug"].num_nodes, data["disease"].num_nodes, data["gene"].num_nodes
    off = {"drug": 0, "disease": n_dr, "gene": n_dr + n_di}
    rng = {"drug": (0, n_dr), "disease": (n_dr, n_dr + n_di), "gene": (n_dr + n_di, n_dr + n_di + n_ge)}
    rels, rows, head_t, tail_t = [], [], [], []
    for et in mp.edge_types:
        s, rel, d = et
        if rel.startswith("rev_"):                                  # forward direction only; direction is carried by the relation embedding
            continue
        ei = mp[et].edge_index.numpy()
        if ei.size == 0:
            continue
        rels.append(rel)
        head_t.append(s)
        tail_t.append(d)
        rows.append(np.stack([ei[0] + off[s], np.full(ei.shape[1], len(rels) - 1), ei[1] + off[d]], 1))
    pos = np.asarray(splits["edges_train"])[:, np.asarray(splits["y_train"]).astype(bool)]
    rels.append(TARGET_REL)
    head_t.append("drug")
    tail_t.append("disease")
    rows.append(np.stack([pos[0] + off["drug"], np.full(pos.shape[1], len(rels) - 1), pos[1] + off["disease"]], 1))
    return np.concatenate(rows).astype(np.int64), rels, head_t, tail_t, rng, off, n_dr + n_di + n_ge


def audit(triples, rels, splits, data, off, eval_sets):
    """Held-out positives must not be training triples; evaluation negatives must not be known pairs."""
    n_di = data["disease"].num_nodes
    t_idx = rels.index(TARGET_REL)
    out = {}
    key = lambda d, s: np.asarray(d, np.int64) * n_di + np.asarray(s, np.int64)  # noqa: E731
    tr = triples[triples[:, 1] == t_idx]
    tr_keys = set(key(tr[:, 0] - off["drug"], tr[:, 2] - off["disease"]).tolist())
    train_pos = np.asarray(splits["edges_train"])[:, np.asarray(splits["y_train"]).astype(bool)]
    out["target_triples_equal_train_positives"] = {"pass": bool(tr_keys == set(key(train_pos[0], train_pos[1]).tolist())), "n": len(tr_keys)}
    held = []
    for nm, e, y in eval_sets:
        e, y = np.asarray(e), np.asarray(y).astype(bool)
        held.append(key(e[0][y], e[1][y]))
    held = np.concatenate(held) if held else np.zeros(0, np.int64)
    out["no_heldout_positive_in_training_triples"] = {"pass": bool(not set(held.tolist()) & tr_keys), "n_heldout": int(held.size)}
    # no drug-disease triple of ANY relation covers a held-out positive (contra / off-label already filtered by mp_graph)
    dd = [i for i, r in enumerate(rels) if r in ("contraindicated_for", "offlabel_for", TARGET_REL)]
    m = np.isin(triples[:, 1], dd)
    kk = key(triples[m, 0] - off["drug"], triples[m, 2] - off["disease"])
    out["no_heldout_pair_in_any_drug_disease_triple"] = {"pass": bool(not np.isin(held, kk).any())}
    known = []
    for r in ("treats", "contraindicated_for", "offlabel_for"):
        et = ("drug", r, "disease")
        if et in data.edge_types:
            ei = data[et].edge_index.numpy()
            known.append(key(ei[0], ei[1]))
    known = np.unique(np.concatenate(known))
    negs = {}
    ok = True
    for nm, e, y in eval_sets:
        e, y = np.asarray(e), np.asarray(y).astype(bool)
        hit = int(np.isin(key(e[0][~y], e[1][~y]), known).sum())
        negs[nm] = hit
        ok &= hit == 0
    out["eval_negatives_are_not_known_pairs"] = {"pass": bool(ok), "detail": negs}
    out["all_pass"] = bool(all(v["pass"] for v in out.values() if isinstance(v, dict) and "pass" in v))
    return out


def run_one(model_name, split_name, seed, a, ctx, out_root):
    run_dir = out_root / model_name / split_name / f"seed{seed}"
    if (run_dir / "metrics.json").exists():
        if a.resume:
            print(f"[resume] {model_name} {split_name} seed {seed} done")
            return
        sys.exit(f"{run_dir} already holds results (use --resume)")
    run_dir.mkdir(parents=True, exist_ok=True)
    data, dev = ctx["data"], ctx["dev"]
    splits, sp_path = load_split(split_name)
    triples, rels, head_t, tail_t, rng_t, off, n_ent = build_triples(data, splits)

    eval_sets = [("val", splits["edges_val"], splits["y_val"])]
    for extra in ("val_popmatch", "test", "test_popmatch"):
        if f"edges_{extra}" in splits:
            eval_sets.append((extra, splits[f"edges_{extra}"], splits[f"y_{extra}"]))
    if a.eval_holdout:
        h = np.load(REPO / "data/processed/primekg/splits_final_20261117/holdout_LOCKED.npz")
        eval_sets += [("holdout", h["edges_holdout"], h["y_holdout"]), ("holdout_popmatch", h["edges_holdout_popmatch"], h["y_holdout_popmatch"])]
    au = audit(triples, rels, splits, data, off, eval_sets)
    (run_dir / "leakage_audit.json").write_text(json.dumps(au, indent=1), encoding="utf-8")
    if not au["all_pass"]:
        sys.exit(f"LEAKAGE AUDIT FAILED for {model_name} {split_name} seed {seed}: {json.dumps(au)[:500]}")

    torch.manual_seed(seed)
    np.random.seed(seed)
    model = KGEModel(model_name, n_ent, len(rels), dim=a.dim, gamma=a.gamma).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=a.lr)
    T = torch.as_tensor(triples, device=dev)
    # per-relation tail/head entity ranges for type-correct corruption
    tail_lo = torch.as_tensor([rng_t[t][0] for t in tail_t], device=dev)
    tail_hi = torch.as_tensor([rng_t[t][1] for t in tail_t], device=dev)
    head_lo = torch.as_tensor([rng_t[t][0] for t in head_t], device=dev)
    head_hi = torch.as_tensor([rng_t[t][1] for t in head_t], device=dev)
    n_di = data["disease"].num_nodes
    known_keys = set()
    for r in ("treats", "contraindicated_for", "offlabel_for"):
        et = ("drug", r, "disease")
        if et in data.edge_types:
            ei = data[et].edge_index.numpy()
            known_keys.update((ei[0].astype(np.int64) * n_di + ei[1]).tolist())
    known = torch.zeros(ctx["n_drug"] * n_di, dtype=torch.bool)
    known[torch.as_tensor(sorted(known_keys), dtype=torch.long)] = True
    known = known.to(dev)
    t_idx = rels.index(TARGET_REL)

    def ev(e, y):
        model.eval()
        with torch.no_grad():
            d = torch.as_tensor(np.asarray(e)[0], dtype=torch.long, device=dev)
            s = torch.as_tensor(np.asarray(e)[1], dtype=torch.long, device=dev) + off["disease"]
            r = torch.full_like(d, t_idx)
            sc = torch.cat([model.score(d[i:i + 20000], r[i:i + 20000], s[i:i + 20000]) for i in range(0, len(d), 20000)])
            return torch.sigmoid(sc).float().cpu().numpy()

    n = T.shape[0]
    best, best_state, best_step, bad, hist = -1.0, None, 0, 0, []
    y_va = np.asarray(splits["y_val"]).astype(int)
    t0 = time.time()
    model.train()
    perm = torch.randperm(n, device=dev)
    cur = 0
    for step in range(1, a.steps + 1):
        if cur + a.batch > n:
            perm = torch.randperm(n, device=dev)
            cur = 0
        b = T[perm[cur:cur + a.batch]]
        cur += a.batch
        h, r, t = b[:, 0], b[:, 1], b[:, 2]
        half = b.shape[0] // 2
        nt = (torch.rand(b.shape[0], a.negs, device=dev) * (tail_hi[r] - tail_lo[r]).unsqueeze(1)).long() + tail_lo[r].unsqueeze(1)
        nh = h.unsqueeze(1).expand(-1, a.negs).clone()
        nh[:half] = (torch.rand(half, a.negs, device=dev) * (head_hi[r[:half]] - head_lo[r[:half]]).unsqueeze(1)).long() + head_lo[r[:half]].unsqueeze(1)
        nt[:half] = t[:half].unsqueeze(1)
        tm = r == t_idx                                         # target relation: never sample a known drug-disease pair as a negative
        if tm.any():
            kk = nh[tm] * n_di + (nt[tm] - off["disease"])
            bad_ = known[kk.clamp(0, known.numel() - 1)]
            if bad_.any():
                rr = (torch.rand(int(bad_.sum()), device=dev) * n_di).long() + off["disease"]
                tmp = nt[tm]
                tmp[bad_] = rr
                nt[tm] = tmp
        opt.zero_grad()
        loss = model.loss(h, r, t, nh, nt, alpha=a.alpha)
        loss.backward()
        opt.step()
        if step % a.eval_every == 0 or step == a.steps:
            auc = float(roc_auc_score(y_va, ev(splits["edges_val"], y_va)))
            hist.append({"step": step, "loss": float(loss.item()), "val_roc_auc": auc})
            if auc > best:
                best, best_step, bad = auc, step, 0
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            else:
                bad += 1
            print(f"  {model_name} {split_name} s{seed} step {step:>6} loss {hist[-1]['loss']:.4f} val AUC {auc:.4f}", flush=True)
            model.train()
            if bad >= a.patience:
                print("  early stop")
                break
    train_s = time.time() - t0
    model.load_state_dict(best_state)
    m = {"model": model_name, "split": split_name, "seed": seed, "best_step": best_step, "steps_run": hist[-1]["step"],
         "train_seconds": round(train_s, 1), "n_params": int(sum(p.numel() for p in model.parameters())), "n_triples": int(n), "n_relations": len(rels),
         "relations": rels}
    ids_d, ids_s = ctx["drug_ids"], ctx["disease_ids"]
    for nm, e, y in eval_sets:
        p = ev(e, y)
        y = np.asarray(y).astype(int)
        m[nm] = all_metrics(y, p)
        e = np.asarray(e)
        pd.DataFrame({"drug_id": ids_d[e[0]], "disease_id": ids_s[e[1]], "label": y, "probability": p}).to_csv(run_dir / f"{nm}_predictions.csv", index=False)
    pd.DataFrame(hist).to_csv(run_dir / "history.csv", index=False)
    torch.save(model.state_dict(), run_dir / "model.pt")
    (run_dir / "metrics.json").write_text(json.dumps(m, indent=1, default=float), encoding="utf-8")
    (run_dir / "run_config.json").write_text(json.dumps({
        "kge_model": model_name, "split": split_name, "split_file": str(sp_path.relative_to(REPO)), "split_sha256": sha(sp_path), "seed": seed,
        "dim": a.dim, "gamma": a.gamma, "negs": a.negs, "alpha": a.alpha, "lr": a.lr, "batch": a.batch, "steps": a.steps, "patience": a.patience,
        "eval_every": a.eval_every, "checkpoint": "best validation ROC-AUC", "git_commit": git_commit(), "torch": torch.__version__,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None, "python": platform.python_version(),
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "note": "post-hoc published-baseline comparison; not a deployment candidate"}, indent=1), encoding="utf-8")
    print(f"DONE {model_name} {split_name} s{seed}: val AUC {m['val']['roc_auc']:.4f} AP {m['val']['pr_auc_ap']:.4f}"
          + (f" | holdout AUC {m['holdout']['roc_auc']:.4f} AP {m['holdout']['pr_auc_ap']:.4f}" if "holdout" in m else "") + f" | {train_s:.0f}s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=list(MODELS), choices=list(MODELS))
    ap.add_argument("--splits", nargs="+", required=True)
    ap.add_argument("--seeds", nargs="+", type=int, default=[42])
    ap.add_argument("--out", required=True)
    ap.add_argument("--dim", type=int, default=128)
    ap.add_argument("--gamma", type=float, default=12.0)
    ap.add_argument("--negs", type=int, default=64)
    ap.add_argument("--alpha", type=float, default=1.0)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--batch", type=int, default=8192)
    ap.add_argument("--steps", type=int, default=12000)
    ap.add_argument("--patience", type=int, default=5)
    ap.add_argument("--eval-every", type=int, default=1000)
    ap.add_argument("--eval-holdout", action="store_true", help="also score the locked holdout (post-hoc comparison only; nothing is selected on it)")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    if "final_audit" not in a.out:
        sys.exit("--out must be under outputs/final_audit_*")
    data = build_hetero_data(REPO / "data/processed/primekg", include_features=False)
    ctx = {"dev": torch.device("cuda" if torch.cuda.is_available() else "cpu"), "data": data, "n_drug": data["drug"].num_nodes,
           "drug_ids": np.asarray(data["drug"].node_ids), "disease_ids": np.asarray(data["disease"].node_ids)}
    for mn in a.models:
        for sp in a.splits:
            for s in a.seeds:
                run_one(mn, sp, s, a, ctx, REPO / a.out)


if __name__ == "__main__":
    main()
