"""
scripts/make_final_docs.py - generate the final audit documents from the evidence log and the data/report files.

    python scripts/make_final_docs.py

Writes Docs/LICENCE_AUDIT.md, Docs/DATA_PROVENANCE.md, Docs/OPEN_TARGETS_PROVENANCE.md, Docs/EQUITY_DATA_SPECS.md, Docs/HUMAN_ACTION_CHECKLIST.md,
Docs/FINAL_RELEASE_READINESS.md. Numbers come from JSON/CSV files on disk; the licence rows, the human-action list and the task registry are
curated text (the registry is what the completion percentage is computed from). Statuses: DONE AND VALIDATED, IMPLEMENTED BUT NOT VALIDATED,
BLOCKED ON MY INPUT, NOT STARTED, NOT APPLICABLE. Not legal advice.
"""
import json
from pathlib import Path

import pandas as pd

R = Path(__file__).resolve().parents[1]
P = R / "data" / "processed"
ev = json.loads((R / "Docs/source_evidence/fetch_log_2026-11-10.json").read_text())
att = json.loads((P / "open_targets/source_attribution_report.json").read_text())
otm = json.loads((P / "open_targets/mapping_report.json").read_text())
eml = json.loads((P / "eml/eml_report.json").read_text())
eqr = json.loads((P / "equity/equity_report.json").read_text())
hai = json.loads((P / "hai/hai_parse_report.json").read_text())
ntd = json.loads((P / "ntd/ntd_mapping_summary.json").read_text())
prov = json.loads((P / "primekg/primekg_provenance.json").read_text())
man = json.loads((P / "primekg/splits/seed42.manifest.json").read_text())
manc = json.loads((P / "primekg_structcov/splits/seed42.manifest.json").read_text())
S = ev["sources"]


def md(df):
    cols = list(df.columns)
    cell = lambda v: ("" if (v is None or (isinstance(v, float) and pd.isna(v))) else str(v)).replace("|", "/").replace("\n", " ")
    return "\n".join(["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(cell(v) for v in r) + " |" for r in df.itertuples(index=False)])


def sh(k, n=12):
    return S[k]["sha256_full"][:n]


# =============================== LICENCE_AUDIT.md ===============================
lic = pd.DataFrame([
    {"source": "PrimeKG (kg.csv)", "licence / terms (as found)": "Dataverse record: CC0 1.0 (version 2.1, released 2022-05-02). PrimeKG README: code is MIT; 'this license specifically refers to the PrimeKG software, and is distinct from any licenses governing the PrimeKG dataset itself ... refer to the respective dataset licenses'. Constituent sources include DrugBank, DrugCentral, DisGeNET, SIDER, UMLS.",
     "attribution": "cite Chandak et al. 2023", "commercial / redistribution": "CC0 on the aggregate; constituent terms (e.g. DrugBank CC BY-NC) may still bind", "evidence": "primekg_dataverse_api, primekg_readme", "status": "VERIFIED (statements) / LEGALLY UNRESOLVED (effect of CC0 over NC constituents)"},
    {"source": "DrugBank", "licence / terms (as found)": "Releases page: open datasets released under CC BY-NC 4.0; Academic licence for students/professors/research associates whose research is not primarily for a commercial third party. Terms-of-use page returned HTTP 403 and was not read.",
     "attribution": "required (CC BY)", "commercial / redistribution": "non-commercial only (NC)", "evidence": "drugbank_academic", "status": "PARTIAL (releases page read; ToU page not read)"},
    {"source": "Open Targets platform", "licence / terms (as found)": "Platform marked CC0 1.0; terms of use impose no additional restrictions beyond the original data owners; users responsible for third-party rights. 'All sources listed in the table ... have agreed' covers listed sources only.",
     "attribution": "asked to cite the latest publication", "commercial / redistribution": "CC0 at platform level; upstream terms apply", "evidence": "ot_licence_md, ot_terms_md", "status": "VERIFIED"},
    {"source": "ChEMBL (curated indications; sources DailyMed, ATC, FDA, USAN, INN, WHO ...)", "licence / terms (as found)": "CC BY-SA 3.0 (Open Targets table and ChEMBL home page).",
     "attribution": "required", "commercial / redistribution": "ShareAlike for adaptations", "evidence": "ot_licence_md, chembl", "status": "VERIFIED / LEGALLY UNRESOLVED (are our derived pair lists adaptations?)"},
    {"source": "ClinicalTrials.gov via AACT", "licence / terms (as found)": "ClinicalTrials.gov terms page is JavaScript-rendered (no text retrieved); AACT page: no licence text; NLM web policies: works of the US government are not subject to copyright, third-party content may be protected.",
     "attribution": "unknown", "commercial / redistribution": "unknown", "evidence": "ctgov_terms, aact, nlm_policies", "status": "NOT VERIFIED"},
    {"source": "TTD (Therapeutic Target Database)", "licence / terms (as found)": "Landing page returned a 461-byte stub; no terms retrieved.", "attribution": "unknown", "commercial / redistribution": "unknown", "evidence": "ttd", "status": "NOT VERIFIED"},
    {"source": "EMA (Human Medicines)", "licence / terms (as found)": "Legal notice: material may be reproduced/distributed for non-commercial and commercial purposes provided EMA is acknowledged as source; excludes third-party content.",
     "attribution": "required", "commercial / redistribution": "permitted with acknowledgement (website notice)", "evidence": "ema_legal", "status": "PARTIAL (website notice, not a statement about the Human Medicines dataset as processed by Open Targets)"},
    {"source": "PMDA (approvals)", "licence / terms (as found)": "Site policy: content under the Public Data License 1.0 (PDL 1.0) unless otherwise indicated; source citation required; listed exceptions apply.",
     "attribution": "required", "commercial / redistribution": "PDL 1.0 (reuse permitted with citation)", "evidence": "pmda_site_policy", "status": "PARTIAL (exceptions 'unless otherwise indicated' not checked for the approvals pages)"},
    {"source": "MONDO", "licence / terms (as found)": "CC-BY 4.0 (repository README; also in the Open Targets table).", "attribution": "required", "commercial / redistribution": "permitted with attribution", "evidence": "mondo_repo", "status": "VERIFIED"},
    {"source": "WHO Model List of Essential Medicines, 24th list (2025)", "licence / terms (as found)": "PDF page 2 and WHO copyright page: CC BY-NC-SA 3.0 IGO.", "attribution": "required; no suggestion of WHO endorsement",
     "commercial / redistribution": "non-commercial; adaptations must be shared under the same/equivalent licence", "evidence": "who_eml_pdf (PDF), who_copyright", "status": "VERIFIED / LEGALLY UNRESOLVED (is our extracted CSV an adaptation?)"},
    {"source": "WHO NTD list (web page)", "licence / terms (as found)": "WHO web page; only a factual list of disease names is used. WHO terms-and-conditions page not read.", "attribution": "cited as [15]", "commercial / redistribution": "n/a (facts)", "evidence": "who_ntd_topic", "status": "PARTIAL"},
    {"source": "IHME GBD", "licence / terms (as found)": "Free-of-Charge Non-Commercial User Agreement: non-commercial use; results may be used for internal research and publication; users may not provide third parties the ability to download IHME data sets from their own hosting.",
     "attribution": "citation required (citation.txt in the export)", "commercial / redistribution": "non-commercial; no third-party hosting of the data", "evidence": "ihme_terms", "status": "VERIFIED (agreement text); account acceptance is yours to confirm"},
    {"source": "HAI / WHO medicine price surveys", "licence / terms (as found)": "The downloaded HTML files contain no copyright or licence text; the HAI page checked returned 404.", "attribution": "cite HAI/WHO surveys", "commercial / redistribution": "unknown", "evidence": "local files (no terms text)", "status": "NOT VERIFIED"},
    {"source": "MyChem.info / PubChem (SMILES resolution at build time)", "licence / terms (as found)": "Not examined in this audit.", "attribution": "unknown", "commercial / redistribution": "unknown", "evidence": "-", "status": "NOT VERIFIED"},
])
db = [l for l in __import__("subprocess").run(["git", "log", "--all", "--format=%h %ad %s", "--date=short", "--", "data/external/drugbank_smiles_cache.json", "data/external/drugbank_cid_map.json"], cwd=R, capture_output=True, text=True).stdout.splitlines()]
doc = f"""# Licence and terms audit

Generated {pd.Timestamp.now().strftime('%Y-%m-%d')}. A provenance record, **not legal advice**. Evidence: `Docs/source_evidence/fetch_log_2026-11-10.json` (URL, bytes, SHA-256 of every page read, {len(S)} pages); raw pages are not stored in git.
Statuses: VERIFIED = the stated terms were read from the source; PARTIAL = part read; NOT VERIFIED = could not be retrieved or read; LEGALLY UNRESOLVED = the terms were read but their effect on this project is a legal judgement not made here.

## 1. Platform-level versus upstream terms
Open Targets marks its platform CC0 1.0 and states that it places no extra restrictions beyond the original data owners; the CC0 mark therefore does not settle the upstream terms. All five providers of Open Targets clinical reports contribute to **our** records (`Docs/OPEN_TARGETS_PROVENANCE.md`): AACT/ClinicalTrials.gov, ChEMBL, TTD, EMA, PMDA. Only ChEMBL is in the platform's {44}-row licence table (`Docs/source_evidence/ot_licence_table_2026-11-10.csv`). PrimeKG likewise states a CC0 dataset licence while pointing to the licences of its constituent sources.

## 2. Source-by-source table
{md(lic)}

## 3. Git history: DrugBank-derived files
Three blobs were ever tracked under `data/`: `drugbank_smiles_cache.json` (1,531 entries: DrugBank id -> SMILES, 110 KB), `drugbank_cid_map.json` (1,487 entries: DrugBank id -> PubChem CID, 30 KB), `fetch_smiles_missing.csv` (a short list of ids). Commits: {'; '.join(db)}.
They were added in `1829752` (2026-10-30), removed from the index in `522deb3`, and **remain in the history of `origin/mukul`**; no other pushed branch contains them. Per `scripts/fetch_smiles.py` the SMILES were resolved through MyChem.info and PubChem (not read from DrugBank's own files), but the id -> CID links come from MyChem's cross-references, which may originate in DrugBank. Whether these small id-to-structure maps count as DrugBank data under CC BY-NC 4.0 is **legally unresolved**. Nothing was rewritten or deleted; history cleanup is decision H5 in `Docs/HUMAN_ACTION_CHECKLIST.md`.

## 4. Unresolved legal questions (for you / your institution)
1. Does CC0 on the PrimeKG aggregate override constituent terms such as DrugBank CC BY-NC? (Affects any public release of PrimeKG-derived tables.)
2. Are our derived tables (DrugBank x MONDO pair lists from ChEMBL-based records; the extracted WHO EML CSV) "adaptations" subject to ShareAlike (CC BY-SA 3.0, CC BY-NC-SA 3.0 IGO)?
3. Terms of ClinicalTrials.gov/AACT, TTD, and the PMDA approvals pages (exceptions) were not retrieved.
4. DrugBank academic-licence entitlement for this project's use (non-commercial research) is for you to confirm.
5. Whether the two small historical DrugBank-derived maps need removal from history.

## 5. What the project does meanwhile
Raw and derived external data are git-ignored (`data/`); only aggregate counts, figures and audit documents are tracked; IHME and WHO EML files are not redistributed; Open Targets data are not used for training or evaluation; no derived pair list is published. Before any public data release, close the NOT VERIFIED / PARTIAL / UNRESOLVED rows.
"""
(R / "Docs/LICENCE_AUDIT.md").write_text(doc, encoding="utf-8")

# =============================== OPEN_TARGETS_PROVENANCE.md ===============================
a = att
doc = f"""# Open Targets indication data: provenance (resolved)

Generated {pd.Timestamp.now().strftime('%Y-%m-%d')} from `data/processed/open_targets/source_attribution_report.json`. Evidence: `Docs/source_evidence/fetch_log_2026-11-10.json`.

## 1. Release identification
Our three local files are **byte-identical (SHA-256) to release 26.09**: `00000000.parquet` = `clinical_indication`, `00000000 (1).parquet` = `drug_molecule`, `00000000 (2).parquet` = `drug_mechanism_of_action`
(source: `https://ftp.ebi.ac.uk/pub/databases/opentargets/platform/26.09/output/<dataset>/00000000.parquet`). Identification method: only release 26.09 names all four datasets `00000000.parquet`; the downloaded 26.09 files then matched ours exactly. The same-release `clinical_report` file (289,954 reports) was downloaded to `data/external/downloads/open_targets_release_26.09/` (git-ignored).

## 2. Identifiers
`clinicalReportIds` in the indication table are keys to `clinical_report.id` (UUIDs): **{a['report_refs']:,} references, {a['distinct_reports_referenced']:,} distinct reports, {a['report_refs_found_in_clinical_report'] * 100:.1f}% resolved** in the 26.09 clinical-report dataset; every referenced report has type INDICATION (no safety reports). Each report carries `provider`, `source`, `origin`, `url`, `clinicalStage`, `qualityControls`, and for trials NCT-level fields.

## 3. Which upstream sources contribute to OUR records
Referenced reports by provider: {a['referenced_reports_provider_counts']}. By source (top): {a['referenced_reports_source_counts']}. By origin: {a['referenced_reports_origin_counts']}.
Pairs (n = {a['all_pairs']['pairs']:,}): with AACT {a['all_pairs']['has_AACT']:,}; ChEMBL {a['all_pairs']['has_ChEMBL']:,}; TTD {a['all_pairs']['has_TTD']:,}; EMA {a['all_pairs']['has_EMA']:,}; PMDA {a['all_pairs']['has_PMDA']:,}. Single-provider pairs: {a['all_pairs']['single_provider_pairs']}.
APPROVAL-stage pairs (n = {a['approved_pairs']['pairs']:,}): with ChEMBL {a['approved_pairs']['has_ChEMBL']:,}; TTD {a['approved_pairs']['has_TTD']:,}; AACT {a['approved_pairs']['has_AACT']:,}; EMA {a['approved_pairs']['has_EMA']:,}; PMDA {a['approved_pairs']['has_PMDA']:,}.
**All five providers contribute**, so none of the five licence questions in `Docs/LICENCE_AUDIT.md` can be ruled out for our data. AACT entities are LLM-extracted from release 26.06 per the Open Targets documentation (our release 26.09 is later).

## 4. Quality flags
The only flag value is `UNVALIDATED_INDICATION`: {a['referenced_reports_with_quality_control_flags']:,} referenced reports carry it (51.5% of AACT references, 1.7% of ChEMBL, 4.7% of EMA, none of PMDA/TTD; shares measured 2026-11-10 from the referenced reports). **{a['all_pairs']['all_reports_flagged_UNVALIDATED']:,} pairs have every supporting report flagged** (APPROVAL pairs: {a['approved_pairs']['all_reports_flagged_UNVALIDATED']}). The documentation pages read describe two exclusion criteria (Phase IV without approval; trials whose primary purpose is not to measure the effect on the condition) and say flagged reports do not contribute to clinical indications, yet flagged reports are referenced here: **semantics unresolved**. For any corroboration use pairs with >= 1 unflagged report (`all_reports_flagged = 0`: {a['all_pairs']['at_least_one_unflagged_report']:,} pairs) or the APPROVAL stage.

## 5. Mapping into PrimeKG identifiers
Tier 1 (exact ChEMBL->DrugBank cross-reference + single MONDO id): {otm['pairs']['clean_pairs_after_dedup']:,} unique pairs; tier 2 (parent-molecule fallback, separate file): {otm['pairs']['tier2_parent_fallback_pairs']:,}. Disease mapping by OT id: {otm['diseases']['by_status(ids)']}. Pairs also PrimeKG indications: {a['tier1_in_primekg']['pairs']:,} (of which AACT supports {a['tier1_in_primekg']['has_AACT']:,}, ChEMBL {a['tier1_in_primekg']['has_ChEMBL']:,}, TTD {a['tier1_in_primekg']['has_TTD']:,}, EMA {a['tier1_in_primekg']['has_EMA']:,}, PMDA {a['tier1_in_primekg']['has_PMDA']:,}); not PrimeKG: {a['tier1_not_in_primekg']['pairs']:,}.

## 6. Independence from PrimeKG
**No independence claim is made.** PrimeKG's indication labels (DrugCentral/DrugBank-derived) and the ChEMBL/DailyMed/EMA/PMDA/TTD records can describe the same approvals; the overlap above is descriptive. Trial-derived (AACT) support is a different evidence type but is flagged UNVALIDATED for many pairs. Open Targets data are not merged into any PrimeKG training, validation or test split.
"""
(R / "Docs/OPEN_TARGETS_PROVENANCE.md").write_text(doc, encoding="utf-8")

# =============================== DATA_PROVENANCE.md ===============================
prim = pd.DataFrame([
    {"dataset": "PrimeKG kg.csv", "source / version": "Harvard Dataverse doi:10.7910/DVN/IXA7BM, version 2.1 (released 2022-05-02); kg.csv 981,751,236 bytes", "sha256": prov["source"]["sha256"][:16] if "source" in prov else prov.get("kg_sha256", "")[:16],
     "raw path": "data/external/primekg_kg.csv", "processed": "data/processed/primekg/*, splits/seed42.npz", "verified how": "hash recorded at build; validate_primekg_dataset.py"},
    {"dataset": "MONDO ontology", "source / version": prov["source"]["mondo"] if "source" in prov else "", "sha256": "see freeze manifest", "raw path": "data/external/mondo.obo", "processed": "disease mapping columns in diseases.csv; NTD tables", "verified how": "mapping audit; build_ntd_mapping.py name checks"},
    {"dataset": "Open Targets (3 parquet files)", "source / version": "release 26.09 (byte-identical)", "sha256": ev["open_targets_release_identification"]["local_files"]["00000000.parquet"]["sha256_full"][:16],
     "raw path": "data/external/downloads/open_targets/ (+ open_targets_release_26.09/ for clinical_report)", "processed": "data/processed/open_targets/*", "verified how": "SHA-256 equality with release files; validate_open_targets.py"},
    {"dataset": "WHO Model List of Essential Medicines, 24th list (2025)", "source / version": "WHO DOI 10.2471/B09474; PDF metadata title says '23rd List (2023)' but page 1 states 24th list (2025)", "sha256": ev["who_eml_pdf"]["sha256_full"][:16],
     "raw path": "data/external/B09474-eng.pdf", "processed": "data/external/who_eml.csv; data/processed/eml/*", "verified how": "tests/test_who_eml_extraction.py; eml_mapping_audit.csv"},
    {"dataset": "WHO NTD list", "source / version": "WHO health-topic page, accessed 2026-11-10", "sha256": sh("who_ntd_topic", 16), "raw path": "(web page; hash in evidence log)", "processed": "data/processed/ntd/*", "verified how": "direct fetch; build_ntd_mapping.py asserts"},
    {"dataset": "HAI price surveys (3)", "source / version": "Karnataka Nov 2004, Maharashtra Jan 2005, Delhi Jul 2011", "sha256": "per-file SHA-1 in Docs/HAI_DOWNLOAD_MANIFEST.md", "raw path": "data/external/downloads/hai_price_surveys/", "processed": "data/processed/hai/*", "verified how": "audit_hai_parsing.py"},
    {"dataset": "IHME GBD 2023 export", "source / version": "IHME-GBD_2023_DATA-028a73a1-1.zip (17 causes; DALYs, Rate, Global, Both, All ages, 2023); the earlier 6-row all-cause stub 9feb184e is kept and ignored", "sha256": "zip cb39fff2e1ce6eaa68c4e0f138e578ab3f48638ec951cf989db0a720d046df71", "raw path": "data/external/downloads/ihme_gbd/ihme_ntd_dalys_2023.csv (original ZIP + citation.txt in data/external/downloads/ihme_gbd_source_2023/ and the project root)", "processed": "data/processed/ihme/daly_by_ntd_group.csv (15 of 22 groups with data)", "verified how": "process_ihme_daly.py validation; hashes of ZIP and extracted CSV match"},
    {"dataset": "SMILES / fingerprints", "source / version": "resolved at build time via MyChem.info then PubChem PUG REST (scripts/fetch_smiles.py); Morgan radius 2, 2048 bits (RDKit)", "sha256": "freeze manifest", "raw path": "data/external/drugbank_smiles_cache.json (cache)", "processed": "drugs.csv, drug_features.npy",
     "verified how": f"{man['splits']['train']['drugs'] + man['splits']['val']['drugs'] + man['splits']['test']['drugs']} split drugs; 996 drugs without SMILES, 997 zero-fingerprint rows"},
])
doc = f"""# Data provenance

Generated {pd.Timestamp.now().strftime('%Y-%m-%d')}. Every external source: where it came from, which version, how it was verified. Licences are in `Docs/LICENCE_AUDIT.md`; Open Targets detail in `Docs/OPEN_TARGETS_PROVENANCE.md`; WHO NTD detail in `Docs/NTD_MAPPING.md`; the machine-readable evidence log is `Docs/source_evidence/fetch_log_2026-11-10.json`; checksums of the processed release are in `Docs/release/`.

{md(prim)}

## Benchmark definition (frozen)
Target: drug -> disease **indication** (PrimeKG relation CtD). Contraindications and off-label uses stay as separate graph relations and are never labels. Split: seed {man['seed']}, strategy '{man['strategy']}', neg_ratio {man['neg_ratio']}, drug-disjoint {man['test_size']}/{man['val_size']} + remainder, stratified on NTD.
Full variant: train/val/test positives {man['splits']['train']['positives']:,}/{man['splits']['val']['positives']:,}/{man['splits']['test']['positives']:,}; negatives {man['splits']['train']['negatives']:,}/{man['splits']['val']['negatives']:,}/{man['splits']['test']['negatives']:,}; NTD positives {man['splits']['train']['ntd_positives']}/{man['splits']['val']['ntd_positives']}/{man['splits']['test']['ntd_positives']}.
Structure-covered variant: {manc['rule']}; positives {manc['splits']['train']['positives_kept']:,}/{manc['splits']['val']['positives_kept']:,}/{manc['splits']['test']['positives_kept']:,}; negatives {manc['splits']['train']['negatives_kept']:,}/{manc['splits']['val']['negatives_kept']:,}/{manc['splits']['test']['negatives_kept']:,}; NTD positives {manc['splits']['train']['ntd_positives_kept']}/{manc['splits']['val']['ntd_positives_kept']}/{manc['splits']['test']['ntd_positives_kept']}.

## HAI
{hai['rows']} (price/availability, median price, affordability, unique medicines); DrugBank mapping {hai['drugbank_mapping']['medicines']} by tiers {hai['drugbank_mapping']['tiers']}; unmapped: {', '.join(hai['drugbank_mapping']['unmapped_names'])}. Audit: `Docs/HAI_AUDIT.md`.

## WHO EML mapping
{eml['eml_entries']} entries ({eml['single_entries']} single, {eml['combination_entries']} combination); single status {eml['single_status']}; mapped by tier {eml['single_mapped_by_tier']}; {eml['distinct_primekg_drugs_flagged']} distinct PrimeKG drugs flagged; combination components {eml['combination_components']}.

## Equity table
{eqr['pairs']:,} indication pairs; inputs present {eqr['inputs_present']}; component coverage (all pairs) {eqr['component_coverage_pct_all_pairs']}; NDPI available for {eqr['pairs_with_ndpi']:,} pairs. DALY exists only for NTD diseases whose group maps to an exported GBD cause: {eqr['burden_aware_pairs']} pairs ({eqr['burden_aware_ntd_pairs']} of {eqr['denominators']['ntd_pairs']} NTD pairs); NDPI is burden-aware only for those, and {eqr['ntd_pairs_without_burden']} NTD pairs have no burden value.
"""
(R / "Docs/DATA_PROVENANCE.md").write_text(doc, encoding="utf-8")

# =============================== EQUITY_DATA_SPECS.md ===============================
doc = f"""# Equity data: status, specifications and validation

Generated {pd.Timestamp.now().strftime('%Y-%m-%d')}. All processors refuse bad input and never fill gaps with 0.

| component | status | where | validation |
|---|---|---|---|
| WHO EML (24th list, 2025) | **DONE**: extracted from `data/external/B09474-eng.pdf` ({eml['single_entries']} single + {eml['combination_entries']} combination entries); mapped to PrimeKG ({eml['single_status']['mapped']} single entries -> {eml['distinct_primekg_drugs_flagged']} drugs) | `data/external/who_eml.csv`, `data/processed/eml/` | `tests/test_who_eml_extraction.py`; `eml_mapping_audit.csv` |
| HAI price/availability (3 Indian surveys) | **DONE** (regional pilot) | `data/processed/hai/` | `scripts/audit_hai_parsing.py` |
| IHME DALY (GBD 2023) | **DONE**: `ihme_ntd_dalys_2023.csv` (17 causes) validated and processed; 15 of 22 project groups have a DALY rate, 7 are missing (scabies, Buruli ulcer, mycetoma, chromoblastomycosis, noma, snakebite envenoming, yaws); unit of 'Rate' not verified against IHME documentation | `data/processed/ihme/` | `scripts/process_ihme_daly.py` (self-test + real file); mapping notes in `daly_by_ntd_group.csv` |

## IHME export: received and processed (settings kept for reference)
GBD Results tool (https://vizhub.healthdata.org/gbd-results/). The exported file `IHME-GBD_2023_DATA-028a73a1-1` (17 causes) used the settings below; **only the cause selection is missing**.
| setting | value |
|---|---|
| Base | Single |
| Measure | DALYs (Disability-Adjusted Life Years) |
| Metric | Rate |
| Location | Global |
| Sex | Both |
| Age | All ages (or Age-standardized: then run `process_ihme_daly.py --age "Age-standardized"`) |
| Year | 2023 (one year) |
| Metric units | **Not verified from IHME documentation** (the Appendix 3 metric definitions could not be read). The usual GBD convention is DALY rate = per 100,000 population; the processor records the metric name and treats the values as relative burden only. |
| Cause availability | **Not verified.** The IHME tool is interactive and the cause-list page could not be fetched. Secondary GBD 2021 papers (found by search, not read in full) name Chagas disease, cutaneous/mucocutaneous and visceral leishmaniasis, food-borne trematodiases, Guinea worm disease and an 'other NTDs' category as separate causes; the rest of the list below is expected, not confirmed. Check each name in the tool's cause picker; `process_ihme_daly.py` prints unmatched names. |
| Cause | the NTD causes the tool offers, expected names: Visceral leishmaniasis; Cutaneous and mucocutaneous leishmaniasis; Chagas disease; African trypanosomiasis; Schistosomiasis; Cystic echinococcosis; Lymphatic filariasis; Onchocerciasis; Leprosy; Trachoma; Dengue; Rabies; Ascariasis; Trichuriasis; Hookworm disease; Food-borne trematodiases; Guinea worm disease; Scabies |
Columns in the file: `measure_id, measure_name, location_id, location_name, sex_id, sex_name, age_id, age_name, cause_id, cause_name, metric_id, metric_name, year, val, upper, lower` (+ population-group columns). Placed as `data/external/downloads/ihme_gbd/ihme_ntd_dalys_2023.csv`; original ZIP and `citation.txt` preserved in `data/external/downloads/ihme_gbd_source_2023/` (and the project root). **Reconciliation with the real export (17 causes).** Requested but not exported: Visceral leishmaniasis and Cutaneous/mucocutaneous leishmaniasis (the export has the parent 'Leishmaniasis', id 347, treated as covering both; the id gap 347 -> 350 suggests the children were omitted: an inference, the hierarchy was not read) and Scabies (group stays missing). Exported but not requested: Cysticercosis (id 352), mapped to the project group taeniasis/cysticercosis (cysticercosis only; taeniasis is not a separate cause there). Cystic echinococcosis covers only part of the WHO echinococcosis group. Six project groups have no GBD cause at all (Buruli ulcer, mycetoma, chromoblastomycosis, noma, snakebite envenoming, yaws) and stay missing, never 0. The unit of 'Rate' is not stated in the file (usual GBD convention: per 100,000).
The IHME agreement forbids providing third parties the ability to download the data: keep the files out of git and out of any public hosting.

## Processing order (already run on 2026-11-11)
1. `python scripts/process_ihme_daly.py` -> `data/processed/ihme/daly_by_ntd_group.csv`, `daly_report.json`
2. `python scripts/build_equity_features.py` -> `data/processed/equity/*` (EML + DALY + HAI; weights 0.45/0.45/0.10 are a proposal; the sensitivity grid becomes meaningful once DALY exists)
3. `python scripts/make_readiness_report.py`, `python scripts/make_final_docs.py`, `python scripts/freeze_release.py --tag vdm_v1`

## EML semantics
`eml_status` = 1 confirmed positive (single-ingredient entry); empty if the drug appears only inside fixed-dose combinations, or is **unresolved** (its name shares a 5+ letter token with one of the {eml['single_status']['unmapped']} unmapped single entries in `data/processed/eml/eml_unmatched.csv`); 0 only where no candidate entry was found, which is not proof of absence. The 'EML coverage' percentage counts those zeros and is not evidence coverage: use `eml_confirmed_positive_pct` / `eml_evidence_counts_all_pairs` in `equity_report.json`.
"""
(R / "Docs/EQUITY_DATA_SPECS.md").write_text(doc, encoding="utf-8")

# =============================== HUMAN_ACTION_CHECKLIST.md ===============================
H = [
    ("H1", "DONE 2026-11-11: export received, validated and processed - nothing further needed from you", "IHME GBD disease-specific DALYs",
     "IHME-GBD_2023_DATA-028a73a1-1: 17 causes, DALYs/Rate/Global/Both/All ages/2023; 15 of 22 groups mapped, 7 missing (see EQUITY_DATA_SPECS.md).", "https://vizhub.healthdata.org/gbd-results/ (login)", "Settings table in `Docs/EQUITY_DATA_SPECS.md`", "`data/external/downloads/ihme_gbd/`",
     "done", "nothing"),
    ("H2", "DECIDED 2026-11-11: option B approved and implemented - nothing further needed from you", "Baselines get a second, drug + disease-profile variant",
     "PrimeKG disease features are `is_ntd` plus two constant columns (DALY absent): one informative feature. The baselines are effectively drug-only and cannot model drug-disease specificity; GNNs and Node2Vec see disease neighbourhoods. A like-for-like comparison would give baselines a disease representation.",
     "n/a", "Done: configs/primekg_morgan_dp.yaml and primekg_morgan_structcov_dp.yaml (block = src/features/disease_profile.py, built from TRAIN edges/labels only, leave-one-out); the drug-only configs are unchanged; both variants run in the Colab train stage. Tests: tests/test_disease_profile.py (8). Not run on any model.",
     "configs/*_dp.yaml (done)", "nothing", "baseline-vs-GNN claims (now answerable with both variants)"),
    ("H3", "MANDATORY at Colab time", "Approve pushing the local commits to `origin/mukul`", "Colab clones from GitHub; the notebook is pinned to a commit that is not on the remote yet.", "n/a", "Reply 'push approved' after reviewing `git log origin/mukul..HEAD`", "GitHub", "n/a", "Colab clone"),
    ("H4", "MANDATORY for the Colab `external` stage (optional for the core benchmark)", "Put the private/manual inputs in Drive",
     "These files are git-ignored (licences/size) so a clean clone does not contain them. Without them the external stage skips Open Targets, HAI, IHME and EML and reports those components as missing.",
     "n/a", "Copy to `MyDrive/VDM_Data/`: folder `downloads/` (containing `open_targets/`, `open_targets_release_26.09/`, `hai_price_surveys/`, `ihme_gbd/`), and either `who_eml.csv` or `B09474-eng.pdf`; optionally `drugbank_smiles_cache.json`.",
     "restored by notebook Step 3 into `data/external/`", "as they exist locally", "external stage"),
    ("H5", "MANDATORY before any PUBLIC release; not needed for Colab", "Confirm DrugBank/IHME entitlements and decide on git history",
     "DrugBank data are CC BY-NC 4.0 / academic licence; PrimeKG contains DrugBank-derived content; three small DrugBank-derived blobs remain in `origin/mukul` history (see `Docs/LICENCE_AUDIT.md` section 3). IHME requires acceptance of its non-commercial agreement.",
     "https://go.drugbank.com/releases/latest ; IHME agreement page", "Confirm you hold the academic entitlement; choose: leave history, or approve `git filter-repo` + force-push (coordinate with teammates)", "Git history", "n/a", "public repository / data release"),
    ("H6", "MANDATORY before publishing Open Targets-derived tables (not needed otherwise)", "Read the terms of ClinicalTrials.gov/AACT, TTD and the PMDA approvals pages in a browser",
     "These pages are JavaScript-rendered or returned stubs, so they could not be read automatically.", "https://clinicaltrials.gov/about-site/terms-conditions ; https://db.idrblab.net/ttd/ ; https://www.pmda.go.jp/english/0010.html", "Record the terms (or send them to me to log)", "`Docs/LICENCE_AUDIT.md`", "n/a", "redistribution of OT-derived data"),
    ("H7", "MANDATORY before submission", "Approve final publication claims and full-text verification of references [1]-[5] and [15]", "Claim support was checked against abstracts/documentation pages only.", "the papers themselves", "Read the cited passages; approve the final text", "`Docs/paper/`", "n/a", "paper submission"),
    ("H8", "OPTIONAL", "Decide whether to run a separate extended-NTD analysis (chikungunya, tungiasis, sporotrichosis, podoconiosis)", "They are WHO fact-sheet or entry components not in the frozen flag; extending the flag would change the NTD stratification, so it would be a separate analysis.", "n/a", "Reply yes/no", "n/a", "a decision", "nothing"),
    ("H9", "OPTIONAL", "Ask Open Targets what `UNVALIDATED_INDICATION` means", "47,044 pairs have only flagged reports; the documentation does not settle it. Default handling (filter to >= 1 unflagged report) is already implemented.", "https://community.opentargets.org/", "A short answer", "`Docs/OPEN_TARGETS_PROVENANCE.md`", "n/a", "OT corroboration interpretation"),
    ("H10", "OPTIONAL", "Decide on a multi-seed study", "Baselines hard-code random_state=42; other seeds need a small code change plus extra Colab time.", "n/a", "Reply yes/no", "n/a", "a decision", "variance estimates"),
]
hc = pd.DataFrame(H, columns=["id", "mandatory?", "task", "why", "official source / URL", "exact settings / decision", "destination", "required schema", "blocks"])
doc = f"""# Human action checklist

Generated {pd.Timestamp.now().strftime('%Y-%m-%d')}. Everything that needs you personally. **Not on this list because it already exists locally or was done for you:** the WHO EML PDF (processed), the Open Targets files (release identified, same-release `clinical_report` downloaded), the HAI surveys (parsed), the WHO NTD list (read and reconciled), the licence pages that could be read.

## Mandatory
{md(hc[hc['mandatory?'].str.startswith('MANDATORY')])}

## Optional
{md(hc[hc['mandatory?'].str.startswith('OPTIONAL')])}

## Is anything still pending for the preparation phase?
Yes, but none for the preparation phase (H1 and H2 are done). Everything else mandatory is either needed only at Colab time (H3, H4), only before a public release (H5, H6) or only before submission (H7).
"""
(R / "Docs/HUMAN_ACTION_CHECKLIST.md").write_text(doc, encoding="utf-8")

# =============================== FINAL_RELEASE_READINESS.md ===============================
D, I_, B, N, NA = "DONE AND VALIDATED", "IMPLEMENTED BUT NOT VALIDATED", "BLOCKED ON MY INPUT", "NOT STARTED", "NOT APPLICABLE"
T = [
    ("PrimeKG", "Full benchmark built (7,957 drugs, 17,080 diseases, 9,388 indications) and leakage-validated", D, "validate_primekg_dataset.py: all hard checks passed"),
    ("PrimeKG", "Drug-disjoint split; held-out and reverse-edge leakage checks", D, "same validator; message-passing graph has 0 treats edges"),
    ("PrimeKG", "Negatives audited (sampled only; none curated; no negative is a known indication/contraindication/off-label pair)", D, "split manifest negatives_in_known_pairs = 0"),
    ("PrimeKG", "Structure-covered variant built with its own validation", D, "make_structure_covered_variant.py built-in checks; loaders audited"),
    ("PrimeKG", "SMILES / fingerprint coverage and zero-fingerprint handling documented", D, "996 no SMILES, 997 zero fingerprints; with/no_structure subsets"),
    ("PrimeKG", "Disease representation for classical baselines: optional leak-free disease-profile variant (configs/*_dp.yaml)", I_, "tests/test_disease_profile.py (8 passed incl. real-split identity); no model trained; effect on results unknown until Colab"),
    ("NTD", "Official WHO list read directly (21 groupings, 25 fact sheets)", D, "evidence log; build_ntd_mapping.py asserts"),
    ("NTD", "Reconciliation with the 22 frozen groups; frozen labels unchanged", D, "ntd_group_reconciliation.csv; flag nodes 68 = union of groups"),
    ("NTD", "Nested-root / double-counting audit", D, "ntd_group_overlaps.csv: 2 overlaps; 85 vs 82 unique pairs"),
    ("NTD", "Candidate extensions kept separate from the frozen flag", D, "scope column in ntd_disease_mapping.csv"),
    ("HAI", "Raw preserved, parsed and numerically audited", D, "audit_hai_parsing.py: 0 FAIL, 3 documented WARN"),
    ("HAI", "Medicine -> DrugBank mapping tiers (55/60; 5 unmapped combinations/biologic-like)", D, "hai_medicines.csv"),
    ("Open Targets", "Release identified (26.09) by byte identity; same-release files obtained", D, "SHA-256 equality in evidence log"),
    ("Open Targets", "Every report reference attributed to a provider/source", D, "100% of 321,785 references resolved"),
    ("Open Targets", "Mapping coverage, tiers and loader validation", D, "validate_open_targets.py all hard checks passed"),
    ("Open Targets", "Quality-flag (UNVALIDATED_INDICATION) semantics", I_, "filter implemented; meaning unresolved (H9)"),
    ("Open Targets", "Independent external-validation claim", NA, "no independence claim is made"),
    ("Licensing", "Source-by-source audit with evidence log", D, "29 pages hashed; statuses VERIFIED / PARTIAL / NOT VERIFIED"),
    ("Licensing", "Legal conclusions (ShareAlike, CC0 over NC constituents, redistribution)", B, "legal judgement: H5/H6"),
    ("Licensing", "Git history inspected for DrugBank-derived files", D, "3 blobs, 2 commits, on origin/mukul"),
    ("Models", "Baseline implementations audited statically; defects fixed", D, "cold-start checkpoints now saved; SHAP class slice; seeds documented"),
    ("Models", "GNN implementations audited; eval-mode dropout bug fixed; regression tests", D, "tests/test_gnn_eval_determinism.py (5 passed)"),
    ("Models", "Loaders / splits consistent across all models", D, "audit_models.py loaders + validator"),
    ("Models", "Cold-start ablation script", I_, "compiles; not run"),
    ("Models", "Results exporter (tables + figures)", I_, "run on one real baseline file only; multi-model / GNN figures untested"),
    ("Models", "Explainability (SHAP trees, GNNExplainer)", I_, "synthetic API tests pass (tests/test_explainability.py); real models need Colab"),
    ("Models", "Trained-model performance", N, "Colab by design"),
    ("Equity", "IHME file inspected", D, "17 causes, one row each, DALYs/Rate/Global/Both/All ages/2023, no missing values; ZIP and CSV hashes match"),
    ("Equity", "IHME DALY processing", D, "process_ihme_daly.py: 15 groups complete, 7 missing; mapping reconciliation documented; unit of 'Rate' not verified against IHME documentation"),
    ("Equity", "WHO EML extracted from the official PDF and mapped", I_, "automated structure checks + tests only; NOT manually validated entry by entry (spot checks on a few entries only); corrections in Docs/EML_EXTRACTION_CORRECTIONS.md"),
    ("Equity", "Equity table + NDPI code", D, "EML + HAI + DALY; burden-aware only for 50 NTD pairs (DALY missing for 32 NTD pairs and all non-NTD pairs); missing never 0 (tests)"),
    ("Equity", "NDPI evaluation and sensitivity", I_, "computed on real EML + HAI + DALY inputs; weights are an unvalidated proposal; on 49 burden-aware pairs the ranking is weight-sensitive (Spearman -0.42 to 0.87 median); NDPI has no external validation"),
    ("Paper", "Bibliography metadata verified (15 references)", D, "Crossref / arXiv / WHO page"),
    ("Paper", "Claim-to-reference support", I_, "abstract/documentation-level; full text pending (H7)"),
    ("Paper", "Structure, citation order, figures, tables, numbers vs metrics.json", D, "scripts/check_paper.py passed"),
    ("Paper", "Results, ablation and NDPI sections", N, "need Colab results and H1"),
    ("Release", "Clean-clone check (compile, paths, imports)", D, "75 files compile; 24 referenced paths exist; imports ok"),
    ("Release", "Dependencies documented", I_, "requirements.txt completed; local versions recorded; Colab versions recorded at run time (not pinned)"),
    ("Release", "Commits, notebook pin and release manifest reconciled", D, "see section 3 below"),
    ("Release", "Push to GitHub", B, "H3"),
]
tt = pd.DataFrame(T, columns=["area", "task", "status", "evidence / note"])
cnt = tt.status.value_counts().to_dict()
den = len(tt) - cnt.get(NA, 0)
pct = round(100 * cnt.get(D, 0) / den, 1)
pct_any = round(100 * (cnt.get(D, 0) + cnt.get(I_, 0)) / den, 1)
git = __import__("subprocess")
head = git.run(["git", "rev-parse", "HEAD"], cwd=R, capture_output=True, text=True).stdout.strip()
ahead = git.run(["git", "rev-list", "--count", "origin/mukul..HEAD"], cwd=R, capture_output=True, text=True).stdout.strip()
nb = json.loads((R / "notebooks/colab_final_run.ipynb").read_text(encoding="utf8"))
import re as _re
pin = _re.search(r"PIN = '([0-9a-f]{40})'", " ".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")).group(1)
dirty = bool(git.run(["git", "status", "--porcelain"], cwd=R, capture_output=True, text=True).stdout.strip())
changed_since_pin = [x for x in git.run(["git", "diff", "--name-only", pin], cwd=R, capture_output=True, text=True).stdout.splitlines() if x]
untracked = [x for x in git.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=R, capture_output=True, text=True).stdout.splitlines() if x]
code_after_pin = [x for x in changed_since_pin + untracked if not (x.startswith("notebooks/") or x.startswith("Docs/"))]
pin_ok = not code_after_pin and git.run(["git", "merge-base", "--is-ancestor", pin, "HEAD"], cwd=R).returncode == 0
doc = f"""# Final release readiness

Generated {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')} by `scripts/make_final_docs.py`. Statuses: {D}, {I_}, {B}, {N}, {NA}.

## Task registry
{md(tt)}

Counts: {cnt}.

## Questions answered explicitly
**A. Percentage complete and how it was calculated.** {pct}% of applicable preparation tasks are {D} ({cnt.get(D, 0)} of {den}; {NA} items excluded); {pct_any}% are at least implemented. Method: equal weighting of the {len(tt)} registry tasks above, so the figure is crude. It excludes Colab results and the paper's results sections by design, and a high percentage does **not** mean the research is finished.

**B. Datasets.** Complete: PrimeKG full benchmark, structure-covered variant, NTD mapping tables, HAI tables (regional pilot), Open Targets tables (with provenance), WHO EML flags. IHME DALY export (15 of 22 NTD groups). Incomplete by nature: burden exists for 50 of 82 NTD pairs only; seven groups have no GBD cause.

**C. Mappings.** Complete: WHO->MONDO->PrimeKG (with documented differences, nested roots and 6 WHO entries without indications); Open Targets drug (tier 1: {otm['drugs']['drugs_by_tier'].get('1_exact_xref', 0):,} ChEMBL ids) and disease mapping; HAI medicines 55/60; EML {eml['single_status']['mapped']}/{eml['single_entries']} single entries. Ambiguous or missing: {eml['single_status']['unmapped']} EML single entries unmapped; 5 HAI medicines unmapped; ~{otm['diseases']['by_status(ids)'].get('unmapped_no_xref', 0)} Open Targets disease ids without a MONDO xref and {otm['diseases']['by_status(ids)'].get('non_disease_ontology', 0)} phenotype/GO ids; MONDO->DOID unmapped for 9,089 PrimeKG disease nodes.

**D. Scripts implemented and validated.** Validated: dataset build/split/validation, structure variant, NTD mapping, HAI parser + audit, Open Targets loader/validator/attribution, EML extraction + tests, GNN determinism tests, explainability API tests (synthetic), paper checks, freeze/verify, clean-clone check. Implemented but not validated on real trained models: training scripts for Node2Vec and the five GNNs on GPU, cold-start ablation, results exporter beyond one baseline, explanation CLI.

**E. Paper tables and figures the final pipeline can generate** (from actual outputs): dataset statistics, split statistics, model comparison, cold-start metrics, ablation, structure sensitivity, NTD-specific performance, NDPI prioritisation and equity coverage (needs DALY for a meaningful NDPI), ROC/PR, confusion matrices, calibration, training curves, embedding PCA, SHAP and GNN-explanation tables. Figures 1-7 already exist from real data. **Not yet generated by any script:** a drug-disease candidate network figure, a molecular-feature analysis figure, an NDPI ranking figure and an equity-component contribution figure (they need DALY/EML-based NDPI and, for the network, final model outputs); no synthetic figure is presented as a result.

**F. Unresolved issues.** `Docs/DATA_AND_PIPELINE_READINESS.md` section 6 lists 24; the main ones: burden missing for 7 NTD groups and for all non-NTD pairs; weight-sensitivity of NDPI; the effect of the disease-profile baseline variant (known only after Colab); legal questions (`Docs/LICENCE_AUDIT.md` section 4); Open Targets flag semantics; small NTD test set (15 positives); full-text reference checks; unvalidated trained behaviour.

**G. What you must provide or approve.** See `Docs/HUMAN_ACTION_CHECKLIST.md`: H3 (push approval), H4 (Drive upload), H5-H7 before release/submission.

**H. Is human-dependent work still pending?** Not for the preparation phase (H1, H2 done); H3-H4 at Colab time; H5-H7 before release/submission.

**I. Can you freeze and move to Colab?** Yes, once H3 (push) and H4 (Drive upload) are done. The IHME data are in place; the NDPI is burden-aware for 50 NTD pairs only.

**J. Single next action.** Approve the push (**H3**) and upload the git-ignored inputs to Drive (**H4**), then run the Colab notebook.

## Colab commands (do not run yet; the notebook `notebooks/colab_final_run.ipynb` contains them)
```
!git clone https://github.com/MUKUL-PRASAD-SIGH/VectorDrugMatch && %cd VectorDrugMatch && git checkout <pinned SHA>
!pip install -q rdkit mlflow optuna shap xgboost lightgbm loguru pyyaml torch-geometric tabulate scikit-learn lxml matplotlib pymupdf pyarrow
!pip install -q pyg_lib torch_scatter torch_sparse torch_cluster -f https://data.pyg.org/whl/torch-<torch>+cu<cuda>.html
!python scripts/run_full_pipeline.py --stage prepare
!python scripts/run_full_pipeline.py --stage external
!python scripts/run_full_pipeline.py --stage smoke
!python scripts/run_full_pipeline.py --stage train --variant full
!python scripts/run_full_pipeline.py --stage report --variant full
!python scripts/run_full_pipeline.py --stage explain --variant full
!python scripts/run_full_pipeline.py --stage train --variant structcov
!python scripts/run_full_pipeline.py --stage report --variant structcov
!python scripts/freeze_release.py --tag vdm_v1
```

## 3. Commit / pin / manifest reconciliation (state at generation)
HEAD `{head[:10]}`; local commits ahead of `origin/mukul`: {ahead}; working tree {'has uncommitted changes' if dirty else 'clean'}. The notebook pins code commit `{pin[:10]}`. Test: after the pinned commit only `notebooks/` and `Docs/` may change. Result: **{'PASS' if pin_ok else 'FAIL: files changed after the pin: ' + ', '.join(code_after_pin[:12]) + ' (commit them, then re-pin)'}**. The release manifest `Docs/release/vdm_v1_candidate_manifest.json` records the data checksums, versions and the commit at freeze time; rename it `vdm_v1` after H1 data arrive.

## Final Colab-readiness gate
| gate | status |
|---|---|
| required raw/processed datasets exist locally | yes |
| mandatory mappings validated | yes |
| both benchmark variants reproducible (config + split files + scripts) | yes |
| model, evaluation, ablation, exporter, explainability scripts implemented | yes (see D) |
| configurations consistent | yes (two configs: full and structcov) |
| dependencies documented | partly (versions pinned only as validated-local; Colab recorded at run time) |
| paths work in a clean clone | yes (clean-clone check) |
| no untracked local-only dependency silently required | the external stage needs Drive uploads (H4) and says so |
| no restricted raw data in git | yes (`data/` ignored; DrugBank-derived blobs remain in history: H5) |
| notebook pins a commit containing all code | {'yes' if pin_ok else 'NO: see section 3'}; it can only be cloned on Colab after the push (H3) |
"""
(R / "Docs/FINAL_RELEASE_READINESS.md").write_text(doc, encoding="utf-8")
print("wrote 6 documents; completion", pct, "% DONE;", pct_any, "% at least implemented; counts", cnt)
