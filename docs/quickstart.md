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

### Auto-Downloading & Streaming from Hugging Face Hub

Users don't need to manually build packages; `FAERS.from_hf` (or `Dataset.from_hf`) streams precompiled packages directly from Hugging Face Hub (zero auth required):

```python
from raxtik_etl import FAERS

# 1. Default (Recommended): Downloads once, caches locally, and queries in milliseconds
with FAERS.from_hf("2024Q1") as faers:
    faers.print_summary()
    cases_df = faers.cases(limit=100)
    print(f"Loaded {len(cases_df)} cases.")

# 2. Remote Streaming (No Full Dataset Download): Queries over HTTPS without downloading full packages
with FAERS.from_hf("2024Q1", remote=True) as faers:
    cases_df = faers.cases(limit=100)
    drugs_df = faers.drugs(limit=100)
    reactions_df = faers.reactions(limit=100)
```

### Silver Tier: Quarter-Scoped Cross-Quarter Deduplication & Case Timelines

The **Silver Tier** resolves cases across all indexed quarters (`2004Q1–present`) using a compact 16-shard Parquet index (`silver/index/`), without duplicating Bronze tables. Opening `FAERS.from_hf("<quarter>", tier="silver", as_of_period="<cutoff>")` is **quarter-scoped**: it attaches `<quarter>` and filters `cases` and child tables (`drug`, `reac`, `outc`, `indi`, `ther`, `rpsr`) to cases whose winning report (as of `<cutoff>`) lives in `<quarter>`, while `case_timeline(case_id)` returns the full multi-quarter history across all quarters:

```python
from raxtik_etl import FAERS

# 1. Remote Silver Query (No Full Dataset Download): Streams both Bronze data & Silver index over HTTPS
with FAERS.from_hf(
    "2024Q1",
    tier="silver",
    remote=True,
    as_of_period="2025Q4",  # Optional point-in-time cutoff
) as faers:
    # Only cases whose authoritative winning report belongs to 2024Q1 (as of 2025Q4)
    cases_df = faers.cases(limit=100)
    drugs_df = faers.drugs(limit=100)

    # Full multi-quarter version history for any case_id
    cid = str(cases_df["case_id"][0])
    timeline = faers.case_timeline(cid)
    print(timeline)

# 2. Cache the lightweight Silver index locally for millisecond repeated queries
with FAERS.from_hf("2024Q1", tier="silver", cache_index=True) as faers:
    # Export a standalone filtered Silver DuckDB package
    faers.materialize_tier("data/output/faers_2024Q1_silver.duckdb")
```

### Direct Remote SQL via DuckDB

You can also run ad-hoc SQL directly over remote packages using DuckDB's built-in `httpfs` extension:

```python
import duckdb

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")

# Option A: Attach remote DuckDB file (1 URL for all 7 tables + views)
db_url = "https://huggingface.co/datasets/raxtik-org/faers-safety-database/resolve/main/bronze/2024/faers_2024Q1.duckdb"
con.execute(f"ATTACH '{db_url}' AS faers (READ_ONLY);")

con.execute("""
    SELECT d.reported_drug_name, COUNT(*) AS report_count
    FROM faers.drug d
    JOIN faers.reac r ON d.primary_id = r.primary_id
    WHERE d.role_code = 'PS' AND r.reported_reaction_term = 'Myocardial infarction'
    GROUP BY d.reported_drug_name ORDER BY report_count DESC LIMIT 5;
""").show()
```

---

## 2. Command Line Interface (CLI)

`raxtik-etl` provides a unified modern command-line interface:

### Downloading Compiled Packages

```bash
# Download a compiled package from Hugging Face Hub (zero auth required)
raxtik-etl download -d 2004Q1

# Download to a custom destination directory
raxtik-etl download -d 2004Q1 --dest-dir ./my_packages
```

### Building Single-Quarter Packages

```bash
# Build 2004Q1 from cached or downloaded archive
raxtik-etl build -d 2004Q1

# Build using an explicit zip archive path
raxtik-etl build -d 2004Q2 --zip-path data/raw/archives_cache/2004q2_ascii.zip
```

### Batch Building & Distributing Packages

```bash
# Build a continuous range of quarters
raxtik-etl build --start 2004Q1 --end 2006Q4

# Batch build and upload to Hugging Face with memory batch buffering and auto-cleanup
export HF_TOKEN="hf_..."
raxtik-etl build \
    --start 2004Q1 \
    --end 2026Q3 \
    --upload \
    --clean-local \
    --batch-size-gb 2.5 \
    --tag v0.1.0.dev1 \
    --repo-id raxtik-org/faers-safety-database
```

### Inspecting Package Metadata & Data Quality

```bash
# Inspect a compiled quarterly package
raxtik-etl inspect -d 2004Q1
```

### Silver Tier Index Management (`raxtik-etl index`)

```bash
# Build a fresh Silver index across a range (auto-downloads Bronze & cleans up after extraction)
raxtik-etl index build --source faers --tier silver --start 2004Q1 --end 2026Q3 --cleanup-bronze

# Incrementally update the index with a new quarter (writes 1 delta file, zero base shard rewrites)
raxtik-etl index update --data-period 2026Q4 --source faers --tier silver

# Verify logical equivalence against a full ledger rebuild (shard-by-shard EXCEPT ALL)
raxtik-etl index verify --source faers --tier silver

# Inspect the full multi-quarter timeline of a specific case
raxtik-etl index lookup --case-id 12345678 --source faers --tier silver

# Publish silver/index/ to Hugging Face Hub with optimistic concurrency & tagging
export HF_TOKEN="hf_..."
raxtik-etl index upload --source faers --tier silver --tag v0.1.0
```

### Cross-Period Case Deduplication & Consolidation

```bash
# Consolidate 2004-2006 into a unified deduplicated dataset
raxtik-etl consolidate --start 2004Q1 --end 2006Q4 --output-name faers_2004_2006_consolidated

# Inspect the consolidated package metrics
raxtik-etl inspect --db-path data/packages/faers_2004_2006_consolidated.duckdb
```

### Hugging Face Distribution Commands

```bash
# Upload a compiled package to Hugging Face Hub (requires HF_TOKEN)
export HF_TOKEN="hf_..."
raxtik-etl upload -d 2004Q1 --repo-id raxtik-org/faers-safety-database
