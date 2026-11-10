"""
scripts/audit_primekg_mapping.py - audit the PrimeKG MONDO -> DOID disease mapping.

    python scripts/audit_primekg_mapping.py

Inputs (data/external/, fetched by scripts/fetch_public_data.py --primekg):
    primekg_kg.csv, mondo.obo
Outputs:
    data/external/primekg_mondo_doid_map.csv   one row per PrimeKG disease node, with status
    data/external/who_ntd_list.csv             REGENERATED from verified MONDO roots (old bundle file is
                                               kept once as who_ntd_list_bundle_UNVERIFIED.csv)
    outputs/primekg_mapping_audit.json         headline numbers
    outputs/primekg_ntd_coverage.csv           per WHO NTD group
    outputs/primekg_unmapped_diseases.csv      every non-clean node (nothing silently dropped)
    outputs/primekg_obsolete_resolution.csv    every obsolete MONDO id: replaced / unresolved
    Docs/PRIMEKG_MAPPING_AUDIT.md              human-readable summary
Mapping rules: see src/data/mondo.py.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from src.data.mondo import (NTD_BROAD, NTD_ROOTS, build_children, map_disease_nodes,  # noqa: E402
                            mondo_version, ntd_descendants, parse_mondo)

EXT, OUT, DOCS = REPO / "data" / "external", REPO / "outputs", REPO / "Docs"
REL = ["indication", "contraindication", "off-label use"]

# rough name regexes from the earlier "lead" (kept only to show how much the lead moved)
NAME_LEAD = {
    "soil-transmitted helminthiases": r"ascariasis|trichuriasis|hookworm|soil-transmitted|ancylostom|necator|strongyloid",
    "foodborne trematodiases": r"clonorchiasis|opisthorchiasis|fascioliasis|paragonimiasis|trematod",
    "snakebite envenoming": r"snake ?bite|envenom", "noma": r"\bnoma\b", "leprosy": r"leprosy|hansen",
    "yaws": r"\byaws\b", "rabies": r"rabies", "taeniasis/cysticercosis": r"cysticercosis|taeniasis",
    "lymphatic filariasis": r"lymphatic filariasis|filariasis|elephantiasis", "scabies": r"scabies",
    "schistosomiasis": r"schistosom|bilharzia", "leishmaniasis": r"leishmania", "dengue": r"dengue",
    "dracunculiasis": r"dracunc|guinea worm", "human African trypanosomiasis": r"african trypanosom|sleeping sickness",
    "Chagas disease": r"chagas|american trypanosom", "Buruli ulcer": r"buruli", "echinococcosis": r"echinococc|hydatid",
    "chromoblastomycosis": r"chromoblastomycosis|chromomycosis", "mycetoma": r"mycetoma",
    "onchocerciasis": r"onchocerc|river blindness", "trachoma": r"trachoma",
}


def load_pairs_and_diseases(kg_path: Path):
    cols = ["relation", "x_id", "x_type", "x_name", "x_source", "y_id", "y_type", "y_name", "y_source"]
    kg = pd.read_csv(kg_path, usecols=cols, dtype=str, low_memory=False)
    dis = pd.concat([
        kg.loc[kg.x_type == "disease", ["x_id", "x_name", "x_source"]].set_axis(["id", "name", "source"], axis=1),
        kg.loc[kg.y_type == "disease", ["y_id", "y_name", "y_source"]].set_axis(["id", "name", "source"], axis=1),
    ]).drop_duplicates("id").reset_index(drop=True)
    lab = kg[kg.relation.isin(REL)]
    a = lab[lab.x_type == "drug"][["relation", "x_id", "y_id"]].set_axis(["relation", "drug_id", "disease_id"], axis=1)
    b = lab[lab.x_type == "disease"][["relation", "y_id", "x_id"]].set_axis(["relation", "drug_id", "disease_id"], axis=1)
    return dis, pd.concat([a, b]).drop_duplicates()


def main():
    for p in (EXT / "primekg_kg.csv", EXT / "mondo.obo"):
        if not p.exists():
            sys.exit(f"missing {p} - run: python scripts/fetch_public_data.py --primekg")
    OUT.mkdir(exist_ok=True)
    terms = parse_mondo(EXT / "mondo.obo")
    children = build_children(terms)
    print(f"MONDO {mondo_version(EXT / 'mondo.obo')}: {len(terms):,} terms")
    dis, pairs = load_pairs_and_diseases(EXT / "primekg_kg.csv")
    print(f"{len(dis):,} disease nodes; label pairs: {pairs.relation.value_counts().to_dict()}")

    nm = map_disease_nodes(dis, terms)
    cnt = pairs.groupby(["disease_id", "relation"]).size().unstack(fill_value=0).reindex(columns=REL, fill_value=0)
    nm = nm.merge(cnt, how="left", left_on="primekg_id", right_index=True).fillna({r: 0 for r in REL})
    for r in REL:
        nm[r] = nm[r].astype(int)
    nm.to_csv(EXT / "primekg_mondo_doid_map.csv", index=False)

    usable = nm["status"].isin(["mapped", "ambiguous"])
    rep = {"primekg_disease_nodes": len(nm), "status_counts": nm["status"].value_counts().to_dict(),
           "grouped_nodes": int(nm.grouped.sum()),
           "grouped_resolved_fully": int(((nm.status == "mapped") & nm.grouped).sum()),
           "grouped_partial": int((nm.status == "partial").sum()),
           "nodes_with_obsolete_id_followed": int(nm.was_obsolete.sum()),
           "mondo_release": mondo_version(EXT / "mondo.obo") + " (PrimeKG was built with an older MONDO)"}
    ob = []                                           # obsolete-id accounting per component
    for r in nm.itertuples():
        for orig, res, st in zip(r.mondo_ids.split("|"), r.mondo_resolved.split("|"), r.obsolete_status.split("|")):
            if st != "current":
                ob.append({"primekg_id": r.primekg_id, "mondo_original": orig, "mondo_resolved": res, "outcome": st})
    ob = pd.DataFrame(ob, columns=["primekg_id", "mondo_original", "mondo_resolved", "outcome"])
    ob.to_csv(OUT / "primekg_obsolete_resolution.csv", index=False)
    rep["obsolete_resolution"] = ob["outcome"].value_counts().to_dict()
    rep["label_pairs"] = {r: {
        "total": int(nm[r].sum()),
        "on_fully_mapped_nodes": int(nm.loc[nm.status == "mapped", r].sum()),
        "on_ambiguous_nodes": int(nm.loc[nm.status == "ambiguous", r].sum()),
        "on_partial_grouped_nodes": int(nm.loc[nm.status == "partial", r].sum()),
        "on_unmapped_nodes": int(nm.loc[nm.status.str.startswith("unmapped"), r].sum())} for r in REL}

    # ---- NTD coverage (curated MONDO roots + descendants -> PrimeKG nodes)
    desc_by_group = ntd_descendants(terms, children)
    comp2node = defaultdict(set)
    for r in nm.itertuples():
        for c in r.mondo_resolved.split("|"):
            comp2node[c].add(r.primekg_id)
    node_row = nm.set_index("primekg_id")
    cov, ntd_doid_rows, all_nodes = [], [], set()
    for group, roots in NTD_ROOTS.items():
        desc = desc_by_group[group]
        nodes = set().union(*[comp2node.get(m, set()) for m in desc]) if desc else set()
        all_nodes |= nodes
        sub = node_row.loc[sorted(nodes)] if nodes else node_row.iloc[0:0]
        doids = sorted({d for m in desc for d in terms[m]["doid_exact"] if not terms[m]["obsolete"]})
        ntd_doid_rows += [{"disease_id": d, "disease_name": group, "mondo_root": "|".join(m for m, _ in roots)}
                          for d in doids]
        pat = NAME_LEAD.get(group)
        lead = nm[nm.name.str.contains(pat, case=False, regex=True, na=False)] if pat else nm.iloc[0:0]
        cov.append({"ntd_group": group, "mondo_roots": "|".join(f"{m} ({n})" for m, n in roots),
                    "mondo_descendants": len(desc), "doids_for_hetionet_join": len(doids), "primekg_nodes": len(nodes),
                    "indication": int(sub["indication"].sum()), "contraindication": int(sub["contraindication"].sum()),
                    "off-label use": int(sub["off-label use"].sum()),
                    "nodes_ambiguous_or_partial": int(sub["status"].isin(["ambiguous", "partial"]).sum()),
                    "name_lead_nodes": len(lead), "name_lead_indication": int(lead["indication"].sum()),
                    "note": NTD_BROAD.get(group, "")})
    cov = pd.DataFrame(cov)
    cov.to_csv(OUT / "primekg_ntd_coverage.csv", index=False)
    uniq = node_row.loc[sorted(all_nodes)] if all_nodes else node_row.iloc[0:0]
    rep["ntd"] = {
        "groups_total": len(cov), "groups_resolved_to_mondo": int((cov.mondo_roots != "").sum()),
        "groups_with_primekg_nodes": int((cov.primekg_nodes > 0).sum()),
        "groups_with_indication_pairs": int((cov.indication > 0).sum()),
        "groups_with_indication_name_lead": int((cov.name_lead_indication > 0).sum()),
        "unique_ntd_primekg_nodes": len(all_nodes),
        "unique_ntd_indication_pairs": int(uniq["indication"].sum()),
        "unique_ntd_contraindication_pairs": int(uniq["contraindication"].sum()),
        "unique_ntd_offlabel_pairs": int(uniq["off-label use"].sum()),
        "unique_ntd_nodes_ambiguous_or_partial": int(uniq["status"].isin(["ambiguous", "partial"]).sum()),
        "note": "per-group totals can overlap; unique_* de-duplicate nodes shared between groups"}
    old, bak = EXT / "who_ntd_list.csv", EXT / "who_ntd_list_bundle_UNVERIFIED.csv"
    if old.exists() and not bak.exists():
        old.rename(bak)
    pd.DataFrame(ntd_doid_rows).drop_duplicates().to_csv(old, index=False)

    # ---- Hetionet overlap
    hp = REPO / "data" / "processed" / "baseline_morgan"
    if (hp / "diseases.csv").exists():
        hd = set(pd.read_csv(hp / "diseases.csv", low_memory=False)["disease_id"].astype(str))
        hdr = set(pd.read_csv(hp / "drugs.csv", low_memory=False)["drug_id"].astype(str))
        pk = {d for v in nm.loc[usable, "doid_exact"] for d in v.split("|") if d}
        ind = pairs[pairs.relation == "indication"]
        rep["hetionet_overlap"] = {
            "hetionet_diseases_found_in_primekg_via_doid": len(hd & pk), "hetionet_diseases": len(hd),
            "primekg_indication_drugs": int(ind.drug_id.nunique()),
            "primekg_indication_drugs_in_hetionet": int(ind.drug_id[ind.drug_id.isin(hdr)].nunique())}
    (OUT / "primekg_mapping_audit.json").write_text(json.dumps(rep, indent=2))
    nm[~nm["status"].eq("mapped")].sort_values("indication", ascending=False).to_csv(
        OUT / "primekg_unmapped_diseases.csv", index=False)

    md = ["# PrimeKG MONDO -> DOID mapping audit", "",
          f"Generated by `scripts/audit_primekg_mapping.py`. MONDO {rep['mondo_release']}.", "",
          "## Disease nodes", "", f"{rep['primekg_disease_nodes']:,} nodes ({rep['grouped_nodes']:,} grouped).", "",
          "| status | nodes |", "|---|---|"] + [f"| {k} | {v:,} |" for k, v in rep["status_counts"].items()]
    md += ["", "Obsolete MONDO ids: " + (", ".join(f"{k}={v}" for k, v in rep["obsolete_resolution"].items()) or "none"), "",
           "## Label pairs surviving (relations kept separate)", "",
           "| relation | total | fully mapped | ambiguous | partial grouped | unmapped |", "|---|---|---|---|---|---|"]
    md += [f"| {k} | {v['total']:,} | {v['on_fully_mapped_nodes']:,} | {v['on_ambiguous_nodes']:,} | "
           f"{v['on_partial_grouped_nodes']:,} | {v['on_unmapped_nodes']:,} |" for k, v in rep["label_pairs"].items()]
    md += ["", "## WHO NTD coverage (curated MONDO roots + descendants)", "",
           "| NTD group | MONDO roots | nodes | indication | contra | off-label | name-lead indication | note |",
           "|---|---|---|---|---|---|---|---|"]
    md += [f"| {r['ntd_group']} | {r['mondo_roots'] or '-'} | {r['primekg_nodes']} | {r['indication']} | "
           f"{r['contraindication']} | {r['off-label use']} | {r['name_lead_indication']} | {r['note']} |"
           for r in cov.to_dict("records")]
    n = rep["ntd"]
    md += ["", f"**{n['groups_with_indication_pairs']} of {n['groups_total']}** groups have >=1 indication pair. "
           f"De-duplicated: {n['unique_ntd_primekg_nodes']} nodes, {n['unique_ntd_indication_pairs']} indication / "
           f"{n['unique_ntd_contraindication_pairs']} contraindication / {n['unique_ntd_offlabel_pairs']} off-label pairs.", ""]
    if "hetionet_overlap" in rep:
        h = rep["hetionet_overlap"]
        md += ["## Overlap with Hetionet", "",
               f"- Hetionet diseases reachable via exact DOID: {h['hetionet_diseases_found_in_primekg_via_doid']} / {h['hetionet_diseases']}",
               f"- PrimeKG indication drugs: {h['primekg_indication_drugs']} (in Hetionet's 1,552: {h['primekg_indication_drugs_in_hetionet']})", ""]
    md += ["## Caveats", "",
           "- Non-`MONDO:equivalentTo` DOID xrefs are `related` and not used for labels.",
           "- Newer MONDO than PrimeKG used; obsolete ids followed via `replaced_by` (see primekg_obsolete_resolution.csv).",
           "- Unmapped/ambiguous nodes: outputs/primekg_unmapped_diseases.csv (none dropped).",
           "- Drug ids are DrugBank; check upstream DrugBank/DrugCentral terms before redistributing derived label files.", ""]
    DOCS.mkdir(exist_ok=True)
    (DOCS / "PRIMEKG_MAPPING_AUDIT.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()
