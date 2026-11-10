"""
src/features/disease_profile.py - leak-free disease-profile block for the classical baselines (optional variant "drug + disease profile").

Motivation: the PrimeKG disease features are one informative flag (is_ntd) plus constant columns, so the classical baselines see only the
drug. This block describes each candidate pair through what is already known about the DISEASE from TRAINING indications only:
the training drugs that treat it ("profile drugs") and how similar the candidate drug's structure is to them.

For a pair (drug d, disease s), with P(s) = { training-positive drugs of s } minus { d }:
  dp_log_train_degree  log(1 + |P(s)|)                       how many OTHER training drugs are known to treat s
  dp_max_tanimoto      max over p in P(s) of Tanimoto(fp_d, fp_p)   (0 if P(s) is empty or fp_d is all-zero)
  dp_mean_tanimoto     mean over p in P(s) of Tanimoto(fp_d, fp_p)  (0 in the same cases)
  dp_has_profile       1 if |P(s)| > 0 and fp_d has at least one bit, else 0 (distinguishes "no evidence" from "dissimilar")

Leakage control (enforced by tests/test_disease_profile.py):
  * the function receives ONLY the training edges/labels (never val/test edges, held-out pairs, or any graph relation, so reverse or
    alternative relations cannot enter), plus the drug fingerprints;
  * leave-one-out: a training positive (d, s) never sees itself in P(s), so its own label is not in its own feature; val/test drugs are
    absent from the training edges (drug-disjoint split), so their features use the full training profile and nothing else;
  * the features of any row are unchanged if val/test labels or edges are changed (tested).
Residual limitation: training-side degree is a popularity signal; it describes the training distribution and is evaluated only on held-out drugs.
"""
import numpy as np

NAMES = ["dp_log_train_degree", "dp_max_tanimoto", "dp_mean_tanimoto", "dp_has_profile"]


def _tanimoto(a, b):
    """a: (n, bits) binary, b: (m, bits) binary -> (n, m) Tanimoto; 0 where both vectors are empty."""
    a, b = a.astype(np.float32), b.astype(np.float32)
    inter = a @ b.T
    union = a.sum(1)[:, None] + b.sum(1)[None, :] - inter
    return np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)


def build_disease_profile_block(drug_fp, train_edges, train_y, query_edges):
    """drug_fp (n_drugs, bits) binary; train_edges (2, N) [drug_idx, disease_idx]; train_y (N,) labels; query_edges (2, M).

    Only the positive training pairs define the profile. Returns (M, 4) float32 in the order of NAMES.
    """
    train_edges, train_y, query_edges = np.asarray(train_edges), np.asarray(train_y), np.asarray(query_edges)
    pos = train_edges[:, train_y == 1]
    profile = {}
    for d, s in zip(pos[0].tolist(), pos[1].tolist()):
        profile.setdefault(s, set()).add(d)
    out = np.zeros((query_edges.shape[1], len(NAMES)), dtype=np.float32)
    by_dis = {}
    for row, s in enumerate(query_edges[1].tolist()):
        by_dis.setdefault(s, []).append(row)
    for s, rows in by_dis.items():
        members = np.array(sorted(profile.get(s, ())), dtype=np.int64)
        rows = np.array(rows)
        qd = query_edges[0][rows]
        if len(members) == 0:
            continue                                                             # no evidence: degree 0, similarities 0, has_profile 0
        sim = _tanimoto(drug_fp[qd], drug_fp[members])
        self_mask = qd[:, None] == members[None, :]                              # leave-one-out
        valid = ~self_mask
        n_other = valid.sum(1)
        simv = np.where(valid, sim, -1.0)
        mx = simv.max(1)
        mean = np.where(valid, sim, 0.0).sum(1) / np.maximum(n_other, 1)
        nonempty = drug_fp[qd].sum(1) > 0
        has = (n_other > 0) & nonempty
        out[rows, 0] = np.log1p(n_other)
        out[rows, 1] = np.where(has, np.maximum(mx, 0.0), 0.0)
        out[rows, 2] = np.where(has, mean, 0.0)
        out[rows, 3] = has.astype(np.float32)
    return out
