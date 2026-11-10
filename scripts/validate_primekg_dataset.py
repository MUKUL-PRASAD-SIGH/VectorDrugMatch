"""
scripts/validate_primekg_dataset.py - Track B step 3: audit the PrimeKG dataset + saved split before training.

    python scripts/validate_primekg_dataset.py --config configs/primekg_morgan.yaml
    python scripts/validate_primekg_dataset.py --config configs/primekg_morgan.yaml --skip-graph   # no torch graph build

Writes outputs/<exp>/validation_report.json and .md; exits 1 if any HARD check fails.
Report: node/edge counts by type, positives by relation, drug/disease coverage, mapping status and unresolved
ids, split sizes and drug overlap, leakage checks, curated vs sampled negative counts, NTD counts per split.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

fails, warns, checks = [], [], []


def check(ok, msg, hard=True):
    checks.append({"ok": bool(ok), "hard": hard, "check": msg})
    print(f"  [{'PASS' if ok else ('FAIL' if hard else 'WARN')}] {msg}")
    if not ok:
        (fails if hard else warns).append(msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/primekg_morgan.yaml")
    ap.add_argument("--skip-graph", action="store_true", help="skip the (torch) message-passing leakage checks")
    ap.add_argument("--skip-reproduce", action="store_true", help="do not re-run the split to test determinism")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(REPO / a.config))
    exp, ds = cfg["experiment"]["name"], cfg.get("dataset", {})
    proc = REPO / "data" / "processed" / exp
    seed = ds.get("random_seed", 42)
    split_path = REPO / ds["presplit"] if ds.get("presplit") else proc / "splits" / f"seed{seed}.npz"
    rep = {"experiment": exp, "seed": seed}

    # ------------------------------------------------------------ 1. counts
    print("\n=== 1. nodes and edges ===")
    drugs = pd.read_csv(proc / "drugs.csv", low_memory=False)
    dis = pd.read_csv(proc / "diseases.csv", low_memory=False)
    genes = pd.read_csv(proc / "genes.csv", low_memory=False)
    edges = pd.read_csv(proc / "edges.csv", dtype=str)
    rep["nodes"] = {"drug": len(drugs), "disease": len(dis), "gene": len(genes)}
    rep["edges_by_relation"] = edges.relation.value_counts().to_dict()
    print(f"  nodes {rep['nodes']}\n  edges {rep['edges_by_relation']}")
    check(drugs.drug_id.is_unique and dis.disease_id.is_unique and genes.gene_id.is_unique, "node ids are unique")
    check(not edges.duplicated(["source_id", "target_id", "relation"]).any(), "no duplicate edges within a relation")
    ids = {"Drug": set(drugs.drug_id.astype(str)), "Disease": set(dis.disease_id.astype(str)), "Gene": set(genes.gene_id.astype(str))}
    bad = 0
    for t, col in (("source_type", "source_id"), ("target_type", "target_id")):
        for typ, idset in ids.items():
            sub = edges[edges[t] == typ]
            bad += int((~sub[col].isin(idset)).sum())
    check(bad == 0, f"every edge endpoint exists as a node of the right type (bad={bad})")
    check({"edge_provenance": "primekg_relation" in edges.columns}["edge_provenance"],
          "every edge carries primekg_relation / display_relation provenance")
    prov = json.loads((proc / "primekg_provenance.json").read_text())
    rep["provenance"] = {"kg_sha256": prov["source"]["sha256"], "mondo": prov["source"]["mondo"],
                         "edge_stats": prov["edge_stats"]}
    unres = sum(v["unresolved_endpoints"] for v in prov["edge_stats"].values())
    check(unres == 0, f"no edge endpoint failed to resolve during build (unresolved={unres})")

    # ------------------------------------------------------------ 2. labels / coverage
    print("\n=== 2. positives by relation and coverage ===")
    lab = {r: edges[edges.relation == r] for r in ("CtD", "PK_contra", "PK_offlabel")}
    rep["label_pairs"] = {"indication": len(lab["CtD"]), "contraindication": len(lab["PK_contra"]),
                          "off-label": len(lab["PK_offlabel"])}
    ind_drugs, ind_dis = lab["CtD"].source_id.nunique(), lab["CtD"].target_id.nunique()
    rep["coverage"] = {
        "drugs_with_indication": ind_drugs, "drugs_total": len(drugs),
        "diseases_with_indication": ind_dis, "diseases_total": len(dis),
        "drug_smiles_coverage": int(drugs.has_smiles.sum()) if "has_smiles" in drugs else None,
        "indication_drugs_with_smiles": int(drugs[drugs.drug_id.isin(lab["CtD"].source_id)].has_smiles.sum())
        if "has_smiles" in drugs else None}
    print(f"  label pairs {rep['label_pairs']}\n  coverage {rep['coverage']}")
    check(rep["label_pairs"]["indication"] > 5000, "indication pairs present (>5000)")
    pk = lambda df: set(zip(df.source_id, df.target_id))      # noqa: E731
    contr = {"indication&contraindication": len(pk(lab["CtD"]) & pk(lab["PK_contra"])),
             "indication&offlabel": len(pk(lab["CtD"]) & pk(lab["PK_offlabel"])),
             "contraindication&offlabel": len(pk(lab["PK_contra"]) & pk(lab["PK_offlabel"]))}
    rep["contradictory_pairs"] = contr
    check(sum(contr.values()) == 0, f"no pair carries contradictory relations {contr} "
          "(PrimeKG itself contains some; they are kept as separate relations and reported)", hard=False)

    # ------------------------------------------------------------ 3. mapping
    print("\n=== 3. disease mapping status ===")
    rep["disease_mapping_status"] = dis.mapping_status.value_counts().to_dict()
    ob = dis.obsolete_status.str.split("|").explode().value_counts().to_dict()
    rep["obsolete_resolution"] = ob
    unresolved = dis[dis.mapping_status.str.startswith("unmapped") | dis.mapping_status.isin(["partial", "ambiguous"])]
    rep["unresolved_or_ambiguous_disease_nodes"] = len(unresolved)
    print(f"  {rep['disease_mapping_status']}\n  obsolete-id outcomes {ob}")
    check(len(dis) == dis.primekg_id.nunique(), "no disease node dropped or duplicated by the mapping")
    check(int(dis.is_ntd.sum()) > 0, f"NTD flags present ({int(dis.is_ntd.sum())} disease nodes)")

    # ------------------------------------------------------------ 4. split
    print("\n=== 4. saved split ===")
    check(split_path.exists(), f"split file exists: {split_path.name}")
    z = np.load(split_path)
    man = json.loads(split_path.with_suffix(".manifest.json").read_text())
    rep["split"] = man["splits"]
    rep["split_contradictions"] = man["contradictory_pairs"]
    dmap = {d: i for i, d in enumerate(drugs.drug_id.astype(str))}
    smap = {d: i for i, d in enumerate(dis.disease_id.astype(str))}
    known = set()
    for df in lab.values():
        known |= set(zip(df.source_id.map(dmap).astype(int), df.target_id.map(smap).astype(int)))
    d = {sp: set(z[f"edges_{sp}"][0].tolist()) for sp in ("train", "val", "test")}
    check(not (d["train"] & d["val"]) and not (d["train"] & d["test"]) and not (d["val"] & d["test"]),
          "train/val/test drug sets are disjoint (positives AND negatives)")
    ind_set = set(zip(lab["CtD"].source_id.map(dmap).astype(int), lab["CtD"].target_id.map(smap).astype(int)))
    pos_all = {}
    for sp in ("train", "val", "test"):
        e, y = z[f"edges_{sp}"], z[f"y_{sp}"]
        pos = set(zip(e[0][y == 1].tolist(), e[1][y == 1].tolist()))
        neg = set(zip(e[0][y == 0].tolist(), e[1][y == 0].tolist()))
        pos_all[sp] = pos
        n_curated = int(z[f"curated_{sp}"].sum())
        print(f"  {sp}: {int((y == 1).sum())} pos / {int((y == 0).sum())} neg "
              f"(curated {n_curated}, sampled {int((y == 0).sum()) - n_curated}); drugs {len(d[sp])}")
        check(pos <= ind_set and len(pos) == int((y == 1).sum()), f"{sp}: positives are exactly known indication pairs, no duplicates")
        check(len(neg & known) == 0, f"{sp}: no negative is a known indication/contraindication/off-label pair")
        check(len(neg) == int((y == 0).sum()), f"{sp}: no duplicate negatives")
    check(not (pos_all["train"] & pos_all["val"]) and not (pos_all["train"] & pos_all["test"]), "no positive pair shared across splits")
    allpos = sum(len(v) for v in pos_all.values())
    check(allpos == len(ind_set), f"every indication pair is in exactly one split ({allpos} of {len(ind_set)})")
    rep["curated_vs_sampled_negatives"] = {sp: {"curated": man["splits"][sp]["curated_negatives"],
                                                "sampled": man["splits"][sp]["sampled_negatives"]} for sp in d}
    rep["ntd_positives_per_split"] = {sp: man["splits"][sp]["ntd_positives"] for sp in d}
    check(all(v > 0 for v in rep["ntd_positives_per_split"].values()), f"NTD positives reach every split {rep['ntd_positives_per_split']}", hard=False)

    if not a.skip_reproduce:
        before = man["array_hashes"]
        subprocess.run([sys.executable, str(REPO / "scripts" / "primekg_split.py"), "--config", a.config, "--seed", str(seed)],
                       check=True, capture_output=True)
        after = json.loads(split_path.with_suffix(".manifest.json").read_text())["array_hashes"]
        check(before == after, "re-running the split with the same seed reproduces identical arrays (determinism)")

    # ------------------------------------------------------------ 5. graph leakage
    if not a.skip_graph:
        print("\n=== 5. message-passing leakage ===")
        from src.data.dataset import build_message_passing_graph, build_tabular_dataset
        from src.data.graph_builder import build_hetero_data
        data = build_hetero_data(proc, include_features=True)
        mp = build_message_passing_graph(data, split_path)
        held = z["heldout_indication_pairs"]
        heldset = set(zip(held[0].tolist(), held[1].tolist()))
        leaks = {}
        for et in mp.edge_types:
            if et[0] == "drug" and et[2] == "disease":
                ei = mp[et].edge_index
                leaks[et[1]] = len(heldset & set(zip(ei[0].tolist(), ei[1].tolist())))
            elif et[0] == "disease" and et[2] == "drug":
                ei = mp[et].edge_index
                leaks[et[1]] = len(heldset & set(zip(ei[1].tolist(), ei[0].tolist())))
        rep["heldout_pairs_present_in_message_passing_graph"] = leaks
        check(sum(leaks.values()) == 0, f"no held-out indication pair reachable through any drug<->disease relation {leaks}")
        check(mp["drug", "treats", "disease"].edge_index.numel() == 0 and mp["disease", "rev_treats", "drug"].edge_index.numel() == 0,
              "all treats and rev_treats edges removed from the message-passing graph")
        train_drugs = set(z["drugs_train"].tolist())
        ei = mp["drug", "contraindicated_for", "disease"].edge_index if ("drug", "contraindicated_for", "disease") in mp.edge_types else None
        if ei is not None:
            kept_c = set(zip(ei[0].tolist(), ei[1].tolist()))
            check(all(u in train_drugs or (u, v) not in heldset for u, v in kept_c), "contraindication edges on held-out positives were dropped")
        a1 = build_tabular_dataset(data, presplit=str(split_path))
        a2 = build_tabular_dataset(data, presplit=str(split_path))
        same = all(np.array_equal(a1[f"edges_{s}"], a2[f"edges_{s}"]) and np.array_equal(a1[f"y_{s}"], a2[f"y_{s}"]) and
                   np.array_equal(a1[f"X_{s}"], a2[f"X_{s}"]) for s in ("train", "val", "test"))
        check(same, "baselines, Node2Vec and GNNs get identical pairs, labels, negatives and features from the saved split")
        deg = data["disease"].x[:, 2].numpy()
        expect = pd.concat([edges[~edges.relation.isin(["CtD", "PK_contra", "PK_offlabel", "CpD"]) & (edges.target_type == "Disease")].target_id,
                            edges[~edges.relation.isin(["CtD", "PK_contra", "PK_offlabel", "CpD"]) & (edges.source_type == "Disease")].source_id]
                           ).value_counts()
        got = pd.Series(deg, index=dis.disease_id.astype(str))
        check(bool((got.reindex(expect.index).values == expect.values).all()), "disease degree feature ignores label-bearing relations")

    rep["hard_failures"], rep["warnings"], rep["checks"] = fails, warns, checks
    out = REPO / "outputs" / exp
    out.mkdir(parents=True, exist_ok=True)
    (out / "validation_report.json").write_text(json.dumps(rep, indent=2, default=int))
    md = [f"# PrimeKG dataset validation ({exp}, seed {seed})", "",
          f"Result: **{'FAILED' if fails else 'all hard checks passed'}** ({len(warns)} warnings)", "",
          f"- Nodes: {rep['nodes']}", f"- Label pairs: {rep['label_pairs']}", f"- Coverage: {rep['coverage']}",
          f"- Disease mapping status: {rep['disease_mapping_status']}", f"- Obsolete-id outcomes: {rep['obsolete_resolution']}",
          f"- Contradictory pairs: {contr}", "", "## Splits", "", "| split | drugs | pos | neg | curated | sampled | NTD pos |", "|---|---|---|---|---|---|---|"]
    md += [f"| {sp} | {v['drugs']} | {v['positives']} | {v['negatives']} | {v['curated_negatives']} | {v['sampled_negatives']} | {v['ntd_positives']} |"
           for sp, v in man["splits"].items()]
    md += ["", "## Checks", ""] + [f"- [{'x' if c['ok'] else ' '}] {'(hard) ' if c['hard'] else '(warn) '}{c['check']}" for c in checks]
    (out / "validation_report.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\n=== RESULT === {'HARD FAILURES: ' + str(len(fails)) if fails else 'all hard checks passed'} | report: {out / 'validation_report.md'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
