# Quickstart Guide

This guide walks through using the Python SDK and command-line interface to interact with compiled FAERS safety datasets.

---

## 1. Using the Python SDK (`FAERS`)

The `FAERS` client provides zero-copy querying with DuckDB and returns blazing-fast [Polars](https://pola.rs) DataFrames.

### Loading a Local Package

```python
from raxtik_etl import FAERS

# Connects to data/packages/faers_2004Q1.duckdb
with FAERS("2004Q1") as faers:
    # Print data quality report and package summary
    faers.print_summary()

    # Query authoritative deduplicated cases
    cases_df = faers.cases(limit=10)
    print(cases_df.select(["case_id", "primary_id", "standard_age_years", "standard_sex_label"]))

    # Query suspect drugs
    drugs_df = faers.drugs(limit=5)
    print(drugs_df)

    # Execute custom analytics SQL
    custom_df = faers.query("""
        SELECT
            reported_drug_name,
            COUNT(*) AS reaction_count
        FROM case_adverse_events_summary
        GROUP BY reported_drug_name
        ORDER BY reaction_count DESC
        LIMIT 10
    """)
    print(custom_df)
```

### Auto-Downloading from Hugging Face Hub

Users don't need to manually build packages; `FAERS.from_hf` streams precompiled packages directly from Hugging Face Hub (zero auth required):

```python
from raxtik_etl import FAERS

# Automatically downloads from Hugging Face Hub if missing locally
with FAERS.from_hf("2004Q1") as faers:
    df = faers.cases(limit=100)
    print(f"Loaded {len(df)} cases.")
```

---

## 2. Command Line Interface (CLI)

`raxtik-etl` provides a command-line interface:

### Building Single-Quarter Packages

```bash
# Build 2004Q1 from cached archive
raxtik-etl build-package --release 2004Q1

# Build using an explicit zip archive path
raxtik-etl build-package --release 2004Q2 --zip-path data/raw/archives_cache/2004q2_ascii.zip
```

### Building Batch Cohorts

```bash
# Build all 12 quarters from 2004Q1 to 2006Q4 in one command
raxtik-etl build-cohort --start 2004Q1 --end 2006Q4
```

### Cross-Quarter Case Deduplication & Longitudinal Merging

```bash
# Merge 2004-2006 into a consolidated deduplicated dataset
raxtik-etl merge-cohort --start 2004Q1 --end 2006Q4 --output-name faers_2004_2006_merged

# Inspect the merged cohort metrics
raxtik-etl inspect-cohort
```

### Hugging Face Distribution Commands

```bash
# Download a compiled package (no auth required)
raxtik-etl hf-download --release 2004Q1

# Upload compiled package to Hugging Face Hub (requires HF_TOKEN)
export HF_TOKEN="hf_..."
raxtik-etl hf-upload --release 2004Q1 --repo-id vigilforms/faers-safety-database
```
