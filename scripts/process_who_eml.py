"""
scripts/process_who_eml.py - map the extracted WHO Model List (scripts/extract_who_eml_pdf.py -> data/external/who_eml.csv) onto PrimeKG drugs.

    python scripts/extract_who_eml_pdf.py      # PDF -> who_eml.csv (once)
    python scripts/process_who_eml.py          # who_eml.csv -> data/processed/eml/*

Input columns used: name (required), entry_type (single | combination; derived from ' + ' if absent), section_code, section, list,
optional drugbank_id (if you add verified ids by hand, they win), edition. If who_eml.csv is absent the script exits WITHOUT writing
anything: EML status then stays UNKNOWN downstream (never 0).

Mapping tiers (DrugBank name index = PrimeKG drugs.csv; exact, no fuzzy matching; a name that hits >1 DrugBank id is `ambiguous`, never used):
  0 given_drugbank_id   id supplied in the file (verified by hand)
  1 exact_name          the full WHO name equals a DrugBank name (case/punctuation-normalised, British 'sulph' -> 'sulf')
  2 primary_or_alias    text before '(' or the text inside '(...)' equals a DrugBank name (e.g. 'epinephrine (adrenaline)'); if the two hit
                        DIFFERENT drugs the entry is ambiguous. Parenthesised QUALIFIERS (e.g. 'insulin (human, short-acting)') are not aliases
                        and simply stay unmapped when they do not match.
  3 salt_stripped       as tier 1 after removing salt words (sodium, hydrochloride, sulfate, ...)
  4 curated_inn_synonym WHO INN <-> US name pairs from CURATED_INN below; the target must exist as an EXACT DrugBank name
Combination products (' + '): NEVER counted as a single drug's EML status. Each component is mapped with the same tiers and written to
eml_combination_components.csv for transparency; a drug whose only EML presence is inside fixed-dose combinations has eml_status UNKNOWN->0
in build_equity_features only if you decide to count it, which this project does not (see Docs/EQUITY_DATA_SPECS.md).
Outputs (data/processed/eml/): eml_mapping_audit.csv (every entry + status/tier/candidates), eml_drug_flags.csv (single-ingredient entries mapped to
exactly one DrugBank id), eml_unmatched.csv, eml_combination_components.csv, eml_report.json.
The WHO list is CC BY-NC-SA 3.0 IGO: derived files stay in git-ignored data/ (Docs/LICENCE_AUDIT.md).
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
SALTS = r"\b(hydrochloride|hcl|sodium|potassium|sulphate|sulfate|phosphate|acetate|maleate|besylate|tartrate|citrate|succinate|mesylate|bromide|calcium|dihydrate|hydrobromide|fumarate)\b"
# WHO INN -> US name (single-ingredient only). Each target is looked up as an exact DrugBank name; if absent the entry stays unmapped.
CURATED_INN = {
    "paracetamol": "Acetaminophen", "salbutamol": "Albuterol", "rifampicin": "Rifampin", "ciclosporin": "Cyclosporine", "glibenclamide": "Glyburide",
    "aciclovir": "Acyclovir", "adrenaline": "Epinephrine", "noradrenaline": "Norepinephrine", "phenobarbitone": "Phenobarbital", "pethidine": "Meperidine",
    "isoprenaline": "Isoproterenol", "glyceryl trinitrate": "Nitroglycerin", "cefalexin": "Cephalexin", "colecalciferol": "Cholecalciferol",
    "beclometasone": "Beclomethasone dipropionate",
    # added after checking each target exists as an exact DrugBank name in PrimeKG's drug set (salt / word-order differences noted)
    "calcium folinate": "Leucovorin",                      # leucovorin calcium
    "glycerol": "Glycerin",
    "hyoscine butylbromide": "Butylscopolamine",
    "hyoscine hydrobromide": "Scopolamine",                # salt form not distinguished
    "charcoal, activated": "Activated charcoal",           # word order
    "p-aminosalicylate sodium": "Aminosalicylic acid",     # salt form not distinguished
    "leuprorelin": "Leuprolide",
    "all-trans retinoid acid": "Tretinoin",                # WHO spelling 'retinoid'; ATRA
    "amidotrizoate": "Diatrizoate",
    "diloxanide": "Diloxanide furoate",                    # formulation is the furoate
}


def norm1(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+, ]", "", re.sub(r"[-/]", " ", str(s).lower()).replace("sulphate", "sulfate").replace("sulph", "sulf"))).strip()


def norm2(s):
    return re.sub(r"\s+", " ", re.sub(SALTS, "", norm1(s))).strip()


def split_alias(name):
    m = re.match(r"^(.*)\s*\(([^()]*)\)\s*$", name)       # LAST parenthesised group is the alias/qualifier
    return (m.group(1).strip(), m.group(2).strip()) if m else (name.strip(), "")


class Mapper:
    def __init__(self, drugs):
        self.i1, self.i2 = {}, {}
        for d, n in zip(drugs.drug_id, drugs.name.astype(str)):
            self.i1.setdefault(norm1(n), set()).add(d)
            self.i2.setdefault(norm2(n), set()).add(d)

    def lookup(self, name):
        """-> (status, tier, ids)  status in mapped|ambiguous|unmapped"""
        prim, alias = split_alias(name)
        h = self.i1.get(norm1(name), set())
        if len(h) == 1:
            return "mapped", "1_exact_name", sorted(h)
        if len(h) > 1:
            return "ambiguous", "1_exact_name", sorted(h)
        hp, ha = self.i1.get(norm1(prim), set()), (self.i1.get(norm1(alias), set()) if alias else set())
        cand = hp | ha
        if len(cand) == 1:
            return "mapped", "2_primary_or_alias", sorted(cand)
        if len(cand) > 1:
            return "ambiguous", "2_primary_or_alias", sorted(cand)
        h2 = self.i2.get(norm2(prim), set())
        if len(h2) == 1:
            return "mapped", "3_salt_stripped", sorted(h2)
        if len(h2) > 1:
            return "ambiguous", "3_salt_stripped", sorted(h2)
        tgt = CURATED_INN.get(norm1(prim))
        if tgt:
            ht = self.i1.get(norm1(tgt), set())
            if len(ht) == 1:
                return "mapped", "4_curated_inn_synonym", sorted(ht)
        return "unmapped", "none", []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/external/who_eml.csv")
    a = ap.parse_args()
    p = REPO / a.input
    if not p.exists():
        sys.exit(f"{a.input} not found: EML status stays UNKNOWN downstream (nothing written).")
    eml = pd.read_csv(p, keep_default_na=False)
    if "name" not in eml.columns:
        sys.exit("who_eml.csv needs a `name` column")
    if "entry_type" not in eml.columns:
        eml["entry_type"] = eml.name.map(lambda n: "combination" if " + " in n else "single")
    dr = pd.read_csv(REPO / "data" / "processed" / "primekg" / "drugs.csv", usecols=["drug_id", "name"])
    mp = Mapper(dr)
    by_id = set(dr.drug_id)
    audit, comps = [], []
    for r in eml.itertuples():
        given = str(getattr(r, "drugbank_id", "") or "").strip()
        if r.entry_type == "combination":
            parts = [x.strip() for x in r.name.split(" + ")]
            for k, part in enumerate(parts, 1):
                st, tier, ids = mp.lookup(part)
                comps.append({"eml_entry": r.name, "section_code": getattr(r, "section_code", ""), "component_no": k, "component": part,
                              "status": st, "tier": tier, "drugbank_ids": "|".join(ids)})
            audit.append({"eml_name": r.name, "entry_type": "combination", "section_code": getattr(r, "section_code", ""), "list": getattr(r, "list", ""),
                          "status": "combination_not_counted", "tier": "", "drugbank_ids": "", "n_components": len(parts)})
            continue
        if given in by_id:
            st, tier, ids = "mapped", "0_given_drugbank_id", [given]
        else:
            st, tier, ids = mp.lookup(r.name)
        audit.append({"eml_name": r.name, "entry_type": "single", "section_code": getattr(r, "section_code", ""), "section": getattr(r, "section", ""),
                      "list": getattr(r, "list", ""), "status": st, "tier": tier, "drugbank_ids": "|".join(ids), "n_components": 1,
                      "edition": getattr(r, "edition", "")})
    au = pd.DataFrame(audit)
    cp = pd.DataFrame(comps)
    ok = au[(au.entry_type == "single") & (au.status == "mapped")].copy()
    ok["drug_id"] = ok.drugbank_ids
    flags = ok.groupby("drug_id").agg(eml_name=("eml_name", lambda s: " | ".join(sorted(set(s)))), matched_by=("tier", lambda s: "|".join(sorted(set(s)))),
                                      sections=("section_code", lambda s: "|".join(sorted(set(map(str, s))))),
                                      eml_list=("list", lambda s: "core" if "core" in set(s) else "complementary"), n_entries=("eml_name", "size")).reset_index()
    flags["eml_status"] = 1
    flags["edition"] = eml.edition.iloc[0] if "edition" in eml else ""
    out = REPO / "data" / "processed" / "eml"
    out.mkdir(parents=True, exist_ok=True)
    au.to_csv(out / "eml_mapping_audit.csv", index=False)
    flags.to_csv(out / "eml_drug_flags.csv", index=False)
    au[(au.entry_type == "single") & (au.status != "mapped")].to_csv(out / "eml_unmatched.csv", index=False)
    cp.to_csv(out / "eml_combination_components.csv", index=False)
    single = au[au.entry_type == "single"]
    rep = {"eml_entries": int(len(au)), "single_entries": int(len(single)), "combination_entries": int((au.entry_type == "combination").sum()),
           "single_status": single.status.value_counts().to_dict(), "single_mapped_by_tier": single[single.status == "mapped"].tier.value_counts().to_dict(),
           "distinct_primekg_drugs_flagged": int(len(flags)), "flags_by_list": flags.eml_list.value_counts().to_dict(),
           "combination_components": {"components": int(len(cp)), "status": cp.status.value_counts().to_dict() if len(cp) else {}},
           "ambiguous_entries": single[single.status == "ambiguous"].eml_name.tolist(), "curated_inn_pairs_used": sorted(set(
               n for n in single[single.tier == "4_curated_inn_synonym"].eml_name)),
           "note": "single-ingredient entries only count toward eml_status; combinations are reported separately; unmapped entries include vaccines, biologics, blood products and medicines absent from PrimeKG's DrugBank drug set"}
    (out / "eml_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
