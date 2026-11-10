# Citation audit — `PAPER_DRAFT_IEEE.md`

Audit date: 2026-11-10. Method: (a) bibliographic metadata checked against Crossref (journal/proceedings entries) or the arXiv API (arXiv-only entries) and the official documentation page; (b) for the five references whose published abstract Crossref exposes, the abstract was read to confirm it supports the specific claim attached to it; (c) `scripts/check_paper.py` verifies that every in-text citation has an entry and vice versa, and that numbering follows first citation.

**Limits of this audit.** (b) used abstracts, not full texts. Entries marked *method attribution* are cited only to credit a well-known method and were checked for metadata, not re-read. A DOI that resolves is not treated as evidence that the paper supports a claim; the "claim supported" column is the evidence.

| # | Reference | Metadata check | Claim in the draft | Claim supported? | Caveat |
|---|---|---|---|---|---|
| 1 | Chandak, Huang, Zitnik, *Sci. Data* 10(1):67, 2023 | Crossref: exact title, authors, year, volume, article no., DOI | "benchmark on PrimeKG"; data source row | **Yes.** Abstract: 20 resources, **17,080 diseases**, 4,050,249 relationships, approved drugs with therapeutic action. Our node count (17,080 disease nodes) matches. | The abstract does not list relation types; the indication / contraindication / off-label split is read from the KG file itself (our provenance JSON), not attributed to the paper. CC0 licence is from Dataverse metadata, not this paper. |
| 2 | Himmelstein *et al.*, *eLife* 6:e26726, 2017 | Crossref: journal article, vol. 6, e26726 (Crossref's top search hits were the decision letter and preprint; the article DOI was fetched directly) | Hetionet is a separate Track-A reference graph | **Yes.** Abstract: Hetionet v1.0, 47,031 nodes, 2,250,197 relationships, trained on **755 existing treatments** (matches our Hetionet positive count). | Draft says only that Hetionet is kept as a reference; no Hetionet results are reported. |
| 3 | Vasilevsky *et al.*, Mondo, medRxiv 2022 | Crossref: preprint (posted-content), 86 authors, DOI 10.1101/2022.04.13.22273750. No peer-reviewed version found in Crossref. | MONDO integrates terminologies and carries cross-references | **Yes (general).** Abstract: open ontology integrating medical terminologies, records the sources of all data. | **Preprint, not peer reviewed**; cited as such. The rule "use only xrefs qualified `MONDO:equivalentTo`" is our design choice applied to the `.obo` file, not a claim of the paper. Check for a published version before submission. |
| 4 | Ochoa *et al.*, *Nucleic Acids Res.* 51(D1):D1353–D1359, 2023 | Crossref: exact title, vol. 51, issue D1, pages, DOI (online 2022, issue 2023) | "Open Targets Platform" as the source of clinical reports | **Partly.** Supports the platform itself. | The 2023 paper predates the clinical-report / stage dataset used here, so it is **not** cited for the stage vocabulary; that comes from [5]. The draft says so explicitly. |
| 5 | Open Targets, "Clinical report," platform docs, accessed 2026-11-10 | Page fetched and read (HTTP 200) | Stage categories and their descriptions; no official ranking | **Yes.** Lists categories with descriptions, states no ordering. | The page states no data licence and gives no enum spellings; both are flagged as open items. Web pages can change, so the access date is recorded. |
| 6 | Breiman, *Mach. Learn.* 45(1):5–32, 2001 | Crossref: exact | Random Forest | method attribution | — |
| 7 | Chen and Guestrin, KDD 2016, pp. 785–794 | Crossref: exact | XGBoost | method attribution | — |
| 8 | Rogers and Hahn, *J. Chem. Inf. Model.* 50(5):742–754, 2010 | Crossref: exact (no abstract available) | Morgan / extended-connectivity fingerprint | method attribution (ECFP is the standard reference for Morgan fingerprints) | The RDKit implementation itself is not cited; add if the venue requires software citations. |
| 9 | Grover and Leskovec, node2vec, KDD 2016, pp. 855–864 | Crossref: exact | Node2Vec | method attribution | Our leakage-safe use is ours (walk graph = message-passing graph + train positives only). |
| 10 | Kipf and Welling, ICLR 2017, arXiv:1609.02907 | arXiv API: title, authors, "Published as a conference paper at ICLR 2017" | GCN | method attribution | No DOI; arXiv id given. |
| 11 | Hamilton, Ying, Leskovec, NIPS 2017, arXiv:1706.02216 | arXiv API: title, authors, "Published in NIPS 2017" | GraphSAGE | method attribution | Page range omitted (not confirmed in this audit). |
| 12 | Veličković *et al.*, ICLR 2018, arXiv:1710.10903 | arXiv API: 6 authors confirmed, "To appear at ICLR 2018" | GAT | method attribution | — |
| 13 | Schlichtkrull *et al.*, ESWC 2018, LNCS, pp. 593–607 | Crossref: exact title, pages, DOI | RGCN | method attribution | Listed as "*et al.*" (6 authors; Crossref returned a truncated list). |
| 14 | Hu, Dong, Wang, Sun, WWW 2020, pp. 2704–2710 | Crossref: exact | HGT | method attribution | — |

## Corrections made by this audit
* The draft previously had **no in-text citations** (a bibliography only). Citations were added at the specific claims above.
* Reference list renumbered by first citation (IEEE requirement); added [5], [6], [7], [8] (documentation page, RF, XGBoost, ECFP) because the draft names those methods and sources.
* [3] relabelled as a preprint; [4] no longer implied to describe the stage vocabulary.
* The earlier draft listed the Mondo paper without a venue; Crossref shows only a medRxiv preprint, so it is now labelled as one.

## Still open before submission
1. Full-text confirmation of the claims for [1]–[4] (abstract-level only so far).
2. Licence terms of upstream Open Targets clinical sources and of PrimeKG's upstream data (e.g. DrugBank terms) — not covered by any citation.
3. Check whether the WHO NTD group list used here matches the current official list (the draft cites no WHO source because our 22 groups were curated by us).
4. Re-run `python scripts/check_paper.py` after any edit.
