# Canonical Data Model Specification

This document serves as the authoritative single source of truth for the **canonical pharmacovigilance data model** in `raxtik-etl`.

All source adapters (including `raxtik-source-faers`) map raw, era-specific files into this unified schema.

---

## 1. Architectural Overview

`raxtik-etl` implements an analytical **star-schema architecture** optimized for high-performance querying in DuckDB and columnar storage in Apache Parquet.

```text
                             ┌───────────────────────┐
                             │       cases (view)    │
                             │ (Authoritative Latest)│
                             └───────────┬───────────┘
                                         │ 1:1
                                         ▼
                               ┌───────────────────┐
                ┌─────────────►│    demo (fact)    │◄─────────────┐
                │              │ (Raw Submissions) │              │
                │              └─────────┬─────────┘              │
                │                        │                        │
       1:N      │               1:N      │               1:N      │
 ┌──────────────┴──────┐  ┌──────────────┴──────┐  ┌──────────────┴──────┐
 │     reac (fact)     │  │     drug (fact)     │  │     rpsr (fact)     │
 │  (Adverse Events)   │  │  (Exposures/Regimen)│  │   (Report Sources)  │
 └─────────────────────┘  └──────┬──────┬───────┘  └─────────────────────┘
                                 │      │
                        1:N      │      │      1:N
                  ┌──────────────┴┐    ┌┴──────────────┐
                  │  indi (fact)  │    │  ther (fact)  │
                  │ (Indications) │    │  (Durations)  │
                  └───────────────┘    └───────────────┘
                                 ▲
                                 │ Relational Lookup Joins
               ┌─────────────────┴──────────────────┐
               │    16 Reference Dimension Tables   │
               │         (`_code_*` tables)         │
               └────────────────────────────────────┘
```

The data model consists of three primary components:
1. **7 Canonical Fact Tables**: Raw reported events, regimens, indications, outcomes, and demographics.
2. **Authoritative Case View (`cases`)**: Deduplicated view tracking the latest known report version.
3. **16 Embedded Reference Dimension Tables (`_code_*`)**: Normalized codelists conforming to FDA CDER and ICH E2B(R2)/(R3) standards.

---

## 2. Core Fact Tables

Every source connector projects extracted submission records into 7 canonical fact tables:

| Table | Entity / Domain | Primary Key | Foreign Key | Description |
| :--- | :--- | :--- | :--- | :--- |
| **`demo`** | Case Submissions & Demographics | `primary_id`, `case_id` | *(Root fact table)* | Demographic data, reporting source details, manufacturer submission tracking, and receipt dates. |
| **`drug`** | Drug Exposures & Regimens | `primary_id`, `drug_seq` | `primary_id` -> `demo.primary_id` | Reported medicinal products, active ingredients, dosage forms, routes of administration, and suspect roles. |
| **`reac`** | Adverse Reactions | `primary_id`, `pt` | `primary_id` -> `demo.primary_id` | Adverse event terms coded using MedDRA Preferred Terms (`pt`). |
| **`outc`** | Clinical Outcomes | `primary_id`, `outc_code` | `primary_id` -> `demo.primary_id` | Seriousness criteria indicating severe clinical consequences (death, hospitalization, disability, etc.). |
| **`indi`** | Therapy Indications | `primary_id`, `indi_drug_seq`, `indi_pt` | `primary_id`, `indi_drug_seq` -> `drug.drug_seq` | Reported medical conditions and clinical indications for which each drug was prescribed. |
| **`ther`** | Therapy Timelines | `primary_id`, `dsg_drug_seq` | `primary_id`, `dsg_drug_seq` -> `drug.drug_seq` | Start dates, end dates, and duration durations for drug administration. |
| **`rpsr`** | Report Sources | `primary_id`, `rpsr_code` | `primary_id` -> `demo.primary_id` | Original source categories contributing to the safety report submission. |

---

## 3. Authoritative Case View (`cases`)

In pharmacovigilance surveillance, multiple versions (`CASEVERSION` or follow-up submissions) may be submitted over months or years for a single patient incident (`CASEID`).

The `cases` view provides an **authoritative, deduplicated cross-sectional representation**:
- Deduplicates on `case_id` by selecting the most current authoritative report record based on version numbers and report dates (`canonical_case_version`, `fda_date`).
- Pre-computes standardized analytical flags:
  - `has_serious_outcome`: Evaluates outcomes across `outc` for any serious criterion (`DE`, `LT`, `HO`, `DS`, `CA`, `RI`, `OT`).
  - `is_death`: Identifies cases resulting in patient death (`DE`).
  - `is_expedited`: Identifies 15-day expedited alert reports.
- Retains complete traceability to the underlying latest submission (`primary_id`).

---

## 4. Pre-Materialized Reference Dimensions (`_code_*`)

Packaged datasets compile 16 self-describing reference dimension tables directly within DuckDB databases and Parquet directories. This allows downstream analysts and BI applications to perform instant star-schema joins without maintaining external mapping services:

| Dimension Table | Foreign Key Field in Fact Table | Key Columns | Description & Standard |
| :--- | :--- | :--- | :--- |
| `_code_countries` | `reporter_country_code`, `occr_country_code` | `code`, `name` | 240+ sovereign nations and territories per **ISO 3166-1 alpha-2**. |
| `_code_report_types` | `report_type_code` | `code`, `label`, `is_expedited`, `is_combination_product` | Direct, 15-day expedited, periodic, 5-day and 30-day combination product reports (21 CFR Part 4). |
| `_code_roles` | `role_code` | `code`, `label`, `description` | Drug suspect roles: Primary Suspect (`PS`), Secondary Suspect (`SS`), Concomitant (`C`), Interacting (`I`). |
| `_code_outcomes` | `outc_code` | `code`, `label`, `is_death`, `is_serious` | Patient outcome criteria (`DE`, `HO`, `LT`, `DS`, `CA`, `RI`, `OT`). |
| `_code_outcome_semantics` | `outc_code` | `code`, `label`, `severity_tier`, `is_death` | Clinical severity tiers and ICH classifications. |
| `_code_sources` | `rpsr_code` | `code`, `label`, `description` | Report source categories: Health Professional, Consumer, Study, Literature, Foreign, User Facility. |
| `_code_occupations` | `reporter_occupation_code` | `code`, `label`, `category` | Reporter qualification: Physician, Pharmacist, Other Health Professional, Lawyer, Consumer. |
| `_code_sex` | `reported_sex_code` | `code`, `label` | Biological sex standards: Male (`M`), Female (`F`), Unknown (`UNK`). |
| `_code_age_units` | `reported_age_unit_code` | `code`, `label`, `to_years_factor` | Unit normalization multipliers converting age values to decimal years. |
| `_code_age_groups` | `age_group_code` | `code`, `label`, `age_range_text` | ICH pediatric and adult life-stage categories (Neonate, Infant, Child, Adolescent, Adult, Elderly). |
| `_code_weight_units` | `reported_weight_unit_code` | `code`, `label`, `to_kg_factor` | Unit normalization multipliers converting patient weight to kilograms. |
| `_code_dechallenge` | `dechal_code`, `rechal_code` | `code`, `label`, `clinical_implication` | Positive (`Y`), Negative (`N`), Unknown (`U`), or Not Applicable (`D`) response categories. |
| `_code_drug_name_sources` | `reported_validation_code` | `code`, `label`, `is_validated` | FDA dictionary validation: Validated trade name (`1`) vs. verbatim text (`2`). |
| `_code_dose_frequencies` | `dose_frequency_code` | `code`, `label`, `daily_frequency_factor` | Standardized administration frequencies (`QD`, `BID`, `TID`, `QID`, `PRN`, `Q4H`–`Q24H`, `BIW`, `QW`, etc.). |
| `_code_cumulative_dose_units`| `cumulative_dose_unit_code` | `code`, `label`, `category` | ICH ICSR E2B(R2)/(R3) numeric codes `001`–`032` and metric units (`kg`, `g`, `mg`, `µg`, `mL`, etc.). |
| `_code_duration_units` | `reported_duration_code` | `code`, `label`, `to_days_factor` | Time unit multipliers converting therapy durations into fractional days. |

---

## 5. Canonical Standardization Principles

### A. Zero Redundancy & Single Canonical Name
The schema enforces a strict single-source-of-truth naming standard. Duplicate columns historically created from divergent raw CSV column headers are consolidated:
- Raw `rept_cod` maps strictly to `report_type_code` (legacy alias `report_code` eliminated).
- Raw `mfr_num` maps strictly to `manufacturer_control_number` (legacy alias `manufacturer_num` eliminated).
- Raw `mfr_sndr` maps strictly to `manufacturer_name` (legacy alias `manufacturer_sender` eliminated).
- Raw `age_grp` maps strictly to `age_group_code` (legacy alias `reported_age_group_code` eliminated).

### B. Transparent Lineage Provenance
Every column in the schema defines its precise origin and lifecycle classification via `TransformationCategory`:
- `TransformationCategory.A_RAW_UNCHANGED`: Preserves raw reported data unmodified.
- `TransformationCategory.B_RENAMED_ALIAS`: Pure rename for canonical standard compliance.
- `TransformationCategory.C_ADDED_LATER`: Attributes introduced in later regulatory revisions (e.g., modern E2B enhancements).
- `TransformationCategory.D_NORMALIZED`: Mathematically converted values (e.g., `standard_age_years`, `standard_weight_kg`).
- `TransformationCategory.E_DERIVED`: Analytical aggregations and business logic (e.g., `has_serious_outcome`).

### C. Standard Human-Readable Labels
To accelerate data discovery and avoid redundant SQL joins for basic queries, every coded field is paired with an inline human-readable label (`*_label`) on the fact tables:
- `report_type_label`
- `reported_age_unit_label`
- `age_group_label`
- `standard_sex_label`
- `reported_weight_unit_label`
- `reporter_occupation_label`
- `standard_role_label`
- `reported_validation_label`
- `dose_frequency_label`
- `cumulative_dose_unit_label`
- `standard_outc_label`
- `reported_duration_label`
- `standard_rpsr_label`
