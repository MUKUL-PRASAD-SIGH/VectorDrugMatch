"""
scripts/final_audit/export_bundle.py - package a trained model as a self-contained, checksummed serving bundle (CPU, no torch / PyG needed to serve).

    # the frozen, selected model (after scripts/final_audit/select_dev.py freeze)
    python scripts/final_audit/export_bundle.py --selection reports/final_audit_20261117/FROZEN_SELECTION.json --version vdm-1.0.0
    # anything else is PROVISIONAL (testing the service only; the API reports the status on every response)
    python scripts/final_audit/export_bundle.py --provisional --kind rankavg --gcn-runs <run_dir> ... --gbm <model.joblib> --version vdm-0.0.0-provisional

Bundle layout (<out>/<version>/):
  manifest.json        version, status, kind, components, hyper-parameters, git commit, selection file hash, SHA-256 of every file, parity checks
  ids.npz              drug / disease ids and names (PrimeKG order = model index order)
  known_pairs.npz      PrimeKG indication / contraindication / off-label pairs (annotation only; never model input beyond what training used)
  graph.npz            leakage-safe message-passing matrices of the TRAINING graph (exact training transformation) + training pairs/labels
  fingerprints.npz     packed Morgan bits
  gcn_seed<s>.npz      final-layer drug / disease embeddings (eval mode) + link-predictor weights; scored in numpy (parity vs torch recorded)
  gbm.joblib           HistGradientBoosting model on src/features/simple_baselines.py groups
  reference.npz        component scores on the final_train internal-validation pairs: the percentile reference for the ranking score
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import scipy.sparse as sp
import torch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "final_audit"))
from src.data.graph_builder import build_hetero_data  # noqa: E402
from src.features.simple_baselines import GROUPS, PairFeaturizer, design, feature_matrices  # noqa: E402
from src.serving.scoring import GBM_GROUP, gcn_head_numpy  # noqa: E402
from train_gcn_protocol import graph_edges, load_split, make_model, mp_graph  # noqa: E402


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def export_gcn(run_dir, data, out, idx):
    rc = json.loads((run_dir / "run_config.json").read_text())
    z, _ = load_split(rc["split"])
    hp = {k: rc[k] for k in ("name", "arch", "variant", "layers", "emb", "head", "dropout", "lr", "wd", "k", "epochs", "patience", "sched_patience")}
    dev = torch.device("cpu")
    ed = graph_edges(data, z, hp["variant"])
    x = {t: data[t].x.float() for t in data.node_types}
    model = make_model(hp, data, graph_edges(data, z, "original"), x, torch.as_tensor(z["edges_train"]), rc["seed"], dev)
    model.load_state_dict(torch.load(run_dir / "model.pth", map_location="cpu"))
    model.eval()
    with torch.no_grad():
        zd = model.gnn(x, ed)
        emb_d, emb_s = zd["drug"].numpy(), zd["disease"].numpy()
        W = {"W1": model.predictor.lin1.weight.numpy(), "b1": model.predictor.lin1.bias.numpy(), "W2": model.predictor.lin2.weight.numpy(), "b2": model.predictor.lin2.bias.numpy()}
        rng = np.random.default_rng(0)
        pairs = np.stack([rng.integers(0, emb_d.shape[0], 3000), rng.integers(0, emb_s.shape[0], 3000)])
        p_torch = torch.sigmoid(model.forward_logits(x, ed, torch.as_tensor(pairs))).numpy()
    p_np = gcn_head_numpy(emb_d, emb_s, W, pairs[0], pairs[1])
    parity = float(np.abs(p_torch - p_np).max())
    assert parity < 1e-4, f"numpy head differs from torch: {parity}"
    f = out / f"gcn_seed{rc['seed']}.npz"
    np.savez_compressed(f, emb_drug=emb_d.astype(np.float32), emb_disease=emb_s.astype(np.float32), **W)
    return {"file": f.name, "run_dir": str(run_dir.relative_to(REPO)), "seed": rc["seed"], "split": rc["split"], "split_sha256": rc["split_sha256"],
            "model_pth_sha256": sha(run_dir / "model.pth"), "hp": hp, "train_git_commit": rc.get("git_commit"), "gpu": rc.get("gpu"),
            "numpy_vs_torch_max_abs_diff": parity}, z


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selection")
    ap.add_argument("--provisional", action="store_true")
    ap.add_argument("--kind", choices=["gcn", "gbm", "rankavg"])
    ap.add_argument("--gcn-runs", nargs="*", default=[])
    ap.add_argument("--gbm")
    ap.add_argument("--version", required=True)
    ap.add_argument("--out", default="outputs/final_audit_20261117/bundles")
    a = ap.parse_args()
    sel = None
    if a.selection:
        sel = json.loads((REPO / a.selection).read_text())
        m = sel["selected_model"]
        kind = "rankavg" if m.startswith("rankavg[") else ("gbm" if m == "deg_conn_fp_gbm" else "gcn")
        gcn_runs = sorted({str(Path(p).parent) for p in sel["gcn_final_checkpoints"]}) if kind in ("gcn", "rankavg") else []
        gbm_path = sel["gbm_final_model"] if kind in ("gbm", "rankavg") else None
        status = "FROZEN"
    elif a.provisional:
        kind, gcn_runs, gbm_path, status = a.kind, a.gcn_runs, a.gbm, "PROVISIONAL"
    else:
        sys.exit("give --selection (frozen) or --provisional")
    out = REPO / a.out / a.version
    if out.exists():
        sys.exit(f"{out} exists: bundles are immutable; use a new --version")
    out.mkdir(parents=True)
    data = build_hetero_data(REPO / "data/processed/primekg", include_features=True)
    comps, z = [], None
    for r in gcn_runs:
        info, z_r = export_gcn(REPO / r, data, out, len(comps))
        if z is not None:
            assert (z_r["edges_train"] == z["edges_train"]).all(), "GCN seeds trained on different splits"
        z = z_r
        comps.append({"type": "gcn", **info})
    if gbm_path:
        gp = REPO / gbm_path
        split_name = gp.parts[-3]
        z_g, _ = load_split(split_name)
        if z is not None:
            assert (z_g["edges_train"] == z["edges_train"]).all(), "GBM and GCN trained on different splits"
        z = z_g
        shutil.copy2(gp, out / "gbm.joblib")
        comps.append({"type": "gbm", "file": "gbm.joblib", "source": gbm_path, "split": split_name, "group": GBM_GROUP})
    fp = data["drug"].x.numpy().astype(np.uint8)
    F = PairFeaturizer(mp_graph(data, z), z["edges_train"], z["y_train"], fp)
    mats = F.matrices()
    np.savez_compressed(out / "graph.npz", train_edges=z["edges_train"], train_y=z["y_train"], train_drugs=z["drugs_train"],
                        **{f"{k}_{a_}": getattr(m.tocsr(), a_) for k, m in mats.items() for a_ in ("data", "indices", "indptr")},
                        **{f"{k}_shape": np.array(m.shape) for k, m in mats.items()})
    np.savez_compressed(out / "fingerprints.npz", packed=np.packbits(fp, axis=1), n_bits=np.array(fp.shape[1]))
    drugs = pd.read_csv(REPO / "data/processed/primekg/drugs.csv", dtype=str)
    dis = pd.read_csv(REPO / "data/processed/primekg/diseases.csv", dtype=str, low_memory=False)
    assert list(drugs.drug_id) == list(data["drug"].node_ids) and list(dis.disease_id) == list(data["disease"].node_ids)
    genes = pd.read_csv(REPO / "data/processed/primekg/genes.csv", dtype=str)
    np.savez_compressed(out / "ids.npz", drug_id=drugs.drug_id.values.astype(str), drug_name=drugs.name.fillna("").values.astype(str),
                        disease_id=dis.disease_id.values.astype(str), disease_name=dis.disease_name.fillna("").values.astype(str),
                        gene_symbol=genes.gene_symbol.fillna(genes.gene_id).values.astype(str), is_ntd=dis.is_ntd.astype(int).values)
    kp = {r: data[("drug", r, "disease")].edge_index.numpy() for r in ("treats", "contraindicated_for", "offlabel_for")}
    np.savez_compressed(out / "known_pairs.npz", **kp)
    # percentile reference: component scores on the final_train internal-validation pairs (never the holdout)
    from src.serving.scoring import Scorer
    ref_e = z["edges_val"]
    tmp = {"kind": kind, "components": comps}
    (out / "manifest.json").write_text(json.dumps(tmp), encoding="utf-8")
    sc = Scorer(out, verify=False, reference=False)
    raw = sc.component_scores(ref_e[0], ref_e[1])
    np.savez_compressed(out / "reference.npz", **{k: np.sort(v) for k, v in raw.items()}, labels=z["y_val"])
    files = {p.name: sha(p) for p in sorted(out.iterdir()) if p.name != "manifest.json"}
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "src", "scripts"], cwd=REPO, capture_output=True, text=True).stdout.strip())
    manifest = {"bundle_version": a.version, "status": status, "kind": kind, "components": comps, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "export_git_commit": git, "export_tree_dirty": dirty, "selection_file": a.selection, "selection_sha256": sha(REPO / a.selection) if a.selection else None,
                "selected_model": sel["selected_model"] if sel else None, "files_sha256": files,
                "score_definition": ("ranking_score = mean over components of the component's percentile among the final_train internal-validation pairs "
                                     "(sampled negatives, 1:5); gcn component = mean probability over seeds. A relative ranking score, NOT a probability of efficacy."),
                "intended_use": "research-grade computational prioritisation of drug-disease indication hypotheses for expert review; not for clinical decisions",
                "holdout_metrics": None}
    if status != "FROZEN":
        manifest["warning"] = "PROVISIONAL bundle for service testing only: not a selected or validated model."
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("bundle_version", "status", "kind", "files_sha256")}, indent=1))


if __name__ == "__main__":
    main()
