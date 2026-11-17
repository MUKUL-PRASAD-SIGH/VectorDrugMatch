"""
scripts/final_audit/select_dev.py - run the predeclared stages and apply the predeclared selection rule (configs/final_audit_20261117_plan.json).

    python scripts/final_audit/select_dev.py run A            # convergence rerun on the historical split
    python scripts/final_audit/select_dev.py run B            # one-factor development CV
    python scripts/final_audit/select_dev.py run C            # top configs + combination, 2 more seeds (derived from B results)
    python scripts/final_audit/select_dev.py run final        # best GCN config on final_train, 5 seeds
    python scripts/final_audit/select_dev.py summarize        # dev table (GCN configs, baselines, rank-average ensembles)
    python scripts/final_audit/select_dev.py freeze           # write reports/.../FROZEN_SELECTION.json (refuses to overwrite)

Only validation files of the development folds are read. The locked holdout is never touched.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.metrics import average_precision_score, roc_auc_score

REPO = Path(__file__).resolve().parents[2]
PLAN = json.loads((REPO / "configs/final_audit_20261117_plan.json").read_text(encoding="utf-8"))
OUT = "outputs/final_audit_20261117"
DEV = REPO / OUT / "dev_cv"
REPORT = REPO / "reports/final_audit_20261117"
FOLDS = PLAN["stage_B_one_factor"]["splits"]
BASE_GBM = "deg_conn_fp_gbm"


def hp_of(over):
    return {**PLAN["common"], **over}


def cmd(name, hp, splits, seeds, out):
    c = [sys.executable, "scripts/final_audit/train_gcn_protocol.py", "--name", name, "--splits", *splits, "--seeds", *map(str, seeds), "--out", out, "--resume"]
    for k, flag in (("arch", "--arch"), ("variant", "--variant"), ("layers", "--layers"), ("emb", "--emb"), ("head", "--head"), ("dropout", "--dropout"),
                    ("lr", "--lr"), ("wd", "--wd"), ("k", "--k"), ("epochs", "--epochs"), ("patience", "--patience"), ("sched_patience", "--sched-patience")):
        c += [flag, str(hp[k])]
    return c


def run(c):
    print(">>", " ".join(c[1:]), flush=True)
    r = subprocess.run(c, cwd=REPO)
    if r.returncode:
        sys.exit(f"run failed ({r.returncode})")


def val_scores(model, fold):
    """list of (seed, labels, probs) of validation predictions for model/fold (hard and popmatch)."""
    out = []
    for d in sorted((DEV / model / fold).glob("seed*")):
        f = d / "val_predictions.csv"
        if f.exists():
            v = pd.read_csv(f)
            pm = pd.read_csv(d / "val_popmatch_predictions.csv")
            out.append((int(d.name[4:]), v, pm))
    return out


def dev_table():
    gcn = sorted({p.parts[-4] for p in DEV.glob("*/cv_fold*/seed*/run_config.json")})
    base = sorted({p.parts[-4] for p in DEV.glob("*/cv_fold*/seed0/metrics.json")} - set(gcn))
    rows = []

    def add(name, kind, fold, seed, v, pm, n_params=None):
        rows.append({"model": name, "kind": kind, "fold": fold, "seed": seed, "val_auc": roc_auc_score(v.label, v.probability), "val_ap": average_precision_score(v.label, v.probability),
                     "popmatch_auc": roc_auc_score(pm.label, pm.probability), "popmatch_ap": average_precision_score(pm.label, pm.probability), "n_params": n_params})

    for m in gcn + base:
        for f in FOLDS:
            for s, v, pm in val_scores(m, f):
                npar = None
                mj = DEV / m / f / f"seed{s}" / "metrics.json"
                if m in gcn:
                    npar = json.loads(mj.read_text())["n_params"]
                add(m, "gcn" if m in gcn else "baseline", f, s, v, pm, npar)
    # parameter-free rank-average ensembles of each GCN config with the strongest simple baseline (same rows: same split file)
    for m in gcn:
        for f in FOLDS:
            b = val_scores(BASE_GBM, f)
            if not b:
                continue
            _, bv, bpm = b[0]
            for s, v, pm in val_scores(m, f):
                assert (v.drug_id.values == bv.drug_id.values).all() and (v.label.values == bv.label.values).all()
                ev = v.assign(probability=(rankdata(v.probability) + rankdata(bv.probability)) / (2 * len(v)))
                epm = pm.assign(probability=(rankdata(pm.probability) + rankdata(bpm.probability)) / (2 * len(pm)))
                add(f"rankavg[{m}+{BASE_GBM}]", "ensemble", f, s, ev, epm)
    df = pd.DataFrame(rows)
    g = df.groupby(["model", "kind"])
    summ = g.agg(n_runs=("val_ap", "size"), n_folds=("fold", "nunique"), n_seeds=("seed", "nunique"), val_ap=("val_ap", "mean"), val_ap_sd=("val_ap", "std"),
                 val_auc=("val_auc", "mean"), val_auc_sd=("val_auc", "std"), popmatch_ap=("popmatch_ap", "mean"), popmatch_auc=("popmatch_auc", "mean"),
                 n_params=("n_params", "max")).reset_index().sort_values("val_ap", ascending=False)
    return df, summ


def select(summ, candidates):
    c = summ[summ.model.isin(candidates)].copy()
    best = c.val_ap.max()
    tied = c[c.val_ap >= best - 0.005].copy()
    tied["is_ensemble"] = tied.kind.eq("ensemble")
    tied = tied.sort_values(["popmatch_ap", "is_ensemble", "n_params"], ascending=[False, True, True])
    return tied.iloc[0].model, tied


def stage_b_means(summ):
    return summ.set_index("model").val_ap


def stage_c_configs(df):
    """Stage C plan from the STAGE B runs only (stage B seeds, all folds). Bug fixed 2026-11-18: the first version used means over every seed present,
    so re-running stage C after it had added seeds changed the plan (observed on Colab: L4 replaced L3_emb128 on the second run)."""
    sb = PLAN["stage_B_one_factor"]["configs"]
    sb_seeds = PLAN["stage_B_one_factor"]["seeds"]
    m = df[df.model.isin(sb) & df.seed.isin(sb_seeds)].groupby("model").val_ap.mean()
    top = list(m.sort_values(ascending=False).index[: PLAN["stage_C"]["n_top"]])
    base = m["L3_base"]
    combo, gain_of = {}, {}
    for name, over in sb.items():
        if name == "L3_base" or set(over) & {"variant", "arch"} or name not in m:
            continue
        g = m[name] - base
        if g >= PLAN["stage_C"]["combo_min_gain_ap"]:
            for k, v in over.items():
                if k not in combo or g > gain_of[k]:
                    combo[k], gain_of[k] = v, g
    cfg = {t: sb[t] for t in top}
    if len([k for k in combo if k != "head"]) >= 2:
        cfg["L3_combo"] = combo
    return cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["run", "summarize", "freeze"])
    ap.add_argument("stage", nargs="?")
    a = ap.parse_args()
    if a.action == "run":
        if a.stage == "A":
            s = PLAN["stage_A_convergence"]
            run(cmd(s["name"], hp_of(s["overrides"]), s["splits"], s["seeds"], f"{OUT}/convergence"))
        elif a.stage == "B":
            s = PLAN["stage_B_one_factor"]
            for name, over in s["configs"].items():
                run(cmd(name, hp_of(over), s["splits"], s["seeds"], f"{OUT}/dev_cv"))
        elif a.stage == "C":
            df, _ = dev_table()
            cfgs = stage_c_configs(df)
            (REPO / OUT / "stage_C_plan.json").write_text(json.dumps(cfgs, indent=1), encoding="utf-8")
            print("stage C configs:", json.dumps(cfgs))
            seeds = [42] + PLAN["stage_C"]["seeds_added"]
            for name, over in cfgs.items():
                run(cmd(name, hp_of(over), FOLDS, seeds, f"{OUT}/dev_cv"))
        elif a.stage == "final":
            name, over = best_gcn()
            run(cmd(name, hp_of(over), [PLAN["final_training"]["split"]], PLAN["final_training"]["seeds"], f"{OUT}/final_model"))
        else:
            sys.exit("stage must be A, B, C or final")
        return
    df, summ = dev_table()
    REPORT.mkdir(parents=True, exist_ok=True)
    df.to_csv(REPORT / "DEV_CV_RUNS.csv", index=False)
    summ.to_csv(REPORT / "DEV_CV_SUMMARY.csv", index=False)
    print(summ.round(4).to_string(index=False))
    if a.action == "freeze":
        f = REPORT / "FROZEN_SELECTION.json"
        if f.exists():
            sys.exit(f"{f} exists: the selection is frozen once")
        gname, gover = best_gcn()
        final, tied = select(summ, [gname, BASE_GBM, f"rankavg[{gname}+{BASE_GBM}]"])
        ckpts = sorted((REPO / OUT / "final_model" / gname / "final_train").glob("seed*/model.pth"))
        sel = {"frozen_utc": pd.Timestamp.utcnow().isoformat(), "rule": PLAN["selection_metric"] + "; " + PLAN["tie_rule"], "best_gcn_config": gname,
               "best_gcn_hp": hp_of(gover), "selected_model": final, "tied_candidates": tied.to_dict("records"),
               "gcn_final_checkpoints": {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in ckpts},
               "gbm_final_model": str((DEV / BASE_GBM / "final_train" / "seed0" / "model.joblib").relative_to(REPO)),
               "holdout_status": "not yet evaluated"}
        if not ckpts:
            sys.exit("no final_train GCN checkpoints: run 'run final' first")
        f.write_text(json.dumps(sel, indent=1, default=str), encoding="utf-8")
        print(json.dumps({k: v for k, v in sel.items() if k != "tied_candidates"}, indent=1, default=str))


def best_gcn():
    _, summ = dev_table()
    planC = REPO / OUT / "stage_C_plan.json"
    if not planC.exists():
        sys.exit("stage C has not run")
    cfgs = json.loads(planC.read_text())
    full = summ[summ.model.isin(cfgs) & (summ.n_seeds >= 3) & (summ.n_folds == len(FOLDS))]
    name, _ = select(full, list(full.model))
    return name, cfgs[name]


if __name__ == "__main__":
    main()
