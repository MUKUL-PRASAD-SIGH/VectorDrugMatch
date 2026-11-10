"""
scripts/fetch_public_data.py - download the publicly available datasets the pipeline uses.

    python scripts/fetch_public_data.py            # Hetionet + PharmacotherapyDB + DrugCentral targets
    python scripts/fetch_public_data.py --primekg  # also the ~1 GB PrimeKG kg.csv

Files that need a login / manual step (DALY burden, WHO EML) are NOT fetched; see the
"MANUAL" section printed at the end, and Docs/DATASETS.md.
Existing files are skipped (use --force to re-download).
"""
import argparse
import gzip
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW, EXT = ROOT / "data" / "raw", ROOT / "data" / "external"
HET = "https://github.com/hetio/hetionet/raw/main/hetnet/tsv"

# (url, destination, gunzip?)
FILES = [
    (f"{HET}/hetionet-v1.0-nodes.tsv", RAW / "hetionet-v1.0-nodes.tsv", False),
    (f"{HET}/hetionet-v1.0-edges.sif.gz", RAW / "hetionet-v1.0-edges.sif", True),
    ("https://raw.githubusercontent.com/dhimmel/indications/master/catalog/indications.tsv",
     EXT / "indications_pharmacotherapydb.tsv", False),
    ("https://unmtid-shinyapps.net/download/DrugCentral/2021_09_01/drug.target.interaction.tsv.gz",
     EXT / "drugcentral_drug_target.tsv.gz", False),
    ("https://unmtid-shinyapps.net/download/DrugCentral/2021_09_01/structures.smiles.tsv",
     EXT / "drugcentral_structures.smiles.tsv", False),
]
PRIMEKG = ("https://dataverse.harvard.edu/api/access/datafile/6180620", EXT / "primekg_kg.csv", False)
MONDO = ("https://github.com/monarch-initiative/mondo/releases/latest/download/mondo.obo", EXT / "mondo.obo", False)

MANUAL = """
MANUAL downloads (need a login / no stable direct link):
  DALY burden  -> data/external/daly_burden.csv  (columns: disease_id or disease_name, daly_rate)
      WHO GHE:  https://www.who.int/data/gho/data/themes/mortality-and-global-health-estimates/ghe-leading-causes-of-death
      IHME GBD: https://vizhub.healthdata.org/gbd-results/   (free account)
  WHO EML      -> data/external/who_eml.csv      (columns: name and/or atc_code and/or drugbank_id)
      https://www.who.int/publications/i/item/WHO-MHP-HPS-EML-2023.02   (xlsx/pdf list)
      https://list.essentialmeds.org/
"""


def fetch(url: str, dest: Path, gunzip: bool, force: bool):
    if dest.exists() and not force:
        print(f"  skip (exists): {dest.relative_to(ROOT)}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"  GET {url}")
    with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    if gunzip:
        with gzip.open(tmp, "rb") as g, open(dest, "wb") as f:
            shutil.copyfileobj(g, f)
        tmp.unlink()
    else:
        tmp.replace(dest)
    print(f"  -> {dest.relative_to(ROOT)} ({dest.stat().st_size / 1e6:.1f} MB)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--primekg", action="store_true", help="also download PrimeKG kg.csv (~1 GB) and mondo.obo (~50 MB)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    files = FILES + ([PRIMEKG, MONDO] if a.primekg else [])
    for url, dest, gz in files:
        try:
            fetch(url, dest, gz, a.force)
        except Exception as e:
            print(f"  [FAILED] {url}: {e}", file=sys.stderr)
    print(MANUAL)


if __name__ == "__main__":
    main()
