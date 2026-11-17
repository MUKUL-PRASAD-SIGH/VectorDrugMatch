"""
scripts/final_audit/make_final_protocol_split.py - the FINAL evaluation protocol (2026-11-17). Written once, before any model selection.

    python scripts/final_audit/make_final_protocol_split.py            # refuses to overwrite an existing protocol

Why: the historical seed-42 test split has been examined by many experiments and is no longer an untouched holdout. It is kept (unchanged) for
historical comparisons only.

Design
  * Universe: every drug with >= 1 PrimeKG indication (CtD). Drugs are the unit: all pairs of a drug live in exactly one partition.
  * Final holdout: 20% of those drugs, stratified on (has an NTD indication, indication-count bucket), seed 20261117. LOCKED: its pairs are written to
    a separate file whose SHA-256 is recorded; scripts/final_audit/evaluate_final_holdout.py refuses to run before a frozen selection exists and
    refuses to run twice.
  * Development: the remaining 80% of drugs, 5 drug-grouped folds (same stratification). CV fold f: train = other 4 folds, val = fold f.
  * Final training split: development drugs, with 10% of them (stratified) as an internal validation set for checkpoint selection / early stopping.
  * Positives = indication pairs of the partition's drugs. Negatives (two candidate sets per evaluation partition, fixed now):
        "hard"     historical protocol: drug uniform over the partition's positive drugs x disease uniform over the partition's positive diseases
                   (5 per positive). Comparable with every historical number.
        "popmatch" drug and disease drawn from the partition's POSITIVE pair multiset marginals (i.e. proportional to their number of positives), so a
                   drug's or disease's popularity carries no label information. Robustness set; predeclared as secondary.
    Every negative avoids ALL known drug-disease pairs of any relation (indication, contraindication, off-label). Sampled negatives are unlabelled
    pairs, not confirmed non-indications.
  * Graph exclusion: for each split file, `exclude_from_graph_pairs` = the indication pairs of every non-training drug (val fold + holdout, or internal
    val + holdout). Trainers remove those pairs from contraindicated_for / offlabel_for (both directions); treats edges are never in the graph.
    Holdout LABELS are needed only to remove holdout pairs from the graph; the holdout negatives and the holdout file are never read by training code.
Outputs: data/processed/primekg/splits_final_20261117/{cv_fold{0-4}.npz, final_train.npz, holdout_LOCKED.npz, protocol_manifest.json}
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, train_test_split

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from src.data.link_prediction_dataset import build_link_prediction_dataset  # noqa: E402

SEED = 20261117
OUT = REPO / "data/processed/primekg/splits_final_20261117"
NEG_RATIO = 5


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def pairs_of(edges, rel, dmap, smap):
    e = edges[edges.relation == rel]
    s, t = e.source_id.map(dmap), e.target_id.map(smap)
    ok = s.notna() & t.notna()
    assert ok.all(), f"unresolvable endpoints in {rel}"
    return np.unique(np.stack([s.astype(np.int64).values, t.astype(np.int64).values]), axis=1)


def popmatch_negatives(pos, n_drug, n_dis, known_keys, rng, ratio=NEG_RATIO):
    """Negatives whose drug and disease marginals equal those of the positives (both drawn from the positive pair multiset)."""
    out, seen = [], set()
    need = ratio * pos.shape[1]
    tries = 0
    while len(out) < need:
        tries += 1
        if tries > need * 200:
            raise RuntimeError("popmatch sampling exhausted")
        i, j = rng.integers(0, pos.shape[1], 2)
        u, v = int(pos[0, i]), int(pos[1, j])
        k = u * n_dis + v
        if k in known_keys or k in seen:
            continue
        seen.add(k)
        out.append((u, v))
    neg = np.array(out, dtype=np.int64).T
    e = np.concatenate([pos, neg], 1)
    y = np.concatenate([np.ones(pos.shape[1], np.int8), np.zeros(neg.shape[1], np.int8)])
    perm = rng.permutation(len(y))
    return e[:, perm], y[perm]


def main():
    if OUT.exists() and any(OUT.iterdir()):
        sys.exit(f"{OUT} exists: the final protocol is written once and never regenerated")
    OUT.mkdir(parents=True)
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

    pos_drugs = np.unique(ind[0])
    cnt = pd.Series(ind[0]).value_counts().reindex(pos_drugs).values
    ntd = np.zeros(n_drug, int)
    ntd[ind[0][is_ntd[ind[1]] == 1]] = 1
    bucket = np.digitize(cnt, [2, 4, 9])                      # 1 | 2-3 | 4-8 | 9+
    strata = ntd[pos_drugs] * 10 + bucket
    dev, hold = train_test_split(pos_drugs, test_size=0.20, random_state=SEED, stratify=strata)
    assert not set(dev) & set(hold)
    st_dev = strata[np.isin(pos_drugs, dev)]
    dev = pos_drugs[np.isin(pos_drugs, dev)]                  # sorted order aligned with st_dev
    folds = [dev[te] for _, te in StratifiedKFold(5, shuffle=True, random_state=SEED).split(dev, st_dev)]
    ft_tr, ft_va = train_test_split(dev, test_size=0.10, random_state=SEED, stratify=st_dev)

    def pos_of(dr):
        return ind[:, np.isin(ind[0], dr)]

    def hard(dr, seed):
        p = pos_of(dr)
        r = build_link_prediction_dataset(p[0], p[1], n_drug, n_dis, neg_ratio=NEG_RATIO, seed=seed, strategy="hard", forbid_pairs=(known[0], known[1]))
        return r.edge_index.astype(np.int64), r.labels.astype(np.int8)

    def pm(dr, seed):
        return popmatch_negatives(pos_of(dr), n_drug, n_dis, known_keys, np.random.default_rng(seed))

    hold_pos = pos_of(hold)
    manifest = {"protocol": "final_audit_20261117", "seed": SEED, "neg_ratio": NEG_RATIO, "n_indication_drugs": int(len(pos_drugs)),
                "n_dev_drugs": int(len(dev)), "n_holdout_drugs": int(len(hold)), "stratification": "has NTD indication x indication-count bucket (1|2-3|4-8|9+)",
                "inputs_sha256": {"edges.csv": sha(proc / "edges.csv"), "drugs.csv": sha(proc / "drugs.csv"), "diseases.csv": sha(proc / "diseases.csv"),
                                  "drug_features.npy": sha(proc / "drug_features.npy")},
                "files": {}}

    def save(name, train_dr, val_dr, seed):
        e_tr, y_tr = hard(train_dr, seed)
        e_va, y_va = hard(val_dr, seed + 1)
        e_vp, y_vp = pm(val_dr, seed + 2)
        excl = np.concatenate([pos_of(val_dr), hold_pos], 1)
        arr = {"edges_train": e_tr, "y_train": y_tr, "edges_val": e_va, "y_val": y_va, "edges_val_popmatch": e_vp, "y_val_popmatch": y_vp,
               "drugs_train": np.sort(train_dr), "drugs_val": np.sort(val_dr), "exclude_from_graph_pairs": excl.astype(np.int64)}
        assert not set(train_dr) & set(val_dr) and not set(train_dr) & set(hold) and not set(val_dr) & set(hold)
        for k in ("train", "val"):
            e, y = arr[f"edges_{k}"], arr[f"y_{k}"]
            assert not np.isin(e[0, y == 0] * n_dis + e[1, y == 0], known[0] * n_dis + known[1]).any()
        p = OUT / f"{name}.npz"
        np.savez_compressed(p, **arr)
        manifest["files"][p.name] = {"sha256": sha(p), "train_drugs": int(len(train_dr)), "val_drugs": int(len(val_dr)),
                                     "train_pos": int(y_tr.sum()), "train_neg": int((y_tr == 0).sum()), "val_pos": int(y_va.sum()), "val_neg": int((y_va == 0).sum()),
                                     "val_popmatch_pos": int(y_vp.sum()), "val_popmatch_neg": int((y_vp == 0).sum()), "excluded_graph_pairs": int(excl.shape[1])}

    for f in range(5):
        tr = np.concatenate([folds[g] for g in range(5) if g != f])
        save(f"cv_fold{f}", tr, folds[f], SEED + 100 * f)
    save("final_train", ft_tr, ft_va, SEED + 1000)
    e_h, y_h = hard(hold, SEED + 2000)
    e_hp, y_hp = pm(hold, SEED + 2001)
    hp = OUT / "holdout_LOCKED.npz"
    np.savez_compressed(hp, edges_holdout=e_h, y_holdout=y_h, edges_holdout_popmatch=e_hp, y_holdout_popmatch=y_hp, drugs_holdout=np.sort(hold),
                        holdout_indication_pairs=hold_pos)
    manifest["holdout"] = {"file": hp.name, "sha256": sha(hp), "drugs": int(len(hold)), "pos": int(y_h.sum()), "neg": int((y_h == 0).sum()),
                           "popmatch_pos": int(y_hp.sum()), "popmatch_neg": int((y_hp == 0).sum()), "ntd_positive_pairs": int(is_ntd[hold_pos[1]].sum()),
                           "status": "LOCKED - evaluate once, only via scripts/final_audit/evaluate_final_holdout.py after selection is frozen"}
    hist = np.load(proc / "splits/seed42.npz")
    manifest["overlap_with_historical_seed42_test_drugs"] = int(len(set(hold) & set(hist["drugs_test"].tolist())))
    manifest["note"] = ("The holdout drugs overlap the historical seed-42 val/test drugs by chance (independent re-partition). Those historical test "
                        "results were seen, but no model trained for the final protocol uses holdout labels; the overlap is reported, not hidden.")
    (OUT / "protocol_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
