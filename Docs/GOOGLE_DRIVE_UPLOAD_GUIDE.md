# Google Drive upload guide (one upload, then Colab)

> **Status update (2026-11-11):** the Colab run described here as pending has been completed. Current status, results, the code of record (`1c85d98`) and known caveats: [`Docs/PROJECT_STATUS.md`](PROJECT_STATUS.md). Where this document says "pending", "not yet run" or names an older pin, the status file wins.


This is the single reference for **what goes into Google Drive**. The file list is machine-checked: `Docs/drive_upload_expected.json` (path, size and SHA-256 of every file; hashes only, no data).
`<REPO>` below means the folder on your computer that contains `README.md`. No script uploads anything: **you** upload, and you keep both Drive folders private.

## 0. Where the guides are, and which one to follow
| document | path in the repository | use |
|---|---|---|
| **Authoritative beginner guide** | `Docs/COLAB_BEGINNER_HANDBOOK.md` | follow it top to bottom: A (before Colab), B (open the notebook), C (connect Drive), D (run, step by step), E (problems), F (resume), G (results), H (check success) |
| This file (upload inventory) | `Docs/GOOGLE_DRIVE_UPLOAD_GUIDE.md` | the exact files and folders for Drive; handbook section A3 points here |
| Technical reference | `Docs/COLAB_TRAINING_HANDOFF.md` | pin, dependencies, ordered steps, CV/calibration decision |
| Remaining human actions | `Docs/FINAL_PROJECT_HANDOFF.md`, `Docs/HUMAN_ACTION_CHECKLIST.md` | licence and team-name decisions (none blocks training) |
| Publication record | `Docs/PUBLICATION_PLAN.md` | which commits are public, what the next push adds |
| Notebook | `notebooks/colab_final_run.ipynb` | what you run; opened from GitHub |

Before training you must read: sections 1-4 of this guide and handbook sections A-D. Nothing else is required.
A copy of these documents is also in the git-ignored folder `<REPO>/VDM_FINAL_FOLDER/` on your computer, next to a ready-to-upload folder (section 4.1).

## 1. What goes where
1. **Must upload** (REQUIRED in the table): the frozen MONDO release, the two DrugBank-derived caches, the safety copy of the frozen benchmark.
2. **Recommended** (RECOMMENDED): WHO EML PDF, HAI surveys, Open Targets release tables, IHME export. If you omit one, its component of the equity table is reported as **missing, never 0**; the benchmark and all models are unaffected.
3. **Already in GitHub (do not upload):** all code, configs, tests, the notebook, and the release manifest `Docs/release/vdm_v1_candidate_manifest.json`.
4. **Created automatically in Colab (do not upload):** `primekg_kg.csv` (about 1 GB, downloaded in Step 4 from Harvard Dataverse and hash-checked in Step 4b), the rebuilt benchmark tables, Python packages, checkpoints, predictions, metrics, logs.
5. **Must NOT upload:** `data/external/primekg_kg.csv`; any other DrugBank file (`drug_target_drugbank.tsv`, `drugs_enriched.csv`, ...); `data/raw/`; `data/external/downloads/ihme_gbd_source_2023/` and the IHME ZIP in the project root; `outputs/`, `mlruns/`, `.git/`; `.env` or any key. Do not upload the whole repository.
6. **Duplicates removed on purpose:** the three files in `downloads/open_targets/` are byte-identical (SHA-256 verified) to three of the four files in `open_targets_release_26.09/`, so only the release folder is uploaded; the notebook (Step 3) recreates `open_targets/` from it.

## 2. Complete inventory (46 files, 341.0 MB)
| # | Level | Exact source on your PC (`<REPO>` = the folder that contains `README.md`) | Exact Google Drive destination | Size | Purpose |
|---|---|---|---|---|---|
| 1 | REQUIRED | `<REPO>\data\external\mondo.obo` | `MyDrive/VDM_Data/mondo.obo` | 53.4 MB | frozen MONDO release 2026-11-03 (disease mapping); without it the latest release is downloaded and the benchmark drifts |
| 2 | REQUIRED | `<REPO>\data\external\drugbank_smiles_cache.json` | `MyDrive/VDM_Data/drugbank_smiles_cache.json` | 546.9 KB | 6,984 cached SMILES (DrugBank-derived; keeps drug features identical) |
| 3 | REQUIRED | `<REPO>\data\external\drugbank_cid_map.json` | `MyDrive/VDM_Data/drugbank_cid_map.json` | 153.4 KB | DrugBank-to-PubChem CID map for the SMILES lookup |
| 4 | RECOMMENDED | `<REPO>\data\external\B09474-eng.pdf` | `MyDrive/VDM_Data/B09474-eng.pdf` | 1.4 MB | WHO Essential Medicines List PDF (EML component of NDPI; missing = reported as missing, not 0) |
| 5 | RECOMMENDED | `<REPO>\data\external\downloads\hai_price_surveys\delhi_2011-07\affordability_excel.xls` | `MyDrive/VDM_Data/downloads/hai_price_surveys/delhi_2011-07/affordability_excel.xls` | 31.4 KB | HAI price/affordability surveys (access component) |
| 6 | RECOMMENDED | `<REPO>\data\external\downloads\hai_price_surveys\delhi_2011-07\median_price_by_medicine_excel.xls` | `MyDrive/VDM_Data/downloads/hai_price_surveys/delhi_2011-07/median_price_by_medicine_excel.xls` | 35.4 KB | HAI price/affordability surveys (access component) |
| 7 | RECOMMENDED | `<REPO>\data\external\downloads\hai_price_surveys\delhi_2011-07\price_availability_survey_detail_excel (1).php` | `MyDrive/VDM_Data/downloads/hai_price_surveys/delhi_2011-07/price_availability_survey_detail_excel (1).php` | 14.9 KB | HAI price/affordability surveys (access component) |
| 8 | RECOMMENDED | `<REPO>\data\external\downloads\hai_price_surveys\delhi_2011-07\price_availability_survey_detail_excel (2).php` | `MyDrive/VDM_Data/downloads/hai_price_surveys/delhi_2011-07/price_availability_survey_detail_excel (2).php` | 15.1 KB | HAI price/affordability surveys (access component) |
| 9 | RECOMMENDED | `<REPO>\data\external\downloads\hai_price_surveys\delhi_2011-07\price_availability_survey_detail_excel.php` | `MyDrive/VDM_Data/downloads/hai_price_surveys/delhi_2011-07/price_availability_survey_detail_excel.php` | 14.6 KB | HAI price/affordability surveys (access component) |
| 10 | RECOMMENDED | `<REPO>\data\external\downloads\hai_price_surveys\karnataka_2004-11\affordability_excel (2).xls` | `MyDrive/VDM_Data/downloads/hai_price_surveys/karnataka_2004-11/affordability_excel (2).xls` | 28.8 KB | HAI price/affordability surveys (access component) |
| 11 | RECOMMENDED | `<REPO>\data\external\downloads\hai_price_surveys\karnataka_2004-11\median_price_by_medicine_excel (2).xls` | `MyDrive/VDM_Data/downloads/hai_price_surveys/karnataka_2004-11/median_price_by_medicine_excel (2).xls` | 31.7 KB | HAI price/affordability surveys (access component) |
| 12 | RECOMMENDED | `<REPO>\data\external\downloads\hai_price_surveys\karnataka_2004-11\price_availability_survey_detail_excel (6).php` | `MyDrive/VDM_Data/downloads/hai_price_surveys/karnataka_2004-11/price_availability_survey_detail_excel (6).php` | 16.8 KB | HAI price/affordability surveys (access component) |
| 13 | RECOMMENDED | `<REPO>\data\external\downloads\hai_price_surveys\karnataka_2004-11\price_availability_survey_detail_excel (7).php` | `MyDrive/VDM_Data/downloads/hai_price_surveys/karnataka_2004-11/price_availability_survey_detail_excel (7).php` | 17.2 KB | HAI price/affordability surveys (access component) |
| 14 | RECOMMENDED | `<REPO>\data\external\downloads\hai_price_surveys\karnataka_2004-11\price_availability_survey_detail_excel (8).php` | `MyDrive/VDM_Data/downloads/hai_price_surveys/karnataka_2004-11/price_availability_survey_detail_excel (8).php` | 18.0 KB | HAI price/affordability surveys (access component) |
| 15 | RECOMMENDED | `<REPO>\data\external\downloads\hai_price_surveys\maharashtra_2005-01\affordability_excel (1).xls` | `MyDrive/VDM_Data/downloads/hai_price_surveys/maharashtra_2005-01/affordability_excel (1).xls` | 30.5 KB | HAI price/affordability surveys (access component) |
| 16 | RECOMMENDED | `<REPO>\data\external\downloads\hai_price_surveys\maharashtra_2005-01\median_price_by_medicine_excel (1).xls` | `MyDrive/VDM_Data/downloads/hai_price_surveys/maharashtra_2005-01/median_price_by_medicine_excel (1).xls` | 30.1 KB | HAI price/affordability surveys (access component) |
| 17 | RECOMMENDED | `<REPO>\data\external\downloads\hai_price_surveys\maharashtra_2005-01\price_availability_survey_detail_excel (3).php` | `MyDrive/VDM_Data/downloads/hai_price_surveys/maharashtra_2005-01/price_availability_survey_detail_excel (3).php` | 16.0 KB | HAI price/affordability surveys (access component) |
| 18 | RECOMMENDED | `<REPO>\data\external\downloads\hai_price_surveys\maharashtra_2005-01\price_availability_survey_detail_excel (4).php` | `MyDrive/VDM_Data/downloads/hai_price_surveys/maharashtra_2005-01/price_availability_survey_detail_excel (4).php` | 16.4 KB | HAI price/affordability surveys (access component) |
| 19 | RECOMMENDED | `<REPO>\data\external\downloads\hai_price_surveys\maharashtra_2005-01\price_availability_survey_detail_excel (5).php` | `MyDrive/VDM_Data/downloads/hai_price_surveys/maharashtra_2005-01/price_availability_survey_detail_excel (5).php` | 17.2 KB | HAI price/affordability surveys (access component) |
| 20 | RECOMMENDED | `<REPO>\data\external\downloads\ihme_gbd\IHME-GBD_2023_DATA-9feb184e-1.zip` | `MyDrive/VDM_Data/downloads/ihme_gbd/IHME-GBD_2023_DATA-9feb184e-1.zip` | 870 B | IHME GBD 2023 DALY export for 17 causes (burden component) |
| 21 | RECOMMENDED | `<REPO>\data\external\downloads\ihme_gbd\ihme_ntd_dalys_2023.csv` | `MyDrive/VDM_Data/downloads/ihme_gbd/ihme_ntd_dalys_2023.csv` | 3.2 KB | IHME GBD 2023 DALY export for 17 causes (burden component) |
| 22 | RECOMMENDED | `<REPO>\data\external\downloads\ihme_gbd\ihme_ntd_dalys_2023_citation.txt` | `MyDrive/VDM_Data/downloads/ihme_gbd/ihme_ntd_dalys_2023_citation.txt` | 327 B | IHME GBD 2023 DALY export for 17 causes (burden component) |
| 23 | RECOMMENDED | `<REPO>\data\external\downloads\open_targets_release_26.09\clinical_indication.parquet` | `MyDrive/VDM_Data/downloads/open_targets_release_26.09/clinical_indication.parquet` | 5.0 MB | Open Targets release 26.09 tables (source attribution) |
| 24 | RECOMMENDED | `<REPO>\data\external\downloads\open_targets_release_26.09\clinical_report.parquet` | `MyDrive/VDM_Data/downloads/open_targets_release_26.09/clinical_report.parquet` | 75.9 MB | Open Targets release 26.09 tables (source attribution) |
| 25 | RECOMMENDED | `<REPO>\data\external\downloads\open_targets_release_26.09\drug_mechanism_of_action.parquet` | `MyDrive/VDM_Data/downloads/open_targets_release_26.09/drug_mechanism_of_action.parquet` | 322.8 KB | Open Targets release 26.09 tables (source attribution) |
| 26 | RECOMMENDED | `<REPO>\data\external\downloads\open_targets_release_26.09\drug_molecule.parquet` | `MyDrive/VDM_Data/downloads/open_targets_release_26.09/drug_molecule.parquet` | 6.9 MB | Open Targets release 26.09 tables (source attribution) |
| 27 | REQUIRED | `<REPO>\data\processed\primekg\disease_features.npy` | `MyDrive/VDM_Data/frozen_processed/primekg/disease_features.npy` | 205.1 KB | safety copy of the frozen benchmark (primekg); restored automatically only if a regenerated file differs |
| 28 | REQUIRED | `<REPO>\data\processed\primekg\diseases.csv` | `MyDrive/VDM_Data/frozen_processed/primekg/diseases.csv` | 2.1 MB | safety copy of the frozen benchmark (primekg); restored automatically only if a regenerated file differs |
| 29 | REQUIRED | `<REPO>\data\processed\primekg\drug_features.npy` | `MyDrive/VDM_Data/frozen_processed/primekg/drug_features.npy` | 65.2 MB | safety copy of the frozen benchmark (primekg); restored automatically only if a regenerated file differs |
| 30 | REQUIRED | `<REPO>\data\processed\primekg\drugs.csv` | `MyDrive/VDM_Data/frozen_processed/primekg/drugs.csv` | 779.0 KB | safety copy of the frozen benchmark (primekg); restored automatically only if a regenerated file differs |
| 31 | REQUIRED | `<REPO>\data\processed\primekg\edges.csv` | `MyDrive/VDM_Data/frozen_processed/primekg/edges.csv` | 29.0 MB | safety copy of the frozen benchmark (primekg); restored automatically only if a regenerated file differs |
| 32 | REQUIRED | `<REPO>\data\processed\primekg\genes.csv` | `MyDrive/VDM_Data/frozen_processed/primekg/genes.csv` | 350.6 KB | safety copy of the frozen benchmark (primekg); restored automatically only if a regenerated file differs |
| 33 | REQUIRED | `<REPO>\data\processed\primekg\graph_metadata.json` | `MyDrive/VDM_Data/frozen_processed/primekg/graph_metadata.json` | 258 B | safety copy of the frozen benchmark (primekg); restored automatically only if a regenerated file differs |
| 34 | REQUIRED | `<REPO>\data\processed\primekg\primekg_provenance.json` | `MyDrive/VDM_Data/frozen_processed/primekg/primekg_provenance.json` | 2.7 KB | safety copy of the frozen benchmark (primekg); restored automatically only if a regenerated file differs |
| 35 | REQUIRED | `<REPO>\data\processed\primekg\splits\seed42.manifest.json` | `MyDrive/VDM_Data/frozen_processed/primekg/splits/seed42.manifest.json` | 3.2 KB | safety copy of the frozen benchmark (primekg); restored automatically only if a regenerated file differs |
| 36 | REQUIRED | `<REPO>\data\processed\primekg\splits\seed42.npz` | `MyDrive/VDM_Data/frozen_processed/primekg/splits/seed42.npz` | 313.2 KB | safety copy of the frozen benchmark (primekg); restored automatically only if a regenerated file differs |
| 37 | REQUIRED | `<REPO>\data\processed\primekg_structcov\disease_features.npy` | `MyDrive/VDM_Data/frozen_processed/primekg_structcov/disease_features.npy` | 205.1 KB | safety copy of the frozen benchmark (primekg_structcov); restored automatically only if a regenerated file differs |
| 38 | REQUIRED | `<REPO>\data\processed\primekg_structcov\diseases.csv` | `MyDrive/VDM_Data/frozen_processed/primekg_structcov/diseases.csv` | 2.1 MB | safety copy of the frozen benchmark (primekg_structcov); restored automatically only if a regenerated file differs |
| 39 | REQUIRED | `<REPO>\data\processed\primekg_structcov\drug_features.npy` | `MyDrive/VDM_Data/frozen_processed/primekg_structcov/drug_features.npy` | 65.2 MB | safety copy of the frozen benchmark (primekg_structcov); restored automatically only if a regenerated file differs |
| 40 | REQUIRED | `<REPO>\data\processed\primekg_structcov\drugs.csv` | `MyDrive/VDM_Data/frozen_processed/primekg_structcov/drugs.csv` | 779.0 KB | safety copy of the frozen benchmark (primekg_structcov); restored automatically only if a regenerated file differs |
| 41 | REQUIRED | `<REPO>\data\processed\primekg_structcov\edges.csv` | `MyDrive/VDM_Data/frozen_processed/primekg_structcov/edges.csv` | 29.0 MB | safety copy of the frozen benchmark (primekg_structcov); restored automatically only if a regenerated file differs |
| 42 | REQUIRED | `<REPO>\data\processed\primekg_structcov\genes.csv` | `MyDrive/VDM_Data/frozen_processed/primekg_structcov/genes.csv` | 350.6 KB | safety copy of the frozen benchmark (primekg_structcov); restored automatically only if a regenerated file differs |
| 43 | REQUIRED | `<REPO>\data\processed\primekg_structcov\graph_metadata.json` | `MyDrive/VDM_Data/frozen_processed/primekg_structcov/graph_metadata.json` | 258 B | safety copy of the frozen benchmark (primekg_structcov); restored automatically only if a regenerated file differs |
| 44 | REQUIRED | `<REPO>\data\processed\primekg_structcov\primekg_provenance.json` | `MyDrive/VDM_Data/frozen_processed/primekg_structcov/primekg_provenance.json` | 2.7 KB | safety copy of the frozen benchmark (primekg_structcov); restored automatically only if a regenerated file differs |
| 45 | REQUIRED | `<REPO>\data\processed\primekg_structcov\splits\seed42.manifest.json` | `MyDrive/VDM_Data/frozen_processed/primekg_structcov/splits/seed42.manifest.json` | 1.1 KB | safety copy of the frozen benchmark (primekg_structcov); restored automatically only if a regenerated file differs |
| 46 | REQUIRED | `<REPO>\data\processed\primekg_structcov\splits\seed42.npz` | `MyDrive/VDM_Data/frozen_processed/primekg_structcov/splits/seed42.npz` | 1.4 MB | safety copy of the frozen benchmark (primekg_structcov); restored automatically only if a regenerated file differs |

## 3. Final Drive structure (matches the notebook paths exactly)
```
MyDrive/
├── VDM_Data/                                   (you upload this; about 341 MB, 46 files)
│   ├── mondo.obo
│   ├── drugbank_smiles_cache.json
│   ├── drugbank_cid_map.json
│   ├── B09474-eng.pdf
│   ├── downloads/
│   │   ├── hai_price_surveys/
│   │   │   ├── delhi_2011-07/         (5 files)
│   │   │   ├── karnataka_2004-11/     (5 files)
│   │   │   └── maharashtra_2005-01/   (5 files)
│   │   ├── open_targets_release_26.09/
│   │   │   ├── clinical_indication.parquet
│   │   │   ├── clinical_report.parquet
│   │   │   ├── drug_mechanism_of_action.parquet
│   │   │   └── drug_molecule.parquet
│   │   └── ihme_gbd/
│   │       ├── ihme_ntd_dalys_2023.csv
│   │       ├── ihme_ntd_dalys_2023_citation.txt
│   │       └── IHME-GBD_2023_DATA-9feb184e-1.zip
│   └── frozen_processed/
│       ├── primekg/            (10 files: disease_features.npy, diseases.csv, drug_features.npy, drugs.csv, edges.csv, genes.csv, graph_metadata.json, primekg_provenance.json, splits/seed42.manifest.json, splits/seed42.npz)
│       └── primekg_structcov/  (the same 10 files)
└── VDM_Outputs/                                (an EMPTY folder you create; the notebook fills it)
```

## 4. How to do it
### 4.1 Easiest route: one folder, one upload
1. Open a terminal in `<REPO>` and run `python Docs/make_upload_folder.py VDM_FINAL_FOLDER/UPLOAD_THIS`. It copies exactly the 46 files and deletes nothing (a ready-made copy may already exist).
2. Run `python Docs/check_drive_folder.py VDM_FINAL_FOLDER/UPLOAD_THIS/VDM_Data`. It must end with `RESULT: PASS`.
3. Open https://drive.google.com and sign in with the Google account you will use in Colab. Click **New -> Folder**, name it exactly `VDM_Outputs`, **Create**. Leave it empty.
4. Click **New -> Folder upload**, choose `<REPO>/VDM_FINAL_FOLDER/UPLOAD_THIS/VDM_Data` (the folder named `VDM_Data`, not its parent), confirm. Wait for "upload complete" (about 341 MB).
5. Do **not** upload `VDM_Outputs_CREATE_EMPTY_FOLDER_IN_DRIVE` or the parent `UPLOAD_THIS`.

### 4.2 Verify
* Size: in Drive right-click `VDM_Data` -> **File information -> Details**: about 341 MB. The tree must equal section 3.
* Content: Colab **Step 3a** prints `RESULT: PASS` after checking every file's existence, size and SHA-256. It prints `EXTRA` for anything not on the list and fails if a restricted file such as `primekg_kg.csv` is present. Do not continue past a FAIL.

### 4.3 Keep it private
Never click **Share** on `VDM_Data` or `VDM_Outputs`, never create a link, never add people. Check: right-click -> **Share** must show only you. These folders hold DrugBank-derived caches, IHME and Open Targets data and the WHO EML PDF, whose terms do not allow public redistribution.

### 4.4 Avoid uploading restricted files by accident
Upload only the `VDM_Data` folder from 4.1 (it contains nothing else). Never drag `data/`, `outputs/` or the repository into Drive. Step 3a flags and fails on `primekg_kg.csv`, `drugbank_vocabulary.csv`, `full database.xml` and `.env`.

## 5. What Colab loads, and from where
| kind | what | how |
|---|---|---|
| Google Drive (yours, private) | everything in section 2 | Step 2 mounts Drive (`/content/drive`); Step 3 copies `VDM_Data` into `data/external/` of the session |
| GitHub (code) | the repository at the **exact pinned commit** | Step 2: `git clone https://github.com/MUKUL-PRASAD-SIGH/VectorDrugMatch`, then `git checkout $PIN`; `PIN` is the 40-character value on the line `PIN = '...'` in the notebook (see `Docs/COLAB_TRAINING_HANDOFF.md` section 1). The commit must exist on GitHub (`mukul`) |
| Downloaded automatically | PrimeKG `kg.csv` (Harvard Dataverse, about 1 GB); drug structures missing from the cache may be queried live (Step 4b verifies the result) | Step 4 (`fetch_public_data.py --primekg`, `primekg_dataset.py`) |
| Installed automatically | rdkit, torch-geometric and extensions, xgboost, shap, mlflow, ... | Step 2 `pip install` cells |
| The frozen benchmark | rebuilt from the inputs, compared by SHA-256 with `Docs/release/vdm_v1_candidate_manifest.json`; the Drive copy `frozen_processed/` is restored if a file differs | Step 4b (stops on a mismatch of `mondo.obo` or `primekg_kg.csv`) |
| Generated during training | checkpoints, predictions, metrics, logs, explanations, `vdm_results.zip` | Step 6b links `outputs/` to `MyDrive/VDM_Outputs/outputs`, so they are written to Drive as they are produced |

## 6. Colab link
`https://colab.research.google.com/github/MUKUL-PRASAD-SIGH/VectorDrugMatch/blob/mukul/notebooks/colab_final_run.ipynb`
The link opens the notebook **as it is on GitHub**. The notebook checks out its pinned commit, which must be on GitHub: until the pending local commits are pushed (this needs your approval) the link shows an older notebook and the new pin does not exist there. See `Docs/PUBLICATION_PLAN.md`.

## 7. Automation: what can and cannot be delegated
* **Needs you:** signing in to Google; the Drive permission pop-up in Step 2 (your click, your account); choosing the T4 GPU. No external agent can use your Google account unless you sign in and allow it in a browser you control.
* **A browser-controlling assistant** (Claude in Chrome, ChatGPT agent or similar, if you choose to enable one) can in principle click cells and read output in a Colab tab **that you opened and signed in to**; you approve its access and any permission prompt. Claude Code, which prepared this repository, has not launched Colab and cannot speak for another vendor's product. Automation is optional: the notebook needs only a few clicks without it.
* **Minimal manual route (recommended):** do not use *Run all*. Run Steps 1-6b one cell at a time, read the smoke-test numbers, then run Steps 7, 7b, 8, 9 (each one cell). Step 3a and Step 4b stop the run on a bad upload or a changed benchmark.
* **Can run unattended** once started: Steps 7, 7b and 8, while the tab stays open and the runtime stays connected. Colab may disconnect on inactivity or session-length limits set by Google; this cannot be predicted here.
* **Recovery:** re-run Steps 1-6b, then re-run the Step 7/8 cell. `--resume` skips every model that already finished at this commit (the log is on Drive), so only the unfinished model restarts.
* **Outputs preserved:** `MyDrive/VDM_Outputs/` (checkpoints, predictions, metrics, logs, environment record, `vdm_results.zip`).
