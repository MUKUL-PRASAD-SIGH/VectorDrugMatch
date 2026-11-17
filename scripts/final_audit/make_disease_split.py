"""
scripts/final_audit/make_disease_split.py - a DISEASE-disjoint split, mirroring the protocol published methods use (TxGNN's 'complex_disease':
hold out whole diseases and move all of their indications to the test set).

    python scripts/final_audit/make_disease_split.py            # refuses to overwrite

Purpose: VectorDrugMatch's own protocol holds out DRUGS (a new-indication-for-a-known-drug setting). The drug-repurposing literature, including
TxGNN, holds out DISEASES (a zero-shot-disease setting). The two protocols are not comparable, so this file lets the same model be measured on the
other protocol as well. It is a comparison artifact: no model is selected on it, and it is NOT the locked holdout.

Design (deliberately close to the published setting, otherwise identical to `make_final_protocol_split.py`)
  * Universe: diseases with >= 1 PrimeKG indication. 5% go to test, 5% to validation, the rest to train, stratified on (is NTD, indication-count
    bucket), seed 20261118. Every indication of a disease lives in exactly one partition.
  * Negatives: 1:5, drawn per partition from that partition's positive drugs x that partition's positive diseases, never any known drug-disease
    pair of any relation. A popularity-matched negative set is provided as well.
  * `exclude_from_graph_pairs` = all indication pairs of validation + test diseases, removed from contraindication / off-label edges in both
    directions by the trainer (indication edges are never in the message-passing graph).
Output: data/processed/primekg/splits_disease_20261118/{disease_split.npz, manifest.json}
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "final_audit"))
from make_final_protocol_split import pairs_of, popmatch_negatives, sha  # noqa: E402
from src.data.link_prediction_dataset import build_link_prediction_dataset  # noqa: E402

SEED = 20261118
OUT = REPO / "data/processed/primekg/splits_disease_20261118"
NEG_RATIO = 5


def main():
    if OUT.exists() and any(OUT.iterdir()):
        sys.exit(f"{OUT} exists: written once")
    OUT.mkdir(parents=True, exist_ok=True)
    proc = REPO / "data/processed/primekg"
    drugs = pd.read_csv(proc / "drugs.csv", usecols=["drug_id"], dtype=str)
    dis = pd.read_csv(proc / "diseases.csv", dtype=str, low_memory=False)
    edges = pd.read_csv(proc / "edges.csv", usecols=["source_id", "target_id", "relation"], dtype=str)
    dmap = {d: i for i, d in enumerate(drugs.drug_id)}
    smap = {d: i for i, d in enumerate(dis.disease_id)}
    n_drug, n_dis = len(drugs), len(dis)
    is_ntd = dis.is_ntd.astype(int).values
    ind, con, off = (pairs_of(edges, r, dmap, smap) for r in ("CtD", "PK_contra", "PK_offlabel"))
    known = np.concatenate([ind, con, off], 1)
    known_keys = set((known[0] * n_dis + known[1]).tolist())

    pos_dis = np.unique(ind[1])
    cnt = pd.Series(ind[1]).value_counts().reindex(pos_dis).values
    bucket = np.digitize(np.asarray(cnt), [2, 4, 9])
    strata = is_ntd[pos_dis] * 10 + bucket
    train_d, rest = train_test_split(pos_dis, test_size=0.10, random_state=SEED, stratify=strata)
    rest_strata = strata[np.isin(pos_dis, rest)]
    rest_sorted = pos_dis[np.isin(pos_dis, rest)]
    try:
        val_d, test_d = train_test_split(rest_sorted, test_size=0.5, random_state=SEED, stratify=rest_strata)
        stratified_val_test = True
    except ValueError:                                    # some stratum has a single member in the 10% remainder
        val_d, test_d = train_test_split(rest_sorted, test_size=0.5, random_state=SEED)
        stratified_val_test = False
    assert not (set(train_d) & set(val_d)) and not (set(train_d) & set(test_d)) and not (set(val_d) & set(test_d))

    arrays, info = {}, {}
    for nm, dd in (("train", train_d), ("val", val_d), ("test", test_d)):
        p = ind[:, np.isin(ind[1], dd)]
        r = build_link_prediction_dataset(p[0], p[1], n_drug, n_dis, neg_ratio=NEG_RATIO, seed=SEED + len(nm), strategy="hard",
                                          forbid_pairs=(known[0], known[1]))
        arrays[f"edges_{nm}"], arrays[f"y_{nm}"] = r.edge_index.astype(np.int64), r.labels.astype(np.int8)
        e2, y2 = popmatch_negatives(p, n_drug, n_dis, known_keys, np.random.default_rng(SEED + 7 + len(nm)))
        arrays[f"edges_{nm}_popmatch"], arrays[f"y_{nm}_popmatch"] = e2, y2
        arrays[f"diseases_{nm}"] = np.sort(dd).astype(np.int64)
        arrays[f"drugs_{nm}"] = np.unique(p[0]).astype(np.int64)
        neg = r.edge_index[:, r.labels == 0]
        assert not np.isin(neg[0].astype(np.int64) * n_dis + neg[1], known[0] * n_dis + known[1]).any()
        info[nm] = {"diseases": int(len(dd)), "positives": int(r.labels.sum()), "negatives": int((r.labels == 0).sum()),
                    "distinct_drugs": int(len(np.unique(p[0]))), "ntd_positive_pairs": int(is_ntd[p[1]].sum())}
    excl = ind[:, np.isin(ind[1], np.concatenate([val_d, test_d]))]
    arrays["exclude_from_graph_pairs"] = excl.astype(np.int64)
    # the trainer expects drugs_train / drugs_val keys for its audit; diseases are the held-out unit here
    arrays["drugs_val"] = arrays["drugs_val"]
    f = OUT / "disease_split.npz"
    np.savez_compressed(f, **arrays)
    man = {"protocol": "disease_disjoint_comparison_20261118", "seed": SEED, "neg_ratio": NEG_RATIO,
           "purpose": "measure VectorDrugMatch under the zero-shot-DISEASE protocol used by published methods (e.g. TxGNN 'complex_disease'); "
                      "not the locked holdout, no model is selected on it",
           "stratification": "is_ntd x indication-count bucket (1|2-3|4-8|9+)", "val_test_stratified": stratified_val_test, "splits": info, "file_sha256": sha(f),
           "excluded_graph_pairs": int(excl.shape[1]),
           "caveat": "drug sets OVERLAP across partitions by construction (diseases are the held-out unit), so these numbers are not comparable "
                     "with the drug-disjoint results and must never be mixed with them"}
    (OUT / "manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
    print(json.dumps(man, indent=1))


if __name__ == "__main__":
    main()
