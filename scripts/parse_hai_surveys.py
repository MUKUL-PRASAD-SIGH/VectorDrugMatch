"""
scripts/parse_hai_surveys.py - parse the three HAI/WHO medicine price surveys into structured, provenance-preserving tables.

    python scripts/parse_hai_surveys.py

Input : data/external/downloads/hai_price_surveys/<survey>/*.xls|*.php   (HTML tables saved with Excel/PHP extensions)
Output: data/processed/hai/
    hai_price_availability.csv   survey, sector, medicine, product type, MPR, p25, p75, availability % (or #orders)
    hai_median_price.csv         survey, medicine, product type, sector, median price ratio (Proc/Pub/Priv)
    hai_affordability.csv        survey, condition+medicine (raw), product type, sector, median treatment price, days of wages
    hai_medicines.csv            unique medicine names with parsed strength/form and DrugBank mapping (tier + status)
    hai_surveys.csv              per-survey metadata (location, date, reference price list, wage) + source file SHA-1
    hai_parse_report.json        row counts, mapping coverage, parse warnings

Scope: regional, historical PILOT evidence (Karnataka 2004-11, Maharashtra 2005-01, Delhi 2011-07). Not a global access score.
Values like "free" are kept as price_status="free" with an empty number, never as 0. Raw strings are always retained.
DrugBank mapping: exact normalised-name match only (tier 1 exact; tier 2 after British->US spelling + salt-word removal);
>1 DrugBank id for a name = "ambiguous" (not used); no fuzzy matching.
"""
import hashlib
import io
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "data" / "external" / "downloads" / "hai_price_surveys"
OUT = REPO / "data" / "processed" / "hai"
PK = REPO / "data" / "processed" / "primekg"
warn = []


def sha1(p):
    return hashlib.sha1(Path(p).read_bytes()).hexdigest()


def read_tables(p):
    return pd.read_html(io.StringIO(Path(p).read_text(encoding="utf8", errors="replace")))


def clean(x):
    return None if (x is None or (isinstance(x, float) and np.isnan(x)) or str(x).strip() in ("", "nan")) else re.sub(r"\s+", " ", str(x)).strip()


def num(x):
    """-> (value, status) status in value|free|missing|other"""
    s = clean(x)
    if s is None:
        return np.nan, "missing"
    if s.lower() == "free":
        return np.nan, "free"
    try:
        return float(s.replace("%", "").replace(",", "").strip()), "value"
    except ValueError:
        return np.nan, "other:" + s[:20]


def survey_meta(folder, files):
    t = " ".join(clean(c) or "" for c in read_tables(files["median"])[0].iloc[:, 0].head(3).tolist())
    loc_date = re.search(r"Medicine prices (.+?)(?: \*price|$)", t)
    ref = re.search(r"International reference price: (\w+)", " ".join(map(str, read_tables(files["median"])[0].iloc[:, 0].head(6))))
    aff = read_tables(files["afford"])[0].astype(str).values.ravel().tolist()
    wage = re.search(r"Daily wage of lowest paid government worker \(in local currency\)\s+(\d+(?:\.\d+)?)\s+([A-Za-z ]+?)\s{0,3}(?:procurement|$)", " ".join(aff))
    return {"survey_id": folder.name, "location_and_date": loc_date.group(1).strip() if loc_date else None,
            "reference_price_list": ref.group(1) if ref else None,
            "daily_wage_lowest_paid_govt_worker": float(wage.group(1)) if wage else None,
            "wage_currency": wage.group(2).strip() if wage else None,
            "source_files": {k: v.name for k, v in files.items()},
            "source_sha1": {k: sha1(v)[:12] for k, v in files.items()}}


def split_medicine(raw):
    """'Amitriptyline - 25 mg cap/tab' or 'Amoxicillin 125 mg/5ml suspension' -> (name, strength_form)"""
    raw = re.sub(r"\s+", " ", raw).strip()
    m = re.match(r"^(.*?)\s*-\s*(\d.*)$", raw) or re.match(r"^(.*?)\s+(\d.*)$", raw)
    return (m.group(1).strip(), m.group(2).strip()) if m else (raw, "")


def parse_detail(path, survey):
    t = read_tables(path)[1]
    sector = clean(t.iloc[0, 0])
    ref = re.search(r"reference price: (\w+)", clean(t.iloc[1, 0]) or "")
    last = clean(t.iloc[3, t.shape[1] - 1]) or ""
    rows, med = [], None
    for i in range(4, len(t)):
        c0, ptype = clean(t.iloc[i, 0]), clean(t.iloc[i, 2])
        if c0 and not ptype:
            med = c0
            continue
        if med and ptype:
            mpr, mst = num(t.iloc[i, 3])
            p25, _ = num(t.iloc[i, 4])
            p75, _ = num(t.iloc[i, 5])
            av, ast = num(t.iloc[i, 6])
            name, sf = split_medicine(med)
            rows.append({"survey_id": survey, "sector": sector, "medicine_raw": med, "medicine_name": name, "strength_form": sf,
                         "product_type": ptype, "mpr": mpr, "mpr_status": mst, "p25": p25, "p75": p75,
                         "availability_pct": av if "Availab" in last else np.nan,
                         "n_orders_or_facilities": av if "orders" in last else np.nan, "last_col_status": ast,
                         "reference_price_list": ref.group(1) if ref else None, "source_file": path.name})
    return rows


def parse_median(path, survey):
    t = read_tables(path)[0]
    types = t.iloc[4].tolist()
    sect = t.iloc[5].tolist()
    cur, rows, other_cols = None, [], 0
    for j in range(1, t.shape[1]):
        cur = clean(types[j]) or cur
        types[j] = cur
    for i in range(6, len(t)):
        med = clean(t.iloc[i, 0])
        if not med:
            continue
        for j in range(1, t.shape[1]):
            s = clean(sect[j])
            if not s:                                        # the two unnamed columns per block
                if clean(t.iloc[i, j]):
                    other_cols += 1
                continue
            v, st = num(t.iloc[i, j])
            if st == "missing":
                continue
            name, sf = split_medicine(med)
            rows.append({"survey_id": survey, "medicine_raw": med, "medicine_name": name, "strength_form": sf,
                         "product_type": types[j], "sector": {"Proc": "public procurement", "Pub": "public patient", "Priv": "private patient"}.get(s, s),
                         "median_price_ratio": v, "price_status": st, "source_file": path.name})
    if other_cols:
        warn.append(f"{survey}: {other_cols} non-empty values in unnamed columns of median-price file were not parsed")
    return rows


def parse_afford(path, survey, known_names):
    t = read_tables(path)[1]
    sectors = []
    cur = None
    for j in range(2, t.shape[1], 2):
        cur = clean(t.iloc[0, j]) or cur
        sectors.append(cur)
    rows, cond_med = [], None
    for i in range(3, len(t)):
        c0, ptype = clean(t.iloc[i, 0]), clean(t.iloc[i, 1])
        is_header = c0 and (clean(t.iloc[i, 1]) == c0 or ptype is None)
        if c0 and (ptype is None or ptype == c0):
            cond_med = c0
            continue
        if cond_med and ptype:
            for k, sec in enumerate(sectors):
                price, pst = num(t.iloc[i, 2 + 2 * k])
                days, dst = num(t.iloc[i, 3 + 2 * k])
                if pst == "missing" and dst == "missing":
                    continue
                rows.append({"survey_id": survey, "condition_and_medicine_raw": cond_med, "product_type": ptype, "sector": sec,
                             "median_treatment_price": price, "price_status": pst, "days_of_wages": days, "source_file": path.name})
    # the condition and medicine are concatenated in one cell: recover the medicine as the LONGEST known generic name contained in it
    df = pd.DataFrame(rows)
    if len(df):
        low = df.condition_and_medicine_raw.str.lower()
        names = sorted(known_names, key=len, reverse=True)
        found = []
        for s in low:
            hit = next((n for n in names if n and n in s), None)
            found.append(hit)
        df["medicine_name_recovered"] = found
        df["condition_recovered"] = [r[: r.lower().find(h)].strip() if h else None for r, h in zip(df.condition_and_medicine_raw, found)]
    return df


SALTS = r"\b(hydrochloride|hcl|sodium|potassium|sulphate|sulfate|phosphate|acetate|maleate|besylate|tartrate|citrate|succinate|mesylate|bromide|calcium|dihydrate)\b"


# TIER 3: curated INN <-> US name synonyms (single-ingredient products only). Each target must exist as an exact DrugBank name.
INN_SYNONYMS = {
    "paracetamol": "Acetaminophen", "aciclovir": "Acyclovir", "glibenclamide": "Glyburide",
    "phenobarbitone": "Phenobarbital",
    "beclometasone": "Beclomethasone dipropionate",   # inhaler: salt form (dipropionate) assumed - flagged in the note column
}


def norm1(s):
    return re.sub(r"[^a-z0-9+ ]", "", s.lower().replace("sulphate", "sulfate")).strip()


def norm2(s):
    return re.sub(r"\s+", " ", re.sub(SALTS, "", norm1(s))).strip()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    surveys, pa, mp, af = [], [], [], []
    for folder in sorted(p for p in SRC.iterdir() if p.is_dir()):
        sid = folder.name
        files = {"median": next(folder.glob("median_price_by_medicine_excel*.xls")), "afford": next(folder.glob("affordability_excel*.xls"))}
        surveys.append(survey_meta(folder, files))
        for p in sorted(folder.glob("price_availability_survey_detail_excel*.php")):
            pa += parse_detail(p, sid)
        mp += parse_median(files["median"], sid)
        surveys[-1]["detail_files"] = sorted(p.name for p in folder.glob("price_availability_survey_detail_excel*.php"))
    pa, mp = pd.DataFrame(pa), pd.DataFrame(mp)
    known = set(pd.concat([pa.medicine_name, mp.medicine_name]).str.lower())
    for folder in sorted(p for p in SRC.iterdir() if p.is_dir()):
        af.append(parse_afford(next(folder.glob("affordability_excel*.xls")), folder.name, known))
    af = pd.concat(af, ignore_index=True)

    # --- unique medicines + DrugBank mapping (exact normalised names only) ---
    dr = pd.read_csv(PK / "drugs.csv", usecols=["drug_id", "name"])
    idx1, idx2 = {}, {}
    for d, n in zip(dr.drug_id, dr.name.astype(str)):
        idx1.setdefault(norm1(n), set()).add(d)
        idx2.setdefault(norm2(n), set()).add(d)
    med = (pd.concat([pa[["survey_id", "medicine_name", "strength_form"]], mp[["survey_id", "medicine_name", "strength_form"]]])
           .assign(medicine_name=lambda d: d.medicine_name.str.strip())
           .groupby("medicine_name").agg(n_surveys=("survey_id", "nunique"), surveys=("survey_id", lambda s: "|".join(sorted(set(s)))),
                                         strengths_forms=("strength_form", lambda s: "|".join(sorted({x for x in s if x}))[:200])).reset_index())
    maps = []
    for n in med.medicine_name:
        n1, n2 = norm1(n), norm2(n)
        if len(idx1.get(n1, ())) == 1:
            maps.append((next(iter(idx1[n1])), "1_exact_name", "mapped"))
        elif len(idx1.get(n1, ())) > 1:
            maps.append(("|".join(sorted(idx1[n1])), "1_exact_name", "ambiguous"))
        elif len(idx2.get(n2, ())) == 1 and n2:
            maps.append((next(iter(idx2[n2])), "2_normalised_name", "mapped"))
        elif len(idx2.get(n2, ())) > 1:
            maps.append(("|".join(sorted(idx2[n2])), "2_normalised_name", "ambiguous"))
        elif n.lower() in INN_SYNONYMS and len(idx1.get(norm1(INN_SYNONYMS[n.lower()]), ())) == 1:
            maps.append((next(iter(idx1[norm1(INN_SYNONYMS[n.lower()])])), "3_curated_inn_synonym", "mapped"))
        else:
            maps.append(("", "none", "unmapped"))
    med["drugbank_id"], med["map_tier"], med["map_status"] = zip(*maps)
    med["note"] = np.where(med.medicine_name.str.contains(r"[/+]|\band\b|^co-", case=False), "combination product: not mapped (single-ingredient rule)", "")
    med.loc[med.map_tier == "3_curated_inn_synonym", "note"] = "curated INN->US name synonym; verify"
    med.loc[med.medicine_name.str.lower() == "beclometasone", "note"] = "curated INN synonym; salt form (dipropionate) assumed for the inhaler"
    # affordability medicine names -> the same mapping via the recovered generic name
    m_idx = {r.medicine_name.lower(): (r.drugbank_id, r.map_status) for r in med.itertuples()}
    af["drugbank_id"] = af.medicine_name_recovered.map(lambda n: m_idx.get(n, ("", ""))[0] if n else "")
    af["drugbank_map_status"] = af.medicine_name_recovered.map(lambda n: m_idx.get(n, ("", "unmapped"))[1] if n else "no_medicine_recovered")
    for df in (pa, mp):
        df["drugbank_id"] = df.medicine_name.str.strip().str.lower().map(lambda n: m_idx.get(n, ("", ""))[0])
        df["drugbank_map_status"] = df.medicine_name.str.strip().str.lower().map(lambda n: m_idx.get(n, ("", "unmapped"))[1])

    pa.to_csv(OUT / "hai_price_availability.csv", index=False)
    mp.to_csv(OUT / "hai_median_price.csv", index=False)
    af.to_csv(OUT / "hai_affordability.csv", index=False)
    med.to_csv(OUT / "hai_medicines.csv", index=False)
    pd.DataFrame(surveys).to_csv(OUT / "hai_surveys.csv", index=False)

    rep = {
        "surveys": [{k: s[k] for k in ("survey_id", "location_and_date", "reference_price_list", "daily_wage_lowest_paid_govt_worker", "wage_currency")} for s in surveys],
        "rows": {"price_availability": len(pa), "median_price": len(mp), "affordability": len(af), "unique_medicines": len(med)},
        "rows_by_survey": {"price_availability": pa.survey_id.value_counts().to_dict(), "median_price": mp.survey_id.value_counts().to_dict(),
                           "affordability": af.survey_id.value_counts().to_dict()},
        "sectors_price_availability": pa.groupby("survey_id").sector.unique().map(list).to_dict(),
        "status_counts": {"mpr_status": pa.mpr_status.value_counts().to_dict(), "median_price_status": mp.price_status.value_counts().to_dict(),
                          "affordability_price_status": af.price_status.value_counts().to_dict()},
        "drugbank_mapping": {"medicines": med.map_status.value_counts().to_dict(), "tiers": med.map_tier.value_counts().to_dict(),
                             "unmapped_names": med[med.map_status == "unmapped"].medicine_name.tolist(),
                             "ambiguous_names": med[med.map_status == "ambiguous"].medicine_name.tolist(),
                             "affordability_rows_medicine_recovered_pct": round(100 * (af.medicine_name_recovered.notna()).mean(), 1)},
        "warnings": warn,
        "scope": "regional historical pilot evidence (3 Indian surveys); not a global access score",
    }
    (OUT / "hai_parse_report.json").write_text(json.dumps(rep, indent=2, default=int), encoding="utf-8")
    print(json.dumps(rep, indent=1, default=int)[:3500])


if __name__ == "__main__":
    main()
