# 2004Q1 Dataset Integration & Usage Guide

This guide explains how downstream applications (such as `vigilforms-data` patient simulation, adverse event generation, and analytics) consume the compiled **2004 Q1** FAERS data package.

---

## 📦 Package Summary & Baseline

The package `faers_2004Q1.duckdb` is a **standalone, self-describing analytical relational database** (with matching ZSTD-compressed Parquet shards in `faers_2004Q1.parquet/`).

### Ingested Canonical Counts (Frozen Baseline)
```text
2004Q1 Canonical Baseline (Signature S1)
----------------------------------------
demo   :  65,902  (Raw physical submission reports)
cases  :  58,235  (Resolved authoritative patient cases)
drug   : 235,361  (Reported drug exposures, doses, lot numbers)
reac   : 264,410  (Reported MedDRA Preferred Term reactions)
outc   :  57,592  (Reported patient outcome seriousness)
indi   :  78,639  (Reported medical treatment indications)
ther   :  84,964  (Therapy start/end dates and normalized duration)
rpsr   :  78,306  (Report source types)
----------------------------------------
Total  : 865,174  Clean canonical fact records
```

---

## 🚀 Quickstart: Consuming via Python SDK

The `raxtik_etl.FAERS` client provides zero-copy query execution returning [Polars](https://pola.rs/) DataFrames or PyArrow tables.

```python
from raxtik_etl import FAERS

# 1. Connect to the versioned 2004Q1 package
faers = FAERS("2004Q1")

# 2. Print self-describing metadata & data quality report
faers.print_summary()

# 3. Retrieve resolved patient cases (deterministic latest caseversion)
cases_df = faers.cases(limit=1000)
print(cases_df.select([
    "case_id",
    "primary_id",
    "canonical_case_version",
    "standard_age_years",
    "standard_sex_label",
    "event_date",
]))

# 4. Query drugs and adverse reactions
drugs_df = faers.drugs(limit=500)
reacs_df = faers.reactions(limit=500)
```

---

## 🧬 Data Generation Recipe for `vigilforms-data`

To generate realistic synthetic patients and adverse event simulation profiles based on empirical 2004Q1 clinical patterns:

### Recipe 1: Denormalized Patient AE Profile
```python
import duckdb

con = duckdb.connect("data/packages/faers_2004Q1.duckdb", read_only=True)

patient_profile_sql = """
SELECT 
    c.case_id,
    c.standard_age_years,
    c.standard_sex_label,
    c.event_date,
    -- Primary Suspect Drug
    d.reported_drug_name AS suspect_drug,
    d.route,
    d.reported_dose_verbatim,
    -- Reaction & Outcome
    r.reported_reaction_term AS adverse_reaction,
    o.outcome_code,
    co.outcome_label,
    sem.is_serious,
    sem.ich_seriousness_category
FROM cases c
JOIN drug d 
    ON c.primary_id = d.primary_id AND d.role_code = 'PS'
JOIN reac r 
    ON c.primary_id = r.primary_id
LEFT JOIN outc o 
    ON c.primary_id = o.primary_id
LEFT JOIN _code_outcomes co 
    ON o.outcome_code = co.outcome_code
LEFT JOIN _code_outcome_semantics sem 
    ON o.outcome_code = sem.outcome_code
WHERE c.standard_age_years IS NOT NULL
LIMIT 50000;
"""

df_patients = con.execute(patient_profile_sql).pl()
print(df_patients.head(10))
```

### Recipe 2: Pre-Aggregated View
The package comes pre-built with the analytical view `case_adverse_events_summary`:
```python
df_summary = con.execute("""
    SELECT * 
    FROM case_adverse_events_summary
    WHERE primary_suspect_drug = 'FORTEO'
    LIMIT 100;
""").pl()
```

---

## 📖 Embedded Reference & Dimension Tables

Fact tables (`demo`, `drug`, `reac`, `outc`, `rpsr`) store raw reported codes. To decode them, join directly with the embedded reference tables:

| Table | Content | Key Columns |
| :--- | :--- | :--- |
| **`_code_outcomes`** | Official FDA Serious Outcomes | `outcome_code`, `outcome_label` |
| **`_code_outcome_semantics`** | Raxtik Clinical Seriousness | `outcome_code`, `is_serious`, `ich_seriousness_category`, `severity_rank` |
| **`_code_roles`** | Drug Suspect Roles | `role_code` (`PS`, `SS`, `C`, `I`), `role_label` |
| **`_code_occupations`** | Reporter Professions | `occupation_code` (`MD`, `PH`, `OT`, `LW`, `CN`), `occupation_label` |
| **`_code_report_sources`** | Report Source Channels | `report_source_code` (`FGN`, `SDY`, `LIT`, `HP`, `CSM`), `report_source_label` |
| **`_code_dechallenge`** | Action on Drug Discontinuation | `dechallenge_code` (`Y`, `N`, `U`, `D`), `dechallenge_label` |
| **`_code_rechallenge`** | Action on Drug Reintroduction | `rechallenge_code` (`Y`, `N`, `U`, `D`), `rechallenge_label` |
| **`_schema_registry`** | Complete Machine-Readable Column Catalog | `entity`, `field_name`, `data_type`, `value_origin`, `category` |
| **`_data_quality_report`** | Automated EDA Profiling Snapshot | `metric_name`, `metric_value`, `metric_category` |
| **`_metadata`** | Quad-Versioning & Licensing Terms | `release_quarter`, `package_format_version`, `source_data_license`, etc. |

---

## 🛠 Rebuilding or Verifying the Package

To rebuild the package from source:
```bash
uv run raxtik-etl build-package --release 2004Q1
```

To run the full contract and correctness audit suite:
```bash
uv run pytest tests/test_package_2004q1_audit.py -v
```
