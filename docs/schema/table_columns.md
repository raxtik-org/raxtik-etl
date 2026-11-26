# Table Column Reference

Complete column-by-column data dictionary for the Raxtik Canonical Schema (`v1.0.0`) and the Silver Tier Deduplication Index.

---

## 1. Canonical Fact Tables (Bronze & Silver Views)

In **Bronze** packages, all 7 tables contain every submitted report for that quarter. In **Silver** mode (`tier="silver"`), `cases` resolves to the winning submission per `case_id` across all indexed quarters, and child tables (`drug`, `reac`, `outc`, `indi`, `ther`, `rpsr`) are automatically scoped to those winning `primary_id`s.

### Case Submissions & Demographics (`demo`)

**Columns:** 54

| Column | Type | Nullable | Key | Origin | Description |
| :--- | :--- | :---: | :--- | :--- | :--- |
| `primary_id` | `VARCHAR` | No | PK | `SOURCE_REPORTED` | Unique submission report identifier |
| `case_id` | `VARCHAR` | No | — | `SOURCE_REPORTED` | Stable case identifier across versions |
| `source_case_version` | `INTEGER` | Yes | — | `SOURCE_REPORTED` | Source-provided version number |
| `canonical_case_version` | `INTEGER` | No | — | `DERIVED` | Raxtik analytical case version ordinal |
| `case_version_source` | `VARCHAR` | No | — | `DERIVED` | Version determination methodology |
| `foll_seq` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Legacy follow-up sequence number |
| `initial_or_followup_code` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Report type flag (I=Initial, F=Followup) |
| `initial_or_followup_label` | `VARCHAR` | Yes | — | `DERIVED` | Human-readable label for report type |
| `event_date` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Date adverse event occurred (YYYYMMDD) |
| `standard_event_date` | `DATE` | Yes | — | `NORMALIZED` | Imputed/parsed date adverse event occurred |
| `event_date_precision` | `VARCHAR` | Yes | — | `DERIVED` | Event date precision audit classification (EXACT, YEAR_MONTH, YEAR_ONLY, INVALID) |
| `manufacturer_date` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Date manufacturer received report (YYYYMMDD) |
| `standard_manufacturer_date` | `DATE` | Yes | — | `NORMALIZED` | Imputed/parsed date manufacturer received report |
| `manufacturer_date_precision` | `VARCHAR` | Yes | — | `DERIVED` | Manufacturer date precision classification |
| `initial_regulatory_date` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Date initial report received by regulatory agency (YYYYMMDD) |
| `standard_initial_regulatory_date` | `DATE` | Yes | — | `NORMALIZED` | Imputed/parsed date initial report received by regulatory agency |
| `initial_regulatory_date_precision` | `VARCHAR` | Yes | — | `DERIVED` | Initial regulatory date precision classification |
| `latest_regulatory_date` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Date latest version received by regulatory agency (YYYYMMDD) |
| `standard_latest_regulatory_date` | `DATE` | Yes | — | `NORMALIZED` | Imputed/parsed date latest version received by regulatory agency |
| `latest_regulatory_date_precision` | `VARCHAR` | Yes | — | `DERIVED` | Latest regulatory date precision classification |
| `report_date` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Date report was sent by reporter (YYYYMMDD) |
| `standard_report_date` | `DATE` | Yes | — | `NORMALIZED` | Imputed/parsed date report was sent by reporter |
| `report_date_precision` | `VARCHAR` | Yes | — | `DERIVED` | Report date precision classification |
| `death_date` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Date patient died (YYYYMMDD) |
| `standard_death_date` | `DATE` | Yes | — | `NORMALIZED` | Imputed/parsed date patient died |
| `death_date_precision` | `VARCHAR` | Yes | — | `DERIVED` | Death date precision classification |
| `confidentiality_flag` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Voluntary reporter confidentiality request flag (Y/N) |
| `report_type_code` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Report type code (renamed from raw FDA rept_cod: DIR, EXP, PER, 5DAY, 30DAY) |
| `report_type_label` | `VARCHAR` | Yes | — | `DERIVED` | Human-readable label for report type |
| `expedited_flag` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | 15-day alert expedited flag (Y/N) |
| `electronic_submission_flag` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Electronic submission flag (Y/N) |
| `manufacturer_control_number` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Manufacturer internal control number (renamed from raw FDA mfr_num) |
| `manufacturer_name` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Manufacturer name (renamed from raw FDA mfr_sndr) |
| `auth_num` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Regulatory authorization number (Introduced 2014Q3) |
| `lit_ref` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Literature reference text (Introduced 2014Q3) |
| `to_mfr` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Distributor made report available to manufacturer flag (Y/N) |
| `sender_type_code` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Sender type code (PUB, IND, PHM) |
| `sender_type_label` | `VARCHAR` | Yes | — | `DERIVED` | Human-readable sender type label |
| `reported_age` | `DOUBLE` | Yes | — | `SOURCE_REPORTED` | Reported patient age value |
| `reported_age_code` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Reported unit of age (YR, MON, WK, DY, HR, DEC) |
| `reported_age_unit_label` | `VARCHAR` | Yes | — | `DERIVED` | Human-readable patient age measurement unit label |
| `age_group_code` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Patient age group code (from raw FDA age_grp: N=Neonate, I=Infant, C=Child, T=Adolescent, A=Adult, E=Elderly) |
| `age_group_label` | `VARCHAR` | Yes | — | `DERIVED` | Human-readable patient age group classification label |
| `reported_sex_code` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Reported sex code (M, F, UNK) |
| `reported_weight` | `DOUBLE` | Yes | — | `SOURCE_REPORTED` | Reported patient weight value |
| `reported_weight_code` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Unit of weight (KG, LBS, GMS) |
| `reported_weight_unit_label` | `VARCHAR` | Yes | — | `DERIVED` | Human-readable patient weight measurement unit label |
| `standard_age_years` | `DOUBLE` | Yes | — | `NORMALIZED` | Normalized patient age in decimal years (0.0 to 125.0) |
| `standard_sex_label` | `VARCHAR` | Yes | — | `NORMALIZED` | Standardized human-readable sex label (Male, Female, Unknown) |
| `standard_weight_kg` | `DOUBLE` | Yes | — | `NORMALIZED` | Normalized patient weight in kilograms |
| `reporter_occupation_code` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Reporter occupation code (MD, PH, OT, LW, CN) |
| `reporter_occupation_label` | `VARCHAR` | Yes | — | `DERIVED` | Human-readable reporter occupation label |
| `reporter_country` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Reporter ISO country code |
| `occurrence_country` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Event occurrence country code |

### Drug Products & Regimens (`drug`)

**Columns:** 33

| Column | Type | Nullable | Key | Origin | Description |
| :--- | :--- | :---: | :--- | :--- | :--- |
| `primary_id` | `VARCHAR` | No | PK, FK → `demo.primary_id` | `SOURCE_REPORTED` | Links to demo.primary_id |
| `case_id` | `VARCHAR` | No | FK → `demo.case_id` | `SOURCE_REPORTED` | Links to demo.case_id |
| `drug_seq` | `VARCHAR` | No | PK | `SOURCE_REPORTED` | Sequence number of drug in report |
| `reported_drug_name` | `VARCHAR` | No | — | `SOURCE_REPORTED` | Immutable reported verbatim drug name |
| `role_code` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Suspect role of drug (PS, SS, C, I) |
| `role_label` | `VARCHAR` | Yes | — | `DERIVED` | Human-readable suspect role classification label |
| `reported_active_ingredient` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Active ingredient text (Added 2014Q3) |
| `reported_validation_code` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Validation flag (1=validated trade name, 2=verbatim name) |
| `reported_validation_label` | `VARCHAR` | Yes | — | `DERIVED` | Human-readable drug name validation status label |
| `route` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Administration route |
| `reported_dose_verbatim` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Verbatim dosage text |
| `dose_amount` | `DOUBLE` | Yes | — | `SOURCE_REPORTED` | Numerical dose amount |
| `dose_unit` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Dose unit (MG, G, etc.) |
| `dose_form` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Physical form (TABLET, CAPSULE, etc.) |
| `dose_frequency` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Dosing frequency (QD, BID, etc.) |
| `dose_frequency_label` | `VARCHAR` | Yes | — | `DERIVED` | Human-readable dosing frequency label |
| `cumulative_dose_amount` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Cumulative dose taken before event |
| `cumulative_dose_unit` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Cumulative dose unit |
| `cumulative_dose_unit_label` | `VARCHAR` | Yes | — | `DERIVED` | Human-readable cumulative dose unit label |
| `dechallenge_code` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Dechallenge flag (Y, N, U, D) |
| `dechallenge_label` | `VARCHAR` | Yes | — | `DERIVED` | Human-readable dechallenge outcome label |
| `rechallenge_code` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Rechallenge flag (Y, N, U, D) |
| `rechallenge_label` | `VARCHAR` | Yes | — | `DERIVED` | Human-readable rechallenge outcome label |
| `lot_number` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Manufacturer lot number |
| `expiration_date` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Product expiration date (YYYYMMDD) |
| `standard_expiration_date` | `DATE` | Yes | — | `NORMALIZED` | Imputed/parsed product expiration date |
| `expiration_date_precision` | `VARCHAR` | Yes | — | `DERIVED` | Product expiration date precision classification |
| `regulatory_auth_num` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Regulatory authorization or application number (NDA, ANDA, BLA, MAA, DIN) |
| `structural_clean_drug_name` | `VARCHAR` | Yes | — | `NORMALIZED` | Standardized drug name string with noise removed |
| `standard_concept_name` | `VARCHAR` | Yes | — | `DERIVED` | Normalized generic/INN substance concept name |
| `standard_concept_source` | `VARCHAR` | Yes | — | `DERIVED` | Terminology system used for concept mapping (e.g. RxNorm) |
| `rxcui` | `VARCHAR` | Yes | — | `DERIVED` | RxNorm Concept Unique Identifier if resolved |
| `derivation_status` | `VARCHAR` | No | — | `DERIVED` | Status of automated standardization and vocabulary mapping |

### Adverse Reactions (`reac`)

**Columns:** 5

| Column | Type | Nullable | Key | Origin | Description |
| :--- | :--- | :---: | :--- | :--- | :--- |
| `primary_id` | `VARCHAR` | No | PK, FK → `demo.primary_id` | `SOURCE_REPORTED` | Links to demo.primary_id |
| `case_id` | `VARCHAR` | No | FK → `demo.case_id` | `SOURCE_REPORTED` | Links to demo.case_id |
| `reported_reaction_term` | `VARCHAR` | No | PK | `SOURCE_REPORTED` | MedDRA Preferred Term adverse reaction |
| `reaction_seq` | `INTEGER` | Yes | — | `SOURCE_REPORTED` | Sequence ordinal for the reaction entry within the report |
| `drug_reaction_action` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Action taken with drug (Added 2014Q3) |

### Patient Outcomes (`outc`)

**Columns:** 5

| Column | Type | Nullable | Key | Origin | Description |
| :--- | :--- | :---: | :--- | :--- | :--- |
| `primary_id` | `VARCHAR` | No | PK, FK → `demo.primary_id` | `SOURCE_REPORTED` | Links to demo.primary_id |
| `case_id` | `VARCHAR` | No | FK → `demo.case_id` | `SOURCE_REPORTED` | Links to demo.case_id |
| `outcome_code` | `VARCHAR` | No | PK | `SOURCE_REPORTED` | Outcome code (DE, LT, HO, DS, CA, RI, OT) |
| `outcome_label` | `VARCHAR` | No | — | `DERIVED` | Human-readable outcome label |
| `is_serious` | `BOOLEAN` | No | — | `DERIVED` | Clinical flag indicating seriousness criteria |

### Therapy Indications (`indi`)

**Columns:** 4

| Column | Type | Nullable | Key | Origin | Description |
| :--- | :--- | :---: | :--- | :--- | :--- |
| `primary_id` | `VARCHAR` | No | PK, FK → `demo.primary_id` | `SOURCE_REPORTED` | Links to demo.primary_id |
| `case_id` | `VARCHAR` | No | FK → `demo.case_id` | `SOURCE_REPORTED` | Links to demo.case_id |
| `indication_drug_seq` | `VARCHAR` | No | PK, FK → `drug.drug_seq` | `SOURCE_REPORTED` | Links to drug.drug_seq |
| `reported_indication_term` | `VARCHAR` | No | PK | `SOURCE_REPORTED` | MedDRA Preferred Term indication |

### Therapy Timelines & Durations (`ther`)

**Columns:** 13

| Column | Type | Nullable | Key | Origin | Description |
| :--- | :--- | :---: | :--- | :--- | :--- |
| `primary_id` | `VARCHAR` | No | PK, FK → `demo.primary_id` | `SOURCE_REPORTED` | Links to demo.primary_id |
| `case_id` | `VARCHAR` | No | FK → `demo.case_id` | `SOURCE_REPORTED` | Links to demo.case_id |
| `therapy_drug_seq` | `VARCHAR` | No | PK, FK → `drug.drug_seq` | `SOURCE_REPORTED` | Links to drug.drug_seq |
| `start_date` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Therapy start date (YYYYMMDD) |
| `standard_start_date` | `DATE` | Yes | — | `NORMALIZED` | Imputed/parsed therapy start date |
| `start_date_precision` | `VARCHAR` | Yes | — | `DERIVED` | Therapy start date precision classification |
| `end_date` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Therapy end date (YYYYMMDD) |
| `standard_end_date` | `DATE` | Yes | — | `NORMALIZED` | Imputed/parsed therapy end date |
| `end_date_precision` | `VARCHAR` | Yes | — | `DERIVED` | Therapy end date precision classification |
| `reported_duration` | `DOUBLE` | Yes | — | `SOURCE_REPORTED` | Duration of therapy value |
| `reported_duration_code` | `VARCHAR` | Yes | — | `SOURCE_REPORTED` | Unit of duration (YR, MON, WK, DY, DAY, HR, MIN, SEC) |
| `reported_duration_label` | `VARCHAR` | Yes | — | `DERIVED` | Human-readable therapy duration unit label |
| `standard_duration_days` | `DOUBLE` | Yes | — | `NORMALIZED` | Standardized therapy duration normalized to days |

### Report Sources (`rpsr`)

**Columns:** 4

| Column | Type | Nullable | Key | Origin | Description |
| :--- | :--- | :---: | :--- | :--- | :--- |
| `primary_id` | `VARCHAR` | No | PK, FK → `demo.primary_id` | `SOURCE_REPORTED` | Links to demo.primary_id |
| `case_id` | `VARCHAR` | No | FK → `demo.case_id` | `SOURCE_REPORTED` | Links to demo.case_id |
| `report_source_code` | `VARCHAR` | No | PK | `SOURCE_REPORTED` | Report source category code (FGN, SDY, LIT, HP, CSM, CR, UF) |
| `report_source_label` | `VARCHAR` | No | — | `DERIVED` | Human-readable description of report origin channel |

---

## 2. Silver Tier Index Tables (`silver/index/`)

### Append-Only Submission Ledger (`ledger/*.parquet`)

Stored per quarter (`YYYYQX.parquet`) and compacted annually (`YYYY.parquet`) once all 4 quarters of a year complete.

| Column | Type | Nullable | Description |
| :--- | :--- | :---: | :--- |
| `case_id` | `VARCHAR` | No | Canonical entity identifier (`CASEID`, or deterministic `REPORT:<primary_id>` fallback if blank/NULL). |
| `primary_id` | `VARCHAR` | No | Unique submission report identifier (`PRIMARYID` / legacy `ISR`). |
| `data_period` | `VARCHAR` | No | Source quarterly release identifier (e.g. `2024Q1`). |
| `canonical_case_version` | `INTEGER` | Yes | Numeric case version (`CASEVERSION` / legacy `FOLL_SEQ` rank). |
| `latest_regulatory_date` | `VARCHAR` | Yes | FDA receipt date (`YYYYMMDD`, used in winning-report ranking). |
| `manufacturer_date` | `VARCHAR` | Yes | Manufacturer receipt date (`YYYYMMDD`, secondary tie-breaker). |

### Sharded Resolved State (`state/base/<snapshot_id>/shard_*.parquet` & `state/deltas/delta_*.parquet`)

Partitioned into 16 deterministic `md5_u32(case_id) % 16` ZSTD Parquet shards. Every row holds the complete resolved state for one `case_id`.

| Column | Type | Nullable | Description |
| :--- | :--- | :---: | :--- |
| `case_id` | `VARCHAR` | No | Canonical case entity key (primary key across all 16 shards). |
| `latest_primary_id` | `VARCHAR` | No | Winning `primary_id` selected by the deterministic resolution policy. |
| `latest_quarter` | `VARCHAR` | No | Quarter (`YYYYQX`) containing `latest_primary_id`. |
| `first_quarter` | `VARCHAR` | No | Earliest quarter (`MIN(data_period)`) in which this `case_id` appeared. |
| `submissions_count` | `INTEGER` | No | Total number of submissions recorded for this `case_id` across all indexed quarters. |
| `is_cross_quarter` | `BOOLEAN` | No | `TRUE` when `MIN(data_period) <> MAX(data_period)` (case appears in 2+ quarterly releases). |
| `resolution_tie` | `BOOLEAN` | No | `TRUE` when the top two submissions tied on version and dates before `primary_id` / `data_period` tie-breaking. |
| `timeline` | `LIST<STRUCT>` | No | Ranked submission history (`quarter`, `version`, `primary_id`, `fda_date`, `mfr_date`), ordered winner-first; enables `as_of_period` point-in-time queries. |

---

## 3. Embedded Metadata & Quality Tables

Every compiled DuckDB package embeds self-describing provenance and audit tables:

| Table | Columns | Description |
| :--- | :--- | :--- |
| `_metadata` | `key`, `value`, `updated_at` | Package format version (`1.0.0`), canonical schema version, source name, data period, tier, and build timestamp. |
| `_data_quality_report` | `metric_name`, `metric_value` | Automated EDA metrics computed at build time (table row counts, null rates, deduplication ratios). |
| `_code_*` (16 tables) | `code`, `label`, ... | Embedded FDA CDER and ICH E2B(R2/R3) lookup dimensions (see [Canonical Data Model](canonical_data_model.md)). |
