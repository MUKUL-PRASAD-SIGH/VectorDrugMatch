# Licence and terms audit

Generated 2026-11-10. This is a provenance record, not legal advice. Evidence: `Docs/source_evidence/fetch_log_2026-11-10.json` (URL, bytes, SHA-256 of every page read); raw pages are not stored in git.

## 1. Open Targets: platform level
* Licence page (<https://platform-docs.opentargets.org/licence>, 12,081 bytes, SHA-256 `1dc64d95df328593...`): *"Open Targets Platform is marked with CC0 1.0. This dedicates the data to the public domain, allowing downstream users to consume the data without restriction."* Code: Apache 2.0.
* Terms of use (<https://platform-docs.opentargets.org/licence/terms-of-use>): Open Targets *"places no additional restrictions on the use or redistribution of the data ... other than those provided by the original data owners"*, and *"the original data may be subject to rights claimed by third parties ... It is the responsibility of users ... to ensure that their exploitation of the data does not infringe any of the rights of such third parties."*
* The licence page also says all sources **listed in its table** *"have agreed for their data to be used without restriction by all Open Targets users."* That sentence covers only the listed sources.
* **Conclusion:** the CC0 marking is the platform's own statement; it does not by itself settle the terms of the upstream records, and Open Targets' own terms defer to the original data owners.

## 2. Complete upstream source licence table (as published; 44 sources)
Copied from the licence page into `Docs/source_evidence/ot_licence_table_2026-11-10.csv`. Only **ChEMBL** among these supplies clinical-indication records.

| data_source | licence_as_stated | feeds_clinical_reports |
|---|---|---|
| AlphaMissense | CC-BY 4.0 | no |
| Cancer Gene Census | Commercial use for Open Targets | no |
| Cancer Genome Interpreter | CC-BY 4.0 | no |
| Cell Ontology | CC BY 4.0 | no |
| ChEMBL | CC BY-SA 3.0 | yes (ChEMBL curated indications + drug warnings) |
| ClinGen | CC0 1.0 | no |
| ClinVar (via EVA) | EMBL-EBI terms of use | no |
| EFO | Apache 2.0 | no |
| Ensembl | CC-BY 4.0 | no |
| Europe PMC | CC-BY, CC-BY-NC or CC0 license or open access (depending on publication licenses) | no |
| eQTL Catalogue | CC-BY 4.0 | no |
| Expression Atlas | CC-BY 4.0 | no |
| FAERS | CC0 1.0 | no |
| FinnGen R12 | Summary statistics can be requested here. | no |
| Gene Ontology | CC-BY 4.0 | no |
| Gene Signature | Apache 2.0 | no |
| Gene2Phenotype | EMBL-EBI terms of use | no |
| Genomics England PanelApp | Commercial use for Open Targets | no |
| gnomAD | CC0 1.0 | no |
| GTEx | CC-BY 4.0 | no |
| GWAS Catalog | EMBL-EBI terms of use (Summary statistics are under CC0 1.0) | no |
| HeCaTos | CC-BY 4.0 | no |
| HPO | CC0 1.0 | no |
| Human Protein Atlas | CC BY-SA 3.0 | no |
| Intact | EMBL-EBI terms of use | no |
| IntOGen | CC0 1.0 | no |
| MGI | CC-BY 4.0 | no |
| MONDO | CC-BY 4.0 | no |
| Orphanet | CC-BY 4.0 | no |
| panUKB | CC BY 4.0 | no |
| PhenoDigm | CC-BY 4.0 | no |
| Probes and Drugs | CC-BY 4.0 | no |
| PROGENy | Apache 2.0 | no |
| Project Score | Commercial use for Open Targets | no |
| Reactome | CC-BY 4.0 | no |
| Sequence Ontology | CC-BY 4.0 | no |
| Signor (via Intact) | EMBL-EBI terms of use | no |
| SLAPenrich | MIT terms of use | no |
| String DB | CC-BY 4.0 | no |
| TEP | CC-BY 4.0 | no |
| Tox21 | CC0 1.0 | no |
| Uberon | CC BY 3.0 | no |
| UKB-PPP | Apache 2.0 | no |
| UniProt | CC-BY 4.0 | no |

## 3. Sources that actually contribute to the clinical-indication data, and their terms
Open Targets integrates **six source families** for clinical reports (clinical-report documentation, read 2026-11-10). **Only one of them, ChEMBL, is in the licence table above.** The other four named sources (AACT/ClinicalTrials.gov, TTD, EMA, PMDA) are absent from it. Which of them contribute to *our* 86,451 records cannot be determined from our files (`Docs/OPEN_TARGETS_PROVENANCE.md` section 3), so none can be ruled out.

| source family (feeds Open Targets clinical reports) | in OT licence table? | own site checked | status | implication / open question |
|---|---|---|---|---|
| ChEMBL curated indications + drug warnings | yes: CC BY-SA 3.0 | ChEMBL home page states 'Creative Commons Attribution-ShareAlike 3.0 Unported license' | VERIFIED | Attribution and ShareAlike apply to adaptations; whether our derived DrugBank x MONDO pair lists are adaptations is an open legal question (not legal advice). |
| ClinicalTrials.gov via AACT | NO | ClinicalTrials.gov terms page returned a JavaScript shell (177 characters of text, no terms); AACT landing page: no licence text found | NOT VERIFIED | Terms unknown from this audit; the platform-level CC0 does not establish them. |
| Therapeutic Target Database (TTD) | NO | TTD landing returned a 461-byte stub; no terms retrieved | NOT VERIFIED | Terms unknown. |
| EMA Human Medicines | NO | EMA legal notice: content may be reproduced and distributed for non-commercial and commercial purposes provided EMA is acknowledged as the source; excludes third-party content | PARTIAL | This is the EMA website's notice, not a statement about the Human Medicines dataset as processed by Open Targets; acknowledgement required. |
| PMDA approvals | NO | page footer reads 'Copyright (c) Pharmaceuticals and Medical Devices Agency, All Rights Reserved' with a Site Policy link; policy text not retrieved | NOT VERIFIED | Footer suggests reserved rights; terms must be read before any redistribution of PMDA-derived records. |
| DailyMed / FDA labels (referenced inside ChEMBL indication records) | not a separate family | not checked | NOT CHECKED | Provenance reference only. |

**Do not conclude** that the dataset has only a ChEMBL licensing requirement: ChEMBL is the only family whose licence is published in Open Targets' table, not the only family that contributes.

## 4. Other project data (status)
| Data | Stated terms | Status |
|---|---|---|
| PrimeKG kg.csv | CC0 1.0 per Harvard Dataverse metadata | upstream components (including DrugBank-derived content) NOT checked |
| MONDO | CC-BY 4.0 as listed in the Open Targets table | Monarch's own statement not checked |
| WHO NTD list | WHO web page ((c) WHO) | used for a factual list of disease names only |
| HAI price surveys, IHME GBD, WHO EML | not checked | terms to be read before redistribution |
| DrugBank-derived files removed from the repo index | present in git history (commit 1829752 on origin/mukul) | team decision on history pending |

## 5. What the project does in the meantime
Raw and derived external data are git-ignored (`data/`); only aggregate counts and figures appear in the paper; Open Targets data are not used for training or evaluation; no derived pair list is redistributed. Before any public data release: close the NOT VERIFIED rows, obtain per-source attribution (provenance doc section 3), and decide on ShareAlike handling for ChEMBL-derived records.
