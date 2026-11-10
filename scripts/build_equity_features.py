"""
scripts/build_equity_features.py - consolidated equity feature table and transparent NDPI for PrimeKG indication pairs.

    python scripts/build_equity_features.py

Inputs (each optional; a missing input leaves its component EMPTY, never 0):
  data/processed/primekg/{edges,drugs,diseases}.csv, splits/seed42.npz  - the frozen benchmark pairs
  data/processed/ihme/daly_by_ntd_group.csv    (scripts/process_ihme_daly.py)  -> burden component (DALY rate per NTD group)
  data/processed/eml/eml_drug_flags.csv        (scripts/process_who_eml.py)    -> essential-medicine component
  data/processed/hai/hai_price_availability.csv + hai_medicines.csv (scripts/parse_hai_surveys.py) -> access component (PILOT)
Output: data/processed/equity/equity_features.csv, ndpi_ntd_candidates.csv, equity_report.json

Components, each scaled to [0,1]:
  EML    1 if the drug is on the supplied WHO list, 0 if a list was supplied and the drug is not on it, EMPTY if no list.
  DALY   percentile rank of the disease's NTD-group DALY rate among the groups with data (EMPTY if no data; for a disease in
         several groups the group with the highest burden is used and flagged).
  ACCESS mean public+private PATIENT-price availability (lowest-price generic, % / 100) over the HAI surveys that cover the drug.
         Regional, historical (India 2004-2011) pilot evidence, NOT global access; affordability (days of wages) is reported
         as a separate column and is NOT part of the score (no defensible transform yet).
NDPI = sum(w_i * c_i) / sum(w_i) over the components with evidence (weights EML 0.45, DALY 0.45, ACCESS 0.10: a proposal, not an
established constant). `evidence_coverage` = sum of weights of available components. NDPI is EMPTY if no component is available.
Sensitivity: all weight triples on a 0.1 grid; Spearman correlation of each alternative ranking with the default ranking over
pairs with >= 2 components (reported "not computable" when fewer than 2 components have any evidence).
"""
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
PK, PR = REPO / "data" / "processed" / "primekg", REPO / "data" / "processed"
W = {"eml": 0.45, "daly": 0.45, "access": 0.10}


def ndpi(df, w):
    num = sum(w[k] * df[f"{k}_score"].fillna(0) * df[f"{k}_score"].notna() for k in w)
    den = sum(w[k] * df[f"{k}_score"].notna() for k in w)
    return (num / den).where(den > 0)


def main():
    out = PR / "equity"
    out.mkdir(parents=True, exist_ok=True)
    edges = pd.read_csv(PK / "edges.csv", usecols=["source_id", "target_id", "primekg_relation"], low_memory=False)
    ind = edges[edges.primekg_relation == "indication"].rename(columns={"source_id": "drug_id", "target_id": "disease_id"})[["drug_id", "disease_id"]]
    dis = pd.read_csv(PK / "diseases.csv", low_memory=False)[["disease_id", "disease_name", "is_ntd", "ntd_groups"]]
    z = np.load(PK / "splits" / "seed42.npz")
    drugs = pd.read_csv(PK / "drugs.csv", usecols=["drug_id", "name"])
    split_of = {}
    for sp in ("train", "val", "test"):
        e, yv = z[f"edges_{sp}"], z[f"y_{sp}"]
        for di, ds in zip(e[0][yv == 1], e[1][yv == 1]):
            split_of[(drugs.drug_id.iloc[di], dis.disease_id.iloc[ds])] = sp
    df = ind.merge(dis, on="disease_id", how="left").merge(drugs.rename(columns={"name": "drug_name"}), on="drug_id", how="left")
    df["split"] = [split_of.get((a, b), "") for a, b in zip(df.drug_id, df.disease_id)]
    df["ntd_group"] = df.ntd_groups.fillna("")
    avail = {"eml": False, "daly": False, "access": False}

    # ---- EML ----
    f = PR / "eml" / "eml_drug_flags.csv"
    df["eml_evidence"] = ""
    if f.exists():
        on = set(pd.read_csv(f).drug_id)
        comp_f = PR / "eml" / "eml_combination_components.csv"
        combo_only = set()
        if comp_f.exists():
            cc = pd.read_csv(comp_f, keep_default_na=False)
            combo_only = {i for ids in cc.drugbank_ids for i in str(ids).split("|") if i} - on
        # 1 = listed as a single-ingredient entry; EMPTY = appears only inside a fixed-dose combination (not counted, not called 0);
        # 0 = not on the list. A 0 can be wrong if the drug matches one of the EML single entries that could not be mapped (eml_unmatched.csv).
        df["eml_status"] = np.where(df.drug_id.isin(on), 1.0, np.where(df.drug_id.isin(combo_only), np.nan, 0.0))
        df["eml_evidence"] = np.where(df.drug_id.isin(on), "single_entry_on_list",
                                      np.where(df.drug_id.isin(combo_only), "combination_component_only", "not_on_list_or_entry_unmapped"))
        avail["eml"] = True
    else:
        df["eml_status"] = np.nan
    df["eml_score"] = df.eml_status

    # ---- DALY ----
    f = PR / "ihme" / "daly_by_ntd_group.csv"
    df["daly_rate"], df["daly_group_used"] = np.nan, ""
    if f.exists():
        g = pd.read_csv(f).dropna(subset=["daly_rate"])
        g["rank"] = g.daly_rate.rank(pct=True)
        rate, rk = dict(zip(g.ntd_group, g.daly_rate)), dict(zip(g.ntd_group, g["rank"]))
        best = []
        for grp in df.ntd_group:
            cands = [x for x in grp.split("|") if x in rate]
            best.append(max(cands, key=lambda x: rate[x]) if cands else "")
        df["daly_group_used"] = best
        df["daly_rate"] = [rate.get(b, np.nan) for b in best]
        df["daly_score"] = [rk.get(b, np.nan) for b in best]
        avail["daly"] = True
    else:
        df["daly_score"] = np.nan

    # ---- ACCESS (HAI pilot) ----
    f = PR / "hai" / "hai_price_availability.csv"
    df["availability"], df["affordability_days_private"], df["n_hai_surveys"] = np.nan, np.nan, 0
    if f.exists():
        pa = pd.read_csv(f)
        pa = pa[(pa.drugbank_map_status == "mapped") & (pa.product_type == "Lowest price generic") & pa.sector.str.contains("patient") & pa.availability_pct.notna()]
        av = pa.groupby("drugbank_id").agg(availability=("availability_pct", lambda s: s.mean() / 100), n_hai_surveys=("survey_id", "nunique"))
        df = df.drop(columns=["availability", "n_hai_surveys"]).merge(av, left_on="drug_id", right_index=True, how="left")
        df["n_hai_surveys"] = df.n_hai_surveys.fillna(0).astype(int)
        af = pd.read_csv(PR / "hai" / "hai_affordability.csv")
        af = af[(af.drugbank_map_status == "mapped") & (af.product_type == "Lowest price generic") & af.sector.str.contains("private", case=False) & af.days_of_wages.notna()]
        df["affordability_days_private"] = df.drug_id.map(af.groupby("drugbank_id").days_of_wages.mean())
        avail["access"] = True
    df["access_score"] = df.availability

    df["evidence_coverage"] = sum(W[k] * df[f"{k}_score"].notna() for k in W)
    df["n_components"] = sum(df[f"{k}_score"].notna().astype(int) for k in W)
    df["ndpi_score"] = ndpi(df, W)
    cols = ["drug_id", "drug_name", "disease_id", "disease_name", "ntd_group", "is_ntd", "split", "eml_status", "eml_evidence", "daly_rate", "daly_group_used",
            "availability", "affordability_days_private", "n_hai_surveys", "eml_score", "daly_score", "access_score", "n_components",
            "evidence_coverage", "ndpi_score"]
    df[cols].to_csv(out / "equity_features.csv", index=False)
    cand = df[(df.is_ntd == 1)][cols].sort_values(["ndpi_score"], ascending=False, na_position="last")
    cand.to_csv(out / "ndpi_ntd_candidates.csv", index=False)

    # ---- sensitivity ----
    sens = {"computable": False}
    two = df[df.n_components >= 2]
    if len(two) >= 10:
        base = ndpi(two, W)
        corr = []
        grid = [(a / 10, b / 10, (10 - a - b) / 10) for a, b in itertools.product(range(11), range(11)) if a + b <= 10]
        for we, wd, wa in grid:
            alt = ndpi(two, {"eml": we, "daly": wd, "access": wa})
            corr.append({"w_eml": we, "w_daly": wd, "w_access": wa, "spearman_vs_default": float(base.corr(alt, method="spearman"))})
        c = pd.DataFrame(corr)
        c.to_csv(out / "ndpi_weight_sensitivity.csv", index=False)
        sens = {"computable": True, "pairs": int(len(two)), "grid_points": len(c), "min_spearman": float(c.spearman_vs_default.min()),
                "median_spearman": float(c.spearman_vs_default.median())}
    n = len(df)
    rep = {"pairs": n, "ntd_pairs": int((df.is_ntd == 1).sum()), "inputs_present": avail, "weights_default": W,
           "component_coverage_pct_all_pairs": {k: round(100 * df[f"{k}_score"].notna().mean(), 2) for k in W},
           "component_coverage_pct_ntd_pairs": {k: round(100 * df.loc[df.is_ntd == 1, f"{k}_score"].notna().mean(), 2) for k in W},
           "eml_evidence_counts_all_pairs": df.eml_evidence.value_counts().to_dict(),
           "eml_unmapped_single_entries_possible_false_zeros": int(len(pd.read_csv(PR / "eml" / "eml_unmatched.csv"))) if (PR / "eml" / "eml_unmatched.csv").exists() else None,
           "pairs_with_ndpi": int(df.ndpi_score.notna().sum()), "ntd_pairs_with_ndpi": int(df.loc[df.is_ntd == 1, "ndpi_score"].notna().sum()),
           "n_components_distribution": df.n_components.value_counts().sort_index().to_dict(), "sensitivity": sens,
           "caveats": ["DALY (burden) is absent until a disease-specific IHME export is supplied: NDPI then reduces to the EML flag (+ the HAI pilot where available), "
                       "i.e. it is NOT a burden-aware equity ranking and must not be reported as one",
                       "EML status 0 means 'not on the list OR its entry could not be mapped' (see eml_unmapped_single_entries_possible_false_zeros); combination-only drugs are left empty",
                       "access = regional historical availability (India 2004-2011), not global access",
                       "weights 0.45/0.45/0.10 are a proposal; the sensitivity grid is computed only over pairs with >= 2 components and is not meaningful while DALY is absent"]}
    (out / "equity_report.json").write_text(json.dumps(rep, indent=2, default=int), encoding="utf-8")
    print(json.dumps(rep, indent=1, default=int))


if __name__ == "__main__":
    main()
