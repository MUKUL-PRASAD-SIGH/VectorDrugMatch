"""
scripts/build_ntd_mapping.py - definitive WHO NTD -> MONDO -> PrimeKG mapping table.

    python scripts/build_ntd_mapping.py

Output: data/processed/ntd/ntd_disease_mapping.csv (+ ntd_mapping_summary.json)

Official list: WHO health-topic page footnote "NTDs include: ..." (21 entries), read 2026-11-10
(https://www.who.int/health-topics/neglected-tropical-diseases; same list on the 2025-12-14 WHO Q&A page).
WHO states no inclusion dates; its page headline (2026-10-15) says requests for new NTDs are on hold pending a
criteria review, which we did not read. The list says "NTDs include", not "exactly".

Rules
  * Benchmark NTD flag (diseases.csv `is_ntd`) is FROZEN: it uses the 22 groups in src/data/mondo.NTD_ROOTS. This table
    documents how those map to the WHO list; it never changes the flag.
  * Candidate extensions (chikungunya, tungiasis) and WHO fact-sheet-only diseases (podoconiosis, sporotrichosis, tungiasis)
    are evaluated for coverage but are NOT in the benchmark flag. Every MONDO root name is checked against mondo.obo.
  * Counts come from the processed PrimeKG tables and the saved split; nothing is typed in by hand.
"""
import json
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd

import sys
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from src.data.mondo import NTD_ROOTS, build_children, parse_mondo  # noqa: E402

WHO_URL = "https://www.who.int/health-topics/neglected-tropical-diseases"
WHO_ACCESSED = "2026-11-10"
# official WHO entry -> (benchmark groups in src/data/mondo.NTD_ROOTS, candidate-extension keys)
WHO = [
    ("Buruli ulcer", ["Buruli ulcer"], []),
    ("Chagas disease", ["Chagas disease"], []),
    ("dengue and chikungunya", ["dengue"], ["chikungunya"]),
    ("dracunculiasis", ["dracunculiasis"], []),
    ("echinococcosis", ["echinococcosis"], []),
    ("foodborne trematodiases", ["foodborne trematodiases"], []),
    ("human African trypanosomiasis", ["human African trypanosomiasis"], []),
    ("leishmaniasis", ["leishmaniasis"], []),
    ("leprosy", ["leprosy"], []),
    ("lymphatic filariasis", ["lymphatic filariasis"], []),
    ("mycetoma, chromoblastomycosis and other deep mycoses", ["mycetoma", "chromoblastomycosis"], []),
    ("noma", ["noma"], []),
    ("onchocerciasis", ["onchocerciasis"], []),
    ("rabies", ["rabies"], []),
    ("scabies and other ectoparasitoses", ["scabies"], ["tungiasis"]),
    ("schistosomiasis", ["schistosomiasis"], []),
    ("soil-transmitted helminthiases", ["soil-transmitted helminthiases"], []),
    ("snakebite envenoming", ["snakebite envenoming"], []),
    ("taeniasis/cysticercosis", ["taeniasis/cysticercosis"], []),
    ("trachoma", ["trachoma"], []),
    ("yaws", ["yaws"], []),
]
# candidate / fact-sheet-only terms: key -> (MONDO id, exact MONDO name, why it is here)
EXTRA = {
    "chikungunya": ("MONDO:0017941", "chikungunya", "part of the WHO entry 'dengue and chikungunya'; not in the frozen benchmark flag"),
    "tungiasis": ("MONDO:0019498", "tungiasis", "WHO fact sheet exists; WHO page does not say whether it falls under 'other ectoparasitoses'"),
    "podoconiosis": ("MONDO:0005425", "podoconiosis", "WHO fact sheet only; not named in the WHO list footnote"),
    "sporotrichosis": ("MONDO:0005968", "sporotrichosis", "WHO fact sheet only; not named in the WHO list footnote"),
}
BROAD = {"lymphatic filariasis": "upper bound: MONDO has only the generic term 'filariasis'",
         "noma": "no MONDO term found; cannot be evaluated from the ontology"}


# ---- official WHO list, read directly from the page (evidence: Docs/source_evidence/fetch_log_2026-11-10.json) ----
# source page bytes 146,039; sha256 f5472b1665a55723...; footnote 1: "NTDs include: ..." (21 groupings, listed verbatim below).
# The page does not state inclusion dates or criteria; its 2026-10-15 headline says requests for new NTDs are on hold pending a criteria review.
# "kind" is OUR classification (WHO does not label entries): single = one named disease; multi = the entry names several diseases or an open grouping.
# Fact-sheet titles are the 25 distinct fact-sheet links on the same page (22 map to entries below; 3 are fact-sheet-only).
WHO_OFFICIAL = [
    (1, "Buruli ulcer", "single", "Buruli ulcer", ["Buruli ulcer (Mycobacterium ulcerans infection)"]),
    (2, "Chagas disease", "single", "Chagas disease", ["Chagas disease (also known as American trypanosomiasis)"]),
    (3, "dengue and chikungunya", "multi", "dengue; chikungunya", ["Dengue"]),
    (4, "dracunculiasis", "single", "dracunculiasis", ["Dracunculiasis (Guinea-worm disease)"]),
    (5, "echinococcosis", "single", "echinococcosis", ["Echinococcosis"]),
    (6, "foodborne trematodiases", "multi", "(members not enumerated by WHO)", ["Foodborne trematode infections"]),
    (7, "human African trypanosomiasis", "single", "human African trypanosomiasis", ["Trypanosomiasis, human African (sleeping sickness)"]),
    (8, "leishmaniasis", "single", "leishmaniasis", ["Leishmaniasis"]),
    (9, "leprosy", "single", "leprosy", ["Leprosy"]),
    (10, "lymphatic filariasis", "single", "lymphatic filariasis", ["Lymphatic filariasis"]),
    (11, "mycetoma, chromoblastomycosis and other deep mycoses", "multi", "mycetoma; chromoblastomycosis; other deep mycoses (not enumerated)", ["Mycetoma", "Chromoblastomycosis"]),
    (12, "noma", "single", "noma", ["Noma"]),
    (13, "onchocerciasis", "single", "onchocerciasis", ["Onchocerciasis"]),
    (14, "rabies", "single", "rabies", ["Rabies"]),
    (15, "scabies and other ectoparasitoses", "multi", "scabies; other ectoparasitoses (not enumerated)", ["Scabies"]),
    (16, "schistosomiasis", "single", "schistosomiasis", ["Schistosomiasis"]),
    (17, "soil-transmitted helminthiases", "multi", "(members not enumerated by WHO)", ["Soil-transmitted helminth infections"]),
    (18, "snakebite envenoming", "single", "snakebite envenoming", ["Snakebite envenoming"]),
    (19, "taeniasis/cysticercosis", "multi", "taeniasis; cysticercosis", ["Taeniasis/cysticercosis"]),
    (20, "trachoma", "single", "trachoma", ["Trachoma"]),
    (21, "yaws", "single", "yaws", ["Yaws"]),
]
FACTSHEET_ONLY = ["Podoconiosis (non-filarial lymphoedema)", "Sporotrichosis", "Tungiasis"]
# how each of the 22 PROJECT groups relates to its WHO entry
RECON = {
    "Buruli ulcer": (1, "identical", ""), "Chagas disease": (2, "identical", ""),
    "dengue": (3, "subset_of_entry", "chikungunya (the other named disease) is NOT in the frozen project flag; evaluated as candidate extension"),
    "dracunculiasis": (4, "identical", ""), "echinococcosis": (5, "identical", ""),
    "foodborne trematodiases": (6, "project_defined_members", "WHO does not enumerate members; project chose clonorchiasis, opisthorchiasis, fascioliasis, paragonimiasis"),
    "human African trypanosomiasis": (7, "identical", ""), "leishmaniasis": (8, "identical", "project roots: leishmaniasis + visceral, cutaneous, mucocutaneous"),
    "leprosy": (9, "identical", ""), "lymphatic filariasis": (10, "identical_but_broad", "MONDO has only generic 'filariasis' (also covers onchocerciasis etc.): upper bound"),
    "mycetoma": (11, "split_component_of_entry", "WHO entry 11 is one grouping; project splits it into two groups"),
    "chromoblastomycosis": (11, "split_component_of_entry", "'other deep mycoses' not enumerated by WHO and not in the project flag (sporotrichosis has its own WHO fact sheet; WHO does not say it is part of this entry)"),
    "noma": (12, "identical_but_unmappable", "no MONDO term found"), "onchocerciasis": (13, "identical", ""), "rabies": (14, "identical", ""),
    "scabies": (15, "subset_of_entry", "'other ectoparasitoses' not enumerated by WHO; tungiasis has its own fact sheet, WHO does not say it is part of this entry; candidate extension only"),
    "schistosomiasis": (16, "identical", ""),
    "soil-transmitted helminthiases": (17, "project_defined_members", "WHO does not enumerate members; project chose ascariasis, trichuriasis, hookworm infectious disease, ancylostomiasis, necatoriasis"),
    "snakebite envenoming": (18, "identical", ""), "taeniasis/cysticercosis": (19, "identical", "taeniasis + cysticercosis"),
    "trachoma": (20, "identical", ""), "yaws": (21, "identical", ""),
}


def descendants(children, ids):
    seen, q = set(ids), deque(ids)
    while q:
        for ch in children.get(q.popleft(), ()):
            if ch not in seen:
                seen.add(ch)
                q.append(ch)
    return seen


def main():
    PK = REPO / "data" / "processed" / "primekg"
    out = REPO / "data" / "processed" / "ntd"
    out.mkdir(parents=True, exist_ok=True)
    terms = parse_mondo(REPO / "data" / "external" / "mondo.obo")
    children = build_children(terms)
    dis = pd.read_csv(PK / "diseases.csv", low_memory=False)
    edges = pd.read_csv(PK / "edges.csv", usecols=["source_id", "target_id", "primekg_relation"], low_memory=False)
    ind = edges[edges.primekg_relation == "indication"]
    z = np.load(PK / "splits" / "seed42.npz")
    comp = dis.mondo_resolved.fillna("").str.split("|")
    node_ids = dis.disease_id.tolist()
    pos_split = {sp: pd.Series(z[f"edges_{sp}"][1][z[f"y_{sp}"] == 1]).value_counts() for sp in ("train", "val", "test")}

    def group_stats(root_ids):
        desc = descendants(children, root_ids)
        hit = [i for i, cs in enumerate(comp) if any(c in desc for c in cs)]
        ids = {node_ids[i] for i in hit}
        npairs = int(ind.target_id.isin(ids).sum())
        sp = {k: int(sum(pos_split[k].get(i, 0) for i in hit)) for k in pos_split}
        status = dis.mapping_status.iloc[hit].value_counts().to_dict() if hit else {}
        return len(desc), len(hit), npairs, sp, status

    rows = []

    def add(who_entry, key, kind, roots, note):
        for mid, nm in roots:
            got = terms.get(mid, {}).get("name")
            if got is None or got.lower() != nm.lower():
                raise ValueError(f"MONDO {mid}: expected '{nm}', ontology has '{got}'")
        ids = [m for m, _ in roots]
        nd, nn, npairs, sp, st = group_stats(ids) if ids else (0, 0, 0, {"train": 0, "val": 0, "test": 0}, {})
        flagged = int(kind == "benchmark_group")
        n_flagged = int(((dis.ntd_groups.fillna("").str.split("|").map(lambda g: key in g)).sum())) if flagged else 0
        rows.append({
            "who_entry": who_entry, "group_key": key, "scope": kind,
            "in_who_list_footnote": int(kind != "who_factsheet_only"),
            "mondo_roots": "|".join(f"{m} ({n})" for m, n in roots), "mondo_names_verified_in_obo": int(bool(roots)),
            "n_mondo_terms_incl_descendants": nd, "n_primekg_disease_nodes": nn,
            "n_nodes_flagged_is_ntd_in_benchmark": n_flagged,
            "n_primekg_indication_pairs": npairs,
            "indication_pos_train": sp["train"], "indication_pos_val": sp["val"], "indication_pos_test": sp["test"],
            "node_mapping_status": json.dumps(st, sort_keys=True), "has_indication_pairs": int(npairs > 0),
            "in_frozen_benchmark_flag": flagged,
            "status": ("no_mondo_term" if not roots else "upper_bound" if key in BROAD and key != "noma" else
                       "mapped_no_indications" if npairs == 0 else "mapped"),
            "note": note, "evidence_source": WHO_URL if kind != "candidate_extension" else "MONDO name match (this repo)",
            "evidence_accessed": WHO_ACCESSED,
        })

    for who_entry, groups, ext in WHO:
        for g in groups:
            add(who_entry, g, "benchmark_group", NTD_ROOTS[g], BROAD.get(g, ""))
        for e in ext:
            mid, nm, why = EXTRA[e]
            add(who_entry, e, "candidate_extension", [(mid, nm)], why)
    for key in ("podoconiosis", "sporotrichosis"):
        mid, nm, why = EXTRA[key]
        add(f"(fact sheet only) {key}", key, "who_factsheet_only", [(mid, nm)], why)
    df = pd.DataFrame(rows)
    df.to_csv(out / "ntd_disease_mapping.csv", index=False)

    # ---- official WHO list (groupings vs diseases vs fact sheets) and reconciliation with the 22 frozen project groups ----
    assert [w[1] for w in WHO_OFFICIAL] == [w[0] for w in WHO], "WHO list differs between the two tables in this script"
    assert set(RECON) == set(NTD_ROOTS), "reconciliation must cover exactly the 22 frozen project groups"
    assert sum(len(w[4]) for w in WHO_OFFICIAL) + len(FACTSHEET_ONLY) == 25, "fact-sheet count (25 links on the page) does not add up"
    src = {"source_url": WHO_URL, "accessed": WHO_ACCESSED, "page_sha256_prefix": "f5472b1665a55723", "page_bytes": 146039,
           "evidence_log": "Docs/source_evidence/fetch_log_2026-11-10.json"}
    pd.DataFrame([{"entry_no": n, "who_grouping_as_listed": t, "kind_project_classification": k, "named_diseases": nd,
                   "fact_sheets_matching": " | ".join(fs), "n_fact_sheets": len(fs), "in_list_footnote": 1, **src} for n, t, k, nd, fs in WHO_OFFICIAL]
                 + [{"entry_no": None, "who_grouping_as_listed": "(fact sheet only; not named in the list footnote)", "kind_project_classification": "fact_sheet_only",
                     "named_diseases": f, "fact_sheets_matching": f, "n_fact_sheets": 1, "in_list_footnote": 0, **src} for f in FACTSHEET_ONLY]
                 ).to_csv(out / "who_official_ntd_list.csv", index=False)
    b = df[df.scope == "benchmark_group"].set_index("group_key")
    rec = []
    for g, (no, rel, note) in RECON.items():
        rec.append({"project_group": g, "who_entry_no": no, "who_entry": WHO_OFFICIAL[no - 1][1], "relation": rel, "note": note,
                    "has_mondo_term": int(b.loc[g, "mondo_roots"] != ""), "n_primekg_indication_pairs": int(b.loc[g, "n_primekg_indication_pairs"]),
                    "in_frozen_benchmark_flag": 1})
    pd.DataFrame(rec).to_csv(out / "ntd_group_reconciliation.csv", index=False)

    # ---- nested-root / double-counting audit across the 22 frozen groups ----
    g_desc, g_nodes, g_pairs = {}, {}, {}
    for g, roots in NTD_ROOTS.items():
        ids = [m for m, _ in roots]
        if not ids:
            g_desc[g], g_nodes[g], g_pairs[g] = set(), set(), set()
            continue
        desc = descendants(children, ids)
        hit = {node_ids[i] for i, cs in enumerate(comp) if any(c in desc for c in cs)}
        g_desc[g], g_nodes[g] = desc, hit
        g_pairs[g] = set(map(tuple, ind[ind.target_id.isin(hit)][["source_id", "target_id"]].values.tolist()))
    keys = list(NTD_ROOTS)
    ov = []
    for i, g1 in enumerate(keys):
        for g2 in keys[i + 1:]:
            sd, sn, sp_ = g_desc[g1] & g_desc[g2], g_nodes[g1] & g_nodes[g2], g_pairs[g1] & g_pairs[g2]
            if sd or sn or sp_:
                ov.append({"group_a": g1, "group_b": g2, "shared_mondo_terms": len(sd), "shared_primekg_nodes": len(sn), "shared_indication_pairs": len(sp_),
                           "a_contains_b_nodes": int(g_nodes[g2] <= g_nodes[g1] and bool(g_nodes[g2])), "b_contains_a_nodes": int(g_nodes[g1] <= g_nodes[g2] and bool(g_nodes[g1]))})
    pd.DataFrame(ov, columns=["group_a", "group_b", "shared_mondo_terms", "shared_primekg_nodes", "shared_indication_pairs", "a_contains_b_nodes", "b_contains_a_nodes"]).to_csv(out / "ntd_group_overlaps.csv", index=False)
    uni_nodes = set().union(*g_nodes.values())
    uni_pairs = set().union(*g_pairs.values())
    flag_nodes = set(dis.disease_id[dis.is_ntd == 1])
    overlap_audit = {"groups_with_overlap": len(ov), "sum_over_groups_nodes": sum(len(v) for v in g_nodes.values()), "unique_nodes": len(uni_nodes),
                     "sum_over_groups_indication_pairs": sum(len(v) for v in g_pairs.values()), "unique_indication_pairs": len(uni_pairs),
                     "frozen_flag_nodes_equal_union_of_groups": bool(flag_nodes == uni_nodes), "frozen_flag_nodes": len(flag_nodes)}

    bench = df[df.scope == "benchmark_group"]
    summary = {
        "who_entries_in_list_footnote": len(WHO),
        "benchmark_groups": len(bench),
        "benchmark_groups_with_mondo_term": int((bench.mondo_roots != "").sum()),
        "benchmark_groups_with_indication_pairs": int(bench.has_indication_pairs.sum()),
        "benchmark_indication_pairs_sum_over_groups": int(bench.n_primekg_indication_pairs.sum()),
        "benchmark_positives_by_split_sum_over_groups": {k: int(bench[f'indication_pos_{k}'].sum()) for k in ("train", "val", "test")},
        "who_entries_with_no_benchmark_group_having_indications": df[(df.scope == "benchmark_group")].groupby("who_entry").has_indication_pairs.max().eq(0).pipe(lambda s: sorted(s[s].index)),
        "candidate_extensions": df[df.scope != "benchmark_group"][["group_key", "scope", "n_primekg_indication_pairs", "has_indication_pairs"]].to_dict("records"),
        "frozen_flag_is_ntd_nodes": int(dis.is_ntd.sum()),
        "who_source": {"url": WHO_URL, "accessed": WHO_ACCESSED,
                       "caveat": "list says 'NTDs include'; no inclusion dates or criteria on the page; WHO headline 2026-10-15: new-NTD requests on hold pending criteria review (article not read)"},
        "overlap_audit": overlap_audit,
        "note": "sum over groups can exceed unique pairs/positives because a pair can fall under several groups (e.g. nested roots); see ntd_group_overlaps.csv",
    }
    (out / "ntd_mapping_summary.json").write_text(json.dumps(summary, indent=2, default=int), encoding="utf-8")
    print(df[["who_entry", "group_key", "scope", "n_primekg_disease_nodes", "n_primekg_indication_pairs", "indication_pos_test", "status"]].to_string(index=False))
    print(json.dumps({k: summary[k] for k in list(summary)[:7]}, indent=1, default=int))


if __name__ == "__main__":
    main()
