"""
scripts/final_audit/evaluate_final_holdout.py - the ONE evaluation of the locked final holdout.

    python scripts/final_audit/evaluate_final_holdout.py --bundle outputs/final_audit_20261117/bundles/vdm-1.0.0

Preconditions (enforced): reports/final_audit_20261117/FROZEN_SELECTION.json exists; the bundle is FROZEN and was exported from that selection
(selection SHA-256 matches); the holdout file hash equals the committed protocol manifest; HOLDOUT_EVALUATED.lock does not exist.
The lock is written BEFORE any holdout label is read, so an interrupted run cannot be silently repeated.

Evaluates, on the holdout drugs (none used for training, selection or tuning):
  * the deployed bundle itself (its ranking_score and each component), plus every predeclared comparator trained on final_train
    (deg_conn_fp_gbm, rf_disease_profile, fingerprint/connectivity/degree GBMs, max_tanimoto, disease_popularity), on the 'hard' and 'popmatch'
    candidate sets: ROC-AUC, AP, trapezoidal PR-AUC, Brier, log loss, ECE, P/R/NDCG@K, stratified bootstrap 95% CIs (seed x pair for GCN);
  * paired hierarchical bootstrap: selected model vs each comparator (Holm-adjusted);
  * calibration (reliability table) of the selected model's probability-like components;
  * per-drug full ranking: for each holdout drug, ALL diseases ranked (pairs known in PrimeKG as contraindication/off-label excluded, the drug's
    holdout indications are the targets): recall@10/50/100, MRR, mean per-drug AP.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from src.features.simple_baselines import GROUPS, design  # noqa: E402
from src.serving.scoring import Scorer  # noqa: E402
from src.utils.final_metrics import all_metrics, hierarchical_paired_bootstrap, holm  # noqa: E402

REP = REPO / "reports/final_audit_20261117"
PROTO = REPO / "data/processed/primekg/splits_final_20261117"
DEV = REPO / "outputs/final_audit_20261117/dev_cv"
BOOT = 20261117


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def reliability(y, p, bins=10):
    idx = np.minimum((p * bins).astype(int), bins - 1)
    return [{"bin": f"[{b / bins:.1f},{(b + 1) / bins:.1f})", "n": int((idx == b).sum()), "mean_pred": float(p[idx == b].mean()) if (idx == b).any() else None,
             "frac_pos": float(y[idx == b].mean()) if (idx == b).any() else None} for b in range(bins)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--B", type=int, default=2000)
    ap.add_argument("--dry-run", action="store_true", help="exercise the full code path on final_train's internal-validation pairs (no lock, no holdout, "
                                                           "nothing written to the bundle); output under outputs/final_audit_20261117/holdout_dry_run")
    a = ap.parse_args()
    if a.dry_run:
        return run(a, REPO / a.bundle, None, REPO / "outputs/final_audit_20261117/holdout_dry_run", dry=True)
    selp = REP / "FROZEN_SELECTION.json"
    lock = REP / "HOLDOUT_EVALUATED.lock"
    if not selp.exists():
        sys.exit("no FROZEN_SELECTION.json: freeze the selection first")
    if lock.exists():
        sys.exit(f"{lock} exists: the holdout has already been evaluated ({lock.read_text()[:200]})")
    bundle = REPO / a.bundle
    man = json.loads((bundle / "manifest.json").read_text())
    if man["status"] != "FROZEN" or man.get("selection_sha256") != sha(selp):
        sys.exit("bundle is not the FROZEN export of the current selection")
    committed = json.loads((REP / "protocol_manifest_committed.json").read_text())
    hp = PROTO / "holdout_LOCKED.npz"
    if sha(hp) != committed["holdout"]["sha256"]:
        sys.exit("holdout file hash differs from the committed protocol manifest")
    lock.write_text(json.dumps({"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "bundle": man["bundle_version"],
                                "selection_sha256": sha(selp), "holdout_sha256": sha(hp)}), encoding="utf-8")
    run(a, bundle, hp, REP / "final_holdout", dry=False, man=man, lock=lock)


def run(a, bundle, hp, out, dry, man=None, lock=None):
    out.mkdir(parents=True, exist_ok=True)
    man = man or json.loads((bundle / "manifest.json").read_text())
    sc = Scorer(bundle)
    from src.data.graph_builder import build_hetero_data
    from src.features.disease_profile import build_disease_profile_block
    from src.features.pair import build_pair_features
    dis_x = build_hetero_data(REPO / "data/processed/primekg", include_features=True)["disease"].x.numpy()   # the RF's disease features, as in training
    if dry:
        z = np.load(PROTO / "final_train.npz")
        h = {"edges_holdout": z["edges_val"], "y_holdout": z["y_val"], "edges_holdout_popmatch": z["edges_val_popmatch"], "y_holdout_popmatch": z["y_val_popmatch"],
             "holdout_indication_pairs": z["edges_val"][:, z["y_val"] == 1][:, :400]}
    else:
        h = np.load(hp)
    res = {"bundle": man["bundle_version"], "selected_model": man["selected_model"], "kind": man["kind"], "sets": {}}
    preds_all = []
    for setname, ek, yk in (("hard", "edges_holdout", "y_holdout"), ("popmatch", "edges_holdout_popmatch", "y_holdout_popmatch")):
        e, y = h[ek], h[yk].astype(int)
        rs, comp, _ = sc.score(e[0], e[1])
        models = {"SELECTED(" + str(man.get("selected_model") or man["bundle_version"]) + ")": rs[None, :]}
        if sc.gcn:                                            # per-seed GCN probabilities (seed-level uncertainty)
            from src.serving.scoring import gcn_head_numpy
            models["gcn_component_per_seed"] = np.stack([gcn_head_numpy(g["emb_drug"], g["emb_disease"], {k: g[k] for k in ("W1", "b1", "W2", "b2")}, e[0], e[1]) for g in sc.gcn])
        feats = {"deg": sc.F.degree(e), "conn": sc.F.connectivity(e), "label": sc.F.label_features(e)}
        for name in GROUPS:
            mp = DEV / name / "final_train" / "seed0" / "model.joblib"
            models[name] = joblib.load(mp).predict_proba(design(feats, name))[:, 1][None, :]
        rf = joblib.load(DEV / "rf_disease_profile" / "final_train" / "seed0" / "model.joblib")
        Xrf = np.concatenate([build_pair_features(sc.fp.astype(np.float32), dis_x, e[0], e[1]), build_disease_profile_block(sc.fp, sc.F.train_edges, sc.F.train_y.astype(int), e)], 1)
        models["rf_disease_profile"] = rf.predict_proba(Xrf)[:, 1][None, :]
        models["max_tanimoto"] = feats["label"][:, 2][None, :]
        models["disease_popularity"] = feats["label"][:, 0][None, :]
        r = {"n_pairs": int(len(y)), "n_pos": int(y.sum()), "n_neg": int((1 - y).sum()), "models": {}, "paired_vs_selected": []}
        for k, S in models.items():
            r["models"][k] = {"per_seed": [all_metrics(y, s) for s in S]}
            m = pd.DataFrame(r["models"][k]["per_seed"]).mean().to_dict()
            ci = hierarchical_paired_bootstrap(y, S, np.zeros((1, len(y))) + 0.5, B=a.B, seed=BOOT)    # vs constant 0.5 => CI of the metric itself
            r["models"][k].update({"mean": m, "roc_auc_ci": [x + 0.5 for x in ci["roc_auc_diff_ci"]],
                                   "ap_ci": [x + y.mean() for x in ci["ap_diff_ci"]]})
        sel = list(models)[0]
        for k in list(models)[1:]:
            c = hierarchical_paired_bootstrap(y, models[sel], models[k], B=a.B, seed=BOOT)
            c.update({"model_1": sel, "model_2": k})
            r["paired_vs_selected"].append(c)
        adj_a, adj_p = holm([c["roc_auc_p"] for c in r["paired_vs_selected"]]), holm([c["ap_p"] for c in r["paired_vs_selected"]])
        for c, x1, x2 in zip(r["paired_vs_selected"], adj_a, adj_p):
            c["roc_auc_p_holm"], c["ap_p_holm"] = x1, x2
        for k, v in comp.items():
            r[f"reliability_{k}"] = reliability(y, v)
        res["sets"][setname] = r
        ids_d, ids_s = sc.drug_ids, sc.disease_ids
        preds_all.append(pd.DataFrame({"set": setname, "drug_id": ids_d[e[0]], "drug_name": sc.drug_names[e[0]], "disease_id": ids_s[e[1]],
                                       "disease_name": sc.disease_names[e[1]], "label": y, "ranking_score": rs,
                                       **{f"score_{k}": v for k, v in comp.items()}, **{f"baseline_{k}": models[k][0] for k in ("deg_conn_fp_gbm", "rf_disease_profile")}}))
    pd.concat(preds_all).to_csv(out / "HOLDOUT_PREDICTIONS.csv", index=False)

    # per-drug full ranking over all diseases
    pos = h["holdout_indication_pairs"]
    excl = (sc.known["contraindicated_for"] + sc.known["offlabel_for"]).tocsr()
    rows = []
    t0 = time.time()
    for d in np.unique(pos[0]):
        tgt = set(pos[1, pos[0] == d].tolist())
        s_all = np.arange(sc.n_dis)
        keep = ~(np.asarray(excl[d].todense()).ravel() > 0) | np.isin(s_all, list(tgt))
        s_all = s_all[keep]
        rs, comp, _ = sc.score(np.full(len(s_all), d), s_all)
        yv = np.isin(s_all, list(tgt)).astype(int)
        row = {"drug_id": str(sc.drug_ids[d]), "n_targets": int(yv.sum()), "n_candidates": int(len(s_all))}
        for k, v in {"selected": rs, **comp}.items():
            o = np.argsort(-v, kind="stable")
            ranks = np.where(yv[o] == 1)[0] + 1
            row.update({f"{k}_recall@10": float((ranks <= 10).mean()), f"{k}_recall@50": float((ranks <= 50).mean()), f"{k}_recall@100": float((ranks <= 100).mean()),
                        f"{k}_mrr": float(1.0 / ranks.min()), f"{k}_ap": float(average_precision_score(yv, v)), f"{k}_median_rank": float(np.median(ranks))})
        rows.append(row)
    pr = pd.DataFrame(rows)
    pr.to_csv(out / "per_drug_full_ranking.csv", index=False)
    res["per_drug_full_ranking"] = {"n_drugs": int(len(pr)), "seconds": round(time.time() - t0, 1),
                                    "means": pr.drop(columns=["drug_id"]).mean().round(4).to_dict(),
                                    "note": "all diseases ranked per holdout drug; PrimeKG contraindication/off-label pairs removed; targets = the drug's PrimeKG indications"}
    res["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    res["dry_run"] = dry
    (out / "HOLDOUT_RESULTS.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    if dry:
        print("DRY RUN OK", json.dumps(res["per_drug_full_ranking"]["means"], default=float)[:400])
        return
    lock.write_text(json.dumps({**json.loads(lock.read_text()), "finished_utc": res["finished_utc"], "results_sha256": sha(out / "HOLDOUT_RESULTS.json")}), encoding="utf-8")
    # attach to the bundle manifest (model files and their checksums unchanged)
    man["holdout_metrics"] = {"results_file": str((out / "HOLDOUT_RESULTS.json").relative_to(REPO)), "results_sha256": sha(out / "HOLDOUT_RESULTS.json"),
                              "hard": res["sets"]["hard"]["models"][list(res["sets"]["hard"]["models"])[0]]["mean"]}
    (bundle / "manifest.json").write_text(json.dumps(man, indent=1, default=float), encoding="utf-8")
    sel = res["sets"]["hard"]["models"][list(res["sets"]["hard"]["models"])[0]]
    print(json.dumps({"selected": man["selected_model"], "hard_auc": sel["mean"]["roc_auc"], "hard_auc_ci": sel["roc_auc_ci"], "hard_ap": sel["mean"]["pr_auc_ap"],
                      "hard_ap_ci": sel["ap_ci"], "per_drug": res["per_drug_full_ranking"]["means"]}, indent=1, default=float))


if __name__ == "__main__":
    main()
