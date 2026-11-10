# legacy/

Files from earlier project phases (Hetionet-era track, first PrimeKG notebook, early plans). They were **moved with `git mv`, not deleted**, so `git log --follow <file>` still shows their history.
They are **not used** by the final pipeline (`scripts/run_full_pipeline.py`) or by `notebooks/colab_final_run.ipynb`. Some are known to be unsafe for the paper: `scripts/train_benchmark.py` and `scripts/run_ablations.py` are not drug-disjoint (leakage-prone). Do not report their results as cold-start results.

| folder | contents |
|---|---|
| `scripts/` | main_pipeline, train_benchmark, run_ablations, optuna_gnn, validate_pipeline, evaluate, export_codebase, validate_negatives |
| `root_scripts/` | fix_proc, featurize_pubchem, process_pubchem_bulk |
| `notebooks/` | colab_primekg, colab_train (older pins) |
| `docs/` | API, ARCHITECTURE, DEVELOPMENT_SUMMARY, MASTER_PLAN, COLAB_PLAYBOOK, FINAL_EXECUTION_PLAN (early plans; may describe components that do not exist) |

Paths inside these files were not edited; they may refer to their old locations.
