---
license: odc-by
task_categories:
  - tabular-classification
  - text-classification
  - question-answering
tags:
  - pharmacovigilance
  - fda
  - faers
  - drug-safety
  - adverse-events
  - clinical
  - medical
  - healthcare
  - epidemiology
  - duckdb
  - parquet
  - tabular-data
pretty_name: "FDA FAERS Adverse Event Safety Database (2004–2026)"
size_categories:
  - 10M<n<100M
---

# FDA FAERS Adverse Event Safety Database (2004–2026) ⚡

[![Documentation](https://img.shields.io/readthedocs/raxtik-etl)](https://raxtik-etl.readthedocs.io/en/latest/)
[![License: ODC-By 1.0](https://img.shields.io/badge/License-ODC--By_1.0-blue.svg)](https://opendatacommons.org/licenses/by/1-0/)
[![Engine: raxtik-etl](https://img.shields.io/badge/Engine-raxtik--etl-informational.svg)](https://github.com/raxtik-org/raxtik-etl)
[![Release Tag: v0.1.0.dev1](https://img.shields.io/badge/Release-v0.1.0.dev1-orange.svg)](https://huggingface.co/datasets/raxtik-org/faers-safety-database/tree/v0.1.0.dev1)

High-performance, standardized, and self-describing pharmacovigilance (PV) surveillance data compiled from official United States Food and Drug Administration (FDA) adverse event reporting systems (**AERS / FAERS**).

Covering **91 consecutive quarters** from **2004Q1 through 2026Q3**, this database encapsulates over **20+ million patient case reports** spanning 22 years of post-marketing drug safety surveillance.

> 📖 **Official Documentation**: Comprehensive guides, canonical schema specifications, and tutorials are available at **[raxtik-etl.readthedocs.io](https://raxtik-etl.readthedocs.io/en/latest/)**. For step-by-step examples, see the **[Quickstart Guide](https://raxtik-etl.readthedocs.io/en/latest/quickstart.html)**.

---

## 🏗️ Partition Layout & File Hierarchy

All quarterly releases are organized under the **Bronze Tier** (`bronze/<YEAR>/`) in dual presentation formats:
- **Standalone DuckDB (`.duckdb`)**: Fully indexed analytical database containing all 7 fact tables, authoritative deduplicated `cases` view, embedded metadata (`_metadata`), and 16 reference dimension codelists (`_code_*`).
- **Apache Parquet (`.parquet/`)**: ZSTD-compressed columnar tables partitioned by clinical entity for distributed ML pipelines and instant remote HTTP streaming.

```text
raxtik-org/faers-safety-database/
└── bronze/
    ├── 2004/
    │   ├── faers_2004Q1.duckdb
    │   ├── faers_2004Q1.parquet/
    │   │   ├── demo.parquet
    │   │   ├── drug.parquet
    │   │   ├── reac.parquet
    │   │   ├── outc.parquet
    │   │   ├── indi.parquet
    │   │   ├── ther.parquet
    │   │   └── rpsr.parquet
    │   ├── faers_2004Q2.duckdb
    │   └── faers_2004Q2.parquet/
    │       └── ...
    ├── ...
    └── 2026/
        ├── faers_2026Q1.duckdb
        ├── faers_2026Q1.parquet/
        ├── faers_2026Q2.duckdb
        ├── faers_2026Q2.parquet/
        ├── faers_2026Q3.duckdb
        └── faers_2026Q3.parquet/
```

---

## 🏛️ Canonical Data Model & Entity Relationships

Every quarterly dataset projects heterogeneous raw FDA ASCII files across historical schema eras (**S1**, **S2**, **S3**) into a unified star-schema architecture:

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
        BIGINT primary_id FK "References demo.primary_id"
        INTEGER drug_seq PK "Unique exposure index per case"
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
        BIGINT primary_id FK "References demo.primary_id"
        VARCHAR reported_reaction_term PK "MedDRA Preferred Term"
        BIGINT reaction_seq "Reaction sequence ordinal"
        VARCHAR drug_reaction_action "Action taken with drug"
    }

    outc {
        BIGINT primary_id FK "References demo.primary_id"
        VARCHAR outc_code PK "Seriousness criterion: DE, HO, LT, DS, CA, RI, OT"
        VARCHAR standard_outc_label "Death, Hospitalization, Life-threatening..."
        BOOLEAN is_death "Flag for fatal outcome (DE)"
        BOOLEAN is_serious "Flag for serious adverse event"
    }

    indi {
        BIGINT primary_id FK "References drug.primary_id"
        INTEGER indi_drug_seq FK "References drug.drug_seq"
        VARCHAR indi_pt PK "MedDRA Preferred Term for clinical indication"
        VARCHAR reported_indication "Reported condition / disease treated"
    }

    ther {
        BIGINT primary_id FK "References drug.primary_id"
        INTEGER dsg_drug_seq FK "References drug.drug_seq"
        DATE start_date "Therapy initiation date"
        DATE end_date "Therapy cessation date"
        DOUBLE duration_days "Standardized duration in days"
    }

    rpsr {
        BIGINT primary_id FK "References demo.primary_id"
        VARCHAR rpsr_code PK "Report source classification code"
        VARCHAR standard_rpsr_label "Health Professional, Study, Consumer..."
    }
```

### Table Definitions

1. **`demo` (Demographics & Submissions)**: Individual safety report submissions, patient demographics (standardized age in years, normalized weight in kg, sex), report type, and receipt dates.
2. **`drug` (Medicinal Products & Regimens)**: Reported medications, active pharmaceutical ingredients, suspect roles (`PS` = Primary Suspect, `SS` = Secondary Suspect, `C` = Concomitant, `I` = Interacting), dosage forms, and routes.
3. **`reac` (Adverse Reactions)**: Adverse events coded using MedDRA Preferred Terms (`pt`) and verbatim reported reactions.
4. **`outc` (Patient Outcomes)**: Seriousness criteria indicating clinical consequences: Death (`DE`), Life-threatening (`LT`), Hospitalization (`HO`), Disability (`DS`), Congenital Anomaly (`CA`), Required Intervention (`RI`), or Other Serious Medical Event (`OT`).
5. **`indi` (Therapy Indications)**: Clinical diagnoses and medical conditions for which the drugs were prescribed.
6. **`ther` (Therapy Dates & Durations)**: Treatment start dates, end dates, and standardized therapy durations in days.
7. **`rpsr` (Report Sources)**: Initial reporter background (Physician, Pharmacist, Health Professional, Consumer, Study).
8. **`cases` (Authoritative Deduplicated View)**: High-performance view resolving multi-version follow-ups to the latest authoritative record per `case_id`, pre-computing `has_serious_outcome`, `is_death`, and `is_expedited`.
9. **Reference Dimensions (`_code_*`)**: 16 embedded lookup tables providing standard descriptions for ISO country codes, dose units, age groups, report types, and clinical classifications.

---

## 🚀 Quickstart: Python SDK

Install the official open-source engine:

```bash
pip install raxtik-etl raxtik-source-faers
```

### Python SDK Quickstart

```python
from raxtik_etl import FAERS

# 1. Default (Recommended): Downloads once, caches locally, and queries in milliseconds
with FAERS.from_hf("2024Q1") as faers:
    faers.print_summary()
    cases_df = faers.cases(limit=1000)
    print(cases_df)

# 2. Zero Local Disk (Remote Streaming): Queries directly over HTTPS without local downloads
with FAERS.from_hf("2024Q1", remote=True) as faers:
    cases_df = faers.cases(limit=100)
    print(cases_df)
```

---

## ⚡ Remote Querying via DuckDB (Zero Local Storage)

You can run analytical SQL queries directly against datasets hosted on Hugging Face Hub over HTTPS without downloading full archives to disk. DuckDB's built-in `httpfs` extension fetches only the metadata and column pages required via HTTP Range requests.

### Option A: Remote DuckDB `ATTACH` (Single File URL, Full Star-Schema & Views)
Points to **one single database file** containing all 7 fact tables (`demo`, `drug`, `reac`, `outc`, `indi`, `ther`, `rpsr`), the precomputed `cases` view, and all 16 reference codelists (`_code_*`):

```python
import duckdb

con = duckdb.connect()
# httpfs is DuckDB's native C++ extension (no pip install required)
con.execute("INSTALL httpfs; LOAD httpfs;")

# 1 single URL attaches the entire quarterly database
db_url = "https://huggingface.co/datasets/raxtik-org/faers-safety-database/resolve/main/bronze/2024/faers_2024Q1.duckdb"
con.execute(f"ATTACH '{db_url}' AS faers (READ_ONLY);")

# Clean standard SQL joins across tables inside the attached database
con.execute("""
    SELECT
        d.reported_drug_name,
        COUNT(*) AS report_count
    FROM faers.drug d
    JOIN faers.reac r
      ON d.primary_id = r.primary_id
    WHERE d.role_code = 'PS'
      AND r.reported_reaction_term = 'Myocardial infarction'
    GROUP BY d.reported_drug_name
    ORDER BY report_count DESC
    LIMIT 5;
""").show()
```
> [!NOTE]
> *Initial `ATTACH` takes ~10s as DuckDB reads the remote database catalog, block manager, and schema headers over HTTP. Once attached, subsequent queries reuse the connection without re-attaching.*

### Option B: Remote Parquet Scanning (Fast Columnar Range Requests)
Directly queries specific columnar Parquet files, skipping unqueried columns entirely:

```python
import duckdb

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")

con.execute("""
    SELECT
        d.reported_drug_name,
        COUNT(*) AS report_count
    FROM 'https://huggingface.co/datasets/raxtik-org/faers-safety-database/resolve/main/bronze/2024/faers_2024Q1.parquet/drug.parquet' d
    JOIN 'https://huggingface.co/datasets/raxtik-org/faers-safety-database/resolve/main/bronze/2024/faers_2024Q1.parquet/reac.parquet' r
      ON d.primary_id = r.primary_id
    WHERE d.role_code = 'PS'
      AND r.reported_reaction_term = 'Myocardial infarction'
    GROUP BY d.reported_drug_name
    ORDER BY report_count DESC
    LIMIT 5;
""").show()
```

---

## 🛡️ Data Quality & Cross-Quarter Case Updates

In post-marketing pharmacovigilance surveillance, pharmaceutical manufacturers frequently submit follow-up reports updating therapy durations, additional reactions, or new clinical indications for cases originally reported in previous quarters.

When FDA releases quarterly ASCII snapshots, child tables (`drug`, `reac`, `indi`, `ther`) occasionally contain update records referencing a `primary_id` from an earlier quarter without re-emitting the unchanged demographic row:
- In isolated single-quarter snapshots, this manifests as referential integrity warnings (< 0.0003% of rows, e.g., 5 orphan rows in 2012Q1 and 2026Q3).
- Rather than silently dropping these clinically valuable update records, `raxtik-etl` retains them and transparently logs referential warnings during packaging.
- Multi-quarter cohort consolidation (`raxtik-etl consolidate`) reconciles multi-version reports into unified case records.

---

## 📜 Citations & Provenance

- **Original Data Source**: United States Food and Drug Administration (FDA) Adverse Event Reporting System ([FAERS Data Files](https://www.fda.gov/drugs/questions-and-answers-fdas-adverse-event-reporting-system-faers/fda-adverse-event-reporting-system-faers-public-dashboard)).
- **Processing Engine**: [raxtik-etl](https://github.com/raxtik-org/raxtik-etl) and [raxtik-source-faers](https://github.com/raxtik-org/raxtik-source-faers).
- **License**: Raw FDA data is in the public domain (US Federal Government Work, 17 U.S.C. § 105). The curated, normalized, and packaged schema datasets are distributed under the [Open Data Commons Attribution License (ODC-By 1.0)](https://opendatacommons.org/licenses/by/1-0/).
