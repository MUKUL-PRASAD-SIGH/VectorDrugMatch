# WHO EML extraction: corrections and validation status

Source: `data/external/B09474-eng.pdf` (WHO Model List of Essential Medicines, 24th list, 2025; CC BY-NC-SA 3.0 IGO; not redistributed).

## Validation status (stated precisely)
* Automated checks only: `tests/test_who_eml_extraction.py` (structure: 30 sections, core/complementary, entry types, a set of expected NTD medicines) and the mapping audit.
* **Not manually validated entry by entry.** Individual entries were compared with the PDF only as spot checks (a few names while fixing defects). Do not describe the extraction as manually verified.

## Correction 2026-11-11: co-packaged products
The PDF joins co-packaged products with an en dash (U+2013). `clean_name` stripped non-ASCII glyphs, so the dash vanished and the entries were read as single ingredients (or, for the antimalarials, with a wrong component split). Evidence from the PDF text layer (page = PDF page):

| PDF page | PDF text | Before | After |
|---|---|---|---|
| 60 | `mifepristone – misoprostol` followed by `mifepristone 200 mg tablet [1] and misoprostol 200 micrograms ...` | single "mifepristone misoprostol" | combination `mifepristone + misoprostol` |
| 53 | `oral rehydration salts – zinc sulfate [c]` | single | combination `oral rehydration salts + zinc sulfate` |
| 29 | `artesunate – sulfadoxine + pyrimethamine` | combination, component "artesunate sulfadoxine" | combination of 3 components |
| 30 | `amodiaquine – sulfadoxine + pyrimethamine [c]` | same defect | combination of 3 components |

These four rows carry `extraction_note` in `who_eml.csv`. The fix is in `scripts/extract_who_eml_pdf.py` (`COPACK`); a search of all entry spans on pages 6-67 found no other letter-dash-letter pattern.

## Correction 2026-11-11 (b): superscript footnote marks glued to names
The PDF has 5.5 pt superscript marks `th` at x=52 next to three entries (PDF page 55 near `octreotide`; page 59 near `levonorgestrel-releasing intrauterine system` and near `efavirenz + emtricitabine + tenofovir`). The prefix-fragment rule (meant for 9 pt fragments such as `lo` + `sartan`) joined them, giving `thoctreotide`, `thlevonorgestrel-releasing intrauterine system` and `thefavirenz + emtricitabine + tenofovir`. The rule now ignores 5.0-6.5 pt marks and accepts fragments only at 8-9.5 pt. After the fix octreotide maps to PrimeKG; `losartan` is still joined correctly. Regression tests: `test_superscript_footnote_marks_do_not_enter_names`, `test_copackaged_entries_are_combinations`.

## Effect on counts (current, deterministic: three consecutive extractions give identical SHA-256)
646 entries: **590 single + 56 combination** (was 592 + 54). Of the 590 single entries, **497 mapped, 93 unmapped**, 378 distinct PrimeKG drugs flagged (297 of them have an indication pair in the benchmark). Combinations never count as a single drug's EML status. An interim run of the mapping before these two corrections had reported 497 mapped / 95 unmapped; the difference of two unmapped entries is exactly the two co-packs that moved to combinations.

## Unmapped entries
All 93 unmapped single entries stay in `data/processed/eml/eml_unmatched.csv` with a `reason` column (vaccine, biologic, blood product, device, ambiguous, not in PrimeKG, ...). Every reason documents a decision; it is not a mapping. None carries the generic reason "no match under any tier" in this build.
