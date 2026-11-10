# Human action checklist

Generated 2026-11-11. Everything that needs you personally. **Not on this list because it already exists locally or was done for you:** the WHO EML PDF (processed), the Open Targets files (release identified, same-release `clinical_report` downloaded), the HAI surveys (parsed), the WHO NTD list (read and reconciled), the licence pages that could be read.

## Mandatory
| id | mandatory? | task | why | official source / URL | exact settings / decision | destination | required schema | blocks |
|---|---|---|---|---|---|---|---|---|
| H3 | MANDATORY at Colab time | Approve pushing the local commits to `origin/mukul` | Colab clones from GitHub; the notebook is pinned to a commit that is not on the remote yet. | n/a | Reply 'push approved' after reviewing `git log origin/mukul..HEAD` | GitHub | n/a | Colab clone |
| H4 | MANDATORY for the Colab `external` stage (optional for the core benchmark) | Put the private/manual inputs in Drive | These files are git-ignored (licences/size) so a clean clone does not contain them. Without them the external stage skips Open Targets, HAI, IHME and EML and reports those components as missing. | n/a | Copy to `MyDrive/VDM_Data/`: folder `downloads/` (containing `open_targets/`, `open_targets_release_26.09/`, `hai_price_surveys/`, `ihme_gbd/`), and either `who_eml.csv` or `B09474-eng.pdf`; optionally `drugbank_smiles_cache.json`. | restored by notebook Step 3 into `data/external/` | as they exist locally | external stage |
| H5 | MANDATORY before any PUBLIC release; not needed for Colab | Confirm DrugBank/IHME entitlements and decide on git history | DrugBank data are CC BY-NC 4.0 / academic licence; PrimeKG contains DrugBank-derived content; three small DrugBank-derived blobs remain in `origin/mukul` history (see `Docs/LICENCE_AUDIT.md` section 3). IHME requires acceptance of its non-commercial agreement. | https://go.drugbank.com/releases/latest ; IHME agreement page | Confirm you hold the academic entitlement; choose: leave history, or approve `git filter-repo` + force-push (coordinate with teammates) | Git history | n/a | public repository / data release |
| H6 | MANDATORY before publishing Open Targets-derived tables (not needed otherwise) | Read the terms of ClinicalTrials.gov/AACT, TTD and the PMDA approvals pages in a browser | These pages are JavaScript-rendered or returned stubs, so they could not be read automatically. | https://clinicaltrials.gov/about-site/terms-conditions ; https://db.idrblab.net/ttd/ ; https://www.pmda.go.jp/english/0010.html | Record the terms (or send them to me to log) | `Docs/LICENCE_AUDIT.md` | n/a | redistribution of OT-derived data |
| H7 | MANDATORY before submission | Approve final publication claims and full-text verification of references [1]-[5] and [15] | Claim support was checked against abstracts/documentation pages only. | the papers themselves | Read the cited passages; approve the final text | `Docs/paper/` | n/a | paper submission |

## Optional
| id | mandatory? | task | why | official source / URL | exact settings / decision | destination | required schema | blocks |
|---|---|---|---|---|---|---|---|---|
| H8 | OPTIONAL | Decide whether to run a separate extended-NTD analysis (chikungunya, tungiasis, sporotrichosis, podoconiosis) | They are WHO fact-sheet or entry components not in the frozen flag; extending the flag would change the NTD stratification, so it would be a separate analysis. | n/a | Reply yes/no | n/a | a decision | nothing |
| H9 | OPTIONAL | Ask Open Targets what `UNVALIDATED_INDICATION` means | 47,044 pairs have only flagged reports; the documentation does not settle it. Default handling (filter to >= 1 unflagged report) is already implemented. | https://community.opentargets.org/ | A short answer | `Docs/OPEN_TARGETS_PROVENANCE.md` | n/a | OT corroboration interpretation |
| H10 | OPTIONAL | Decide on a multi-seed study | Baselines hard-code random_state=42; other seeds need a small code change plus extra Colab time. | n/a | Reply yes/no | n/a | a decision | variance estimates |

## Is anything still pending for the preparation phase?
Yes, but none for the preparation phase (H1 and H2 are done). Everything else mandatory is either needed only at Colab time (H3, H4), only before a public release (H5, H6) or only before submission (H7).
