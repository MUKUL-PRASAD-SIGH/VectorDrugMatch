"""
scripts/audit_hai_parsing.py - numeric and structural audit of the parsed HAI surveys (data/processed/hai/).

    python scripts/audit_hai_parsing.py

Checks (each reported PASS/WARN/FAIL with numbers; nothing is "fixed" silently):
  1. raw files: every file in data/external/downloads/hai_price_surveys still hashes to the SHA-1 recorded in Docs/HAI_DOWNLOAD_MANIFEST.md;
  2. survey identity: 3 surveys, each with 3 sectors in the detail pages, wage + currency + reference price list recorded;
  3. affordability: days_of_wages ~= median_treatment_price / daily wage of the lowest-paid government worker (source rounds days to 1 decimal);
  4. MPR consistency: the median-price file and the detail pages report the same MPR for the same survey/medicine/product type/sector;
  5. ranges and ordering: availability in [0,100], MPR >= 0, p25 <= MPR <= p75 where all three are present;
  6. duplicates on (survey, sector, medicine, product type);
  7. free-medicine handling: 'free' is kept as a status with an empty number (never 0);
  8. DrugBank mapping: ingredient-level only (strength and formulation are NOT used to choose a DrugBank id); tiers, unmapped and ambiguous listed separately;
  9. units/years: currency per survey, reference price list (MSH2003 vs MSH2010) => MPRs are NOT comparable across reference lists.
Writes data/processed/hai/hai_audit_report.json and Docs/HAI_AUDIT.md. Exit code 1 only on FAIL.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
H = REPO / "data" / "processed" / "hai"
SRC = REPO / "data" / "external" / "downloads" / "hai_price_surveys"
res, rows = {}, []


def chk(name, level, detail):
    rows.append({"check": name, "result": level, "detail": detail})
    print(f"  [{level}] {name}: {detail}")


def main():
    # 1. raw preservation vs tracked manifest
    man = (REPO / "Docs" / "HAI_DOWNLOAD_MANIFEST.md").read_text(encoding="utf8")
    exp = {m.group(1).split("/")[-1]: m.group(2) for m in re.finditer(r"\| (hai_price_surveys/[^|]+?) \|[^|]*\|[^|]*\| ([0-9a-f]{8}) \|", man)}
    bad, n = [], 0
    for f in SRC.rglob("*"):
        if f.is_file():
            n += 1
            if exp.get(f.name) and hashlib.sha1(f.read_bytes()).hexdigest()[:8] != exp[f.name]:
                bad.append(f.name)
    chk("raw files unchanged", "PASS" if (not bad and n == len(exp) == 15) else "FAIL", f"{n} files on disk, {len(exp)} in manifest, hash mismatches: {bad}")

    pa, mp, af = (pd.read_csv(H / f"{x}.csv", keep_default_na=False, low_memory=False) for x in ("hai_price_availability", "hai_median_price", "hai_affordability"))
    sv = pd.read_csv(H / "hai_surveys.csv")
    for d in (pa, mp, af):
        for c in d.columns:
            if d[c].dtype == object and c in ("mpr", "p25", "p75", "availability_pct", "n_orders_or_facilities", "median_price_ratio", "median_treatment_price", "days_of_wages"):
                d[c] = pd.to_numeric(d[c], errors="coerce")
    for c in ("mpr", "p25", "p75", "availability_pct"):
        pa[c] = pd.to_numeric(pa[c], errors="coerce")
    mp["median_price_ratio"] = pd.to_numeric(mp.median_price_ratio, errors="coerce")
    af["median_treatment_price"] = pd.to_numeric(af.median_treatment_price, errors="coerce")
    af["days_of_wages"] = pd.to_numeric(af.days_of_wages, errors="coerce")

    # 2. identity
    sec = pa.groupby("survey_id").sector.nunique()
    ok = len(sv) == 3 and (sec == 3).all() and sv.daily_wage_lowest_paid_govt_worker.notna().all() and sv.reference_price_list.notna().all()
    chk("survey identity", "PASS" if ok else "FAIL", f"{len(sv)} surveys; sectors per survey {sec.to_dict()}; wages {dict(zip(sv.survey_id, sv.daily_wage_lowest_paid_govt_worker))}; currency {dict(zip(sv.survey_id, sv.wage_currency))}")

    # 3. affordability recomputation
    wage = dict(zip(sv.survey_id, sv.daily_wage_lowest_paid_govt_worker))
    a = af[af.median_treatment_price.notna() & af.days_of_wages.notna()].copy()
    a["calc"] = a.median_treatment_price / a.survey_id.map(wage)
    a["abs_err"] = (a.calc - a.days_of_wages).abs()
    off = a[a.abs_err > 0.06]
    chk("affordability = price / daily wage", "PASS" if len(off) == 0 else "WARN",
        f"{len(a)} rows recomputed; max |error| {a.abs_err.max():.3f} days (source rounds to 0.1); rows off by >0.06: {len(off)}"
        + (f" e.g. {off[['survey_id','condition_and_medicine_raw','median_treatment_price','days_of_wages','calc']].head(3).values.tolist()}" if len(off) else ""))
    res["affordability_by_sector_rows"] = af.sector.value_counts().to_dict()

    # 4. MPR consistency: detail pages vs median-price file
    def key(s):
        return re.sub(r"\s+", " ", re.sub(r"\s-\s", " ", s)).strip().lower()
    sec_map = {"Public sector procurement prices": "public procurement", "Public sector patient prices": "public patient", "Private sector patient prices": "private patient"}
    d = pa[pa.mpr.notna()].assign(k=lambda x: x.medicine_raw.map(key), sec=lambda x: x.sector.map(sec_map))
    m = mp[mp.median_price_ratio.notna()].assign(k=lambda x: x.medicine_raw.map(key))
    j = d.merge(m, left_on=["survey_id", "k", "product_type", "sec"], right_on=["survey_id", "k", "product_type", "sector"], suffixes=("_detail", "_median"))
    j["diff"] = (j.mpr - j.median_price_ratio).abs()
    mism = j[j["diff"] > 0.011]
    liquid = mism.medicine_raw_detail.str.contains(r"suspension|drops|oral liquid|syrup|inhal", case=False) if len(mism) else pd.Series(dtype=bool)
    chk("MPR: detail pages vs median-price file", "PASS" if (len(j) > 0 and len(mism) == 0) else ("WARN" if len(j) else "FAIL"),
        f"{len(j)} comparable values joined; {len(j) - len(mism)} agree within 0.011; {len(mism)} differ (of {len(d)} detail MPR values, {len(m)} median-file values). "
        + (f"All differing values are in survey(s) {mism.survey_id.unique().tolist()}, product type(s) {mism.product_type.unique().tolist()}, "
           f"{int(liquid.sum())}/{len(mism)} are liquid/drop formulations ({sorted(set(mism.medicine_raw_detail))}); median-file value is {((mism.median_price_ratio / mism.mpr).min()):.2f}-{((mism.median_price_ratio / mism.mpr).max()):.2f}x the detail-page value. "
           "Both are source outputs, kept side by side; cause (unit standardisation of liquids?) is NOT established; MPR is not used in the equity score" if len(mism) else ""))
    res["mpr_mismatches"] = mism[["survey_id", "medicine_raw_detail", "product_type", "sec", "mpr", "median_price_ratio"]].to_dict("records") if len(mism) else []
    res["mpr_join_rows"] = int(len(j))

    # 5. ranges / ordering
    av = pa.availability_pct.dropna()
    chk("availability in [0,100]", "PASS" if ((av >= 0) & (av <= 100)).all() else "FAIL", f"{len(av)} values, min {av.min()}, max {av.max()}")
    neg = int((pa.mpr.dropna() < 0).sum() + (mp.median_price_ratio.dropna() < 0).sum())
    chk("MPR non-negative", "PASS" if neg == 0 else "FAIL", f"negative values: {neg}")
    o = pa[pa.mpr.notna() & pa.p25.notna() & pa.p75.notna()]
    viol = o[(o.p25 > o.mpr + 1e-9) | (o.mpr > o.p75 + 1e-9)]
    chk("p25 <= MPR <= p75", "PASS" if len(viol) == 0 else "WARN", f"{len(o)} rows with all three; violations: {len(viol)}")

    # 6. duplicates
    dup = pa.duplicated(["survey_id", "sector", "medicine_raw", "product_type"]).sum() + mp.duplicated(["survey_id", "medicine_raw", "product_type", "sector"]).sum()
    chk("no duplicate keys", "PASS" if dup == 0 else "FAIL", f"duplicates: {int(dup)}")

    # 7. free handling
    free = int((pa.mpr_status == "free").sum() + (mp.price_status == "free").sum())
    zero_as_value = int(((pa.mpr_status == "value") & (pa.mpr == 0)).sum())
    chk("'free' kept as status, not 0", "PASS" if zero_as_value == 0 else "WARN", f"{free} 'free' entries; numeric zeros recorded as values: {zero_as_value}")

    # 8. DrugBank mapping (ingredient level)
    med = pd.read_csv(H / "hai_medicines.csv", keep_default_na=False)
    multi = pa[pa.drugbank_map_status == "mapped"].groupby("drugbank_id").strength_form.nunique()
    chk("DrugBank mapping tiers", "PASS", f"{med.map_status.value_counts().to_dict()}; tiers {med.map_tier.value_counts().to_dict()}; unmapped {med[med.map_status == 'unmapped'].medicine_name.tolist()}; "
        f"ambiguous {med[med.map_status == 'ambiguous'].medicine_name.tolist()}")
    chk("formulation assumption", "WARN", f"mapping is ingredient-level: {int((multi > 1).sum())} mapped drugs have >1 strength/form in the surveys but share one DrugBank id; "
        "3 curated synonyms and 1 normalised name are tier 2/3 (see hai_medicines.csv note column)")

    # 9. units and years
    chk("units / reference lists", "WARN", f"currency {sv.wage_currency.unique().tolist()} (nominal local currency, years 2004/2005/2011, NOT inflation-adjusted); reference price lists {dict(zip(sv.survey_id, sv.reference_price_list))}: "
        "MPRs are only comparable within the same reference list; surveys are regional historical pilots, not current or global access")

    lv = pd.DataFrame(rows)
    res.update({"checks": rows, "n_fail": int((lv.result == "FAIL").sum()), "n_warn": int((lv.result == "WARN").sum())})
    (H / "hai_audit_report.json").write_text(json.dumps(res, indent=1, default=int), encoding="utf-8")
    md = ["# HAI survey parsing audit", "", "Generated by `scripts/audit_hai_parsing.py` from `data/processed/hai/`. Raw files are preserved and hash-checked against `Docs/HAI_DOWNLOAD_MANIFEST.md`.", "",
          "| check | result | detail |", "|---|---|---|"] + [f"| {r['check']} | {r['result']} | {str(r['detail']).replace('|', '/')} |" for r in rows]
    md += ["", "**Scope:** three Indian surveys (Karnataka Nov 2004, Maharashtra Jan 2005, Delhi Jul 2011). Prices are nominal local currency; MPR is the ratio of the median local price to the international reference price list named per survey. Not a current or global access measure."]
    (REPO / "Docs" / "HAI_AUDIT.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\nFAIL={res['n_fail']} WARN={res['n_warn']}")
    sys.exit(1 if res["n_fail"] else 0)


if __name__ == "__main__":
    main()
