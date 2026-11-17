"""
src/serving/scoring.py - CPU inference over a bundle written by scripts/final_audit/export_bundle.py (numpy / scipy / scikit-learn only).

The features are produced by the SAME code used in training/evaluation (src/features/simple_baselines.py), rebuilt from the bundle's saved training graph;
GCN scores come from embeddings exported from the trained model (numpy head, parity with torch checked at export).

Output semantics: `ranking_score` in [0, 1] is the mean, over the model's components, of the component score's percentile among the reference pairs
(final_train internal-validation pairs: known indications and SAMPLED unlabelled pairs, 1:5). It ranks candidates; it is not a probability that the
drug treats the disease. Explanations list graph evidence around the pair (shared targets, similar drugs with the indication, related diseases); they
describe what the model could see, not a mechanism or proof.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import scipy.sparse as sp

from src.features.simple_baselines import PairFeaturizer, design

GBM_GROUP = "deg_conn_fp_gbm"


class BundleError(RuntimeError):
    pass


def gcn_head_numpy(emb_d, emb_s, W, d, s):
    z = np.concatenate([emb_d[d], emb_s[s]], axis=1)
    h = np.maximum(z @ W["W1"].T + W["b1"], 0.0)
    logit = (h @ W["W2"].T + W["b2"]).ravel()
    return 1.0 / (1.0 + np.exp(-logit))


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class Scorer:
    def __init__(self, bundle_dir, verify=True, reference=True):
        self.dir = Path(bundle_dir)
        mpath = self.dir / "manifest.json"
        if not mpath.exists():
            raise BundleError(f"no manifest.json in {self.dir}")
        self.manifest = json.loads(mpath.read_text(encoding="utf-8"))
        if verify:
            files = self.manifest.get("files_sha256") or {}
            if not files:
                raise BundleError("manifest has no checksums")
            for name, h in files.items():
                p = self.dir / name
                if not p.exists() or _sha(p) != h:
                    raise BundleError(f"checksum mismatch or missing file: {name}")
        ids = np.load(self.dir / "ids.npz")
        self.drug_ids, self.drug_names = ids["drug_id"], ids["drug_name"]
        self.disease_ids, self.disease_names = ids["disease_id"], ids["disease_name"]
        self.gene_symbols, self.is_ntd = ids["gene_symbol"], ids["is_ntd"]
        self.drug_index = {d: i for i, d in enumerate(self.drug_ids.tolist())}
        self.disease_index = {d: i for i, d in enumerate(self.disease_ids.tolist())}
        self.n_drug, self.n_dis = len(self.drug_ids), len(self.disease_ids)
        kp = np.load(self.dir / "known_pairs.npz")
        self.known = {r: sp.csr_matrix((np.ones(kp[r].shape[1]), (kp[r][0], kp[r][1])), shape=(self.n_drug, self.n_dis)) for r in kp.files}
        g = np.load(self.dir / "graph.npz")
        mats = {k: sp.csr_matrix((g[f"{k}_data"], g[f"{k}_indices"], g[f"{k}_indptr"]), shape=tuple(g[f"{k}_shape"])) for k in PairFeaturizer.MATS}
        f = np.load(self.dir / "fingerprints.npz")
        self.fp = np.unpackbits(f["packed"], axis=1)[:, : int(f["n_bits"])]
        self.train_drugs = set(g["train_drugs"].tolist())
        self.F = PairFeaturizer.from_matrices(mats, g["train_edges"], g["train_y"], self.fp)
        self.F.label_features(np.zeros((2, 1), np.int64))           # builds and caches the training-indication matrix
        self.T = self.F._cache[0]
        self.components = self.manifest["components"]
        self.gcn = [dict(np.load(self.dir / c["file"])) for c in self.components if c["type"] == "gcn"]
        self.gbm = None
        if any(c["type"] == "gbm" for c in self.components):
            import joblib
            self.gbm = joblib.load(self.dir / "gbm.joblib")
        self.ref = None
        if reference:
            r = np.load(self.dir / "reference.npz")
            self.ref = {k: r[k] for k in r.files if k != "labels"}
        self.drug_gene_deg = np.asarray(self.F.DG.sum(1)).ravel()
        self.dis_gene_deg = np.asarray(self.F.SG.sum(1)).ravel()
        self.dis_train_deg = np.asarray(self.T.sum(0)).ravel()
        self.fp_bits = self.fp.sum(1)

    # ----- scoring -----
    def component_scores(self, d, s):
        d, s = np.asarray(d, np.int64), np.asarray(s, np.int64)
        out = {}
        if self.gcn:
            out["gcn"] = np.mean([gcn_head_numpy(g["emb_drug"], g["emb_disease"], {k: g[k] for k in ("W1", "b1", "W2", "b2")}, d, s) for g in self.gcn], axis=0)
        if self.gbm is not None:
            e = np.stack([d, s])
            feats = {"deg": self.F.degree(e), "conn": self.F.connectivity(e), "label": self.F.label_features(e)}
            out["gbm"] = self.gbm.predict_proba(design(feats, GBM_GROUP))[:, 1]
        return out

    def score(self, d, s):
        comp = self.component_scores(d, s)
        pct = {k: np.searchsorted(self.ref[k], v, side="right") / len(self.ref[k]) for k, v in comp.items()}
        rank_score = np.mean(list(pct.values()), axis=0)
        return rank_score, comp, pct

    # ----- annotations -----
    def _known(self, rel, d, s):
        return np.asarray(self.known[rel][d, s]).ravel() > 0

    def flags(self, d, s):
        d, s = np.asarray(d), np.asarray(s)
        return {
            "known_indication_in_primekg": self._known("treats", d, s),
            "contraindication_in_primekg": self._known("contraindicated_for", d, s),
            "offlabel_use_in_primekg": self._known("offlabel_for", d, s),
            "drug_was_training_drug": np.isin(d, list(self.train_drugs)),
            "drug_gene_targets": self.drug_gene_deg[d].astype(int),
            "drug_has_fingerprint": self.fp_bits[d] > 0,
            "disease_training_indications": self.dis_train_deg[s].astype(int),
            "disease_gene_associations": self.dis_gene_deg[s].astype(int),
            "disease_is_ntd": self.is_ntd[s].astype(bool),
        }

    @staticmethod
    def warnings_for(fl, i):
        w = []
        if fl["contraindication_in_primekg"][i]:
            w.append("PrimeKG lists this drug as CONTRAINDICATED for this disease: treat as a safety signal, not a candidate.")
        if fl["known_indication_in_primekg"][i]:
            w.append("Already a known indication in PrimeKG (not a new hypothesis).")
        if fl["drug_gene_targets"][i] == 0:
            w.append("Drug has no gene targets in the graph: the score relies on chemical similarity and drug-disease side information.")
        if not fl["drug_has_fingerprint"][i]:
            w.append("Drug has no chemical fingerprint (no SMILES): structure-based evidence unavailable.")
        if fl["disease_training_indications"][i] == 0:
            w.append("Disease has no training indications: few comparable drugs, low-information score.")
        if fl["disease_gene_associations"][i] == 0:
            w.append("Disease has no gene associations in the graph.")
        return w

    def explain(self, d, s, k=5):
        """Graph evidence around one pair (descriptive, not causal)."""
        F = self.F
        shared = (F.DG[d].multiply(F.SG[s])).indices
        tdr = self.T[:, s].nonzero()[0]
        sims = []
        if len(tdr) and self.fp_bits[d] > 0:
            a = self.fp[d].astype(np.float32)
            b = self.fp[tdr].astype(np.float32)
            inter = b @ a
            union = a.sum() + b.sum(1) - inter
            t = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)
            for j in np.argsort(-t)[:k]:
                if tdr[j] != d:
                    sims.append({"drug_id": str(self.drug_ids[tdr[j]]), "drug_name": str(self.drug_names[tdr[j]]), "tanimoto": round(float(t[j]), 3)})
        co_target = []
        if len(tdr):
            ov = np.asarray(F.DD[d, tdr].todense()).ravel()
            for j in np.argsort(-ov)[:k]:
                if ov[j] > 0:
                    co_target.append({"drug_id": str(self.drug_ids[tdr[j]]), "drug_name": str(self.drug_names[tdr[j]]), "shared_targets": int(ov[j])})
        related = []
        rel_dis = F.SS[s].indices
        for rel, M in (("contraindicated_for", F.DC), ("offlabel_for", F.DO)):
            hit = np.intersect1d(M[d].indices, rel_dis)
            for x in hit[:k]:
                related.append({"relation": rel, "disease_id": str(self.disease_ids[x]), "disease_name": str(self.disease_names[x])})
        return {"shared_gene_targets": [str(self.gene_symbols[g]) for g in shared[:10]], "n_shared_gene_targets": int(len(shared)),
                "similar_training_drugs_with_this_indication": sims, "training_drugs_sharing_targets_with_this_indication": co_target,
                "drug_relations_to_related_diseases": related,
                "note": "Evidence the model could use; a predictive path is not a mechanism and does not establish efficacy."}
