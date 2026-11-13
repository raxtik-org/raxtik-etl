# FAERS/AEMS Coded Values & Code-List History Reference

> **Status**: 🟡 **Phase 0 Substantially Complete — Evidence Lock Pending**
> *Note*: Code lists documented below reflect FDA CDER / ICH guidelines. The platform preserves the raw reported code and attaches the applicable canonical label based on verified schema signatures.

---

## 1. Drug Role Codes (`ROLE_COD` / `role_code`)

| Reported Code | Canonical Label | Definition / Clinical Meaning |
| :--- | :--- | :--- |
| `PS` | `Primary Suspect` | The primary suspect drug identified by reporter as causing adverse event |
| `SS` | `Secondary Suspect` | Secondary suspect drug also suspected of contributing |
| `C` | `Concomitant` | Concomitant drug taken concurrently by patient |
| `I` | `Interacting` | Drug suspected of causing a drug-drug interaction |

*Legacy Note: In early AERS data (pre-2012), numerical codes were occasionally observed in raw submissions: `1`=PS, `2`=SS, `3`=C, `4`=I. The source adapter preserves the raw reported code and resolves the canonical code/label.*

---

## 2. Patient Outcome / Seriousness Codes (`OUTC_COD` / `outcome_code`)

| Reported Code | Canonical Label | ICH E2B Seriousness Category |
| :--- | :--- | :--- |
| `DE` | `Death` | Results in death |
| `LT` | `Life-Threatening` | Life-threatening adverse event |
| `HO` | `Hospitalization` | Initial or prolonged inpatient hospitalization |
| `DS` | `Disability` | Disability or significant/permanent incapacity |
| `CA` | `Congenital Anomaly` | Congenital anomaly or birth defect |
| `RI` | `Required Intervention` | Required intervention to prevent permanent harm |
| `OT` | `Other Serious` | Other medically important serious condition |

---

## 3. Patient Sex (`SEX` / `GNDR_COD` / `reported_sex_code`)

| Reported Code | Canonical Label | Notes |
| :--- | :--- | :--- |
| `M` | `Male` | |
| `F` | `Female` | |
| `UNK` | `Unknown` | Gender not specified or unknown |
| `NS` | `Not Specified` | Observed in certain legacy records |

---

## 4. Age Units (`AGE_COD` / `reported_age_code`) & Normalization Multipliers

| Reported Code | Unit | Conversion to `standard_age_years` |
| :--- | :--- | :--- |
| `YR` | Years | `age * 1.0` |
| `DEC`| Decades | `age * 10.0` |
| `MON`| Months | `age / 12.0` |
| `WK` | Weeks | `age / 52.1429` |
| `DY` | Days | `age / 365.25` |
| `HR` | Hours | `age / 8766.0` |

---

## 5. Weight Units (`WT_COD` / `reported_weight_code`) & Normalization Multipliers

| Reported Code | Unit | Conversion to `standard_weight_kg` |
| :--- | :--- | :--- |
| `KG` | Kilograms | `wt * 1.0` |
| `LBS`| Pounds | `wt * 0.45359237` |
| `GMS`| Grams | `wt / 1000.0` |

---

## 6. Reporter Occupation (`OCCP_COD` / `reporter_occupation_code`)

| Reported Code | Canonical Label | Category |
| :--- | :--- | :--- |
| `MD` | `Physician` | Healthcare Professional |
| `PH` | `Pharmacist` | Healthcare Professional |
| `OT` | `Other Health Professional` | Healthcare Professional (Nurse, Dentist, etc.) |
| `LW` | `Lawyer` | Legal Representative |
| `CN` | `Consumer` | Patient, Family Member, or Consumer |

---

## 7. Report Sources (`RPSR_COD` / `report_source_code`)

| Reported Code | Canonical Label | Description |
| :--- | :--- | :--- |
| `FGN` | `Foreign` | Foreign regulatory agency / international report |
| `SDY` | `Study` | Clinical trial or post-marketing surveillance study |
| `LIT` | `Literature` | Published scientific journal or literature |
| `HP` | `Health Professional` | Voluntary report from physician or pharmacist |
| `CSM` | `Consumer` | Voluntary report from consumer or patient |
| `CR` | `Company Representative` | Report submitted via company field rep |
| `UF` | `User Facility` | User facility (hospital, clinic, nursing home) |

---

## 8. Dechallenge / Rechallenge Codes (`DECHAL` / `RECHAL`)

| Reported Code | Canonical Label | Description |
| :--- | :--- | :--- |
| `Y` | `Positive` | Event abated when drug discontinued (or recurred on rechallenge) |
| `N` | `Negative` | Event did not abate when drug discontinued (or did not recur) |
| `U` | `Unknown` | Unknown / Unreported |
| `D` | `Does Not Apply` | Dose was not changed or drug was continued |

---

## 9. Report Types (`REPT_COD` / `report_type_code`)

| Reported Code | Canonical Label | Regulatory Category / Meaning |
| :--- | :--- | :--- |
| `DIR` | `Direct` | Voluntary report submitted directly to FDA (MedWatch 3500) |
| `EXP` / `15D` / `15-DAY` | `Expedited (15-Day)` | Expedited 15-day alert report for serious, unexpected events |
| `PER` / `PERIODIC` | `Periodic` | Periodic adverse experience report (PSUR / PBRER submission) |
| `5D` / `5DAY` | `5-Day Combination Product Report` | Combination product postmarketing safety report (21 CFR Part 4) |
| `30D` / `30DAY` | `30-Day Combination Product Report` | Malfunction / defect combination product report (21 CFR Part 4) |
| `SE` | `Special Evaluation` | Special evaluation report (observed in transition era archives) |
| `OTHER` | `Other` | Other unclassified submission category |
| `UNK` | `Unknown` | Report type not specified |

---

## 10. Drug Name Source / Validation (`VAL_VBM` / `reported_validation_code`)

| Reported Code | Canonical Label | FDA Meaning |
| :--- | :--- | :--- |
| `1` | `Validated trade name used` | Drug name successfully validated against official FDA product dictionary |
| `2` | `Verbatim name used` | Verbatim text entered by reporter; not matched to dictionary |

---

## 11. Patient Age Groups (`AGE_GRP` / `age_group_code`)

| Reported Code | Canonical Label | ICH Pediatric & Adult Classification |
| :--- | :--- | :--- |
| `N` | `Neonate` | Gestational age to 28 days of life |
| `I` | `Infant` | 29 days to < 2 years |
| `C` | `Child` | 2 years to < 12 years |
| `T` | `Adolescent` | 12 years to < 18 years |
| `A` | `Adult` | 18 years to < 65 years |
| `E` | `Elderly` | 65+ years |

---

## 12. Dose Frequency (`DOSE_FREQ` / `dose_frequency_code`)

| Reported Code | Canonical Label | Administration Schedule |
| :--- | :--- | :--- |
| `1/DAY` / `QD` | `Once daily` | Every 24 hours / once a day |
| `2/DAY` / `BID` | `Twice daily` | Twice a day |
| `3/DAY` / `TID` | `Three times daily` | Three times a day |
| `4/DAY` / `QID` | `Four times daily` | Four times a day |
| `5/DAY` | `Five times daily` | Five times a day |
| `6/DAY` | `Six times daily` | Six times a day |
| `PRN` | `As needed` | Pro re nata (as required) |
| `STAT` | `Immediately` | Single immediate administration |
| `Q4H` | `Every 4 hours` | Q4H schedule |
| `Q6H` | `Every 6 hours` | Q6H schedule |
| `Q8H` | `Every 8 hours` | Q8H schedule |
| `Q12H` | `Every 12 hours` | Q12H schedule |
| `Q24H` | `Every 24 hours` | Q24H schedule |
| `BIW` | `Twice weekly` | Two times per week |
| `TIW` | `Three times weekly`| Three times per week |
| `QW` | `Every week` | Once a week |
| `QM` | `Every month` | Once a month |
| `QOD` | `Every other day` | Alternate-day administration |
| `TOTAL` | `Total dose` | Cumulative / single total dose |

---

## 13. Cumulative Dose Units (`CUM_DOS_UNIT` / `cumulative_dose_unit_code`)

The platform supports both literal unit abbreviations and official **ICH ICSR E2B(R2/R3) M2** numeric unit codes:

| Reported Code | Canonical Label | Type |
| :--- | :--- | :--- |
| `001` / `KG` | `kg` | Mass (Kilograms) |
| `002` / `G` | `g` | Mass (Grams) |
| `003` / `MG` | `mg` | Mass (Milligrams) |
| `004` / `UG` / `MCG` | `µg` | Mass (Micrograms) |
| `005` / `NG` | `ng` | Mass (Nanograms) |
| `006` / `PG` | `pg` | Mass (Picograms) |
| `007` / `MG/KG` | `mg/kg` | Normalized Mass per Body Weight |
| `008` / `UG/KG` | `µg/kg` | Normalized Mass per Body Weight |
| `009` / `MG/M2` | `mg/m²` | Normalized Mass per Body Surface Area |
| `010` / `UG/M2` | `µg/m²` | Normalized Mass per Body Surface Area |
| `011` / `L` | `L` | Volume (Liters) |
| `012` / `ML` | `mL` | Volume (Milliliters) |
| `013` / `UL` | `µL` | Volume (Microliters) |
| `014` / `BQ` | `Bq` | Radioactivity (Becquerel) |
| `015` / `GBQ` | `GBq` | Radioactivity (Gigabecquerel) |
| `016` / `MBQ` | `MBq` | Radioactivity (Megabecquerel) |
| `017` / `KBQ` | `kBq` | Radioactivity (Kilobecquerel) |
| `018` / `CI` | `Ci` | Radioactivity (Curie) |
| `019` / `MCI` | `mCi` | Radioactivity (Millicurie) |
| `020` / `UCI` | `µCi` | Radioactivity (Microcurie) |
| `021` / `NCI` | `nCi` | Radioactivity (Nanocurie) |
| `022` / `MOL` | `mol` | Substance Amount (Moles) |
| `023` / `MMOL` | `mmol` | Substance Amount (Millimoles) |
| `024` / `UMOL` | `µmol` | Substance Amount (Micromoles) |
| `025` / `IU` | `IU` | International Units |
| `026` / `KIU` | `kIU` | Kilo-International Units |
| `027` / `MIU` | `MIU` | Mega-International Units |
| `028` / `IU/KG` | `IU/kg` | International Units per kg |
| `029` / `MEQ` | `mEq` | Milliequivalents |
| `030` / `PERCENT` | `%` | Percentage |
| `031` / `GTT` | `gtt` | Drops |
| `032` / `DF` | `dosage form` | Dosage Forms (e.g. Tablets, Puffs) |

---

## 14. Therapy Duration Units (`DUR_COD` / `reported_duration_code`)

| Reported Code | Canonical Label | Duration Multiplier to Days |
| :--- | :--- | :--- |
| `YR` | `Years` | `duration * 365.25` |
| `DEC` | `Decades` | `duration * 3652.5` |
| `MON` | `Months` | `duration * 30.4375` |
| `WK` | `Weeks` | `duration * 7.0` |
| `DY` | `Days` | `duration * 1.0` |
| `HR` | `Hours` | `duration / 24.0` |
| `MIN` | `Minutes` | `duration / 1440.0` |
| `SEC` | `Seconds` | `duration / 86400.0` |

---

## 15. Country Dimensions (`REPORTER_COUNTRY` & `OCCR_COUNTRY`)

Reporter and occurrence countries follow the **ISO 3166-1 alpha-2** standard:
- Two-letter uppercase ISO country codes (e.g., `US`, `GB`, `FR`, `DE`, `JP`, `IN`, `CA`).
- Complete reference tables are mapped against 240+ sovereign nations and administrative jurisdictions per the ISO 3166-1 decoding catalog.

---

## 16. Star-Schema Dimension Tables Architecture (`_code_*`)

Every packaged dataset compiles 16 self-describing reference dimension tables directly inside DuckDB and Parquet artifacts. These enable instant relational joins, star-schema querying, and seamless integration with BI tools:

| Dimension Table | Source Code Field | Key Columns | Description |
| :--- | :--- | :--- | :--- |
| `_code_countries` | `reporter_country_code`, `occr_country_code` | `code`, `name` | 240+ ISO 3166-1 alpha-2 countries |
| `_code_report_types` | `report_type_code` | `code`, `label`, `is_expedited`, `is_combination_product` | 15-day, 5-day, 30-day, periodic, direct |
| `_code_roles` | `role_code` | `code`, `label`, `description` | Drug suspect roles (PS, SS, C, I) |
| `_code_outcomes` | `outc_code` | `code`, `label`, `is_death`, `is_serious` | Patient outcome criteria (DE, HO, LT, DS, etc.) |
| `_code_outcome_semantics` | `outc_code` | `code`, `label`, `severity_tier`, `is_death` | Clinical severity tiers and ICH classifications |
| `_code_sources` | `rpsr_code` | `code`, `label`, `description` | Report source categories (FGN, SDY, LIT, HP, CSM, etc.) |
| `_code_occupations` | `reporter_occupation_code` | `code`, `label`, `category` | Reporter profession (MD, PH, OT, LW, CN) |
| `_code_sex` | `reported_sex_code` | `code`, `label` | Biological sex standards (M, F, UNK) |
| `_code_age_units` | `reported_age_unit_code` | `code`, `label`, `to_years_factor` | Age duration normalization factors |
| `_code_age_groups` | `age_group_code` | `code`, `label`, `age_range_text` | ICH pediatric/adult age bands (N, I, C, T, A, E) |
| `_code_weight_units` | `reported_weight_unit_code` | `code`, `label`, `to_kg_factor` | Body weight normalization factors |
| `_code_dechallenge` | `dechal_code`, `rechal_code` | `code`, `label`, `clinical_implication` | Dechallenge / rechallenge response categories |
| `_code_drug_name_sources` | `reported_validation_code` | `code`, `label`, `is_validated` | FDA trade name vs. verbatim validation |
| `_code_dose_frequencies` | `dose_frequency_code` | `code`, `label`, `daily_frequency_factor` | Administration scheduling standards |
| `_code_cumulative_dose_units`| `cumulative_dose_unit_code` | `code`, `label`, `category` | ICH E2B(R2)/(R3) cumulative dosage metrics |
| `_code_duration_units` | `reported_duration_code` | `code`, `label`, `to_days_factor` | Therapy duration normalization factors |
