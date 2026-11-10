# VectorDrugMatch - Colab Playbook (run everything, step by step)

**How to use this file**

* Easiest: open **`notebooks/colab_primekg.ipynb`** in Colab (File > Open notebook > GitHub, or upload it) - it is
  this same playbook with every code cell ready, so you just press play on each cell in order.
* Or read this page and copy each code block into its own Colab cell.
* Run the cells **top to bottom, one at a time**, and read the "What you should see" line before moving on.
  If something does not match, go to the "If it breaks" line - do not skip ahead.

**What you are about to do (in plain words)**

1. Download PrimeKG (a big biomedical knowledge graph) and the MONDO disease dictionary.
2. Turn PrimeKG into tables the project understands (drugs, diseases, genes, edges).
3. Make ONE fixed train / validation / test split and save it, so every model is tested on exactly the same pairs.
4. Run an automatic safety check (no cheating / no leakage). **If this check fails, stop.**
5. Train the models (simple baselines, Node2Vec, then the 5 graph neural networks).
6. Print one table that compares all models, including a separate look at neglected tropical diseases (NTDs).

**The three tracks** (so you know what is what)

| Track | Data | What it is |
|---|---|---|
| A | Hetionet | the original small graph, kept as a reference (Part B, optional) |
| **B** | **PrimeKG** | **the main model - this playbook (Part A)** |
| C | PrimeKG, NTD diseases only | an analysis done on the same run: the report has an `ntd_only` row |

**Words you will see**

* *Indication* = "this drug is approved/used to treat this disease". This is the ONLY thing the models try to predict.
* *Contraindication / off-label* = other drug-disease facts. They stay in the graph as separate relations and are
  **never** turned into "negative" labels.
* *Drug-disjoint split* = a drug that is in the test set is never seen in training (this is the honest, hard setting).
* *Leakage* = accidentally letting the model see the answer. The validate step checks for this.

**Time and cost (rough guesses, they depend on Colab load)**: downloads and dataset building are minutes; the
baselines are minutes to an hour; the 5 GNNs can take **from about half an hour to a few hours** on a T4. Do a
quick smoke run first (`--epochs 5`) before the long one.

---

## Step 0 - On YOUR PC, once: push the new code to GitHub

Colab downloads the code from GitHub, so the new files must be on GitHub first. Open **PowerShell** in the project folder
and run these lines one by one:

```powershell
cd <path-to-your-local-clone>/VectorDrugMatch
git status
```

Look at the list. You should see new scripts (`primekg_dataset.py`, `primekg_split.py`, ...) and **no** huge files.
Data files are ignored automatically (that is what `.gitignore` is for), so nothing big should appear.

```powershell
git add .gitignore .env.example configs scripts src Docs notebooks data/external/.gitkeep data/external/README.md
git status
git commit -m "Add PrimeKG pipeline (Track B): dataset, split, validation, leak-free baselines, Colab playbook"
git push origin mukul
```

* **Heads up (licences):** two DrugBank-derived files were pushed earlier (`data/external/drugbank_smiles_cache.json`,
  `drugbank_cid_map.json`). This commit stops tracking them, but they still exist in old commits. Decide with your
  team whether to clean history before sharing the repo publicly.
* If `git push` is rejected, run `git pull --rebase origin mukul` and push again.

---

# Part A - Track B: PrimeKG (the main run)

## Step 1 - Pick a GPU

Graph neural networks are slow on CPU. In Colab: **Runtime > Change runtime type > T4 GPU > Save**. Then run this cell.

```python
import torch
print('torch', torch.__version__, '| GPU available:', torch.cuda.is_available())
!nvidia-smi | head -15
```

**What you should see:** `GPU available: True` and a table showing a Tesla T4 (or similar).

**If it breaks:** If it says False: Runtime > Change runtime type > pick GPU, then Runtime > Restart session, and run the cell again.

---

## Step 2 - Connect Google Drive and download the code

Drive is where we save results so they survive if Colab disconnects. The clone line fetches your code from GitHub.

```python
from google.colab import drive
drive.mount('/content/drive')
!mkdir -p /content/drive/MyDrive/VDM_Data /content/drive/MyDrive/VDM_Outputs
%cd /content
!rm -rf VectorDrugMatch
!git clone https://github.com/MUKUL-PRASAD-SIGH/VectorDrugMatch
%cd VectorDrugMatch
!git checkout mukul
# pinned code version (reproducibility): do not change unless you re-audit
!git checkout 522deb30dc87327d694b273c6ab5911ced24c53e
!git log -1 --oneline
!ls scripts/primekg_dataset.py scripts/primekg_split.py scripts/validate_primekg_dataset.py
```

**What you should see:** A line with your latest commit message, then the three file names printed (no 'No such file').

**If it breaks:** 'No such file' means Step 0 was not pushed. Do Step 0 again on your PC, then re-run this cell. If the clone asks for a login, the repo is private: use a GitHub token in the URL or make the repo accessible.

---

## Step 3 - Install the libraries

One-time install for this Colab session (about 2-4 minutes). The long `pip` line for `pyg_lib ...` picks wheels that match Colab's torch version.

```python
!pip install -q rdkit mlflow optuna shap xgboost lightgbm loguru pyyaml torch-geometric tabulate scikit-learn
import torch
v = torch.__version__.split('+')[0]; c = (torch.version.cuda or '').replace('.', '')
!pip install -q pyg_lib torch_scatter torch_sparse torch_cluster -f https://data.pyg.org/whl/torch-{v}+cu{c}.html
import torch_geometric, torch_cluster
print('ok:', torch.__version__, torch_geometric.__version__)
```

**What you should see:** `ok: 2.x.x ...` with no red error text.

**If it breaks:** If `torch_cluster` fails to import, Node2Vec (Step 11) will fail but everything else still works - skip Step 11 and tell me.

---

## Step 4 - Download the data (PrimeKG + MONDO)

Downloads PrimeKG (~1 GB), the MONDO disease dictionary (~50 MB) and a few small files. Takes a few minutes. Nothing to upload by hand.

```python
!python scripts/fetch_public_data.py --primekg
!ls -lh data/external | head -20
```

**What you should see:** Lines like `-> data/external/primekg_kg.csv (981.8 MB)` and `mondo.obo`. At the end it prints a MANUAL list (DALY, WHO EML) - ignore that for now.

**If it breaks:** A `[FAILED]` line = network hiccup: just run the cell again (finished files are skipped). Check the file really is ~981 MB: `!ls -l data/external/primekg_kg.csv`.

---

## Step 5 - (Optional but recommended) Reuse saved drug structures

Building the drug features needs each drug's chemical structure (SMILES). If you saved a cache in Drive last time, this copies it back so Step 6 is faster. First time: nothing to copy, that is fine.

```python
import os, shutil
src = '/content/drive/MyDrive/VDM_Data/drugbank_smiles_cache.json'
if os.path.exists(src):
    shutil.copy(src, 'data/external/drugbank_smiles_cache.json'); print('restored SMILES cache from Drive')
else:
    print('no cache in Drive yet (normal on the first run)')
```

**What you should see:** Either message is fine.

---

## Step 6 - Build the PrimeKG tables

Reads PrimeKG, maps every disease to a standard ID (MONDO to DOID), flags the neglected tropical diseases, looks up drug structures (a web service called MyChem is queried for drugs not in the cache, ~6,000 of them, a few minutes) and writes the tables to `data/processed/primekg/`. Nothing is silently dropped: every disease is kept with a `mapping_status`.

```python
CFG = 'configs/primekg_morgan.yaml'
!python scripts/primekg_dataset.py --config $CFG
# save the SMILES cache so next time is faster
!cp data/external/drugbank_smiles_cache.json /content/drive/MyDrive/VDM_Data/ 2>/dev/null || true
```

**What you should see:** At the end: `"drugs": 7957, "diseases": 17080, ...`, `indication` edges_kept 9388, and `DONE -> .../data/processed/primekg`. The line `SMILES coverage: N/7957` should be roughly 6,900-7,000 (a local test gave 6,961); the rest are mostly biologics with no structure, which is normal. This step takes about 2-3 minutes.

**If it breaks:** If MyChem/PubChem time out, re-run the cell (it only asks for drugs it has not resolved yet). If you are short of RAM (red 'crashed' message), re-run with a lighter graph: add `--skip-relations protein_protein` to the command.

---

## Step 7 - Make and save the train / validation / test split

Splits the drugs (not the pairs) into train / val / test = 70/15/15 so a test drug is never seen in training, and draws the 'not-a-treatment' examples (sampled pairs that are not a known indication, contraindication or off-label pair). The result is saved once and every model reads that same file.

```python
!python scripts/primekg_split.py --config $CFG
```

**What you should see:** A JSON summary then `saved .../splits/seed42.npz`. Train has ~6,730 positives, val ~1,397, test ~1,261; NTD positives in each split (55 / 12 / 15).

---

## Step 8 - The safety check (STOP here if it fails)

Checks for duplicates, broken IDs, drugs shared between train and test, sampled negatives that are really known pairs, held-out answers hiding in the graph the GNN learns from, and that re-running the split gives the identical result.

```python
!python scripts/validate_primekg_dataset.py --config $CFG
```

**What you should see:** The last line must say `all hard checks passed`. Yellow `[WARN]` lines are okay (for example PrimeKG itself lists a few pairs as both indication and contraindication - that is reported, not hidden). A report is saved at `outputs/primekg/validation_report.md`.

**If it breaks:** Any `[FAIL]` = do **not** train. Copy the FAIL lines to me.

---

## Step 9 - Back up the prepared data to Drive

So that if Colab disconnects you can skip Steps 4-8 next time (see the 'Resume' box at the end).

```python
!mkdir -p /content/drive/MyDrive/VDM_Data
!cp -r data/processed/primekg /content/drive/MyDrive/VDM_Data/
!cp outputs/primekg/validation_report.* /content/drive/MyDrive/VDM_Outputs/ 2>/dev/null || true
!ls /content/drive/MyDrive/VDM_Data/primekg
```

**What you should see:** A list with drugs.csv, diseases.csv, genes.csv, edges.csv, splits ...

---

## Step 10 - Train the classical baselines

Logistic Regression, Naive Bayes, Random Forest, XGBoost, MLP. They use the drug's chemical fingerprint plus a few disease numbers. Use the `coldstart_*` numbers it prints (those are on the held-out test drugs). Ignore any plain 5-fold-CV number for the paper: that one pools drugs across folds and is easier than the real task.

```python
%env MLFLOW_TRACKING_URI=sqlite:///mlflow.db
!python scripts/train_baselines.py --model all --config $CFG
```

**What you should see:** For each model: `Cold-start test ROC-AUC: ...  PR-AUC: ...`. Files appear in `outputs/primekg/`.

**If it breaks:** Out of memory? Run one model at a time: `--model xgb` then `--model rf` (names: logistic, nb, rf, xgb, mlp).

---

## Step 11 - Node2Vec (leak-free)

Learns an embedding of every node by random walks, then a small classifier on top. This version only lets the walks see the training answers - the old `train_benchmark.py` let it see the test answers, so do not use that one for PrimeKG.

```python
import torch, torch_cluster
print(torch.__version__, 'torch_cluster available')
!python scripts/train_node2vec.py --config $CFG --dry-run
!python scripts/train_node2vec.py --config $CFG --epochs 1   # one-epoch test; then run the full 10 epochs below
!python scripts/train_node2vec.py --config $CFG --epochs 10
```

**What you should see:** A line `walk graph: ... held-out pairs absent: OK`, then epochs, then a ROC-AUC/PR-AUC/MCC block.

**If it breaks:** Quick test first: add `--dry-run` (only builds and checks the graph). `torch_cluster` import error = Step 3 note.

---

## Step 12 - Train the 5 graph neural networks

GCN, GraphSAGE, GAT, RGCN, HGT. They learn from the whole graph (drug-gene, disease-gene, gene-gene, disease-disease, contraindication, off-label links) but the graph they see has every treatment answer removed. **First do a short smoke run (5 epochs) to make sure nothing crashes**, then the full run.

```python
# smoke run (a few minutes)
!python scripts/train_gnn.py --config $CFG --epochs 5
```

**What you should see:** Each model prints a metrics line. Files appear: `outputs/primekg/gnn_comparison.csv` and `outputs/primekg/predictions/gnn_*_predictions.csv`.

**If it breaks:** `CUDA out of memory`: Runtime > Restart session, re-run Steps 2-3, and rebuild with a lighter graph (Step 6 with `--skip-relations protein_protein`, then Steps 7-9 again).

---

## Step 12b - The full GNN run

Only after the smoke run worked. Colab may disconnect on very long runs, so keep the tab open; if it does, use the 'Resume' box.

```python
!python scripts/train_gnn.py --config $CFG --epochs 100
```

**What you should see:** Same as above, with better numbers.

---

## Step 13 - One table to compare everything

Scores every model on the **same test pairs** and adds: ROC-AUC, PR-AUC, MCC, Precision@K, Recall@K, MRR, NDCG@K (ranking is per disease), plus extra rows for `ntd_only` (neglected tropical diseases) and `mapped_only` (diseases with a clean DOID mapping), and `with_structure` / `no_structure` (drugs with / without a usable chemical fingerprint; 996 drugs have no SMILES and are all-zero features). Compare `all` against `with_structure`: a large gap means the model is using missing-structure as a shortcut. The primary result is the `all` row; always quote the structure coverage printed above the table.

```python
!python scripts/evaluate_primekg.py --config $CFG
import pandas as pd
display(pd.read_csv('outputs/primekg/ranking_report.csv').round(4))
```

**What you should see:** A table with one row per model per subset. Reading tips: compare models on the `all` rows first; the `ntd_only` rows have only ~15 test positives, so treat them as a rough look, not a result.

**If it breaks:** A `[SKIP] ... cannot be aligned` line means that prediction file was not from the saved split - ignore that file.

---

## Step 14 - Save everything and download it

Copies results to Drive and gives you a zip.

```python
!mkdir -p /content/drive/MyDrive/VDM_Outputs
!cp -r outputs /content/drive/MyDrive/VDM_Outputs/primekg_run
!zip -rq vdm_primekg_results.zip outputs
from google.colab import files
files.download('vdm_primekg_results.zip')
```

**What you should see:** A zip downloads to your PC.

---

## Resume box - Colab disconnected, what now?

Do Steps 1, 2 and 3 again (GPU, clone, install). Then, instead of Steps 4-8, restore your saved data:

```python
!mkdir -p data/processed data/external outputs
!cp -r /content/drive/MyDrive/VDM_Data/primekg data/processed/
CFG = 'configs/primekg_morgan.yaml'
!python scripts/validate_primekg_dataset.py --config $CFG --skip-reproduce
```

If that says `all hard checks passed`, continue from Step 10.

---

# Part B (optional) - Track A: the original Hetionet baseline

Only do this if you also want the old reference numbers. Everything goes into `data/processed/baseline_morgan` and
`outputs/baseline_morgan`, so it never overwrites PrimeKG results. Run Steps 1-3 of Part A first (same Colab session is fine).

## B1 - Download Hetionet and build it

Downloads Hetionet and the PharmacotherapyDB negatives, fetches drug structures and builds the tables.

```python
!python scripts/fetch_public_data.py
!python scripts/fetch_smiles.py
!python scripts/preprocess.py --config configs/baseline_morgan.yaml
!python scripts/validate_pipeline.py --config configs/baseline_morgan.yaml
!python scripts/validate_negatives.py --config configs/baseline_morgan.yaml
```

**What you should see:** `All hard checks passed.` (a WARN about DALY is expected - no DALY data yet).

**If it breaks:** FAIL lines = stop and send them to me.

---

## B2 - Train and compare

Same models as Part A, on Hetionet.

```python
CFG_A = 'configs/baseline_morgan.yaml'
%env MLFLOW_TRACKING_URI=sqlite:///mlflow.db
!python scripts/train_baselines.py --model all --config $CFG_A
!python scripts/train_gnn.py --config $CFG_A --epochs 100
!python scripts/evaluate.py --config $CFG_A
import pandas as pd
display(pd.read_csv('outputs/baseline_morgan/model_comparison.csv'))
```

**What you should see:** A comparison table of all models.

**If it breaks:** The old `train_benchmark.py` Node2Vec result is leaky - do not report it.

---

---

## Optional extras (not needed for the core run)

* **DALY burden and WHO Essential Medicines List** are not wired into the PrimeKG tables yet (`daly_rate` stays empty on purpose,
  never zero). When you have them: put `daly_burden.csv` (one row per disease for ONE year / place / sex / age / metric - the loader
  refuses mixed data) and `who_eml.csv` into `data/external/`. They feed the equity score later, not the prediction model.
* **Other seeds** (to report variation): `!python scripts/primekg_split.py --config $CFG --seed 7`, then copy the config, change
  `random_seed` and `presplit` to `seed7`, and repeat Steps 8 to 13.
* **MONDO to DOID audit report** (already built; only run it to refresh): `!python scripts/audit_primekg_mapping.py` - writes `Docs/PRIMEKG_MAPPING_AUDIT.md` and the NTD coverage table.

## If it breaks (quick table)

| What you see | What to do |
|---|---|
| `No such file or directory: scripts/...` | Step 0 push was missed, or you are on the wrong branch (`!git checkout mukul`). |
| `ModuleNotFoundError` | Re-run Step 3, then Runtime > Restart session and run Steps 2-3 again. |
| `CUDA out of memory` | Rebuild lighter: Step 6 with `--skip-relations protein_protein`, then Steps 7-9 again. |
| Red 'Your session crashed (RAM)' | Same lighter rebuild; also close other Colab tabs. |
| Validation prints `[FAIL]` | Do not train. Send me the FAIL lines. |
| Download stuck / `[FAILED]` | Run the cell again. |

## Rules that keep the results honest

1. Do not train anything before Step 8 says `all hard checks passed`.
2. Report the `all` rows first; show `ntd_only` with its small counts and never claim NTD-specific performance from ~15 test positives.
3. Contraindications and off-label uses are never negative labels. Sampled negatives are "unlabelled pairs", not proven non-treatments.
4. Use the same split file for every model; if you change the seed, change it for all of them.
