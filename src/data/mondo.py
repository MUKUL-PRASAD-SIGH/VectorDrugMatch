"""
src/data/mondo.py - MONDO ontology helpers shared by the PrimeKG audit and dataset builder.

* parse_mondo        read mondo.obo (is_a, DOID xrefs, obsolescence, replaced_by)
* resolve_status     follow replaced_by and say what happened to each id
* map_disease_nodes  PrimeKG disease node -> DOID mapping with per-node status (no node dropped)
* NTD_ROOTS          WHO NTD groups -> verified MONDO root terms (name checked at run time)
* ntd_node_groups    PrimeKG disease node -> list of NTD groups (root + descendants)

Mapping rules (conservative):
  * Only DOID xrefs qualified source="MONDO:equivalentTo" count as `exact`; others are `related`
    and never used to keep labels.
  * Obsolete ids are followed through `replaced_by` when it points to another MONDO term.
  * Grouped PrimeKG nodes ("a_b_c") are split into MONDO components: `mapped` if every component
    has an exact DOID, `partial` if some do.
  * One MONDO id with >1 exact DOIDs is `ambiguous` (kept, flagged, all DOIDs listed).
  * A DOID inherited from an ancestor is reported (`ancestor_doid`) but never counted as mapped.
"""
import re
from collections import defaultdict, deque
from pathlib import Path

import pandas as pd

# WHO NTD groups -> MONDO root term(s), chosen by exact term name in the MONDO release and
# verified at run time. The original bundle's who_ntd_list.csv DOIDs were wrong for 17/22 groups.
NTD_ROOTS = {
    "Buruli ulcer": [("MONDO:0000327", "Buruli ulcer disease")],
    "Chagas disease": [("MONDO:0001444", "Chagas disease")],
    "dengue": [("MONDO:0005502", "dengue disease")],
    "dracunculiasis": [("MONDO:0016472", "dracunculiasis")],
    "echinococcosis": [("MONDO:0005738", "echinococcosis")],
    "foodborne trematodiases": [("MONDO:0005705", "clonorchiasis"), ("MONDO:0005884", "opisthorchiasis"),
                                ("MONDO:0004668", "fascioliasis"), ("MONDO:0005895", "paragonimiasis")],
    "human African trypanosomiasis": [("MONDO:0005459", "human African trypanosomiasis")],
    "leishmaniasis": [("MONDO:0011989", "leishmaniasis"), ("MONDO:0005445", "visceral leishmaniasis"),
                      ("MONDO:0005446", "cutaneous leishmaniasis"), ("MONDO:0005859", "mucocutaneous leishmaniasis")],
    "leprosy": [("MONDO:0005124", "leprosy")],
    "lymphatic filariasis": [("MONDO:0016075", "filariasis")],     # BROAD: no LF-specific MONDO term
    "mycetoma": [("MONDO:0016823", "mycetoma")],
    "chromoblastomycosis": [("MONDO:0015908", "chromomycosis")],
    "noma": [],                                                      # no MONDO term found
    "onchocerciasis": [("MONDO:0017137", "onchocerciasis")],
    "rabies": [("MONDO:0019173", "rabies")],
    "scabies": [("MONDO:0004525", "scabies")],
    "schistosomiasis": [("MONDO:0015254", "schistosomiasis")],
    "soil-transmitted helminthiases": [("MONDO:0005654", "ascariasis"), ("MONDO:0005996", "trichuriasis"),
                                       ("MONDO:0005799", "hookworm infectious disease"),
                                       ("MONDO:0005645", "ancylostomiasis"), ("MONDO:0005870", "necatoriasis")],
    "snakebite envenoming": [("MONDO:0018669", "snakebite envenomation")],
    "taeniasis/cysticercosis": [("MONDO:0000367", "taeniasis"), ("MONDO:0015484", "cysticercosis")],
    "trachoma": [("MONDO:0001249", "trachoma")],
    "yaws": [("MONDO:0006019", "yaws")],
}
NTD_BROAD = {"lymphatic filariasis": "MONDO has only generic 'filariasis' (also covers onchocerciasis etc.) - upper bound",
             "noma": "no MONDO term; cannot be evaluated from the ontology"}


def parse_mondo(path: Path) -> dict:
    terms, cur = {}, None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line == "[Term]":
                cur = {"is_a": [], "doid_exact": set(), "doid_related": set(), "obsolete": False,
                       "replaced_by": None, "name": ""}
            elif line.startswith("[") and line.endswith("]"):
                cur = None
            elif cur is None:
                continue
            elif line.startswith("id: "):
                cur["id"] = line[4:].strip()
                terms[cur["id"]] = cur
            elif line.startswith("name: "):
                cur["name"] = line[6:]
            elif line.startswith("is_obsolete: true"):
                cur["obsolete"] = True
            elif line.startswith("replaced_by: MONDO:"):
                cur["replaced_by"] = line.split()[1]
            elif line.startswith("is_a: MONDO:"):
                cur["is_a"].append(re.match(r"is_a: (MONDO:\d+)", line).group(1))
            elif line.startswith("xref: DOID:"):
                m = re.match(r"xref: (DOID:\d+)(.*)", line)
                (cur["doid_exact"] if "MONDO:equivalentTo" in m.group(2) else cur["doid_related"]).add(m.group(1))
    return terms


def mondo_version(path: Path) -> str:
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("data-version:"):
                return line.split(":", 1)[1].strip()
    return "unknown"


def build_children(terms: dict) -> dict:
    children = defaultdict(set)
    for t in terms.values():
        for a in t["is_a"]:
            children[a].add(t["id"])
    return children


def pad(x) -> str:
    return "MONDO:" + str(x).zfill(7)


def resolve_status(terms: dict, mid: str):
    """Return (final_id, status); status in current / replaced / obsolete_no_replacement / not_in_ontology."""
    if mid not in terms:
        return mid, "not_in_ontology"
    seen, cur = set(), mid
    while terms[cur]["obsolete"]:
        rb = terms[cur]["replaced_by"]
        if not rb or rb not in terms or cur in seen:
            return cur, "obsolete_no_replacement"
        seen.add(cur)
        cur = rb
    return cur, ("replaced" if cur != mid else "current")


def ancestors_doid(terms: dict, mid: str):
    q, seen = deque(terms[mid]["is_a"]), set()
    while q:
        a = q.popleft()
        if a in seen or a not in terms:
            continue
        seen.add(a)
        if terms[a]["doid_exact"]:
            return sorted(terms[a]["doid_exact"])
        q.extend(terms[a]["is_a"])
    return []


def map_disease_nodes(dis: pd.DataFrame, terms: dict) -> pd.DataFrame:
    """dis: columns id, name, source (PrimeKG disease nodes). Returns one row per node, none dropped."""
    rows = []
    for r in dis.itertuples():
        comps = [pad(c) for c in r.id.split("_")] if (r.source == "MONDO_grouped" or "_" in r.id) else [pad(r.id)]
        grouped = len(comps) > 1
        info = []
        for c in comps:
            rc, ostat = resolve_status(terms, c)
            t = terms.get(rc)
            if t is None or t["obsolete"]:
                info.append((c, rc, ostat, "not_in_ontology" if t is None else "obsolete_unresolved", [], []))
            elif t["doid_exact"]:
                info.append((c, rc, ostat, "exact", sorted(t["doid_exact"]), []))
            elif t["doid_related"]:
                info.append((c, rc, ostat, "related_only", [], sorted(t["doid_related"])))
            else:
                info.append((c, rc, ostat, "no_doid", [], ancestors_doid(terms, rc)))
        n_exact = sum(1 for c in info if c[3] == "exact")
        all_doids = sorted({d for c in info for d in c[4]})
        if grouped:
            status = "mapped" if n_exact == len(info) else ("partial" if n_exact else "unmapped")
        else:
            c0 = info[0]
            status = ("ambiguous" if len(c0[4]) > 1 else "mapped") if c0[3] == "exact" else "unmapped_" + c0[3]
        rows.append({
            "primekg_id": r.id, "name": r.name, "source": r.source, "grouped": grouped,
            "mondo_ids": "|".join(c[0] for c in info), "mondo_resolved": "|".join(c[1] for c in info),
            "obsolete_status": "|".join(c[2] for c in info),
            "doid_exact": "|".join(all_doids),
            "doid_related": "|".join(sorted({d for c in info for d in c[5] if c[3] == "related_only"})),
            "ancestor_doid": "|".join(sorted({d for c in info for d in c[5] if c[3] == "no_doid"})),
            "n_components": len(info), "n_components_exact": n_exact,
            "was_obsolete": any(c[2] in ("replaced", "obsolete_no_replacement") for c in info), "status": status,
        })
    return pd.DataFrame(rows)


def ntd_descendants(terms: dict, children: dict) -> dict:
    """group -> set of MONDO ids (roots + descendants). Verifies every root's name."""
    out = {}
    for group, roots in NTD_ROOTS.items():
        for mid, expect in roots:
            got = terms.get(mid, {}).get("name")
            if got is None or got.lower() != expect.lower():
                raise ValueError(f"NTD root {mid} expected '{expect}' but MONDO has '{got}'")
        ids = [m for m, _ in roots]
        desc, q = set(ids), deque(ids)
        while q:
            for ch in children.get(q.popleft(), ()):
                if ch not in desc:
                    desc.add(ch)
                    q.append(ch)
        out[group] = desc
    return out


def ntd_node_groups(nm: pd.DataFrame, terms: dict, children: dict) -> dict:
    """PrimeKG disease node id -> sorted list of NTD groups (a node counts if ANY component is under a root)."""
    desc = ntd_descendants(terms, children)
    comp2groups = defaultdict(set)
    for g, ids in desc.items():
        for m in ids:
            comp2groups[m].add(g)
    res = {}
    for r in nm.itertuples():
        gs = set()
        for c in r.mondo_resolved.split("|"):
            gs |= comp2groups.get(c, set())
        if gs:
            res[r.primekg_id] = sorted(gs)
    return res
