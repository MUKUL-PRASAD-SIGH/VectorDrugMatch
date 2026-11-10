"""
scripts/make_readiness_report.py - generate Docs/DATA_AND_PIPELINE_READINESS.md and Docs/DATA_DICTIONARY.md from the real files.

    python scripts/make_readiness_report.py [--skip-validators]

Every number is read from a data file or a report JSON; validator statuses come from RUNNING the validators now (their final
RESULT line is captured). The "unresolved issues" list is curated text (the only hand-written part) and is marked as such.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
P = REPO / "data" / "processed"
DESCR = {
    "drug_id": "DrugBank id (PrimeKG node id)", "disease_id": "PrimeKG disease node id: MONDO:xxxxxxx or MONDO_GROUP:a_b_c for grouped nodes",
    "name": "drug name (DrugBank)", "smiles": "canonical SMILES (empty if unresolved)", "has_smiles": "1 if a SMILES was resolved",
    "disease_name": "disease label", "is_ntd": "1 if the node falls under one of the 22 benchmark NTD groups (FROZEN flag)",
    "ntd_groups": "pipe-separated NTD group keys", "daly_rate": "DALY rate per 100,000 (empty unless IHME data supplied)",
    "mapping_status": "MONDO->DOID status: mapped / ambiguous / partial / unmapped_*", "doid_exact": "exact (equivalence-qualified) DOID ids",
    "mondo_resolved": "MONDO id(s) after following replaced_by", "obsolete_status": "current / replaced / obsolete_no_replacement",
    "source_id": "edge source node id", "target_id": "edge target node id", "relation": "PrimeKG relation code (CtD, PK_contra, ...)",
    "primekg_relation": "indication / contraindication / off-label use / drug_protein / ...", "gene_id": "NCBI gene id (PrimeKG)",
    "drugbank_id": "DrugBank id", "mondo_id": "MONDO id", "max_clinical_stage": "highest Open Targets stage (project ordering convention)",
    "stages_seen": "all stages seen for the pair", "approved": "1 if any report has stage exactly APPROVAL", "drug_map_tier": "1_exact_xref / 2_parent_fallback",
    "chembl_ids": "ChEMBL ids merged into the pair", "n_source_rows": "source rows merged into the pair", "source": "data source",
    "survey_id": "HAI survey folder id (location_date)", "sector": "price sector", "medicine_name": "generic name parsed from the survey",
    "mpr": "median price ratio vs the international reference price list", "availability_pct": "% of facilities with the medicine",
    "ndpi_score": "weighted mean of available equity components (EMPTY if none)", "evidence_coverage": "sum of weights of components with data",
    "eml_status": "1/0 if a WHO EML file is supplied, else empty", "availability": "mean patient-price availability fraction (HAI pilot)",
    "group_key": "benchmark/candidate NTD group key", "who_entry": "official WHO list entry (footnote of the WHO NTD page)",
}


def run(cmd):
    try:
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=1500, encoding="utf-8", errors="replace")
        lines = [ln for ln in (r.stdout + r.stderr).splitlines() if "RESULT" in ln or "selftest ok" in ln or "REJECTED" in ln]
        return (lines[-1].strip() if lines else f"exit {r.returncode}"), r.returncode
    except Exception as e:
        return f"error {e}", 1


def info(path):
    d = pd.read_csv(path, low_memory=False, keep_default_na=True)
    return d


def md(df):
    """dependency-free GitHub pipe table"""
    cols = list(df.columns)

    def cell(v):
        return ("" if (v is None or (isinstance(v, float) and np.isnan(v))) else str(v)).replace("|", "/").replace("\n", " ")
    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(cell(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-validators", action="store_true")
    a = ap.parse_args()
    py = [sys.executable, "-I"]
    val = {}
    if not a.skip_validators:
        val["PrimeKG dataset + leakage (validate_primekg_dataset.py)"] = run(py + ["scripts/validate_primekg_dataset.py", "--config", "configs/primekg_morgan.yaml"])
        val["Open Targets (validate_open_targets.py)"] = run(py + ["scripts/validate_open_targets.py"])
        val["IHME processor self-test"] = run(py + ["scripts/process_ihme_daly.py", "--selftest"])
        val["Paper structure (check_paper.py)"] = run(py + ["scripts/check_paper.py"])
        val["Model/loader audit (audit_models.py)"] = ("see section 3", 0)
    L = [f"# Data and pipeline readiness report\n\nGenerated {datetime.now().strftime('%Y-%m-%d %H:%M')} by `scripts/make_readiness_report.py` from the files on disk. "
         "Numbers are read from data/report files; validator lines are from running the validators during generation. "
         "Section 6 (unresolved issues) is curated text.\n"]

    # ---------- 1. datasets ----------
    pk = P / "primekg"
    drugs, dis = info(pk / "drugs.csv"), info(pk / "diseases.csv")
    genes = info(pk / "genes.csv")
    edges = pd.read_csv(pk / "edges.csv", low_memory=False)
    z = np.load(pk / "splits" / "seed42.npz")
    zc = np.load(P / "primekg_structcov" / "splits" / "seed42.npz") if (P / "primekg_structcov").exists() else None
    rows = []

    def add(name, src, lic, raw, proc, n, d_, ds_, miss, status):
        rows.append({"dataset": name, "source / version": src, "licence": lic, "raw path": raw, "processed path": proc, "rows": n,
                     "unique drugs": d_, "unique diseases": ds_, "missing values": miss, "status": status})
    ind = edges[edges.primekg_relation == "indication"]
    add("PrimeKG nodes: drugs", "PrimeKG kg.csv (Harvard Dataverse doi:10.7910/DVN/IXA7BM), MONDO 2026-11-03", "CC0 per Dataverse metadata; upstream terms (DrugBank) unchecked",
        "data/external/primekg_kg.csv", "data/processed/primekg/drugs.csv", len(drugs), len(drugs), "", f"smiles empty {int((drugs.has_smiles == 0).sum())}", "built; validated")
    add("PrimeKG nodes: diseases", "same", "same", "same", "data/processed/primekg/diseases.csv", len(dis), "", len(dis), f"daly_rate empty {int(dis.daly_rate.isna().sum())} (no DALY data yet)", "built; validated")
    add("PrimeKG nodes: genes", "same", "same", "same", "data/processed/primekg/genes.csv", len(genes), "", "", "none", "built")
    add("PrimeKG edges (all relations)", "same", "same", "same", "data/processed/primekg/edges.csv", len(edges), edges[edges.source_type == "Drug"].source_id.nunique() if "source_type" in edges else "", "", "", "built; validated")
    add("PrimeKG indication pairs (target)", "same", "same", "same", "data/processed/primekg/edges.csv (primekg_relation=indication)", len(ind), ind.source_id.nunique(), ind.target_id.nunique(), "none", "validated")
    for nm, zz, pth in (("Full benchmark split", z, "data/processed/primekg/splits/seed42.npz"), ("Structure-covered split", zc, "data/processed/primekg_structcov/splits/seed42.npz")):
        if zz is None:
            continue
        n = sum(len(zz[f"y_{s}"]) for s in ("train", "val", "test"))
        dr = len({int(x) for s in ("train", "val", "test") for x in zz[f"edges_{s}"][0]})
        di = len({int(x) for s in ("train", "val", "test") for x in zz[f"edges_{s}"][1]})
        add(nm, "derived from PrimeKG indications; seed 42, hard negatives 5:1, drug-disjoint 70/15/15", "derived", "-", pth, n, dr, di, "none", "validated" if nm.startswith("Full") else "built-in checks passed")
    ot = REPO / "data" / "processed" / "open_targets"
    if ot.exists():
        for f, st in (("pairs_drugbank_mondo.csv", "validated (tier 1)"), ("pairs_drugbank_mondo_parent_fallback.csv", "validated (tier 2, separate)")):
            d = info(ot / f)
            add(f"Open Targets {f.split('.')[0]}", "Open Targets Platform export (3 parquet files; SHA-1 in Docs/HAI_DOWNLOAD_MANIFEST.md)", "OT outputs CC0; upstream sources keep own licences (ChEMBL CC BY-SA 3.0; others not listed on OT licence page)",
                "data/external/downloads/open_targets/", f"data/processed/open_targets/{f}", len(d), d.drugbank_id.nunique(), d.mondo_id.nunique(), "none in keys", st + "; NOT merged into training")
    hai = P / "hai"
    if hai.exists():
        for f in ("hai_price_availability", "hai_median_price", "hai_affordability", "hai_medicines"):
            d = info(hai / f"{f}.csv")
            nd = d.drugbank_id.replace("", np.nan).dropna().nunique() if "drugbank_id" in d else ""
            add(f"HAI {f}", "WHO/HAI price surveys: Karnataka 2004-11, Maharashtra 2005-01, Delhi 2011-07", "check HAI terms", "data/external/downloads/hai_price_surveys/", f"data/processed/hai/{f}.csv",
                len(d), nd, "", "numeric blanks = not reported/free (kept as status)", "parsed; regional pilot")
    ntd = P / "ntd" / "ntd_disease_mapping.csv"
    if ntd.exists():
        d = info(ntd)
        add("NTD mapping table", "WHO NTD list (read 2026-11-10) + MONDO + PrimeKG", "n/a", "-", "data/processed/ntd/ntd_disease_mapping.csv", len(d), "", "", "none", "built from files (rows = WHO entry x group)")
    eq = P / "equity" / "equity_features.csv"
    if eq.exists():
        d = info(eq)
        add("Equity feature table", "PrimeKG pairs + HAI (+ IHME, EML when supplied)", "derived", "-", "data/processed/equity/equity_features.csv", len(d), d.drug_id.nunique(), d.disease_id.nunique(),
            f"ndpi empty {int(d.ndpi_score.isna().sum())}/{len(d)}", "built; access-only (EML, DALY absent)")
    add("IHME DALY by NTD group", "IHME GBD 2023 export (must be re-exported)", "IHME terms", "data/external/downloads/ihme_gbd/", "data/processed/ihme/daly_by_ntd_group.csv (not created)", 0, "", "", "n/a", "BLOCKED: export has only 'All causes'")
    add("WHO EML flags", "WHO Model List (file not supplied)", "WHO terms", "data/external/who_eml.csv (absent)", "data/processed/eml/eml_drug_flags.csv (not created)", 0, "", "", "n/a", "BLOCKED: file not supplied")
    L += ["## 1. Datasets\n", md(pd.DataFrame(rows)), "\n### Validators run during generation\n", md(pd.DataFrame([{"check": k, "result": v[0]} for k, v in val.items()])) if val else "(validators skipped)", ""]

    # ---------- 2. mappings ----------
    L.append("## 2. Mappings\n")
    st = dis.mapping_status.value_counts()
    L += ["**Disease MONDO -> DOID (PrimeKG nodes, exact xrefs only):**\n", md(st.rename_axis("status").reset_index(name="nodes")), ""]
    if ntd.exists():
        s = json.loads((P / "ntd" / "ntd_mapping_summary.json").read_text())
        L += [f"**WHO NTD -> MONDO -> PrimeKG:** {s['who_entries_in_list_footnote']} official WHO entries; {s['benchmark_groups']} benchmark groups ({s['benchmark_groups_with_mondo_term']} with a MONDO term, "
              f"{s['benchmark_groups_with_indication_pairs']} with >=1 indication pair; {s['benchmark_indication_pairs_sum_over_groups']} pair-memberships). WHO entries with no indications: {', '.join(s['who_entries_with_no_benchmark_group_having_indications'])}. "
              f"Candidate extensions (chikungunya, tungiasis) and fact-sheet-only diseases are NOT in the frozen flag. Source: {s['who_source']['url']} (accessed {s['who_source']['accessed']}).\n"]
    if ot.exists():
        r = json.loads((ot / "mapping_report.json").read_text())
        L += [f"**Open Targets:** drug tiers (ChEMBL ids) {r['drugs']['drugs_by_tier']}; disease status (OT ids) {r['diseases']['by_status(ids)']}; {r['pairs']['clean_pairs_after_dedup']:,} tier-1 pairs, "
              f"{r['pairs']['tier2_parent_fallback_pairs']:,} tier-2 pairs ({r['pairs']['tier2_pairs_not_already_in_tier1']:,} not already in tier 1). Overlap with PrimeKG: {r['primekg_overlap']}.\n"]
    if hai.exists():
        h = json.loads((hai / "hai_parse_report.json").read_text())
        L += [f"**HAI medicines -> DrugBank:** {h['drugbank_mapping']['medicines']} (tiers {h['drugbank_mapping']['tiers']}); unmapped: {', '.join(h['drugbank_mapping']['unmapped_names'])}.\n"]
    if eq.exists():
        e = json.loads((P / "equity" / "equity_report.json").read_text())
        L += [f"**Equity component coverage (all pairs / NTD pairs):** {e['component_coverage_pct_all_pairs']} / {e['component_coverage_pct_ntd_pairs']} (%); NDPI available for {e['pairs_with_ndpi']} pairs ({e['ntd_pairs_with_ndpi']} NTD).\n"]

    # ---------- 3. models ----------
    aud = json.loads((REPO / "outputs" / "audit" / "models_audit.json").read_text()) if (REPO / "outputs" / "audit" / "models_audit.json").exists() else {}
    mrows = []
    for key, label in (("logistic", "Logistic Regression"), ("nb", "Naive Bayes"), ("rf", "Random Forest"), ("xgb", "XGBoost"), ("mlp", "MLP")):
        mrows.append({"model": label, "script": "scripts/train_baselines.py --model " + key, "input": "pair features (drug fingerprint + 3 disease features), saved split",
                      "outputs": f"outputs/<exp>/baseline_{key}_coldstart_predictions.csv, models/baseline_{key}_metrics.json, baseline_comparison.csv",
                      "audit (instantiate+fit tiny)": aud.get("baselines", {}).get(key, {}).get("status", "not run"), "trained": "no (Colab)"})
    mrows.append({"model": "Node2Vec + LR", "script": "scripts/train_node2vec.py", "input": "walk graph = message-passing graph + TRAIN positives", "outputs": "baseline_node2vec_coldstart_predictions.csv, models/baseline_node2vec_metrics.json",
                  "audit (instantiate+fit tiny)": f"dry run {aud.get('node2vec_dry_run', 'not run')}; torch_cluster absent locally", "trained": "no (Colab)"})
    for k in ("GCN", "GraphSAGE", "GAT", "RGCN", "HGT"):
        mrows.append({"model": k, "script": "scripts/train_gnn.py", "input": "hetero message-passing graph (treats edges removed), saved split", "outputs": f"predictions/gnn_{k}_predictions.csv, models/gnn_{k}.pth, gnn_{k}_history.csv, embeddings .npy, gnn_comparison.csv",
                      "audit (instantiate+fit tiny)": aud.get("gnn", {}).get(k, {}).get("status", "not run") + " (tiny synthetic forward pass)", "trained": "no (Colab)"})
    mrows.append({"model": "Cold-start ablation (RF)", "script": "scripts/run_ablations_coldstart.py", "input": "saved split", "outputs": "ablation_coldstart.csv/json",
                  "audit (instantiate+fit tiny)": "compiles; not run", "trained": "no (Colab)"})
    mrows.append({"model": "Explainability (SHAP / GNNExplainer)", "script": "NOT IMPLEMENTED (src/explainability is empty)", "input": "-", "outputs": "-", "audit (instantiate+fit tiny)": "-", "trained": "-"})
    L += ["\n## 3. Models\n", md(pd.DataFrame(mrows)), f"\nLoader audit: {json.dumps(aud.get('loaders', {}))[:600]}\n"]

    # ---------- 4. metrics and figures ----------
    L += ["## 4. Evaluation metrics and planned outputs\n",
          "**Metrics:** ROC-AUC, PR-AUC, F1, precision, recall, MCC, Brier (probability metrics); Precision@K, Recall@K, Hits@K, MRR, NDCG@K (per-disease ranking, `scripts/evaluate_primekg.py`); subsets all / ntd_only / mapped_only / sampled_negatives / with_structure / no_structure; threshold = Youden on validation only; test scored once.\n",
          "**Paper figures (existing, from real data):** fig1-7 in `Docs/paper/figures/` (graph relations, split composition, disease mapping, NTD coverage, structure shortcut, Open Targets funnel and overlap).\n",
          "**Paper figures (generated by `scripts/make_results_package.py` after training):** ROC/PR per model family, confusion matrices, calibration, model comparison, NTD breakdown, structure sensitivity, GNN training curves, disease-embedding PCA; tables model_comparison, subset_metrics, structure_sensitivity, ntd_breakdown; `results_metrics.json`. Verified locally on the single real baseline prediction file; other models/figures need the Colab run.\n",
          "**Not yet planned/implemented:** NDPI ranking figure and equity-component contribution/sensitivity plots (need DALY + EML data), drug-disease candidate network, coverage/missing-data heatmap.\n"]

    # ---------- 5. pipeline ----------
    L += ["## 5. Execution entry points (nothing below has been run for the final results)\n",
          "`python scripts/run_full_pipeline.py --stage prepare|external|smoke|train|report|all [--variant full|structcov] [--dry-run]` (`external` steps that need files only you can supply are optional: they log a failure and the equity table reports the component as missing; log in `outputs/pipeline_log.jsonl`). Release integrity: `python scripts/freeze_release.py --tag vdm_v1` then `--verify vdm_v1`.\n"]

    # ---------- 6. unresolved ----------
    L += ["## 6. Unresolved scientific / data issues (curated)\n",
          "| # | Issue | Blocks | Needs |\n|---|---|---|---|",
          "| 1 | IHME export contains only 'All causes' (right dimensions, no NTD causes) | DALY component, NDPI | re-export with NTD causes (Docs/EQUITY_DATA_SPECS.md) |",
          "| 2 | WHO EML: extracted from the official 24th-list PDF (646 entries: 592 single, 54 combination; automated checks in tests/test_who_eml_extraction.py); 497 of 592 single entries map to 378 distinct PrimeKG drugs (297 of them have an indication pair in the benchmark) by exact/alias/salt/curated-INN tiers; 95 single entries unmapped, each with a recorded reason in eml_unmatched.csv (vaccines, biologics, blood products, devices, ambiguous names, drugs absent from PrimeKG). EML status separates confirmed positives, unresolved (name overlaps an unmapped entry) and no-candidate zeros | EML component accuracy | none (limitation documented); WHO text is CC BY-NC-SA 3.0 IGO |",
          "| 3 | NDPI has EML (31.3% of pairs confirmed positive, 3.6% unresolved; the rest are no-candidate zeros or combination-only; see equity_report.json denominators) + HAI pilot (6.6%) but NO burden component: it reduces to the EML flag and is NOT a burden-aware equity ranking; weights 0.45/0.45/0.10 unvalidated; sensitivity grid not meaningful until DALY exists | equity claims | IHME re-export |",
          "| 4 | HAI = three Indian surveys 2004-2011; 5 medicines unmapped (combinations, benzathine penicillin) | any global access claim | broader access evidence |",
          "| 5 | WHO NTD list verified directly (21 groupings; 25 fact sheets; `Docs/NTD_MAPPING.md`). The 22 frozen project groups reconcile to it with documented differences (chikungunya, other deep mycoses, other ectoparasitoses not in the flag; WHO does not enumerate members of two groupings). Page says 'NTDs include', gives no dates; headline: new-NTD requests on hold pending a criteria review (article not read). Candidate extensions are NOT in the frozen flag (changing it would change the NTD stratification) | NTD framing | decide whether to run a separate extended-NTD analysis |",
          "| 6 | NTD test set is tiny (15 positives, 13 groups with any test pair); MONDO has only a generic term for lymphatic filariasis; noma has none | NTD performance claims | report as exploratory |",
          "| 7 | 996 drugs have no SMILES (mostly biologics); with/no-structure subsets and the structure-covered variant address the shortcut risk but do not remove it | interpretation | run both variants on Colab |",
          "| 8 | Open Targets licence/provenance (`Docs/LICENCE_AUDIT.md`, `Docs/OPEN_TARGETS_PROVENANCE.md`): CC0 is platform-level; six upstream source families feed clinical reports but only ChEMBL (CC BY-SA 3.0) is in the licence table; terms of AACT/ClinicalTrials.gov, TTD and PMDA unverified, EMA partial; which families feed OUR 86,451 records is unknown (needs the same-release clinical-report dataset; release number also unknown); stage order matches the documented list order but is our encoding; overlap with PrimeKG is not independent validation | external corroboration claims, any redistribution | per-source attribution + terms review |",
          "| 9 | PrimeKG upstream licence terms (DrugBank) unchecked; old DrugBank files remain in git history (commit 1829752 on origin/mukul) | public release | licence review; team decision on history cleanup |",
          "| 10 | Explainability: SHAP (RF/XGBoost) and GNNExplainer (per-link, k-hop) implemented in `src/explainability/explain.py` + `scripts/explain_models.py`, API-tested on synthetic inputs only; MLP/NB/Node2Vec intentionally NOT explained (documented); real-model explanations need the Colab run | explainability section | Colab run |",
          "| 11 | Legacy `scripts/run_ablations.py` and `scripts/train_benchmark.py` are not drug-disjoint / leak-prone; use `run_ablations_coldstart.py` and `train_node2vec.py` | ablation validity | do not report the legacy outputs |",
          "| 12 | `train_baselines.py` prints pooled 5-fold CV numbers (easier than the real task), and its `mrr`/`hits_10`/`precision_10` (also in `compute_all_metrics`) are POOLED over the test set, not per disease: report only `coldstart_roc_auc/pr_auc/f1/mcc/brier`; ranking metrics come from `evaluate_primekg.py` (per disease). `evaluate_primekg.py` MCC is at a fixed 0.5, the results package uses validation-chosen thresholds | misreporting risk | report discipline |",
          "| 13 | Node2Vec training untested (needs torch_cluster); GNNs untested on GPU/real graph; one local CPU logistic smoke run exists in `outputs/primekg/` and is NOT a result | Colab run | smoke stage of run_full_pipeline.py |",
          "| 14 | `src/scoring/{equity,ndpi}.py` are the legacy Hetionet-era scorer; PrimeKG NDPI lives in `scripts/build_equity_features.py` | consistency | decide whether to retire the legacy modules |",
          "| 15 | Bibliography verified at metadata level; claim support checked against abstracts only (Docs/paper/CITATION_AUDIT.md) | submission | full-text check |",
          "| 16 | `notebooks/colab_primekg.ipynb` (pinned to 522deb3) predates the variants / results package / ablations; the final run uses `notebooks/colab_final_run.ipynb`, which drives `run_full_pipeline.py` and is pinned in its first code cell to the commit that contains those scripts | final Colab run | re-pin if code changes after the freeze |",
          "| 17 | Local commits are unpushed by instruction; the final notebook pin must point to a pushed commit | Colab clone | explicit approval to push |",
          "| 18 | Baseline disease representation: the PrimeKG disease features are `is_ntd` plus two columns that are constant (DALY absent) = ONE informative disease feature, so the classical baselines are effectively drug-only and cannot model drug-disease specificity; GNNs/Node2Vec see disease neighbourhoods. Interpret baseline-vs-GNN differences with this in mind | baseline comparison | decision H2 in Docs/HUMAN_ACTION_CHECKLIST.md |",
          "| 19 | Open Targets quality flag: the only flag is UNVALIDATED_INDICATION; 47,044 of 86,451 pairs have every supporting report flagged (mostly AACT trials) although the documentation says flagged reports do not feed clinical indications; semantics unresolved. Use pairs with >=1 unflagged report (or APPROVAL stage) for any corroboration | OT corroboration | optional: ask Open Targets |",
          "| 20 | HAI: 10 of 289 comparable MPR values differ between detail pages and the median-price file (all Delhi 2011, lowest-price generic, liquid/drop forms; 1.02-2.93x); cause not established; MPR is not used in the equity score | HAI MPR use | none |",
          "| 21 | Fixed 2026-11-10: GCN/GraphSAGE/GAT had dropout ACTIVE in eval mode (functional dropout frozen by to_hetero tracing); per-model reseeding added; baseline cold-start models are now saved; RF SHAP normalised to the positive class; regression tests added (tests/test_gnn_eval_determinism.py) | GNN/baseline validity | none (fixed) |",
          "| 22 | `requirements.txt` is open-ended (>=) and listed neither pyarrow, pymupdf, lxml, mlflow, tabulate nor optuna (added); exact versions used locally are in `requirements-validated-local.txt`; Colab versions are recorded at run time, not pinned | exact reproducibility | none |",
          "| 23 | Baselines hard-code random_state=42 (config seed not propagated): multi-seed variation needs a code change | optional multi-seed study | decision H10 |",
          "| 24 | Nested NTD roots: onchocerciasis (2 nodes, 3 pairs) and dracunculiasis (1 node) sit inside the generic lymphatic-filariasis root; sum over groups = 85 pairs vs 82 unique; LF-specific indication pairs = 3 (not 6) | NTD per-group claims | report LF as an upper bound |",
          ""]
    (REPO / "Docs" / "DATA_AND_PIPELINE_READINESS.md").write_text("\n".join(L), encoding="utf-8")

    # ---------- data dictionary ----------
    D = ["# Data dictionary\n", "Generated by `scripts/make_readiness_report.py`: every processed CSV with its columns, types, missing share and an example value. Descriptions are filled for the key columns.\n"]
    for d_ in ("primekg", "open_targets", "ntd", "hai", "equity", "ihme", "eml"):
        base = P / d_
        if not base.exists():
            continue
        for f in sorted(base.glob("*.csv")):
            df = pd.read_csv(f, low_memory=False, nrows=200000)
            D += [f"\n## `data/processed/{d_}/{f.name}`  ({len(pd.read_csv(f, usecols=[0], low_memory=False)):,} rows)\n", "| column | dtype | missing % | example | description |", "|---|---|---|---|---|"]
            for c in df.columns:
                ex = df[c].dropna().astype(str).iloc[0][:40].replace("|", "/") if df[c].notna().any() else ""
                D.append(f"| {c} | {df[c].dtype} | {100 * df[c].isna().mean():.1f} | {ex} | {DESCR.get(c, '')} |")
    D += ["\n## Split files (`splits/seed42.npz`)\n", "Arrays: `edges_{train,val,test}` (2, N) drug/disease row indices into drugs.csv / diseases.csv; `y_*` labels (1 = indication, 0 = sampled negative); `curated_*` (all False for PrimeKG); `drugs_*` drug ids of the split; `diag_contra_*`, `diag_offlabel_*` evaluation-only pairs of that split's drugs (never labels); `heldout_indication_pairs` (2, K) val+test indications removed from message passing.\n"]
    (REPO / "Docs" / "DATA_DICTIONARY.md").write_text("\n".join(D), encoding="utf-8")
    print("wrote Docs/DATA_AND_PIPELINE_READINESS.md and Docs/DATA_DICTIONARY.md")
    print(json.dumps({k: v[0] for k, v in val.items()}, indent=1))


if __name__ == "__main__":
    main()
