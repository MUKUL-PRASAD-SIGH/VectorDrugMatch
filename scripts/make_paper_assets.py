"""
scripts/make_paper_assets.py - regenerate every figure and the metrics table used in Docs/paper/.

    python scripts/make_paper_assets.py

Reads ONLY existing pipeline outputs (nothing is hard-coded except labels); writes
    Docs/paper/figures/fig*.png|pdf      (300 dpi PNG + vector PDF)
    Docs/paper/metrics.json              every number quoted in the paper, with its source file
Model-performance figures are NOT produced here: training has not been run, and no result is invented.
Colour: two validated categorical slots (blue #2a78d6, orange #eb6834) + neutral grey; values are labelled directly.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
import pandas as pd  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
FIG = REPO / "Docs" / "paper" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
PK = REPO / "data" / "processed" / "primekg"
OT = REPO / "data" / "processed" / "open_targets"

BLUE, ORANGE, GREY, INK, MUTED = "#2a78d6", "#eb6834", "#b9b8b2", "#0b0b0b", "#52514e"
plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": INK, "ytick.color": INK, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 150, "savefig.dpi": 300, "axes.linewidth": 0.6})
COL1, COL2 = 3.5, 7.16     # IEEE single / double column width (inches)


def thousands(ax, axis="x"):
    (ax.xaxis if axis == "x" else ax.yaxis).set_major_formatter(FuncFormatter(lambda v, _: f"{int(v):,}"))


def save(fig, name):
    fig.savefig(FIG / f"{name}.png", bbox_inches="tight")
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)
    print("  wrote", name)


def hbar(ax, labels, vals, color=BLUE, fmt="{:,}"):
    y = np.arange(len(labels))[::-1]
    ax.barh(y, vals, color=color, height=0.62)
    ax.set_yticks(y, labels)
    for yi, v in zip(y, vals):
        ax.text(v + max(vals) * 0.01, yi, fmt.format(v), va="center", fontsize=7, color=INK)
    ax.set_xlim(0, max(vals) * 1.18)
    ax.tick_params(axis="y", length=0)


def main():
    M = {}
    man = json.loads((PK / "splits" / "seed42.manifest.json").read_text())
    val = json.loads((REPO / "outputs/primekg/validation_report.json").read_text())
    aud = json.loads((REPO / "outputs/primekg_mapping_audit.json").read_text())
    prov = json.loads((PK / "primekg_provenance.json").read_text())
    drugs = pd.read_csv(PK / "drugs.csv", low_memory=False)
    z = np.load(PK / "splits" / "seed42.npz")
    fp_ok = np.load(PK / "drug_features.npy", mmap_mode="r").any(axis=1)
    has_struct = (drugs.has_smiles.values == 1) & fp_ok

    # ---------------- Fig 1: split composition ----------------
    sp = man["splits"]
    names = ["train", "val", "test"]
    pos = [sp[n]["positives"] for n in names]
    neg = [sp[n]["negatives"] for n in names]
    drg = [sp[n]["drugs"] for n in names]
    ntd = [sp[n]["ntd_positives"] for n in names]
    fig, ax = plt.subplots(figsize=(COL1, 2.5))
    x = np.arange(3)
    ax.bar(x, pos, 0.55, color=BLUE, label="positives (indications)")
    ax.bar(x, neg, 0.55, bottom=pos, color=GREY, label="sampled negatives", linewidth=0)
    ax.set_xticks(x, [f"{n.capitalize()}\n{drg[i]:,} drugs\n{pos[i]:,} pos\n{neg[i]:,} neg\n{ntd[i]} NTD pos."
                      for i, n in enumerate(names)], fontsize=6.5)
    thousands(ax, "y")
    ax.set_ylabel("labelled drug-disease pairs")
    ax.set_ylim(0, max(np.array(pos) + np.array(neg)) * 1.05)
    ax.legend(frameon=False, fontsize=7, loc="upper right")
    save(fig, "fig1_split_composition")
    M["split"] = {n: {k: sp[n][k] for k in ("drugs", "positives", "negatives", "ntd_positives")} for n in names}
    M["split"]["strategy"] = {k: man[k] for k in ("seed", "strategy", "neg_ratio", "test_size", "val_size", "stratified_on_ntd")}

    # ---------------- Fig 2: disease mapping status ----------------
    st = val["disease_mapping_status"]
    order = ["mapped", "ambiguous", "partial", "unmapped_related_only", "unmapped_obsolete_unresolved", "unmapped", "unmapped_no_doid"]
    lab = {"mapped": "mapped (exact DOID)", "ambiguous": "ambiguous (>1 DOID)", "partial": "partial (grouped node)",
           "unmapped_related_only": "related DOID only", "unmapped_obsolete_unresolved": "obsolete, unresolved",
           "unmapped": "unmapped", "unmapped_no_doid": "MONDO term, no DOID"}
    fig, ax = plt.subplots(figsize=(COL1, 2.2))
    hbar(ax, [lab[o] for o in order], [st[o] for o in order])
    thousands(ax)
    ax.set_xlabel("PrimeKG disease nodes (n = 17,080)")
    save(fig, "fig2_disease_mapping")
    M["disease_mapping_status"] = st
    M["indication_pairs_by_mapping"] = aud["label_pairs"]["indication"]

    # ---------------- Fig 3: structure coverage ----------------
    rows = []
    for n in names:
        e, y = z[f"edges_{n}"], z[f"y_{n}"]
        miss = ~has_struct[e[0]]
        rows.append((n, 100 * miss[y == 1].mean(), 100 * miss[y == 0].mean(), int(miss[y == 1].sum()), int(miss[y == 0].sum())))
    fig, ax = plt.subplots(figsize=(COL1, 2.1))
    w = 0.34
    for i, r in enumerate(rows):
        ax.bar(i - w / 2, r[1], w, color=BLUE, label="positives" if i == 0 else None)
        ax.bar(i + w / 2, r[2], w, color=ORANGE, label="negatives" if i == 0 else None)
        ax.text(i - w / 2, r[1] + 0.3, f"{r[1]:.1f}%", ha="center", fontsize=7)
        ax.text(i + w / 2, r[2] + 0.3, f"{r[2]:.1f}%", ha="center", fontsize=7)
    ax.set_xticks(range(3), [r[0].capitalize() for r in rows])
    ax.set_ylabel("pairs, drug without structure (%)", fontsize=7)
    ax.set_ylim(0, max(max(r[1], r[2]) for r in rows) * 1.25)
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    save(fig, "fig3_structure_shortcut")
    M["structure_coverage"] = {"drugs_total": len(drugs), "drugs_no_smiles": int((drugs.has_smiles == 0).sum()),
                               "drugs_zero_fingerprint": int((~fp_ok).sum()),
                               "indication_drugs": val["coverage"]["drugs_with_indication"],
                               "indication_drugs_with_smiles": val["coverage"]["indication_drugs_with_smiles"],
                               "pairs_without_structure_pct": {r[0]: {"positives": round(r[1], 2), "negatives": round(r[2], 2),
                                                                      "n_pos": r[3], "n_neg": r[4]} for r in rows}}

    # ---------------- Fig 4: NTD coverage ----------------
    ntd_df = pd.read_csv(REPO / "outputs/primekg_ntd_coverage.csv")
    d = ntd_df.sort_values("indication", ascending=False)
    fig, ax = plt.subplots(figsize=(COL1, 3.6))
    hbar(ax, [g + (" *" if g in ("lymphatic filariasis", "noma") else "") for g in d.ntd_group], d.indication.tolist())
    ax.set_xlabel("indication pairs in PrimeKG")
    save(fig, "fig4_ntd_coverage")
    M["ntd"] = {"groups": len(d), "groups_with_indication": int((d.indication > 0).sum()),
                "indication_pairs_sum_over_groups": int(d.indication.sum()), "unique_indication_pairs": aud["ntd"].get("unique_ntd_indication_pairs"),
                "per_group": dict(zip(d.ntd_group, d.indication.astype(int)))}

    # ---------------- Fig 5: PrimeKG relation counts ----------------
    ec = val["edges_by_relation"]
    rel = [("GiG", "gene-gene"), ("DaG", "disease-gene"), ("PK_DisDis", "disease-disease"), ("PK_contra", "contraindication"),
           ("CbG", "drug-gene"), ("CtD", "indication (target)"), ("PK_offlabel", "off-label use")]
    rel = sorted(rel, key=lambda r: -ec[r[0]])
    fig, ax = plt.subplots(figsize=(COL1, 2.1))
    y = np.arange(len(rel))[::-1]
    ax.barh(y, [ec[r[0]] for r in rel], color=[ORANGE if r[0] == "CtD" else BLUE for r in rel], height=0.62)
    ax.set_yticks(y, [r[1] for r in rel]); ax.set_xscale("log")
    for yi, r in zip(y, rel):
        ax.text(ec[r[0]] * 1.12, yi, f"{ec[r[0]]:,}", va="center", fontsize=7)
    ax.set_xlim(1e3, 1.2e6); ax.tick_params(axis="y", length=0)
    ax.set_xlabel("edges kept (log scale)")
    save(fig, "fig5_graph_relations")
    M["graph"] = {"nodes": val["nodes"], "edges_by_relation": ec,
                  "kg_sha256": prov["source"]["sha256"] if "source" in prov else None, "mondo_release": prov["source"]["mondo"] if "source" in prov else None}

    # ---------------- Fig 6/7: Open Targets ----------------
    r = json.loads((OT / "mapping_report.json").read_text())
    n_all = r["rows"]["clinical_reports"]
    t1_rows = r["drugs"]["rows_by_tier"].get("1_exact_xref", 0)
    usable = r["pairs"]["rows_usable(drug mapped & single MONDO)"]
    pairs = r["pairs"]["clean_pairs_after_dedup"]
    steps = [("clinical reports", n_all), ("drug mapped to one\nDrugBank id (tier 1)", t1_rows),
             ("and disease mapped to\none MONDO id", usable), ("unique drug-disease\npairs", pairs)]
    fig, ax = plt.subplots(figsize=(COL1, 2.2))
    hbar(ax, [s[0] for s in steps], [s[1] for s in steps])
    thousands(ax)
    ax.set_xlabel("Open Targets indication records")
    save(fig, "fig6_open_targets_funnel")
    ov = pd.read_csv(OT / "primekg_overlap.csv")
    ov = ov[ov.ot_pairs_primekg_drug >= 50].copy()
    ov["lab"] = ov.max_clinical_stage.map(lambda x: {"PHASE_2_3": "Phase 2/3", "PHASE_1_2": "Phase 1/2"}.get(x, x.replace("_", " ").title()))
    fig, ax = plt.subplots(figsize=(COL1, 2.5))
    hbar(ax, ov.lab.tolist(), (100 * ov.frac_of_pairs_with_primekg_drug).round(1).tolist(), fmt="{:.1f}%")
    ax.set_xlabel("% also a PrimeKG indication")
    save(fig, "fig7_open_targets_overlap")
    M["open_targets"] = {k: r[k] for k in ("rows", "drugs", "diseases", "pairs", "primekg_overlap", "inputs", "mondo_release")}
    M["open_targets"]["overlap_by_stage"] = json.loads(ov.drop(columns="lab").to_json(orient="records"))

    (REPO / "Docs/paper/metrics.json").write_text(json.dumps(M, indent=2, default=int), encoding="utf-8")
    print("wrote Docs/paper/metrics.json")


if __name__ == "__main__":
    main()
