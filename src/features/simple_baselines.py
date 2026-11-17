"""
src/features/simple_baselines.py - popularity / connectivity / fingerprint features for the "does the GCN add anything?" baselines (final audit).

Inputs are ONLY (a) the leakage-safe message-passing graph (src.data.dataset.build_message_passing_graph: no treats edges; contra/off-label edges on
held-out indication pairs removed) and (b) TRAINING positive pairs. Nothing reads a validation or test label.

Feature groups (pair = (drug d, disease s)):
  degree       popularity only: log1p of the drug's degree per relation in the MP graph (genes, contraindications, off-label), the disease's degree per
               relation (genes, disease-disease, contra, off-label), and the disease's TRAINING indication count (leave-one-out for training rows:
               a training positive does not count itself).
  connectivity degree + path counts between d and s through the MP graph:
               p_dgs   d -gene- s                         (shared genes)
               p_dggs  d -gene-gene- s
               p_dcs   d -contra- s' -related- s          (drug-disease side information routed through disease-disease)
               p_dos   d -offlabel- s' -related- s
               p_dgdt  d -gene- d' -TRAIN-treats- s, d' != d   (needs training labels; the d'=d term is removed so no row sees its own label)
               p_dss   d -contra/offlabel- s (direct; held-out positives were removed from the graph, kept for completeness)
               reach2/reach3: any path of length <= 2 / <= 3 in the MP graph (undirected, all relations).
  fingerprint  max / mean Morgan Tanimoto of d to the training drugs of s, = src.features.disease_profile.

Label-derived features (training indication degree, p_dgdt, fingerprint profile) for TRAINING rows are CROSS-FITTED by drug (`crossfit_label_features`):
rows of the drugs in fold j use only the training positives of the other folds' drugs. Leave-one-out (the historical disease-profile choice) gives a
training positive a degree one lower than the negatives of the same disease, a train/test shift that a tree model exploits and that does not exist for
held-out drugs (found in this audit: degree-only GBM AUC 0.57 < raw popularity 0.65 on the historical test set). Val/test rows use all training positives.
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from src.features.disease_profile import build_disease_profile_block

DEG_NAMES = ["log_drug_gene_deg", "log_drug_contra_deg", "log_drug_off_deg", "log_dis_gene_deg", "log_dis_dis_deg", "log_dis_contra_deg", "log_dis_off_deg"]
CONN_NAMES = ["log_p_dgs", "log_p_dggs", "log_p_dcs", "log_p_dos", "direct_label_rel", "reach2", "reach3"]
LABEL_NAMES = ["log_dis_train_ind_deg", "log_p_dgdt", "dp_max_tanimoto", "dp_mean_tanimoto", "dp_has_profile"]


def _adj(ei, n0, n1):
    ei = ei.cpu().numpy() if hasattr(ei, "cpu") else np.asarray(ei)
    if ei.size == 0:
        return sp.csr_matrix((n0, n1))
    m = sp.csr_matrix((np.ones(ei.shape[1]), (ei[0], ei[1])), shape=(n0, n1))
    m.data[:] = 1.0
    return m


class PairFeaturizer:
    def __init__(self, mp_graph, train_edges, train_y, drug_fp):
        n_dr, n_di, n_g = mp_graph["drug"].num_nodes, mp_graph["disease"].num_nodes, mp_graph["gene"].num_nodes
        g = lambda et, a, b: _adj(mp_graph[et].edge_index, a, b) if et in mp_graph.edge_types else sp.csr_matrix((a, b))  # noqa: E731
        self.DG = g(("drug", "binds", "gene"), n_dr, n_g)
        self.SG = g(("disease", "associates", "gene"), n_di, n_g)
        GG = g(("gene", "interacts", "gene"), n_g, n_g)
        self.GG = ((GG + GG.T) > 0).astype(float)
        SS = g(("disease", "related_to", "disease"), n_di, n_di)
        self.SS = ((SS + SS.T) > 0).astype(float)
        self.DC = g(("drug", "contraindicated_for", "disease"), n_dr, n_di)
        self.DO = g(("drug", "offlabel_for", "disease"), n_dr, n_di)
        te, ty = np.asarray(train_edges), np.asarray(train_y).astype(bool)
        self.train_edges, self.train_y, self.fp = te, ty, drug_fp
        self.n = (n_dr, n_di, n_g)
        # precomputed products (sparse)
        self.DGG = (self.DG @ self.GG).tocsr()                 # drug -> gene (2 hops)
        DD = (self.DG @ self.DG.T).tocsr()
        DD.setdiag(0)
        DD.eliminate_zeros()
        self.DD = DD
        self.DCS = (self.DC @ self.SS).tocsr()
        self.DOS = (self.DO @ self.SS).tocsr()
        # undirected all-relation adjacency for reachability (drug | disease | gene)
        N = n_dr + n_di + n_g
        blocks = []
        off = {"drug": 0, "disease": n_dr, "gene": n_dr + n_di}
        for M, a, b in ((self.DG, "drug", "gene"), (self.SG, "disease", "gene"), (self.GG, "gene", "gene"), (self.SS, "disease", "disease"),
                        (self.DC, "drug", "disease"), (self.DO, "drug", "disease")):
            c = M.tocoo()
            blocks.append((c.row + off[a], c.col + off[b]))
        r = np.concatenate([b[0] for b in blocks] + [b[1] for b in blocks])
        cc = np.concatenate([b[1] for b in blocks] + [b[0] for b in blocks])
        A = sp.csr_matrix((np.ones(len(r)), (r, cc)), shape=(N, N))
        A.data[:] = 1.0
        self.A, self.off = A, off

    @staticmethod
    def _pick(M, d, s):
        return np.asarray(M[d, s]).ravel()

    def degree(self, edges):
        """graph-only popularity (no labels)."""
        d, s = np.asarray(edges[0]), np.asarray(edges[1])
        cols = [np.asarray(self.DG.sum(1)).ravel()[d], np.asarray(self.DC.sum(1)).ravel()[d], np.asarray(self.DO.sum(1)).ravel()[d],
                np.asarray(self.SG.sum(1)).ravel()[s], np.asarray(self.SS.sum(1)).ravel()[s], np.asarray(self.DC.sum(0)).ravel()[s],
                np.asarray(self.DO.sum(0)).ravel()[s]]
        return np.log1p(np.stack(cols, 1)).astype(np.float32)

    def connectivity(self, edges):
        d, s = np.asarray(edges[0]), np.asarray(edges[1])
        p_dgs = np.asarray(self.DG[d].multiply(self.SG[s]).sum(1)).ravel()
        p_dggs = np.asarray(self.DGG[d].multiply(self.SG[s]).sum(1)).ravel()
        p_dcs, p_dos = self._pick(self.DCS, d, s), self._pick(self.DOS, d, s)
        direct = self._pick(self.DC, d, s) + self._pick(self.DO, d, s)
        # reachability in <= 2 / <= 3 undirected hops
        A = self.A
        u, inv = np.unique(d, return_inverse=True)
        Au = A[u + self.off["drug"]]                                       # 1-hop rows of the unique drugs
        dis_cols = A[:, self.off["disease"]:self.off["disease"] + self.n[1]]
        R1 = Au[:, self.off["disease"]:self.off["disease"] + self.n[1]]
        R2 = (Au @ dis_cols).tocsr()                                       # 2-hop walks drug -> disease
        R3 = ((Au @ A).tocsr() @ dis_cols).tocsr()                         # 3-hop walks drug -> disease
        r1 = np.asarray(R1[inv, s]).ravel() > 0
        r2 = r1 | (np.asarray(R2[inv, s]).ravel() > 0)
        r3 = r2 | (np.asarray(R3[inv, s]).ravel() > 0)
        cols = [np.log1p(p_dgs), np.log1p(p_dggs), np.log1p(p_dcs), np.log1p(p_dos), (direct > 0).astype(float), r2.astype(float), r3.astype(float)]
        return np.stack(cols, 1).astype(np.float32)

    def label_features(self, edges, lab_edges=None, lab_y=None):
        """Features that use training labels, computed from the positives in (lab_edges, lab_y) (default: all training pairs).
        -> (n, 5): log train-indication degree of s, log p_dgdt, max / mean Tanimoto to the profile drugs of s, has_profile."""
        le = self.train_edges if lab_edges is None else np.asarray(lab_edges)
        ly = self.train_y if lab_y is None else np.asarray(lab_y).astype(bool)
        pos = le[:, ly]
        T = sp.csr_matrix((np.ones(pos.shape[1]), (pos[0], pos[1])), shape=(self.n[0], self.n[1]))
        T.data[:] = 1.0
        d, s = np.asarray(edges[0]), np.asarray(edges[1])
        tdeg = np.asarray(T.sum(0)).ravel()[s]
        DGDT = (self.DD @ T).tocsr()
        p_dgdt = self._pick(DGDT, d, s)
        blk = build_disease_profile_block(self.fp, le, ly.astype(int), np.asarray(edges))   # LOO inside is a no-op when d is not a profile drug
        return np.concatenate([np.log1p(np.stack([tdeg, p_dgdt], 1)), blk[:, 1:]], 1).astype(np.float32)

    def crossfit_label_features(self, n_folds=5, seed=0):
        """Label features for the TRAINING rows, cross-fitted by drug (see module docstring)."""
        te, ty = self.train_edges, self.train_y
        drugs = np.unique(te[0])
        rng = np.random.default_rng(seed)
        fold_of = dict(zip(rng.permutation(drugs).tolist(), np.arange(len(drugs)) % n_folds))
        f = np.array([fold_of[int(x)] for x in te[0]])
        out = np.zeros((te.shape[1], 5), np.float32)
        for j in range(n_folds):
            m = f == j
            out[m] = self.label_features(te[:, m], te[:, ~m], ty[~m])
        return out


GROUPS = {   # model name -> (feature blocks, label-feature columns)
    "degree_gbm": (["deg"], [0]),                       # popularity only: graph degrees + training indication count of the disease
    "connectivity_gbm": (["deg", "conn"], [0, 1]),      # + path counts / reachability (incl. d -gene- d' -treats- s)
    "fingerprint_gbm": ([], [0, 2, 3, 4]),              # disease-profile structure similarity (+ disease training degree)
    "deg_conn_fp_gbm": (["deg", "conn"], [0, 1, 2, 3, 4]),
}


def feature_matrices(F, split_edges):
    """split_edges: {'train': edges, other_name: edges, ...} -> {name: {'deg','conn','label'}}; training label features are cross-fitted."""
    out = {}
    for nm, e in split_edges.items():
        lab = F.crossfit_label_features() if nm == "train" else F.label_features(e)
        out[nm] = {"deg": F.degree(e), "conn": F.connectivity(e), "label": lab}
    return out


def design(feats, group):
    blocks, lab_cols = GROUPS[group]
    return np.concatenate([feats[b] for b in blocks] + [feats["label"][:, lab_cols]], 1)
