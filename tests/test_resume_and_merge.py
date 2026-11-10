import subprocess
import sys
from pathlib import Path

import pandas as pd

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R))
sys.path.insert(0, str(R / "scripts"))
from src.utils.results_io import merge_rows  # noqa: E402
import run_full_pipeline as rfp  # noqa: E402


def test_merge_rows_keeps_other_models(tmp_path):
    f = tmp_path / "cmp.csv"
    merge_rows(f, pd.DataFrame({"name": ["GCN"], "roc_auc": [0.7]}))
    merge_rows(f, pd.DataFrame({"name": ["HGT"], "roc_auc": [0.8]}))
    merge_rows(f, pd.DataFrame({"name": ["GCN"], "roc_auc": [0.75], "extra": [1]}))          # same model re-run: replaced, not duplicated
    d = pd.read_csv(f).set_index("name")
    assert set(d.index) == {"GCN", "HGT"} and d.loc["GCN", "roc_auc"] == 0.75 and d.loc["HGT", "roc_auc"] == 0.8


def test_gnn_steps_are_one_call_per_model():
    st = rfp.steps("train", "full", 100)
    gnn = [c for c, _ in st if "train_gnn.py" in c[1]]
    assert [c[c.index("--models") + 1] for c in gnn] == ["GCN", "GraphSAGE", "GAT", "RGCN", "HGT"]
    assert sum("train_baselines.py" in c[1] for c, _ in st) == 10                      # 5 drug-only + 5 disease-profile
    assert any("train_node2vec.py" in c[1] for c, _ in st) and any("run_ablations_coldstart.py" in c[1] for c, _ in st)


def test_resume_skips_only_completed_training_steps(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        class P: returncode = 0; stdout = ""
        return P()
    monkeypatch.setattr(rfp.subprocess, "run", fake_run)
    monkeypatch.setattr(rfp, "REPO", tmp_path)
    monkeypatch.setattr(sys, "argv", ["x", "--stage", "train", "--variant", "full"])
    rfp.main()
    first = len([c for c in calls if len(c) > 1 and c[1].startswith("scripts/")])
    # a fresh session: same log, --resume -> nothing re-run
    calls.clear()
    monkeypatch.setattr(sys, "argv", ["x", "--stage", "train", "--variant", "full", "--resume"])
    rfp.main()
    assert first == 17 and not [c for c in calls if len(c) > 1 and c[1].startswith("scripts/")]
    # an interrupted step has no successful record -> it is re-run; remove one record (HGT) and resume
    log = tmp_path / "outputs" / "pipeline_log.jsonl"
    kept = [l for l in log.read_text().splitlines() if "--models HGT" not in l]
    log.write_text("\n".join(kept) + "\n")
    calls.clear()
    monkeypatch.setattr(sys, "argv", ["x", "--stage", "train", "--variant", "full", "--resume"])
    rfp.main()
    ran = [c for c in calls if len(c) > 1 and c[1].startswith("scripts/")]
    assert len(ran) == 1 and "HGT" in ran[0]


def test_baseline_steps_use_coldstart_only():
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location("rfp", pathlib.Path(__file__).resolve().parents[1] / "scripts" / "run_full_pipeline.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    for variant in ("full", "structcov"):
        base = [c for c, _ in m.steps("train", variant, 100) if "train_baselines.py" in c[1]]
        assert len(base) == 10 and all("--coldstart-only" in c for c in base)
        assert not any("--coldstart-only" in c for c, _ in m.steps("train", variant, 100) if "train_gnn.py" in c[1])
