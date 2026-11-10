"""
scripts/process_ihme_daly.py - validate and process an IHME GBD export into per-NTD-group DALY rates.

    python scripts/process_ihme_daly.py [--year 2023] [--input data/external/downloads/ihme_gbd]
    python scripts/process_ihme_daly.py --selftest            # tests the validator on tiny SYNTHETIC frames (nothing is saved)

Required export (see Docs/EQUITY_DATA_SPECS.md): measure = DALYs, metric = Rate, location = Global, sex = Both,
age = All ages (or Age-standardized), one year, causes = the NTD causes. The processor REFUSES:
  * exports whose measure is not DALYs, or metric not Rate (e.g. the 1 KB all-cause Deaths stub currently in the downloads folder);
  * several rows for the same cause after filtering (it never averages heterogeneous rows);
  * mixed years/locations/sexes/ages unless pinned by the flags.
GBD cause names are mapped to WHO NTD groups through the explicit table below; groups with no matching cause stay EMPTY (NaN),
never 0; groups made of several GBD causes are summed ONLY if all parts are present (rates over one population add) and
are marked partial otherwise. Unmatched GBD cause names are printed so the table can be extended after inspecting the real file.
Output: data/processed/ihme/daly_by_ntd_group.csv + daly_report.json (with source SHA-1).
"""
import argparse
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
# expected GBD cause names per WHO NTD group (benchmark group keys from src/data/mondo.NTD_ROOTS). EXTEND after seeing the real export.
GBD_CAUSES = {
    "Chagas disease": ["Chagas disease"],
    "dengue": ["Dengue"],
    "echinococcosis": ["Cystic echinococcosis"],
    "foodborne trematodiases": ["Food-borne trematodiases"],
    "human African trypanosomiasis": ["African trypanosomiasis"],
    "leishmaniasis": ["Leishmaniasis"],                      # the export has the parent cause (id 347); see MAPPING_NOTES
    "leprosy": ["Leprosy"],
    "lymphatic filariasis": ["Lymphatic filariasis"],
    "onchocerciasis": ["Onchocerciasis"],
    "rabies": ["Rabies"],
    "schistosomiasis": ["Schistosomiasis"],
    "soil-transmitted helminthiases": ["Ascariasis", "Trichuriasis", "Hookworm disease"],
    "trachoma": ["Trachoma"],
    "dracunculiasis": ["Guinea worm disease"],
    "scabies": ["Scabies"],
    "taeniasis/cysticercosis": ["Cysticercosis"],
}
# Reconciliation with the real export IHME-GBD_2023_DATA-028a73a1-1 (17 causes). Groups not listed here map one-to-one by name.
MAPPING_NOTES = {
    "leishmaniasis": "export has the parent cause 'Leishmaniasis' (id 347), not the visceral/cutaneous split requested; the id gap 347 -> 350 is consistent with the two child causes being omitted, which is an inference (the hierarchy was not read); treated as covering both forms",
    "taeniasis/cysticercosis": "GBD 'Cysticercosis' (id 352) only; taeniasis is not a separate cause in the export, so the rate understates the WHO group (an extra cause that was not in the requested list)",
    "echinococcosis": "GBD 'Cystic echinococcosis' only; the WHO group also includes alveolar echinococcosis (no separate cause in the export)",
    "soil-transmitted helminthiases": "sum of Ascariasis + Trichuriasis + Hookworm disease (rates over one population add); other STH species are not in the export",
    "foodborne trematodiases": "GBD 'Food-borne trematodiases'; the project members are clonorchiasis, opisthorchiasis, fascioliasis, paragonimiasis",
    "scabies": "requested but absent from the export: stays missing (never 0)",
    "dracunculiasis": "GBD 'Guinea worm disease' (id 936); the exported rate is essentially zero, so its percentile rank is the lowest, which is real, not missing",
}
NO_GBD_CAUSE = ["Buruli ulcer", "mycetoma", "chromoblastomycosis", "noma", "snakebite envenoming", "yaws"]   # no requested cause; stay missing
DALY_NAMES = ("DALYs (Disability-Adjusted Life Years)", "DALYs")


def sha1(p):
    return hashlib.sha1(Path(p).read_bytes()).hexdigest()


def load_frames(path: Path):
    frames, srcs = [], []
    for f in sorted(path.glob("*")):
        if f.suffix == ".zip":
            with zipfile.ZipFile(f) as z:
                for n in z.namelist():
                    if n.lower().endswith(".csv"):
                        frames.append(pd.read_csv(io.BytesIO(z.read(n))))
                        srcs.append(f"{f.name}:{n}")
        elif f.suffix == ".csv":
            frames.append(pd.read_csv(f))
            srcs.append(f.name)
    return frames, srcs


def validate_and_pivot(df, year=None, age="All ages"):
    need = {"measure_name", "metric_name", "location_name", "sex_name", "age_name", "cause_name", "year", "val"}
    if not need <= set(df.columns):
        raise ValueError(f"missing columns: {sorted(need - set(df.columns))}")
    meas = sorted(df.measure_name.unique())
    if not any(m in DALY_NAMES for m in meas):
        raise ValueError(f"export has measures {meas}, not DALYs (cause rows: {df.cause_name.nunique()}); re-export with the DALYs measure")
    d = df[df.measure_name.isin(DALY_NAMES) & (df.metric_name == "Rate") & (df.location_name == "Global") & (df.sex_name == "Both")]
    d = d[d.age_name == age]
    if year is not None:
        d = d[d.year == year]
    if d.empty:
        raise ValueError("no rows left after pinning DALYs / Rate / Global / Both / age / year")
    if d.year.nunique() != 1:
        raise ValueError(f"several years present {sorted(d.year.unique())}; pass --year")
    dup = d.groupby("cause_name").size()
    if (dup > 1).any():
        raise ValueError(f"several rows per cause after filtering: {dup[dup > 1].index.tolist()[:5]} (refusing to average)")
    return d


def to_groups(d):
    by = d.set_index("cause_name")
    rows = []
    for g, causes in GBD_CAUSES.items():
        found = [c for c in causes if c in by.index]
        if not found:
            rows.append({"ntd_group": g, "daly_rate": np.nan, "lower": np.nan, "upper": np.nan, "gbd_causes_found": "", "gbd_causes_expected": "|".join(causes),
                         "status": "missing", "mapping_note": MAPPING_NOTES.get(g, "")})
            continue
        vals = by.loc[found]
        rows.append({"ntd_group": g, "daly_rate": float(vals.val.sum()),
                     "lower": float(vals.lower.sum()) if "lower" in vals else np.nan, "upper": float(vals.upper.sum()) if "upper" in vals else np.nan,
                     "gbd_causes_found": "|".join(found), "gbd_causes_expected": "|".join(causes),
                     "status": "complete" if len(found) == len(causes) else "partial", "mapping_note": MAPPING_NOTES.get(g, "")})
    for g in NO_GBD_CAUSE:
        rows.append({"ntd_group": g, "daly_rate": np.nan, "lower": np.nan, "upper": np.nan, "gbd_causes_found": "", "gbd_causes_expected": "",
                     "status": "missing", "mapping_note": "no GBD cause was requested/exported for this group"})
    return pd.DataFrame(rows)


def selftest():
    base = dict(measure_name="DALYs (Disability-Adjusted Life Years)", metric_name="Rate", location_name="Global", sex_name="Both",
                age_name="All ages", year=2023, upper=2.0, lower=0.5)
    good = pd.DataFrame([{**base, "cause_name": "Leprosy", "val": 1.0}, {**base, "cause_name": "Ascariasis", "val": 2.0},
                         {**base, "cause_name": "Trichuriasis", "val": 3.0}])
    g = to_groups(validate_and_pivot(good))
    assert g.set_index("ntd_group").loc["leprosy", "daly_rate"] == 1.0
    assert g.set_index("ntd_group").loc["soil-transmitted helminthiases", "status"] == "partial"
    assert np.isnan(g.set_index("ntd_group").loc["rabies", "daly_rate"]) and g.set_index("ntd_group").loc["rabies", "status"] == "missing"
    for bad, msg in ((pd.DataFrame([{**base, "measure_name": "Deaths", "cause_name": "All causes", "val": 1.0}]), "not DALYs"),
                     (pd.concat([good, good]), "several rows per cause")):
        try:
            validate_and_pivot(bad)
        except ValueError as e:
            assert msg in str(e), e
        else:
            raise AssertionError("validator accepted a bad export")
    parent = pd.DataFrame([{**base, "cause_name": "Leishmaniasis", "val": 5.0}, {**base, "cause_name": "Cysticercosis", "val": 7.0}])
    gp = to_groups(validate_and_pivot(parent)).set_index("ntd_group")
    assert gp.loc["leishmaniasis", "daly_rate"] == 5.0 and gp.loc["taeniasis/cysticercosis", "daly_rate"] == 7.0 and gp.loc["scabies", "status"] == "missing"
    assert len(gp) == 22, "one row per project group"
    print("selftest ok: stub rejected, duplicates rejected, partial/missing groups handled, no zero filling")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/external/downloads/ihme_gbd")
    ap.add_argument("--year", type=int, default=None)
    ap.add_argument("--age", default="All ages")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    frames, srcs = load_frames(REPO / a.input)
    if not frames:
        sys.exit(f"no IHME csv/zip under {a.input}")
    df = pd.concat(frames, ignore_index=True)
    try:
        d = validate_and_pivot(df, a.year, a.age)
    except ValueError as e:
        sys.exit(f"IHME export REJECTED: {e}")
    g = to_groups(d)
    if not (g.status != "missing").any():
        sys.exit("IHME export REJECTED: none of the expected NTD causes is present (causes in file: " + ", ".join(sorted(d.cause_name.unique())[:10])
                 + "). Re-export selecting the disease-specific causes (Docs/EQUITY_DATA_SPECS.md).")
    unmatched = sorted(set(d.cause_name) - {c for cs in GBD_CAUSES.values() for c in cs})
    for k, v in (("year", int(d.year.iloc[0])), ("location", "Global"), ("sex", "Both"), ("age", a.age), ("metric", "Rate"), ("measure", "DALYs")):
        g[k] = v
    out = REPO / "data" / "processed" / "ihme"
    out.mkdir(parents=True, exist_ok=True)
    g.to_csv(out / "daly_by_ntd_group.csv", index=False)
    rep = {"sources": srcs, "source_sha1": {f.name: sha1(f)[:12] for f in (REPO / a.input).glob("*") if f.is_file()},
           "groups_complete": int((g.status == "complete").sum()), "groups_partial": int((g.status == "partial").sum()),
           "groups_missing": g[g.status == "missing"].ntd_group.tolist(), "unmatched_gbd_causes": unmatched}
    (out / "daly_report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
