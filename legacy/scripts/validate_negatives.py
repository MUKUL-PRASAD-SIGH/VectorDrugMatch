"""
scripts/validate_negatives.py - audit the curated negatives (PharmacotherapyDB 'NOT' rows).

    python scripts/validate_negatives.py --config configs/baseline_morgan.yaml

Checks identifier mapping, duplicates, contradictions with positives, presence of the pair
as a message-passing edge, split-boundary behaviour (drug-disjoint) and how much of the
curated set is actually usable under a cold-start split. Writes outputs/negatives_audit.json.

NOTE on meaning: a PharmacotherapyDB 'NOT' is a curated *non-indication* ("examined and
judged not to be an approved/established treatment"), not proof of biological inactivity.
Report metrics separately for curated vs sampled negatives (splits[f"curated_{split}"]).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.data.dataset import DEFAULT_CURATED_NEG, build_tabular_dataset  # noqa: E402
from src.data.graph_builder import build_hetero_data  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/baseline_morgan.yaml")
    cfg = yaml.safe_load(open(REPO / ap.parse_args().config))
    ds = cfg.get("dataset", {})
    proc = REPO / "data" / "processed" / cfg["experiment"]["name"]

    labels = pd.read_csv(DEFAULT_CURATED_NEG)
    neg = labels[labels["category"] == "NOT"]
    other = labels[labels["category"] != "NOT"]
    drugs = pd.read_csv(proc / "drugs.csv", low_memory=False)
    diseases = pd.read_csv(proc / "diseases.csv", low_memory=False)
    edges = pd.read_csv(proc / "edges.csv", usecols=["source_id", "target_id", "relation"], dtype=str)

    rep = {"n_not_rows": len(neg)}
    rep["duplicate_pairs"] = int(neg.duplicated(["drug_id", "disease_id"]).sum())
    rep["drug_ids_unmapped"] = int((~neg["drug_id"].isin(drugs["drug_id"])).sum())
    rep["disease_ids_unmapped"] = int((~neg["disease_id"].isin(diseases["disease_id"].astype(str))).sum())
    rep["also_labelled_DM_or_SYM"] = int(len(neg.merge(other, on=["drug_id", "disease_id"])))
    ctd = edges[edges["relation"] == "CtD"]
    known = set(zip(ctd["source_id"], ctd["target_id"]))
    rep["pairs_that_are_CtD_edges"] = int(sum((a, b) in known for a, b in zip(neg["drug_id"], neg["disease_id"])))
    cpd = edges[edges["relation"] == "CpD"]
    pal = set(zip(cpd["source_id"], cpd["target_id"]))
    rep["pairs_that_are_CpD_edges"] = int(sum((a, b) in pal for a, b in zip(neg["drug_id"], neg["disease_id"])))
    rep["top_diseases"] = neg["disease"].value_counts().head(5).to_dict()
    rep["n_curators_mean"] = float(neg["n_curators"].mean())

    data = build_hetero_data(proc)
    treats = data["drug", "treats", "disease"].edge_index.numpy()
    tset = set(zip(treats[0].tolist(), treats[1].tolist()))
    splits = build_tabular_dataset(data, neg_ratio=ds.get("neg_ratio", 5.0), test_size=ds.get("test_size", 0.15),
                                   val_size=ds.get("val_size", 0.15), random_state=ds.get("random_seed", 42))
    split_info, drugs_by_split = {}, {}
    for sp in ("train", "val", "test"):
        e, y, c = splits[f"edges_{sp}"], splits[f"y_{sp}"], splits[f"curated_{sp}"]
        drugs_by_split[sp] = set(e[0].tolist())
        split_info[sp] = {"pos": int((y == 1).sum()), "neg": int((y == 0).sum()), "curated_neg": int(c.sum()),
                          "sampled_neg": int(((y == 0) & ~c).sum()),
                          "negatives_that_are_treats_edges": int(sum((a, b) in tset for a, b in
                                                                     zip(e[0][y == 0].tolist(), e[1][y == 0].tolist())))}
    rep["splits"] = split_info
    rep["drug_overlap_between_splits"] = int(len(drugs_by_split["train"] & drugs_by_split["test"])
                                             + len(drugs_by_split["train"] & drugs_by_split["val"])
                                             + len(drugs_by_split["val"] & drugs_by_split["test"]))
    used = sum(v["curated_neg"] for v in split_info.values())
    rep["curated_used"] = used
    rep["curated_unusable_cold_start"] = len(neg) - used
    rep["note"] = ("NOT rows whose drug has no CtD positive are dropped by the drug-disjoint split; "
                   "'NOT' = curated non-indication, not proven biological negative.")

    out = REPO / "outputs" / "negatives_audit.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep, indent=2))
    bad = (rep["duplicate_pairs"] or rep["drug_ids_unmapped"] or rep["disease_ids_unmapped"]
           or rep["also_labelled_DM_or_SYM"] or rep["pairs_that_are_CtD_edges"] or rep["drug_overlap_between_splits"]
           or any(v["negatives_that_are_treats_edges"] for v in split_info.values()))
    print("\nRESULT:", "PROBLEMS FOUND" if bad else "all hard negative checks passed")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
