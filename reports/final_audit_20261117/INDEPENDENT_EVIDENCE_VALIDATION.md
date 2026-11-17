# Independent evidence review of top-ranked candidates

**Purpose:** computational research prioritisation. Nothing here is a clinical recommendation, efficacy claim, or dosing advice.

## Candidate selection (fixed rule, applied after the holdout evaluation)
Drugs: the 361 locked-holdout drugs (never used in training or selection). For each drug all 17,080 diseases were scored by the deployed bundle
`vdm-1.0.0`; pairs with **any** PrimeKG drug-disease relation (indication, contraindication, off-label) were removed; the top 3 per drug formed a pool
of 1,083 candidates; the 20 highest-scoring, **one per drug**, were reviewed (`analysis/evidence_review_candidates.csv`, with graph-evidence
explanations). None of the 20 is in PrimeKG under any drug-disease relation.

## Method
PubMed via NCBI E-utilities (esearch, relevance sort, top 3 + total count; esummary), retrieved 2026-11-18; the query is the drug name AND the disease
term(s) in title/abstract (`evidence/pubmed_retrieval.json` holds every query, count, PMID, title and date as returned). Only retrieved records are
cited. Classification also uses general pharmacological knowledge where stated; **such statements are marked (K) and need expert verification**.
Independence caveat: PrimeKG's drug-disease labels come from curated drug-label resources; an "established" use that PrimeKG lacks shows **label
incompleteness**, not a discovery.

## Results
| # | Drug → disease (PrimeKG IDs in CSV) | ranking_score | PubMed hits | Retrieved evidence (PMID, year) | Class |
|---|---|---|---|---|---|
| 1 | Prednisone → lupus erythematosus | 0.9999 | 2,171 | EULAR 2019 SLE recommendations (30926722, 2019); controlled trial in lupus nephritis (3511372, 1986); "Corticosteroids in Lupus" (26611550, 2016) | 2 Established |
| 2 | Cefotaxime → staphylococcal infection | 0.9970 | 68 | treatment of severe staphylococcal infections with cefotaxime + fosfomycin (6094452, 1984); cefotaxime in staphylococcal infections (7587040, 1995) | 1 Independently supported (older clinical literature; resistance (K)) |
| 3 | Levocetirizine → atopic conjunctivitis | 0.9954 | 8 | drug reviews for allergic rhinitis and allergic conjunctivitis (33848281, 2021; 40152721, 2025) | 2 Established (antihistamine use; disease term mapped to allergic conjunctivitis) |
| 4 | Triamcinolone → iridocyclitis | 0.9953 | 406 | top hits are reviews of drug-induced uveitis (24100371, 2013; 15803424, 2005) and macular edema (15325193, 2004) | 3 Plausible, weakly supported by retrieved records (corticosteroids for uveitis (K)); one retrieved theme is drug-induced uveitis → expert review |
| 5 | Ceftriaxone → staphylococcal infection | 0.9922 | 106 | endocarditis review (31669426, 2020); staphylococcal mastitis (veterinary, 33568029, 2021) | 3 Plausible, weakly supported (not first-line for staphylococci (K)) |
| 6 | Hydrocortisone → spondyloarthropathy | 0.9920 | 0 | - | 5 Insufficient evidence |
| 7 | Flunisolide → atopic dermatitis | 0.9916 | 1 | asthma/atopic dermatitis biomarker study, not a treatment report (18926054, 2008) | 5 Insufficient (inhaled/nasal formulation vs skin disease (K)) |
| 8 | Prochlorperazine → anxiety disorder | 0.9883 | 25 | "Prochlorperazine in anxiety" (21927108, 1985); akathisia report (38784181, 2024) | 1 Independently supported (historical); **safety: extrapyramidal effects** |
| 9 | Cyproheptadine → neurotic disorder | 0.9881 | 42 | top hits concern cyclic vomiting syndrome (40868416, 2025; 30076469, 2018) | 5 Insufficient |
| 10 | Triazolam → anxiety | 0.9877 | 92 | triazolam and dental anxiety (8031376, 1994); benzodiazepine review (31643621) | 3 Plausible (procedural anxiety); dependence risk (K) |
| 11 | Benzphetamine → anxiety disorder | 0.9854 | 1 | controlled-substance risk review only (30726003) | 4 **Contradicted / safety-concerning**: sympathomimetic anorectic; anxiety is an expected adverse effect (K) |
| 12 | Chlorprothixene → anxiety disorder | 0.9847 | 13 | management of anxiety in tuberculous patients (13900877, 1962); ambulatory psychiatry (14013234, 1962) | 1 Independently supported (old, low-quality evidence) |
| 13 | Aripiprazole lauroxil → bipolar disorder | 0.9835 | 8 | long-acting injectable antipsychotic reviews (37345508, 2023; 38299536, 2024) | 3 Plausible (other aripiprazole formulations used in bipolar disorder (K)) |
| 14 | Flumethasone → ankylosing spondylitis | 0.9811 | 0 | - | 5 Insufficient (topical corticosteroid (K)) |
| 15 | Ciclesonide → atopic eczema | 0.9810 | 0 | - | 5 Insufficient (inhaled corticosteroid (K)) |
| 16 | Amcinonide → asthma | 0.9800 | 2 | corticosteroid hypersensitivity reports (10894975, 2000; 14641354, 2003) | 5 Insufficient (topical corticosteroid; retrieved records are about allergy) |
| 17 | Ampicillin → streptococcal infection | 0.9799 | 328 | ampicillin dosing for group B streptococcal disease in neonates (33091945, 2022); penicillin reviews | 2 Established |
| 18 | Trazodone → manic bipolar affective disorder | 0.9797 | 59 | antidepressant network meta-analysis for depression (29477251, 2018); no mania treatment evidence retrieved | 4 **Safety-concerning**: antidepressants can precipitate mania (K) |
| 19 | Flurandrenolide → asthma | 0.9796 | 0 | - | 5 Insufficient (topical corticosteroid (K)) |
| 20 | Salbutamol → pulmonary emphysema | 0.9794 | 595 | "Drugs for COPD" (32960872, 2020) | 2 Established (bronchodilator in COPD) |

## Summary
| Class | n | Candidates |
|---|---|---|
| 1 Independently supported | 3 | cefotaxime-staphylococcal, prochlorperazine-anxiety, chlorprothixene-anxiety |
| 2 Previously established (missing from PrimeKG labels) | 4 | prednisone-lupus, levocetirizine-allergic conjunctivitis, ampicillin-streptococcal, salbutamol-emphysema/COPD |
| 3 Plausible, weakly supported | 4 | triamcinolone-iridocyclitis, ceftriaxone-staphylococcal, triazolam-anxiety, aripiprazole lauroxil-bipolar |
| 4 Contradicted / safety-concerning | 2 | benzphetamine-anxiety, trazodone-mania |
| 5 Insufficient evidence | 7 | hydrocortisone, flunisolide, cyproheptadine, flumethasone, ciclesonide, amcinonide, flurandrenolide pairs |

Interpretation
* 7/20 have supporting or established evidence and 4/20 are plausible; most of the supported ones are **known uses missing from PrimeKG**, so they
  reflect label incompleteness (and a pessimistic bias in the sampled-negative metrics), not novel discoveries.
* A clear **failure mode**: drug-class generalisation that ignores formulation and route. 8 of 20 top candidates are corticosteroids, and topical or
  inhaled products are proposed for systemic or unrelated-organ diseases (flumethasone, flurandrenolide, amcinonide, ciclesonide, flunisolide).
  PrimeKG drug nodes are active ingredients without route information; the model cannot see the difference.
* 2/20 are safety-concerning (a stimulant for anxiety, an antidepressant for mania). The API excludes PrimeKG contraindications by default, but
  these pairs are not recorded as contraindications, so **expert review is mandatory** for any output.
* Absence of PubMed hits is not evidence that an association is false. This review covers 20 candidates; it is not a systematic review.
