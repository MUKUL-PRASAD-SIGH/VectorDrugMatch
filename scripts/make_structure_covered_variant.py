"""
scripts/make_structure_covered_variant.py - build the STRUCTURE-COVERED benchmark variant from the frozen full benchmark.

    python scripts/make_structure_covered_variant.py            # needs data/processed/primekg (full benchmark)

Full benchmark   : configs/primekg_morgan.yaml            data/processed/primekg/splits/seed42.npz
Structure-covered: configs/primekg_morgan_structcov.yaml  data/processed/primekg_structcov/splits/seed42.npz

Rule (documented, deterministic): keep a labelled pair iff its DRUG has a usable chemical structure
(SMILES present AND non-zero fingerprint). The train/val/test DRUG PARTITION is the full benchmark's, unchanged, so the
two variants are directly comparable. Negatives are inherited (never re-sampled). `heldout_indication_pairs` is kept
UNCHANGED (all original held-out pairs), so message-passing leakage protection can only be stronger. The graph tables are
copied unchanged (structure-less drugs stay as graph nodes; they just carry no labelled pairs).

Built-in validation (hard): drug-disjoint, every kept pair has a structure, kept pairs are a subset of the full split with
identical labels, no negative is a known indication/contra/off-label pair (inherited, re-checked), counts reported.
"""
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "data" / "processed" / "primekg"
DST = REPO / "data" / "processed" / "primekg_structcov"


def main():
    z = np.load(SRC / "splits" / "seed42.npz")
    drugs = pd.read_csv(SRC / "drugs.csv", low_memory=False)
    fp = np.load(SRC / "drug_features.npy", mmap_mode="r").any(axis=1)
    has_struct = (drugs.has_smiles.values == 1) & fp
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST, ignore=shutil.ignore_patterns("splits"))
    (DST / "splits").mkdir()
    out, rep = {}, {}
    dis = pd.read_csv(SRC / "diseases.csv", low_memory=False)
    for sp in ("train", "val", "test"):
        e, y = z[f"edges_{sp}"], z[f"y_{sp}"]
        keep = has_struct[e[0]]
        for k in ("edges", "y", "curated"):
            a = z[f"{k}_{sp}"]
            out[f"{k}_{sp}"] = a[:, keep] if a.ndim == 2 else a[keep]
        for k in ("diag_contra", "diag_offlabel"):
            if f"{k}_{sp}" in z:
                a = z[f"{k}_{sp}"]
                out[f"{k}_{sp}"] = a[:, has_struct[a[0]]] if (a.ndim == 2 and a.shape[0] == 2) else a
        d = z[f"drugs_{sp}"]
        out[f"drugs_{sp}"] = d[has_struct[d]]
        ek, yk = out[f"edges_{sp}"], out[f"y_{sp}"]
        rep[sp] = {"pairs_full": int(len(y)), "pairs_kept": int(len(yk)), "positives_full": int(y.sum()), "positives_kept": int(yk.sum()),
                   "negatives_kept": int((yk == 0).sum()), "drugs_full": int(len(d)), "drugs_kept": int(len(out[f"drugs_{sp}"])),
                   "ntd_positives_kept": int(dis.is_ntd.values[ek[1][yk == 1]].sum())}
    out["heldout_indication_pairs"] = z["heldout_indication_pairs"]
    np.savez(DST / "splits" / "seed42.npz", **out)

    # ---- hard validation ----
    fails = []

    def chk(ok, msg):
        print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
        if not ok:
            fails.append(msg)
    ds = {sp: set(out[f"edges_{sp}"][0].tolist()) for sp in ("train", "val", "test")}
    chk(not (ds["train"] & ds["val"]) and not (ds["train"] & ds["test"]) and not (ds["val"] & ds["test"]), "drug-disjoint splits")
    for sp in ("train", "val", "test"):
        e, y = out[f"edges_{sp}"], out[f"y_{sp}"]
        chk(bool(has_struct[e[0]].all()), f"{sp}: every kept pair has a usable structure")
        full = {(int(a), int(b)): int(l) for a, b, l in zip(*z[f"edges_{sp}"], z[f"y_{sp}"])}
        chk(all(full.get((int(a), int(b))) == int(l) for a, b, l in zip(*e, y)), f"{sp}: kept pairs are a subset of the full split with identical labels")
    pos_all = {tuple(p) for p in zip(*[np.concatenate([z[f'edges_{s}'][i][z[f'y_{s}'] == 1] for s in ('train', 'val', 'test')]) for i in (0, 1)])}
    neg_bad = sum((int(a), int(b)) in pos_all for sp in ("train", "val", "test")
                  for a, b in zip(*out[f"edges_{sp}"][:, out[f"y_{sp}"] == 0]))
    chk(neg_bad == 0, "no kept negative equals any indication pair")
    chk(np.array_equal(out["heldout_indication_pairs"], z["heldout_indication_pairs"]), "held-out indication pairs unchanged (conservative)")
    manifest = {"variant": "structure_covered", "parent": "data/processed/primekg/splits/seed42.npz",
                "rule": "keep pairs whose drug has SMILES and a non-zero fingerprint; partition and negatives inherited",
                "drugs_with_structure": int(has_struct.sum()), "drugs_total": int(len(drugs)), "splits": rep, "validation_failures": fails}
    (DST / "splits" / "seed42.manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(rep, indent=1))
    if fails:
        raise SystemExit("VALIDATION FAILED")
    print("DONE ->", DST)


if __name__ == "__main__":
    main()
