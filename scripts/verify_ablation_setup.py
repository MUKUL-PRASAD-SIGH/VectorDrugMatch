"""
scripts/verify_ablation_setup.py - pre-run verification of the treats-edge ablation on the REAL split (CPU; builds graphs and masks, initialises models, no training).

    python scripts/verify_ablation_setup.py [--epochs 3] [--seeds 21 42]

Checks (each prints PASS/FAIL and the numbers; results are written to reports/treats_edge_ablation_20261111/verification_pre_run.json):
 1. A_k4 and B_k4 receive identical fold assignments, supervised pairs, labels, negatives, initial weights and evaluation pairs; the only difference is the edge dict.
 2. In every training step of B, each supervised positive edge and its reverse are absent from that step's graph.
 3. Validation/test positives and their reverse edges are absent from every message-passing graph (evaluation graph and every masked step graph), all configurations.
 4. Alternate representations: which edge types join drug and disease nodes, whether other relations connect drugs to drugs, whether held-out drugs carry any train treats edge,
    and how many contraindication/off-label edges of held-out drugs remain (documented residual side information, identical in A and B).
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from src.data.dataset import build_message_passing_graph, set_seeds  # noqa: E402
from src.data.graph_builder import build_hetero_data  # noqa: E402
from src.data.treats_edges import REV, TARGET, build_variant_edges, make_folds, supervision_view, train_positive_pairs  # noqa: E402
from src.models.gnn.base import GNNLinkPredictionModel  # noqa: E402
from src.models.gnn.gcn import create_gcn_model  # noqa: E402

from scripts.run_treats_edge_ablation import CONFIGS, make_model  # noqa: E402


def keys(ei, n2):
    e = np.asarray(ei)
    return e[0].astype(np.int64) * n2 + e[1].astype(np.int64) if e.size else np.zeros(0, np.int64)


def sha(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--seeds", nargs="+", type=int, default=[21, 42])
    a = ap.parse_args()
    raw = np.load(REPO / "data/processed/primekg/splits/seed42.npz", allow_pickle=True)
    S = {k: raw[k] for k in raw.files}
    data = build_hetero_data(REPO / "data/processed/primekg", include_features=True)
    base = build_message_passing_graph(data, "data/processed/primekg/splits/seed42.npz")
    n2 = data["disease"].num_nodes
    held = keys(S["heldout_indication_pairs"], n2)
    x = {t: data[t].x.float() for t in data.node_types}
    pos = torch.as_tensor(train_positive_pairs(S))
    pos_rows = np.where(S["y_train"].astype(bool))[0]
    of = {int(r): j for j, r in enumerate(pos_rows)}
    rep = {}

    # ---- 1. identical folds / targets / negatives / init / evaluation pairs for A_k4 and B_k4
    c1 = {}
    for seed in a.seeds:
        seqs = {}
        for cfg in ("A_k4", "B_k4"):
            rng = np.random.default_rng(seed)                       # exactly how run_one seeds the fold generator
            seqs[cfg] = [make_folds(pos.shape[1], S["y_train"], CONFIGS[cfg]["k"], rng) for _ in range(a.epochs)]
        same_folds = all(np.array_equal(f1, f2) for e1, e2 in zip(seqs["A_k4"], seqs["B_k4"]) for f1, f2 in zip(e1, e2))
        cover = all(sorted(np.concatenate(ep).tolist()) == list(range(len(S["y_train"]))) for ep in seqs["B_k4"])
        inits = {}
        for cfg in ("A_orig", "A_k4", "B_k4"):
            m = make_model(CONFIGS[cfg], data, base, S, x, torch.as_tensor(S["edges_train"], dtype=torch.long), seed, torch.device("cpu"))
            h = hashlib.sha256()
            for k, v in m.state_dict().items():
                h.update(k.encode()); h.update(v.detach().numpy().tobytes())
            inits[cfg] = h.hexdigest()[:16]
        c1[f"seed{seed}"] = {"fold_sequences_identical_A_k4_vs_B_k4": bool(same_folds), "folds_partition_all_train_pairs_every_epoch": bool(cover),
                             "initial_weights_hash": inits, "initial_weights_identical": len(set(inits.values())) == 1}
    c1["negatives_and_pairs"] = {"train_pairs_hash": sha(S["edges_train"]), "train_labels_hash": sha(S["y_train"]), "val_pairs_hash": sha(S["edges_val"]), "test_pairs_hash": sha(S["edges_test"]),
                                 "note": "all configurations read these arrays from the one saved split; no negative is resampled"}
    c1["pass"] = all(v["fold_sequences_identical_A_k4_vs_B_k4"] and v["folds_partition_all_train_pairs_every_epoch"] and v["initial_weights_identical"] for k, v in c1.items() if k.startswith("seed"))
    rep["1_A_k4_vs_B_k4_identical_except_edges"] = c1

    # ---- 2. supervised positives and reverse hidden in every masked step (B configs)
    ed_B = build_variant_edges(base, S, "train_treats")
    viol, steps, min_vis, max_vis = 0, 0, 10 ** 9, 0
    for k in (2, 4, 8):
        for seed in a.seeds:
            rng = np.random.default_rng(seed)
            for _ in range(a.epochs):
                for f in make_folds(pos.shape[1], S["y_train"], k, rng):
                    sup = torch.as_tensor([of[int(i)] for i in f if int(i) in of], dtype=torch.long)
                    v = supervision_view(ed_B, pos, sup)
                    sk = keys(pos[:, sup].numpy(), n2)
                    viol += int(np.isin(keys(v[TARGET].numpy(), n2), sk).sum()) + int(np.isin(keys(v[REV].flip(0).numpy(), n2), sk).sum())
                    assert v[TARGET].shape[1] == pos.shape[1] - len(sup) == v[REV].shape[1]
                    min_vis, max_vis, steps = min(min_vis, v[TARGET].shape[1]), max(max_vis, v[TARGET].shape[1]), steps + 1
    rep["2_supervised_edges_and_reverse_hidden"] = {"pass": viol == 0, "steps_checked": steps, "violations": viol, "visible_train_treats_edges_per_step_range": [min_vis, max_vis], "train_positives_total": int(pos.shape[1])}

    # ---- 3. held-out positives and reverses absent from every message-passing graph (evaluation graph and every masked step graph)
    det, ok3 = {}, True
    for cfg, c in CONFIGS.items():
        ed = build_variant_edges(base, S, c["variant"])
        graphs = [("eval", ed)]
        if c["mask"]:
            rng = np.random.default_rng(a.seeds[0])
            for f in make_folds(pos.shape[1], S["y_train"], c["k"], rng):
                sup = torch.as_tensor([of[int(i)] for i in f if int(i) in of], dtype=torch.long)
                graphs.append(("step", supervision_view(ed, pos, sup)))
        n_hit = 0
        for _, g in graphs:
            for rel in ("treats", "contraindicated_for", "offlabel_for"):
                for et, flip in ((("drug", rel, "disease"), False), (("disease", f"rev_{rel}", "drug"), True)):
                    if et in g and g[et].numel():
                        e = g[et].flip(0).numpy() if flip else g[et].numpy()
                        n_hit += int(np.isin(keys(e, n2), held).sum())
        det[cfg] = {"graphs_checked": len(graphs), "heldout_pair_occurrences": n_hit}
        ok3 &= n_hit == 0
    rep["3_heldout_absent_from_every_message_passing_graph"] = {"pass": bool(ok3), "per_config": det, "heldout_pairs": int(held.size)}

    # ---- 4. alternate / duplicate representations
    full = data
    dd = [list(et) for et in full.edge_types if {et[0], et[2]} == {"drug", "disease"}]
    drug_drug = [list(et) for et in full.edge_types if et[0] == "drug" and et[2] == "drug"]
    drugs_ho = set(S["drugs_val"].tolist()) | set(S["drugs_test"].tolist())
    train_treats_drugs = set(ed_B[TARGET][0].numpy().tolist())
    ho_contra = {}
    for rel in ("contraindicated_for", "offlabel_for"):
        et = ("drug", rel, "disease")
        e = base[et].edge_index.numpy()
        ho_contra[rel] = {"edges_of_val_test_drugs_remaining_in_message_passing": int(np.isin(e[0], list(drugs_ho)).sum()), "edges_total": int(e.shape[1])}
    id_dup = {t: int(len(data[t].node_ids) - len(set(data[t].node_ids))) for t in ("drug", "disease")}
    rep["4_alternate_representations"] = {
        "edge_types_joining_drug_and_disease": dd, "drug_drug_edge_types": drug_drug, "heldout_drugs_with_a_train_treats_edge": len(drugs_ho & train_treats_drugs),
        "duplicate_node_ids_drug_disease": id_dup, "val_test_drug_label_bearing_edges_still_in_all_configs_except_C": ho_contra,
        "pass": bool(len(drugs_ho & train_treats_drugs) == 0 and not drug_drug and all(sorted(e[1].replace('rev_', '') for e in dd) == sorted(['treats', 'treats', 'contraindicated_for', 'contraindicated_for', 'offlabel_for', 'offlabel_for']) for _ in [0])),
        "note": "Only treats, contraindicated_for and offlabel_for join drugs to diseases. Contraindication/off-label edges of held-out drugs to OTHER diseases stay in the graph in A, B and the 3-layer pairs (existing design; "
                "identical across A and B, so it cannot explain a difference between them); they are removed only in C."}
    rep["all_pass"] = all(v["pass"] for v in rep.values() if isinstance(v, dict) and "pass" in v)
    out = REPO / "reports/treats_edge_ablation_20261111/verification_pre_run.json"
    out.write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    for k, v in rep.items():
        if isinstance(v, dict):
            print(f"[{'PASS' if v['pass'] else 'FAIL'}] {k}")
    print("ALL PASS" if rep["all_pass"] else "SOME CHECK FAILED")
    print(json.dumps({k: rep[k] for k in list(rep)[:-1]}, indent=1, default=str)[:3500])


if __name__ == "__main__":
    main()
