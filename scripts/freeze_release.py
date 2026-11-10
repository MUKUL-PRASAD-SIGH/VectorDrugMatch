"""
scripts/freeze_release.py - freeze the dataset release: checksums + environment + git state in one manifest.

    python scripts/freeze_release.py [--tag vdm_v1]

Writes Docs/release/<tag>_manifest.json (small, tracked) listing, for every file in the release set: relative path, bytes,
SHA-256, and (for csv) row count. Release set: data/processed/{primekg,primekg_structcov,open_targets,ntd,hai,equity,ihme,eml},
data/external/{primekg_kg.csv,mondo.obo}, configs/*.yaml, Docs/HAI_DOWNLOAD_MANIFEST.md. The data themselves are git-ignored
(licences/size); the manifest lets anyone verify they hold the identical release: `python scripts/freeze_release.py --verify <tag>`.
Also records python/package versions, the git commit, and the split seeds. Nothing is uploaded.
"""
import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DIRS = ["primekg", "primekg_structcov", "open_targets", "ntd", "hai", "equity", "ihme", "eml"]
EXTRA = ["data/external/primekg_kg.csv", "data/external/mondo.obo", "data/external/B09474-eng.pdf", "data/external/who_eml.csv", "Docs/HAI_DOWNLOAD_MANIFEST.md"]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def release_files():
    fs = []
    for d in DIRS:
        base = REPO / "data" / "processed" / d
        if base.exists():
            fs += sorted(p for p in base.rglob("*") if p.is_file())
    fs += [REPO / e for e in EXTRA if (REPO / e).exists()]
    fs += sorted((REPO / "configs").glob("*.yaml"))
    return fs


def nrows(p):
    if p.suffix == ".csv" and p.stat().st_size < 400_000_000:
        with open(p, "rb") as f:
            return max(sum(1 for _ in f) - 1, 0)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="vdm_v1")
    ap.add_argument("--verify", default=None)
    a = ap.parse_args()
    outp = REPO / "Docs" / "release"
    if a.verify:
        man = json.loads((outp / f"{a.verify}_manifest.json").read_text())
        bad = [f["path"] for f in man["files"] if not (REPO / f["path"]).exists() or sha256(REPO / f["path"]) != f["sha256"]]
        print("VERIFIED: all files match" if not bad else f"MISMATCH/missing: {bad}")
        sys.exit(1 if bad else 0)
    files = []
    for p in release_files():
        files.append({"path": p.relative_to(REPO).as_posix(), "bytes": p.stat().st_size, "sha256": sha256(p), "rows": nrows(p)})
        print("  hashed", files[-1]["path"])
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True).stdout.strip())
    except Exception:
        commit, dirty = None, None
    pkgs = {}
    for m in ("numpy", "pandas", "scikit-learn", "torch", "torch_geometric", "xgboost", "rdkit", "matplotlib", "yaml"):
        try:
            mod = __import__("sklearn" if m == "scikit-learn" else m)
            pkgs[m] = getattr(mod, "__version__", "?")
        except Exception:
            pkgs[m] = None
    man = {"tag": a.tag, "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git_commit": commit, "git_tree_dirty_at_freeze": dirty,
           "python": platform.python_version(), "platform": platform.platform(), "packages": pkgs,
           "split": {"seed": 42, "strategy": "hard negatives, drug-disjoint 70/15/15, neg_ratio 5.0",
                     "files": ["data/processed/primekg/splits/seed42.npz", "data/processed/primekg_structcov/splits/seed42.npz"]},
           "n_files": len(files), "files": files,
           "notes": ["data files are git-ignored; verify with --verify", "models and outputs are NOT part of the data release"]}
    outp.mkdir(parents=True, exist_ok=True)
    (outp / f"{a.tag}_manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
    print(f"\nwrote Docs/release/{a.tag}_manifest.json ({len(files)} files)")


if __name__ == "__main__":
    main()
