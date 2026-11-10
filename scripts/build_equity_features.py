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
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.scoring.eml_status import classify  # noqa: E402

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
        # Zeros only where defensible (src/scoring/eml_status.py): a drug whose name shares a stem with an UNMAPPED WHO single entry is
        # UNRESOLVED (empty), combination-only is empty; the remaining zeros mean "no candidate entry found", not a verified negative.
        um = PR / "eml" / "eml_unmatched.csv"
        um_names = pd.read_csv(um, keep_default_na=False).eml_name.tolist() if um.exists() else []
        res = [classify(d, n, on, combo_only, um_names) for d, n in zip(df.drug_id, df.drug_name)]
        df["eml_evidence"] = [r[0] for r in res]
        df["eml_status"] = [r[1] for r in res]
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
    def _grid(sub, fname):
        """Spearman of every alternative weight triple (0.1 grid) vs the default weights, over `sub` (pairs with >= 2 components)."""
        if len(sub) < 10:
            return {"computable": False, "pairs": int(len(sub)), "reason": "fewer than 10 pairs"}
        base = ndpi(sub, W)
        rows = []
        for a_, b_ in itertools.product(range(11), range(11)):
            if a_ + b_ > 10:
                continue
            we, wd, wa = a_ / 10, b_ / 10, (10 - a_ - b_) / 10
            rows.append({"w_eml": we, "w_daly": wd, "w_access": wa, "spearman_vs_default": float(base.corr(ndpi(sub, {"eml": we, "daly": wd, "access": wa}), method="spearman"))})
        c = pd.DataFrame(rows)
        c.to_csv(out / fname, index=False)
        v = c.spearman_vs_default.dropna()
        return {"computable": True, "pairs": int(len(sub)), "grid_points": int(len(c)), "grid_points_undefined": int(c.spearman_vs_default.isna().sum()),
                "min_spearman": float(v.min()), "median_spearman": float(v.median())}

    two = df[df.n_components >= 2]
    sens = _grid(two, "ndpi_weight_sensitivity.csv")                                         # all pairs with >= 2 components (mostly EML + access, no burden)
    # burden-aware subset: only pairs that have a DALY score can say anything about the burden weight
    burden_pairs = two[two.daly_score.notna()]
    sens_burden = _grid(burden_pairs, "ndpi_weight_sensitivity_burden_pairs.csv")
    sens_burden["note"] = "pairs with a DALY score and >= 2 components; all are NTD pairs"
    n = len(df)
    rep = {"pairs": n, "ntd_pairs": int((df.is_ntd == 1).sum()), "inputs_present": avail, "weights_default": W,
           "component_coverage_pct_all_pairs": {k: round(100 * df[f"{k}_score"].notna().mean(), 2) for k in W},
           "component_coverage_pct_ntd_pairs": {k: round(100 * df.loc[df.is_ntd == 1, f"{k}_score"].notna().mean(), 2) for k in W},
           "eml_evidence_counts_all_pairs": df.eml_evidence.value_counts().to_dict(),
           "denominators": {"all_pairs": n, "all_drugs": int(df.drug_id.nunique()), "ntd_pairs": int((df.is_ntd == 1).sum()),
                            "ntd_drugs": int(df.loc[df.is_ntd == 1, "drug_id"].nunique())},
           "eml_evidence_pairs_all": df.eml_evidence.value_counts().to_dict(),
           "eml_evidence_drugs_all": df.drop_duplicates("drug_id").eml_evidence.value_counts().to_dict(),
           "eml_evidence_pairs_ntd": df[df.is_ntd == 1].eml_evidence.value_counts().to_dict(),
           "eml_evidence_drugs_ntd": df[df.is_ntd == 1].drop_duplicates("drug_id").eml_evidence.value_counts().to_dict(),
           "eml_confirmed_positive_pct": round(100 * (df.eml_evidence == "confirmed_positive_single_entry").mean(), 2),
           "eml_unresolved_pct": round(100 * (df.eml_evidence == "unresolved_possible_unmapped_entry").mean(), 2),
           "eml_unmapped_single_entries_possible_false_zeros": int(len(pd.read_csv(PR / "eml" / "eml_unmatched.csv"))) if (PR / "eml" / "eml_unmatched.csv").exists() else None,
           "burden_aware_pairs": int(df.daly_score.notna().sum()), "burden_aware_ntd_pairs": int(df.loc[df.is_ntd == 1, "daly_score"].notna().sum()),
           "ntd_pairs_without_burden": int(df.loc[df.is_ntd == 1, "daly_score"].isna().sum()), "sensitivity_burden_pairs": sens_burden,
           "pairs_with_ndpi": int(df.ndpi_score.notna().sum()), "ntd_pairs_with_ndpi": int(df.loc[df.is_ntd == 1, "ndpi_score"].notna().sum()),
           "n_components_distribution": df.n_components.value_counts().sort_index().to_dict(), "sensitivity": sens,
           "caveats": ["DALY (burden) exists only for NTD diseases whose group maps to an exported GBD cause (see daly_by_ntd_group.csv); NDPI is burden-aware ONLY for pairs with a DALY score (burden_aware_pairs); for every other pair it reduces to the EML flag (+ HAI where available) and must not be called burden-aware",
                       "DALY score = percentile rank of the group rate among the groups with data (15 groups); for a disease in several groups the group with the highest rate is used",
                       "EML: 1 = confirmed positive; 0 = no candidate entry found after all mapping tiers (not a proof of absence); empty = combination-only or unresolved (name overlaps an unmapped WHO entry). "
                       "'component_coverage_pct' for EML counts 0s, so see eml_evidence_counts_all_pairs and eml_confirmed_positive_pct for real evidence",
                       "access = regional historical availability (India 2004-2011), not global access",
                       "weights 0.45/0.45/0.10 are a proposal; the sensitivity grid is computed only over pairs with >= 2 components and is not meaningful while DALY is absent"]}
    (out / "equity_report.json").write_text(json.dumps(rep, indent=2, default=int), encoding="utf-8")
    print(json.dumps(rep, indent=1, default=int))


if __name__ == "__main__":
    main()
