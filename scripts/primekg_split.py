"""
scripts/primekg_split.py - Track B step 2: build and SAVE the drug-disjoint train/val/test split.

    python scripts/primekg_split.py --config configs/primekg_morgan.yaml            # seed from config
    python scripts/primekg_split.py --config configs/primekg_morgan.yaml --seed 7   # another seed

Writes  data/processed/<exp>/splits/seed<N>.npz  and  seed<N>.manifest.json  (sizes, hashes, counts).
Every model (baselines, Node2Vec, GNNs) reads this one file, so they see identical pairs and negatives.

Protocol
  * Positives = indication pairs only. Drugs with >=1 indication are split disjointly
    (stratified on "has an NTD indication" when possible so NTD positives reach val/test).
  * Negatives = SAMPLED (hard) pairs, drawn per split from that split's drugs x diseases, never from ANY
    known drug-disease pair of any relation (indication, contraindication, off-label).
  * Curated negatives: PrimeKG has no explicit "not indicated" relation, so there are none; the
    `curated_*` arrays are all False. Contraindications / off-label are NOT used as negatives; they are
    saved as evaluation-only diagnostics (diag_contra_*, diag_offlabel_*) for the split's drugs.
  * Leakage control for graph models: `heldout_indication_pairs` (val+test positives). The message-passing
    graph drops all treats edges (+reverse) and any contra/off-label edge on those pairs
    (see src/data/dataset.py: build_message_passing_graph).
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.model_selection import train_test_split

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from src.data.link_prediction_dataset import build_link_prediction_dataset  # noqa: E402


def h(a: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()[:16]


def pairs_of(edges, rel, dmap, smap):
    e = edges[edges.relation == rel]
    s = e.source_id.map(dmap)
    t = e.target_id.map(smap)
    ok = s.notna() & t.notna()
    arr = np.unique(np.stack([s[ok].astype(np.int64).values, t[ok].astype(np.int64).values]), axis=1)
    return arr, int((~ok).sum())


def split_drugs(drugs, has_ntd, test_frac, val_frac, seed):
    rest = val_frac + test_frac
    try:
        tr, tmp = train_test_split(drugs, test_size=rest, random_state=seed, stratify=has_ntd)
        tmp_ntd = np.isin(tmp, drugs[has_ntd == 1])
        va, te = train_test_split(tmp, test_size=test_frac / rest, random_state=seed, stratify=tmp_ntd)
        return tr, va, te, True
    except ValueError:                                           # too few NTD drugs to stratify
        tr, tmp = train_test_split(drugs, test_size=rest, random_state=seed)
        va, te = train_test_split(tmp, test_size=test_frac / rest, random_state=seed)
        return tr, va, te, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/primekg_morgan.yaml")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--strategy", default="hard", choices=["hard", "random"])
    a = ap.parse_args()
    cfg = yaml.safe_load(open(REPO / a.config))
    ds = cfg.get("dataset", {})
    seed = a.seed if a.seed is not None else ds.get("random_seed", 42)
    neg_ratio, test_frac, val_frac = ds.get("neg_ratio", 5.0), ds.get("test_size", 0.15), ds.get("val_size", 0.15)
    proc = REPO / "data" / "processed" / cfg["experiment"]["name"]

    drugs = pd.read_csv(proc / "drugs.csv", usecols=["drug_id"], dtype=str)
    dis = pd.read_csv(proc / "diseases.csv", dtype=str, low_memory=False)
    edges = pd.read_csv(proc / "edges.csv", usecols=["source_id", "target_id", "relation"], dtype=str)
    dmap = {d: i for i, d in enumerate(drugs.drug_id)}
    smap = {d: i for i, d in enumerate(dis.disease_id)}
    n_drug, n_dis = len(drugs), len(dis)
    is_ntd = dis.is_ntd.astype(int).values
    status = dis.mapping_status.values if "mapping_status" in dis else np.array(["unknown"] * n_dis)

    ind, bad_i = pairs_of(edges, "CtD", dmap, smap)
    con, bad_c = pairs_of(edges, "PK_contra", dmap, smap)
    off, bad_o = pairs_of(edges, "PK_offlabel", dmap, smap)
    if bad_i or bad_c or bad_o:
        sys.exit(f"unresolvable endpoints: ind={bad_i} contra={bad_c} offlabel={bad_o}")
    key = lambda p: set(zip(p[0].tolist(), p[1].tolist()))        # noqa: E731
    k_ind, k_con, k_off = key(ind), key(con), key(off)
    contradictions = {"indication&contraindication": len(k_ind & k_con), "indication&offlabel": len(k_ind & k_off),
                      "contraindication&offlabel": len(k_con & k_off)}
    k_all = k_ind | k_con | k_off
    known = np.concatenate([ind, con, off], axis=1)               # forbidden as sampled negatives

    pos_drugs = np.unique(ind[0])
    drug_has_ntd = np.zeros(n_drug, dtype=int)
    drug_has_ntd[ind[0][is_ntd[ind[1]] == 1]] = 1
    tr_d, va_d, te_d, stratified = split_drugs(pos_drugs, drug_has_ntd[pos_drugs], test_frac, val_frac, seed)
    groups = {"train": tr_d, "val": va_d, "test": te_d}
    assert not (set(tr_d) & set(va_d)) and not (set(tr_d) & set(te_d)) and not (set(va_d) & set(te_d))

    arrays, info = {}, {}
    for sp, dr in groups.items():
        m = np.isin(ind[0], dr)
        ps, pd_ = ind[0][m], ind[1][m]
        res = build_link_prediction_dataset(ps, pd_, n_drug, n_dis, neg_ratio=neg_ratio, seed=seed,
                                            strategy=a.strategy, forbid_pairs=(known[0], known[1]))
        arrays[f"edges_{sp}"] = res.edge_index.astype(np.int64)
        arrays[f"y_{sp}"] = res.labels.astype(np.int8)
        arrays[f"curated_{sp}"] = res.is_curated.astype(bool)
        for nm_, arr in (("contra", con), ("offlabel", off)):
            mm = np.isin(arr[0], dr)
            arrays[f"diag_{nm_}_{sp}"] = arr[:, mm]
        arrays[f"drugs_{sp}"] = np.sort(dr).astype(np.int64)
        y, e = res.labels, res.edge_index
        negs = e[:, y == 0]
        info[sp] = {
            "drugs": int(len(dr)), "positives": int((y == 1).sum()), "negatives": int((y == 0).sum()),
            "curated_negatives": int(res.is_curated.sum()), "sampled_negatives": int(((y == 0) & ~res.is_curated).sum()),
            "ntd_positives": int(is_ntd[pd_].sum()),
            "positive_mapping_status": {k: int(v) for k, v in zip(*np.unique(status[pd_], return_counts=True))},
            "diag_contra_pairs": int(arrays[f"diag_contra_{sp}"].shape[1]),
            "diag_offlabel_pairs": int(arrays[f"diag_offlabel_{sp}"].shape[1]),
            "negatives_in_known_pairs": int(sum((u, v) in k_all
                                                for u, v in zip(negs[0].tolist(), negs[1].tolist()))),
        }
    held = np.concatenate([ind[:, np.isin(ind[0], va_d)], ind[:, np.isin(ind[0], te_d)]], axis=1)
    arrays["heldout_indication_pairs"] = held.astype(np.int64)

    out_dir = proc / "splits"
    out_dir.mkdir(exist_ok=True)
    npz = out_dir / f"seed{seed}.npz"
    np.savez_compressed(npz, **arrays)
    manifest = {
        "seed": seed, "strategy": a.strategy, "neg_ratio": neg_ratio, "test_size": test_frac, "val_size": val_frac,
        "stratified_on_ntd": stratified, "target": "drug->disease indication (CtD)",
        "n_drugs": n_drug, "n_diseases": n_dis,
        "known_pairs": {"indication": len(k_ind), "contraindication": len(k_con), "offlabel": len(k_off)},
        "contradictory_pairs": contradictions, "splits": info,
        "array_hashes": {k: h(v) for k, v in arrays.items()},
        "inputs_sha": {"edges.csv": hashlib.sha256((proc / "edges.csv").read_bytes()).hexdigest()[:16]},
        "note": "PrimeKG has no explicit non-indication relation: no curated negatives. Contra/off-label are diagnostics only.",
    }
    (out_dir / f"seed{seed}.manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps({k: manifest[k] for k in ("seed", "stratified_on_ntd", "contradictory_pairs", "splits")}, indent=2))
    print(f"\nsaved {npz}")


if __name__ == "__main__":
    main()
