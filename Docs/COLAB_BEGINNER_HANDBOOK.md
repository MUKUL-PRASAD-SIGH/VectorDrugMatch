# Colab beginner handbook: from zero to the final results

Written for someone who has never used Google Colab. Follow it in order. Nothing here needs programming: you click, wait, and check. Button names in Colab change slightly over time; if a label differs a little, look for the closest match.

**The version to use:** the code commit **`b86df0d`** (full value is in the notebook, in the line `PIN = '...'`). **Time needed:** the run is long and its length is **not known in advance**; Step 6 (smoke test) measures speed so you can judge. You can stop and resume.

**Words you will meet**
* *Notebook*: a document made of **cells**. A *code cell* is a grey box with a small **play button (▶)** on its left; pressing it runs the cell. A *text cell* is just explanation.
* *Runtime*: the computer Google lends you for a while. When it disconnects, everything on it is erased, **except what is saved in your Google Drive**. That is why everything important is written to Drive.
* *Drive*: your Google Drive storage.

---

## A. Before opening Colab (do this on your own computer)

### A1. Use a Google account with enough space
You need about **0.5 GB free for the upload** and a few GB for results. Use the account you will use in Colab.

### A2. Create the folders in Google Drive
1. Open https://drive.google.com and sign in.
2. Click **New** → **Folder** → name it exactly `VDM_Data` → Create.
3. Click **New** → **Folder** → name it exactly `VDM_Outputs` → Create. **Leave it empty.**
4. Both folders must stay **private**: do not click *Share*, do not make links public (they will hold restricted data).

### A3. Upload the files (drag and drop onto the folder in Drive)
`<PROJECT>` means the folder on your computer that contains `README.md`. Open `VDM_Data` in Drive and create the structure below, uploading each item from the path shown.

| Upload to (in Drive) | From (on your computer) | Size |
|---|---|---|
| `VDM_Data/mondo.obo` | `<PROJECT>/data/external/mondo.obo` | 53 MB |
| `VDM_Data/drugbank_smiles_cache.json` | `<PROJECT>/data/external/drugbank_smiles_cache.json` | 0.5 MB |
| `VDM_Data/drugbank_cid_map.json` | `<PROJECT>/data/external/drugbank_cid_map.json` | 0.2 MB |
| `VDM_Data/B09474-eng.pdf` | `<PROJECT>/data/external/B09474-eng.pdf` | 1.4 MB |
| `VDM_Data/downloads/hai_price_surveys/` (the whole folder) | `<PROJECT>/data/external/downloads/hai_price_surveys/` | 0.4 MB |
| `VDM_Data/downloads/open_targets/` (3 `.parquet` files) | `<PROJECT>/data/external/downloads/open_targets/` | 12 MB |
| `VDM_Data/downloads/open_targets_release_26.09/` (4 `.parquet` files) | `<PROJECT>/data/external/downloads/open_targets_release_26.09/` | 85 MB |
| `VDM_Data/downloads/ihme_gbd/` (3 files) | `<PROJECT>/data/external/downloads/ihme_gbd/` | 13 KB |
| `VDM_Data/frozen_processed/primekg/` (whole folder) | `<PROJECT>/data/processed/primekg/` | 94 MB |
| `VDM_Data/frozen_processed/primekg_structcov/` (whole folder) | `<PROJECT>/data/processed/primekg_structcov/` | 95 MB |

How: in Drive open `VDM_Data`, **New → New folder** for `downloads` and `frozen_processed`; open a folder and use **New → Folder upload** (for folders) or **New → File upload** (for single files). The total is about **340 MB**; it can take several minutes.

### A4. Check the upload is complete
Open `VDM_Data` in Drive and compare with this picture (names must match exactly, including capital letters; the Open Targets file names contain spaces and brackets, that is normal):
```
VDM_Data/
  mondo.obo
  drugbank_smiles_cache.json
  drugbank_cid_map.json
  B09474-eng.pdf
  downloads/
    hai_price_surveys/   delhi_2011-07/  karnataka_2004-11/  maharashtra_2005-01/
    open_targets/        00000000.parquet  00000000 (1).parquet  00000000 (2).parquet
    open_targets_release_26.09/   clinical_indication.parquet  clinical_report.parquet  drug_mechanism_of_action.parquet  drug_molecule.parquet
    ihme_gbd/            ihme_ntd_dalys_2023.csv  ihme_ntd_dalys_2023_citation.txt  IHME-GBD_2023_DATA-9feb184e-1.zip
  frozen_processed/
    primekg/             (8 files and a `splits` folder)
    primekg_structcov/   (8 files and a `splits` folder)
```
Quick size check: right-click `VDM_Data` → **File information → Details** (or *Get info*): about 340 MB. If a folder is missing or has far fewer files, upload it again.

### A5. What NOT to upload
* **No** `primekg_kg.csv` (the notebook downloads it, 1 GB).
* **No** other DrugBank files (`drug_target_drugbank.tsv`, `drugs_enriched.csv`, ...), nothing from `data/raw/`, nothing from `outputs/`, `mlruns/`, `.git/`.
* **No** `ihme_gbd_source_2023/` folder and no IHME ZIP from the project root (not needed).
* **Never** share the Drive folders. **Never** upload any of these files to GitHub.
* Do not put passwords, keys or `.env` files anywhere.

### A6. Make sure the code is on GitHub
Colab downloads the code from GitHub. The commit above must have been **pushed** (published on `mukul` and `main` on 2026-11-11, after your approval). To check: open https://github.com/MUKUL-PRASAD-SIGH/VectorDrugMatch/commits/mukul and look for a commit starting with `b86df0d`. If it is not there, stop: the run cannot start yet.

---

## B. Opening the notebook

### B1. Open it in Colab
Paste this address into your browser (it opens the notebook straight from GitHub):

`https://colab.research.google.com/github/MUKUL-PRASAD-SIGH/VectorDrugMatch/blob/mukul/notebooks/colab_final_run.ipynb`

Sign in with the same Google account as your Drive. (Alternative: go to https://colab.research.google.com, choose **File → Open notebook → GitHub**, paste `MUKUL-PRASAD-SIGH/VectorDrugMatch`, choose branch `mukul` and the file `notebooks/colab_final_run.ipynb`.)

### B2. Save your own copy to Drive and name it
1. **File → Save a copy in Drive**. A new tab opens with your copy.
2. Click the notebook title at the top-left and rename it to: `VDM_final_run_b86df0d`.
3. Work **only in your copy** from now on, so your own settings and any outputs shown in it are saved in your Drive.

### B3. Check you have the correct version
Scroll to the top: the first text cell says it is pinned to a commit and shows its first 10 characters (`b86df0d...`). Later, Step 2 prints a line with that commit: it must start with `b86df0d`. If it shows anything else, stop.

### B4. Choose the GPU
Menu **Runtime → Change runtime type**. Under *Hardware accelerator* choose **T4 GPU**, then **Save**. (A GPU is needed for the graph models.)

---

## C. Connecting Google Drive
Step 2 of the notebook runs `drive.mount(...)`. When you press ▶ on that cell:
1. A pop-up asks to **permit the notebook to access your Google Drive files**. Click **Connect to Google Drive** (or *Allow*).
2. Choose the **same Google account**.
3. Google lists what is being allowed ("access your Drive files"). This is required because the notebook reads `VDM_Data` and writes `VDM_Outputs`. Click **Continue / Allow**.
4. The cell prints `Mounted at /content/drive`. In the left sidebar, the folder icon now shows a `drive/MyDrive/` entry.
Only this notebook session gets access; you can revoke it later at https://myaccount.google.com/permissions.

---

## D. Running the notebook, step by step
**How to run a cell:** click it, then press the ▶ on its left (or Shift+Enter). Wait until the ▶ stops spinning and a small green check appears. **Run the cells in order, top to bottom. Never skip ahead.** Lines starting with `!` are system commands; that is normal. Red text is not always an error: warnings in red/orange are common. **Stop and read** the "must see" lines below.

| Step | What it does | You must see | Wait (not timed on Colab) |
|---|---|---|---|
| 1 GPU | checks the graphics card | `GPU available: True` and a table naming a Tesla T4 | seconds |
| 2 Drive, code, libraries (3 cells) | mounts Drive, downloads the code at the pinned commit, installs libraries | `Mounted at /content/drive`; a line starting `b86df0d`; `ok: ... torch_cluster available` | a few minutes |
| 3 Inputs | copies your Drive files into the session | `copied` lines for `mondo.obo`, `drugbank_*`, `B09474-eng.pdf`, `downloads/`; **no** error | short |
| 4 Prepare | downloads PrimeKG (about 1 GB) and rebuilds the benchmark | no `[FAIL]` anywhere; ends with `pipeline stage complete` | includes a 1 GB download |
| 4b Frozen-data check | proves the rebuilt data are identical to the frozen benchmark | `FROZEN BENCHMARK VERIFIED: 16 files match` (if it first says `MISMATCH` and then verifies after restoring the frozen copy, that is acceptable; an `AssertionError` is a **stop**) | short |
| 5 External evidence | builds the evidence/equity tables | `pipeline stage complete`; some optional lines may say a step failed only if you left that input out | short (1.6 min on a laptop) |
| 6 Smoke test | a very short run of every kind of model to catch problems early and to measure speed | `pipeline stage complete`; **note the seconds printed for each model** (write them down) | measured for you here |
| 6b Outputs on Drive | links the `outputs` folder to `VDM_Outputs` and records the environment | prints a JSON block (commit, GPU, torch) and `outputs -> /content/drive/MyDrive/VDM_Outputs/outputs` | seconds |
| 7 Full benchmark | trains and evaluates every model on the main benchmark (the long step) | each model prints its metrics; the cell ends with `pipeline stage complete` | long, unknown until Step 6 |
| 7b Explanations | SHAP and graph explanations on test pairs | `explain_manifest.json` mentioned; GNN explanation lines may be marked optional | not timed |
| 8 Structure-covered variant | repeats Step 7 on the second benchmark variant | as in Step 7 | long, unknown until Step 6 |
| 9 Freeze, package, download | writes the release manifest, builds `vdm_results.zip`, saves it to Drive and downloads it | the browser downloads `vdm_results.zip` | short |

### Decide after Step 6
Step 6's printed times let you estimate Step 7 and 8 (the notebook does not guess for you). If the estimate is longer than you can keep Colab open, read section F first: the run is built to be split over several sessions.

### While Step 7/8 runs
* Keep the browser tab open and the computer awake (turn off sleep). Colab may disconnect an idle session; a laptop that sleeps will disconnect it.
* A cell that shows a spinning ▶ is working, even if no text appears for minutes (the long models print only when they finish an epoch or a model).
* Do **not** run another cell at the same time, do not press "Interrupt" unless you want to stop.

---

## E. If something goes wrong
| Symptom | What to do |
|---|---|
| `GPU available: False` | Runtime → Change runtime type → T4 GPU → Save, then **Runtime → Restart session**, then run Step 1 again |
| Step 2: `git checkout` fails ("reference is not a tree") | the commit was not pushed to GitHub yet; stop and finish the push approval |
| Step 3: `AssertionError: upload mondo.obo` | the file is missing or misnamed in `VDM_Data`; fix it in Drive and re-run Step 3 |
| Step 4: a line containing `[FAIL]` | **do not continue to training**; copy the red lines and the lines above them and send them to me |
| Step 4b: `AssertionError` | the data are not the frozen benchmark; do not train; send me the printed list |
| "Disk full" / "out of memory" | Runtime → **Restart session**, re-run Steps 1-6b, then continue |
| Colab disconnected / page reloaded | see section F |
| A model step fails (red error, `STOPPED: step failed`) | note the model name; re-run the same cell once; if it fails again, send me the last 30 lines |
| You are unsure | stop and ask. Nothing is lost: results already saved stay in Drive |

---

## F. Resuming after a disconnect (this is expected on long runs)
Everything finished is already in `MyDrive/VDM_Outputs/outputs`, and `outputs/pipeline_log.jsonl` records which models finished. To continue:
1. Reopen **your saved copy** (`VDM_final_run_b86df0d`) from Drive.
2. Runtime → **Change runtime type** → T4 GPU (if needed) and run **Steps 1 to 6b again, in order**. (Step 6 repeats the smoke test; it can be skipped only if you are sure the session is healthy, but **do not skip 6b**.)
3. Run the Step 7 cell again. Because it uses `--resume`, the models that already finished at this same commit print `[resume] already completed ... skipped`, and only the missing ones train. Do the same for Step 8.
Never delete files in `VDM_Outputs`.

---

## G. Getting the results
* **In Drive:** `MyDrive/VDM_Outputs/outputs/` (all models, predictions, metrics, logs, explanations, figures) and `MyDrive/VDM_Outputs/vdm_results.zip` (the packaged results; Step 9 also downloads it to your computer). Setup/smoke logs are in `VDM_Outputs/smoke_and_setup_logs/`.
* Download a copy of `VDM_Outputs` to your computer (right-click → **Download**) and keep it safe; do not share it publicly (it contains results computed from restricted data).

## H. How to check the run really succeeded
Open (or ask me to open) these, in order:
1. `outputs/pipeline_log.jsonl`: every line has `"returncode": 0` (or `"optional": true` for an optional evidence step).
2. Step 4b printed `FROZEN BENCHMARK VERIFIED`.
3. Folders `outputs/primekg` and `outputs/primekg_structcov` each contain prediction files for all models (`baseline_*_coldstart_predictions.csv`, `predictions/gnn_*_predictions.csv`), and `ranking_report.md` shows no "covers N/M test pairs" warning. The two `_dp` folders hold the disease-profile baseline predictions.
4. `outputs/primekg/ablation_coldstart.csv`: the **shuffled-label control has ROC-AUC near 0.5**. If it does not, the results must not be used.
5. Report only the **cold-start** numbers; never the cross-validation numbers (they mix drugs and look better than they are).
Send me the Drive folder contents (or the zip) and I will prepare the analysis.

## I. Glossary of things that may confuse you
* **Smoke test**: a deliberately tiny run to find problems cheaply; its numbers mean nothing and are moved out of the way in Step 6b.
* **Cold-start**: testing on drugs that were never in training; the only kind of result we report.
* **Frozen benchmark**: the exact data and split fixed before training; Step 4b proves Colab uses the same ones.
* **Resume**: continuing without retraining finished models.
