# Licence and terms audit

Generated 2026-11-11. A provenance record, **not legal advice**. Evidence: `Docs/source_evidence/fetch_log_2026-11-10.json` (URL, bytes, SHA-256 of every page read, 29 pages); raw pages are not stored in git.
Statuses: VERIFIED = the stated terms were read from the source; PARTIAL = part read; NOT VERIFIED = could not be retrieved or read; LEGALLY UNRESOLVED = the terms were read but their effect on this project is a legal judgement not made here.

## 1. Platform-level versus upstream terms
Open Targets marks its platform CC0 1.0 and states that it places no extra restrictions beyond the original data owners; the CC0 mark therefore does not settle the upstream terms. All five providers of Open Targets clinical reports contribute to **our** records (`Docs/OPEN_TARGETS_PROVENANCE.md`): AACT/ClinicalTrials.gov, ChEMBL, TTD, EMA, PMDA. Only ChEMBL is in the platform's 44-row licence table (`Docs/source_evidence/ot_licence_table_2026-11-10.csv`). PrimeKG likewise states a CC0 dataset licence while pointing to the licences of its constituent sources.

## 2. Source-by-source table
| source | licence / terms (as found) | attribution | commercial / redistribution | evidence | status |
|---|---|---|---|---|---|
| PrimeKG (kg.csv) | Dataverse record: CC0 1.0 (version 2.1, released 2022-05-02). PrimeKG README: code is MIT; 'this license specifically refers to the PrimeKG software, and is distinct from any licenses governing the PrimeKG dataset itself ... refer to the respective dataset licenses'. Constituent sources include DrugBank, DrugCentral, DisGeNET, SIDER, UMLS. | cite Chandak et al. 2023 | CC0 on the aggregate; constituent terms (e.g. DrugBank CC BY-NC) may still bind | primekg_dataverse_api, primekg_readme | VERIFIED (statements) / LEGALLY UNRESOLVED (effect of CC0 over NC constituents) |
| DrugBank | Releases page: open datasets released under CC BY-NC 4.0; Academic licence for students/professors/research associates whose research is not primarily for a commercial third party. Terms-of-use page returned HTTP 403 and was not read. | required (CC BY) | non-commercial only (NC) | drugbank_academic | PARTIAL (releases page read; ToU page not read) |
| Open Targets platform | Platform marked CC0 1.0; terms of use impose no additional restrictions beyond the original data owners; users responsible for third-party rights. 'All sources listed in the table ... have agreed' covers listed sources only. | asked to cite the latest publication | CC0 at platform level; upstream terms apply | ot_licence_md, ot_terms_md | VERIFIED |
| ChEMBL (curated indications; sources DailyMed, ATC, FDA, USAN, INN, WHO ...) | CC BY-SA 3.0 (Open Targets table and ChEMBL home page). | required | ShareAlike for adaptations | ot_licence_md, chembl | VERIFIED / LEGALLY UNRESOLVED (are our derived pair lists adaptations?) |
| ClinicalTrials.gov via AACT | ClinicalTrials.gov terms page is JavaScript-rendered (no text retrieved); AACT page: no licence text; NLM web policies: works of the US government are not subject to copyright, third-party content may be protected. | unknown | unknown | ctgov_terms, aact, nlm_policies | NOT VERIFIED |
| TTD (Therapeutic Target Database) | Landing page returned a 461-byte stub; no terms retrieved. | unknown | unknown | ttd | NOT VERIFIED |
| EMA (Human Medicines) | Legal notice: material may be reproduced/distributed for non-commercial and commercial purposes provided EMA is acknowledged as source; excludes third-party content. | required | permitted with acknowledgement (website notice) | ema_legal | PARTIAL (website notice, not a statement about the Human Medicines dataset as processed by Open Targets) |
| PMDA (approvals) | Site policy: content under the Public Data License 1.0 (PDL 1.0) unless otherwise indicated; source citation required; listed exceptions apply. | required | PDL 1.0 (reuse permitted with citation) | pmda_site_policy | PARTIAL (exceptions 'unless otherwise indicated' not checked for the approvals pages) |
| MONDO | CC-BY 4.0 (repository README; also in the Open Targets table). | required | permitted with attribution | mondo_repo | VERIFIED |
| WHO Model List of Essential Medicines, 24th list (2025) | PDF page 2 and WHO copyright page: CC BY-NC-SA 3.0 IGO. | required; no suggestion of WHO endorsement | non-commercial; adaptations must be shared under the same/equivalent licence | who_eml_pdf (PDF), who_copyright | VERIFIED / LEGALLY UNRESOLVED (is our extracted CSV an adaptation?) |
| WHO NTD list (web page) | WHO web page; only a factual list of disease names is used. WHO terms-and-conditions page not read. | cited as [15] | n/a (facts) | who_ntd_topic | PARTIAL |
| IHME GBD | Free-of-Charge Non-Commercial User Agreement: non-commercial use; results may be used for internal research and publication; users may not provide third parties the ability to download IHME data sets from their own hosting. | citation required (citation.txt in the export) | non-commercial; no third-party hosting of the data | ihme_terms | VERIFIED (agreement text); account acceptance is yours to confirm |
| HAI / WHO medicine price surveys | The downloaded HTML files contain no copyright or licence text; the HAI page checked returned 404. | cite HAI/WHO surveys | unknown | local files (no terms text) | NOT VERIFIED |
| MyChem.info / PubChem (SMILES resolution at build time) | Not examined in this audit. | unknown | unknown | - | NOT VERIFIED |

## 3. Git history: DrugBank-derived files
Three blobs were ever tracked under `data/`: `drugbank_smiles_cache.json` (1,531 entries: DrugBank id -> SMILES, 110 KB), `drugbank_cid_map.json` (1,487 entries: DrugBank id -> PubChem CID, 30 KB), `fetch_smiles_missing.csv` (a short list of ids). Commits: 522deb3 2026-11-10 Add PrimeKG pipeline (Track B): dataset, drug-disjoint split, validation, leak-free baselines, Colab playbook; 1829752 2026-10-30 Fix real-data pipeline: Hetionet+SMILES fetch, GNN builds, label leak, NDPI inference.
They were added in `1829752` (2026-10-30), removed from the index in `522deb3`, and **remain in the history of `origin/mukul`**; no other pushed branch contains them. Per `scripts/fetch_smiles.py` the SMILES were resolved through MyChem.info and PubChem (not read from DrugBank's own files), but the id -> CID links come from MyChem's cross-references, which may originate in DrugBank. Whether these small id-to-structure maps count as DrugBank data under CC BY-NC 4.0 is **legally unresolved**. Nothing was rewritten or deleted; history cleanup is decision H5 in `Docs/HUMAN_ACTION_CHECKLIST.md`.

## 4. Unresolved legal questions (for you / your institution)
1. Does CC0 on the PrimeKG aggregate override constituent terms such as DrugBank CC BY-NC? (Affects any public release of PrimeKG-derived tables.)
2. Are our derived tables (DrugBank x MONDO pair lists from ChEMBL-based records; the extracted WHO EML CSV) "adaptations" subject to ShareAlike (CC BY-SA 3.0, CC BY-NC-SA 3.0 IGO)?
3. Terms of ClinicalTrials.gov/AACT, TTD, and the PMDA approvals pages (exceptions) were not retrieved.
4. DrugBank academic-licence entitlement for this project's use (non-commercial research) is for you to confirm.
5. Whether the two small historical DrugBank-derived maps need removal from history.

## 5. What the project does meanwhile
Raw and derived external data are git-ignored (`data/`); only aggregate counts, figures and audit documents are tracked; IHME and WHO EML files are not redistributed; Open Targets data are not used for training or evaluation; no derived pair list is published. Before any public data release, close the NOT VERIFIED / PARTIAL / UNRESOLVED rows.
