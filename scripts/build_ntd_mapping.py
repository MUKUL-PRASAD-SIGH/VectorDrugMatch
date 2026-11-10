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
        "note": "sum over groups can exceed unique pairs/positives because a pair can fall under several groups (e.g. nested roots)",
    }
    (out / "ntd_mapping_summary.json").write_text(json.dumps(summary, indent=2, default=int), encoding="utf-8")
    print(df[["who_entry", "group_key", "scope", "n_primekg_disease_nodes", "n_primekg_indication_pairs", "indication_pos_test", "status"]].to_string(index=False))
    print(json.dumps({k: summary[k] for k in list(summary)[:7]}, indent=1, default=int))


if __name__ == "__main__":
    main()
