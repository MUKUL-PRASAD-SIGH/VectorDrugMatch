# Download manifest (HAI price surveys, Open Targets, IHME GBD)

Provenance record for the raw files in `data/external/downloads/`. The raw files are git-ignored and never committed; this manifest is the tracked copy (copied from `data/external/downloads/MANIFEST.md`).

Moved from repo root on 2026-11-10; filenames unchanged; SHA-1 verified after move.

| file | source / survey | content | sha1 (8) |
|---|---|---|---|
| hai_price_surveys/maharashtra_2005-01/affordability_excel (1).xls | Maharashtra 4 regions, Jan 2005 (ref prices MSH2003) | affordability | da88c97f |
| hai_price_surveys/karnataka_2004-11/affordability_excel (2).xls | Karnataka, Nov 2004 (ref prices MSH2003) | affordability | 497a1584 |
| hai_price_surveys/delhi_2011-07/affordability_excel.xls | NCT Delhi, Jul 2011 (ref prices MSH2010) | affordability | b426fdd9 |
| hai_price_surveys/maharashtra_2005-01/median_price_by_medicine_excel (1).xls | Maharashtra 4 regions, Jan 2005 (ref prices MSH2003) | median_price | 16fa2aba |
| hai_price_surveys/karnataka_2004-11/median_price_by_medicine_excel (2).xls | Karnataka, Nov 2004 (ref prices MSH2003) | median_price | 2ad26550 |
| hai_price_surveys/delhi_2011-07/median_price_by_medicine_excel.xls | NCT Delhi, Jul 2011 (ref prices MSH2010) | median_price | 9165a2f2 |
| hai_price_surveys/delhi_2011-07/price_availability_survey_detail_excel (1).php | NCT Delhi, Jul 2011 (ref prices MSH2010) | price_availability_detail: Public sector patient | f575664d |
| hai_price_surveys/delhi_2011-07/price_availability_survey_detail_excel (2).php | NCT Delhi, Jul 2011 (ref prices MSH2010) | price_availability_detail: Private sector patient | ebc5cce7 |
| hai_price_surveys/maharashtra_2005-01/price_availability_survey_detail_excel (3).php | Maharashtra 4 regions, Jan 2005 (ref prices MSH2003) | price_availability_detail: Public sector procurement | 0d6314d1 |
| hai_price_surveys/maharashtra_2005-01/price_availability_survey_detail_excel (4).php | Maharashtra 4 regions, Jan 2005 (ref prices MSH2003) | price_availability_detail: Public sector patient | e85c88d3 |
| hai_price_surveys/maharashtra_2005-01/price_availability_survey_detail_excel (5).php | Maharashtra 4 regions, Jan 2005 (ref prices MSH2003) | price_availability_detail: Private sector patient | 46976940 |
| hai_price_surveys/karnataka_2004-11/price_availability_survey_detail_excel (6).php | Karnataka, Nov 2004 (ref prices MSH2003) | price_availability_detail: Public sector procurement | 457d80cd |
| hai_price_surveys/karnataka_2004-11/price_availability_survey_detail_excel (7).php | Karnataka, Nov 2004 (ref prices MSH2003) | price_availability_detail: Public sector patient | 0580687d |
| hai_price_surveys/karnataka_2004-11/price_availability_survey_detail_excel (8).php | Karnataka, Nov 2004 (ref prices MSH2003) | price_availability_detail: Private sector patient | d50d723c |
| hai_price_surveys/delhi_2011-07/price_availability_survey_detail_excel.php | NCT Delhi, Jul 2011 (ref prices MSH2010) | price_availability_detail: Public sector procurement | 4d05fe1a |
| open_targets/00000000.parquet | Open Targets | clinical reports (drugId,diseaseId,maxClinicalStage) | 6fefb231 |
| open_targets/00000000 (1).parquet | Open Targets | drug molecules | df76b1fb |
| open_targets/00000000 (2).parquet | Open Targets | mechanisms of action | c58a63b1 |
| ihme_gbd/IHME-GBD_2023_DATA-9feb184e-1.zip | IHME GBD 2023 | UNUSABLE stub: All-causes Deaths only; re-export DALYs | 70aea470 |

Notes: HAI surveys are regional, historical pilots (not a global Access score); Delhi uses MSH2010 reference prices, Karnataka/Maharashtra MSH2003, so MPRs are not directly comparable across surveys. Open Targets is not integrated into the benchmark yet.