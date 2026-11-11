"""
src/data/treats_edges.py - leakage-safe handling of the target (drug -treats-> disease) edges in the message-passing graph.

Graph variants (all start from build_message_passing_graph(), i.e. every treats / rev_treats edge removed and the held-out pairs
removed from contraindicated_for / offlabel_for):

  original      "A"   the code-of-record graph: no treats edges.
  train_treats  "B"   + the TRAIN-positive treats edges (and their reverse). Held-out (val/test) positives are never added.
  mechanism     "C"   "A" without the drug->disease label-bearing relations (contraindicated_for, offlabel_for): only drug-gene,
                      disease-gene, gene-gene and disease-disease relations remain.

Why training needs masking. If a train-positive pair is both a supervised target AND an edge of the message-passing graph, the model can read the
label off the edge (target leakage in training; the held-out pairs have no such edge, so validation/test scores would collapse relative to training).
`supervision_view` therefore removes, for each optimisation step, the pairs being supervised (and their reverse edges) from the treats / rev_treats
edges; the remaining train-positive edges are the "known indications" the model may use. Evaluation (val/test) uses ALL train-positive edges.
"naive" inclusion (no masking) exists only as a labelled diagnostic.

Nothing here reads a validation or test label except to EXCLUDE it.
"""
from __future__ import annotations

import numpy as np

TARGET = ("drug", "treats", "disease")
REV = ("disease", "rev_treats", "drug")
LABEL_REL = ("contraindicated_for", "offlabel_for")


def _pair_keys(pairs, n_second):
    return pairs[0].astype(np.int64) * n_second + pairs[1].astype(np.int64)


def train_positive_pairs(splits):
    """(2,P) int64 array of train positive pairs from a splits dict (edges_train, y_train)."""
    e = np.asarray(splits["edges_train"])
    y = np.asarray(splits["y_train"]).astype(bool)
    return e[:, y].astype(np.int64)


def build_variant_edges(base_graph, splits, variant):
    """-> dict {edge_type: edge_index (LongTensor)} for the chosen variant. `base_graph` = build_message_passing_graph(...) output."""
    import torch
    ed = {et: base_graph[et].edge_index for et in base_graph.edge_types}
    if variant == "original":
        return ed
    if variant == "train_treats":
        pos = torch.as_tensor(train_positive_pairs(splits), dtype=torch.long)
        ed = dict(ed)
        ed[TARGET] = pos
        ed[REV] = pos.flip(0)
        return ed
    if variant == "mechanism":
        ed = dict(ed)
        for rel in LABEL_REL:
            for et in (("drug", rel, "disease"), ("disease", f"rev_{rel}", "drug")):
                if et in ed:
                    ed[et] = torch.empty((2, 0), dtype=torch.long)
        return ed
    raise ValueError(f"unknown variant {variant}")


def supervision_view(edge_dict, train_pos, sup_idx):
    """Edge dict for ONE optimisation step: the train-positive pairs `train_pos[:, sup_idx]` are removed from treats and rev_treats.
    `train_pos` is the (2,P) tensor of ALL train-positive edges present in `edge_dict` (same order); `sup_idx` indexes the pairs supervised in this step."""
    import torch
    keep = torch.ones(train_pos.shape[1], dtype=torch.bool, device=train_pos.device)
    keep[sup_idx] = False
    kept = train_pos[:, keep]
    out = dict(edge_dict)
    out[TARGET] = kept
    out[REV] = kept.flip(0)
    return out


def make_folds(n_pos, y_train, k, rng):
    """Random partition of the TRAIN pairs into k folds, stratified by label. -> list of index arrays into edges_train.
    Fold j supervises its positives and negatives; the positives of fold j are the ones masked from message passing in that step."""
    y = np.asarray(y_train).astype(bool)
    pos = np.where(y)[0]
    neg = np.where(~y)[0]
    rng.shuffle(pos)
    rng.shuffle(neg)
    return [np.concatenate([pos[j::k], neg[j::k]]) for j in range(k)]


def _keys_of(ed, et, n_second):
    ei = ed[et].cpu().numpy()
    return _pair_keys(ei, n_second) if ei.size else np.zeros(0, dtype=np.int64)


def leakage_audit(edge_dict, splits, full_graph, n_drugs, n_diseases, variant, sup_check=None):
    """Automated leakage assertions for one message-passing edge dict. Returns {check: {"pass": bool, ...}}; nothing is raised here.
    edge_dict  : edges used at EVALUATION time (all train positives for variant 'train_treats').
    full_graph : the complete HeteroData (all treats / contra / offlabel edges) used to verify negatives are not known pairs.
    sup_check  : optional list of (train_pos_tensor, sup_idx_list) to verify masking for concrete steps."""
    import torch
    n2 = n_diseases
    out = {}
    held = np.asarray(splits["heldout_indication_pairs"]).astype(np.int64)
    hk = _pair_keys(held, n2)
    val_pos = np.asarray(splits["edges_val"])[:, np.asarray(splits["y_val"]).astype(bool)]
    test_pos = np.asarray(splits["edges_test"])[:, np.asarray(splits["y_test"]).astype(bool)]
    vk, tk = _pair_keys(val_pos, n2), _pair_keys(test_pos, n2)
    out["heldout_pairs_equal_val_plus_test_positives"] = {"pass": bool(set(hk.tolist()) == set(vk.tolist()) | set(tk.tolist())), "n_heldout": int(hk.size)}

    # held-out positives absent from every drug->disease relation in the MP graph, both directions
    rels = [TARGET] + [("drug", r, "disease") for r in LABEL_REL]
    per = {}
    ok = True
    for et in rels:
        fk = _keys_of(edge_dict, et, n2)
        rev_et = ("disease", f"rev_{et[1]}", "drug")
        rk = _pair_keys(edge_dict[rev_et].flip(0).cpu().numpy(), n2) if rev_et in edge_dict and edge_dict[rev_et].numel() else np.zeros(0, dtype=np.int64)
        n_f, n_r = int(np.isin(fk, hk).sum()), int(np.isin(rk, hk).sum())
        per[et[1]] = {"heldout_in_forward": n_f, "heldout_in_reverse": n_r}
        ok &= n_f == 0 and n_r == 0
    out["no_heldout_pair_in_any_drug_disease_edge_or_its_reverse"] = {"pass": bool(ok), "detail": per}
    out["val_test_positives_absent_from_treats"] = {"pass": bool(not np.isin(_keys_of(edge_dict, TARGET, n2), np.concatenate([vk, tk])).any())}

    # treats edges present are train positives only; their drugs are train drugs
    tr_pos = train_positive_pairs(splits)
    trk = _pair_keys(tr_pos, n2)
    tk_mp = _keys_of(edge_dict, TARGET, n2)
    out["mp_treats_subset_of_train_positives"] = {"pass": bool(np.isin(tk_mp, trk).all()), "n_mp_treats_edges": int(tk_mp.size), "n_train_positives": int(trk.size),
                                                  "expected": {"original": 0, "mechanism": 0, "train_treats": int(trk.size)}[variant]}
    out["mp_treats_edge_count_matches_variant"] = {"pass": bool(tk_mp.size == out["mp_treats_subset_of_train_positives"]["expected"])}
    drugs_mp = set(edge_dict[TARGET][0].cpu().numpy().tolist())
    out["mp_treats_drugs_are_train_drugs"] = {"pass": bool(drugs_mp <= set(np.asarray(splits["drugs_train"]).tolist()))}
    out["drug_sets_disjoint"] = {"pass": bool(len(set(splits["drugs_train"].tolist()) & set(splits["drugs_val"].tolist())) == 0 and len(set(splits["drugs_train"].tolist()) & set(splits["drugs_test"].tolist())) == 0
                                             and len(set(splits["drugs_val"].tolist()) & set(splits["drugs_test"].tolist())) == 0)}
    # reverse symmetry
    r = edge_dict[REV].flip(0)
    out["rev_treats_is_flip_of_treats"] = {"pass": bool(set(_pair_keys(r.cpu().numpy(), n2).tolist()) == set(tk_mp.tolist()))}

    # negatives (all splits) are not known pairs of any drug->disease relation in the FULL graph, and not MP edges
    known = []
    for et in [TARGET] + [("drug", rel, "disease") for rel in LABEL_REL]:
        if et in full_graph.edge_types:
            known.append(_pair_keys(full_graph[et].edge_index.numpy(), n2))
    known = np.unique(np.concatenate(known))
    neg_ok, neg_n = True, {}
    for nm in ("train", "val", "test"):
        e = np.asarray(splits[f"edges_{nm}"])
        y = np.asarray(splits[f"y_{nm}"]).astype(bool)
        nk = _pair_keys(e[:, ~y], n2)
        hit = int(np.isin(nk, known).sum())
        neg_n[nm] = {"n_negatives": int(nk.size), "known_pairs_among_negatives": hit, "in_mp_treats": int(np.isin(nk, tk_mp).sum())}
        neg_ok &= hit == 0 and neg_n[nm]["in_mp_treats"] == 0
    out["negatives_are_not_graph_edges"] = {"pass": bool(neg_ok), "detail": neg_n}

    if sup_check is not None:                       # masking: supervised train positives must be absent from the step's treats and rev_treats edges
        viol, steps = 0, 0
        for (full_pos, idx_list) in sup_check:
            for idx in idx_list:
                v = supervision_view({TARGET: full_pos, REV: full_pos.flip(0)}, full_pos, idx)
                sk = _pair_keys(full_pos[:, idx].cpu().numpy(), n2)
                viol += int(np.isin(_keys_of(v, TARGET, n2), sk).sum()) + int(np.isin(_pair_keys(v[REV].flip(0).cpu().numpy(), n2), sk).sum())
                steps += 1
        out["supervised_positives_masked_in_each_step"] = {"pass": bool(viol == 0), "steps_checked": steps, "violations": viol}
    out["all_pass"] = bool(all(v["pass"] for k, v in out.items() if isinstance(v, dict) and "pass" in v))
    return out
