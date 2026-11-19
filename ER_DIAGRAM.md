# Canonical Entity-Relationship (ER) Diagram

Visual representation of the **7 canonical pharmacovigilance fact tables**, composite keys, and entity relationships in `raxtik-etl`.

---

## 🏛️ Visual Schema Model

```mermaid
erDiagram
    demo ||--o{ drug : "primary_id"
    demo ||--o{ reac : "primary_id"
    demo ||--o{ outc : "primary_id"
    demo ||--o{ rpsr : "primary_id"
    drug ||--o{ indi : "primary_id, drug_seq"
    drug ||--o{ ther : "primary_id, drug_seq"

    demo {
        BIGINT primary_id PK "Unique submission report ID"
        BIGINT case_id "Unique patient case identifier"
        INTEGER case_version "Report version number"
        VARCHAR event_country "Country where reaction occurred"
        VARCHAR reporter_country_code "ISO 3166-1 alpha-2"
        DATE fda_date "Receipt date at FDA"
        VARCHAR age_group_code "ICH life stage classification"
        DOUBLE standard_age_years "Normalized age in decimal years"
        VARCHAR standard_sex_label "Male / Female / Unknown"
        DOUBLE standard_weight_kg "Normalized patient weight in kg"
        VARCHAR reporter_occupation_label "Physician, Pharmacist, Consumer..."
        VARCHAR report_type_label "Expedited 15-day, Periodic, Direct..."
    }

    drug {
        BIGINT primary_id PK,FK "References demo.primary_id (Composite PK Part 1)"
        INTEGER drug_seq PK "Exposure sequence per report (Composite PK Part 2)"
        VARCHAR role_code "Role: PS, SS, C, I"
        VARCHAR standard_role_label "Primary Suspect, Concomitant..."
        VARCHAR reported_drug_name "Reported medicinal trade/brand name"
        VARCHAR active_ingredient "Normalized generic active substance"
        VARCHAR route "Administration route (Oral, IV...)"
        VARCHAR dose_form "Dosage formulation (Tablet, Solution...)"
        DOUBLE cumulative_dose "Normalized cumulative amount"
        VARCHAR cumulative_dose_unit_label "Metric dose unit (mg, mL...)"
    }

    reac {
        BIGINT primary_id PK,FK "References demo.primary_id (Composite PK Part 1)"
        VARCHAR reported_reaction_term PK "MedDRA Preferred Term (Composite PK Part 2)"
        BIGINT reaction_seq "Reaction sequence ordinal"
        VARCHAR drug_reaction_action "Action taken with drug"
    }

    outc {
        BIGINT primary_id PK,FK "References demo.primary_id (Composite PK Part 1)"
        VARCHAR outc_code PK "Seriousness criterion: DE, HO, LT, DS, CA, RI, OT (Composite PK Part 2)"
        VARCHAR standard_outc_label "Death, Hospitalization, Life-threatening..."
        BOOLEAN is_death "Flag for fatal outcome (DE)"
        BOOLEAN is_serious "Flag for serious adverse event"
    }

    indi {
        BIGINT primary_id PK,FK "Composite PK Part 1 / References drug(primary_id, drug_seq)"
        INTEGER indi_drug_seq PK,FK "Composite PK Part 2 / References drug(primary_id, drug_seq)"
        VARCHAR reported_indication_term PK "MedDRA Indication Term (Composite PK Part 3)"
        VARCHAR reported_indication "Reported condition / disease treated"
    }

    ther {
        BIGINT primary_id PK,FK "Composite PK Part 1 / References drug(primary_id, drug_seq)"
        INTEGER dsg_drug_seq PK,FK "Composite PK Part 2 / References drug(primary_id, drug_seq)"
        DATE start_date "Therapy initiation date"
        DATE end_date "Therapy cessation date"
        DOUBLE duration_days "Standardized duration in days"
    }

    rpsr {
        BIGINT primary_id PK,FK "References demo.primary_id (Composite PK Part 1)"
        VARCHAR rpsr_code PK "Report source classification code (Composite PK Part 2)"
        VARCHAR standard_rpsr_label "Health Professional, Study, Consumer..."
    }
```

---

## 🔑 Composite Primary Keys & Relational Cardinality

| Table | Entity / Domain | Primary Key (Composite) | Foreign Key Relationship | Cardinality | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`demo`** | Case Submissions & Demographics | `primary_id` | *(Root submission table)* | Root | Individual patient report submission with demographic covariates. |
| **`drug`** | Drug Exposures & Regimens | `(primary_id, drug_seq)` | `primary_id` → `demo.primary_id` | 1 : N | Reported medicinal products, active ingredients, dosage forms, and suspect roles. |
| **`reac`** | Adverse Reactions | `(primary_id, reported_reaction_term)` | `primary_id` → `demo.primary_id` | 1 : N | Adverse reaction terms coded with MedDRA Preferred Terms (`reported_reaction_term`). |
| **`outc`** | Patient Outcomes | `(primary_id, outc_code)` | `primary_id` → `demo.primary_id` | 1 : N | Clinical seriousness criteria (`DE`, `HO`, `LT`, `DS`, `CA`, `RI`, `OT`). |
| **`indi`** | Therapy Indications | `(primary_id, indi_drug_seq, reported_indication_term)` | `(primary_id, indi_drug_seq)` → `drug(primary_id, drug_seq)` | 1 : N | Medical conditions and clinical indications for which each drug was prescribed. |
| **`ther`** | Therapy Timelines | `(primary_id, dsg_drug_seq)` | `(primary_id, dsg_drug_seq)` → `drug(primary_id, drug_seq)` | 1 : N | Start dates, end dates, and standardized therapy durations in days. |
| **`rpsr`** | Report Sources | `(primary_id, rpsr_code)` | `primary_id` → `demo.primary_id` | 1 : N | Reporting source categories (Physician, Pharmacist, Consumer, Study). |
| **`cases`** | Authoritative Deduplicated View | `case_id` | Derived from `demo` | 1 : 1 | Precomputed view resolving multi-version follow-ups to latest report version. |

---

## 📖 Related Documentation

- **[Architecture & Engine Design](docs/architecture.md)**
- **[Canonical Data Model Specification](docs/schema/canonical_data_model.md)**
- **[Coded Values Reference](docs/schema/code_list_history.md)**
- **[ReadTheDocs Interactive Documentation](https://raxtik-etl.readthedocs.io/en/latest/)**
