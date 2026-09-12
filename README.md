# raxtik-etl ⚡

[![CI](https://github.com/VigilForms/raxtik-etl/actions/workflows/ci.yml/badge.svg)](https://github.com/VigilForms/raxtik-etl/actions/workflows/ci.yml)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

Adverse event data extraction, loading, and transformation pipeline for pharmacovigilance datasets (**FDA FAERS**, openFDA) using **`dlt`** (data load tool) and **DuckDB**.

`raxtik-etl` processes large-scale FDA adverse event distribution dumps into compact, indexed statistical seeds (**SQLite** & **Parquet**) for downstream consumption by synthetic data generators in `vigilforms-data` / `raxtik-data`.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Raw FDA FAERS                          │
│     (Quarterly ZIPs: DEMO, DRUG, REAC, OUTC, INDI)          │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│              raxtik-etl (dlt Extract & Load)                │
│  - @dlt.source("faers")                                     │
│    ├── @dlt.resource("demo") -> streams DEMO records        │
│    ├── @dlt.resource("drug") -> streams DRUG records        │
│    ├── @dlt.resource("reac") -> streams REAC records        │
│    ├── @dlt.resource("outc") -> streams OUTC records        │
│    └── @dlt.resource("indi") -> streams INDI records        │
│  - Destination: DuckDB (`data/intermediate/faers.duckdb`)   │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│             Transformations (DuckDB SQL Engine)             │
│  1. Case Deduplication (Latest caseversion/fda_dt per case) │
│  2. Drug Normalization (PS vs Concomitant, name cleanup)    │
│  3. Statistical Aggregations:                               │
│     - Co-occurrence: (drug_name, pt, count, prr)            │
│     - Demographics: (drug_name, age_mean, gender_ratio)     │
│     - Regimens: (drug_name, route, route_pct)               │
│     - Indications: (drug_name, indication_pt, count, pct)   │
│     - Serious Outcomes: (drug_name, death, hosp, LT counts) │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│              Seed Exporter (Standalone Output)              │
│  - SQLite Seed Bundle (`data/output/faers_seed.sqlite`)     │
│  - Parquet Seed Bundle (`data/output/parquet/*.parquet`)    │
│  => Ready for synthetic generation in vigilforms-data       │
└──────────────────────────────┴──────────────────────────────┘
```

---

## 🚀 Quickstart

### 1. Installation

Requires Python 3.11+ (Python 3.13 recommended) and [`uv`](https://github.com/astral-sh/uv).

```bash
# Set local python version
pyenv local 3.13.5

# Create virtual environment and install dependencies
uv venv --python 3.13.5 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### 2. Run Sample Pipeline (Instant Test)

Run the full end-to-end pipeline against the included fixture datasets:

```bash
raxtik-etl pipeline --sample --output-dir ./data/output
```

This will ingest sample data into DuckDB, execute all deduplication & aggregation transformations, and export `data/output/faers_seed.sqlite` and `data/output/parquet/`.

---

## 🛠️ CLI Commands

`raxtik-etl` provides a modular Typer CLI for both step-by-step and automated execution:

### 1. Fetch FDA FAERS Data
Download and unpack FDA quarterly ASCII archives:
```bash
raxtik-etl fetch --year 2024 --quarter 1
```

### 2. Ingest Data via `dlt`
Load `$`-delimited FAERS ASCII files into DuckDB:
```bash
raxtik-etl ingest --source-dir ./data/raw/faers_2024q1
```

### 3. Transform Data with DuckDB
Execute deduplication, drug normalization, and statistical metric aggregations:
```bash
raxtik-etl transform
```

### 4. Export Distribution Seeds
Compile indexed SQLite bundles and Parquet files:
```bash
# Export both SQLite and Parquet
raxtik-etl export --format all

# Export only SQLite
raxtik-etl export --format sqlite --sqlite-path ./data/output/faers_seed.sqlite

# Export only Parquet
raxtik-etl export --format parquet --parquet-dir ./data/output/parquet
```

### 5. Automated Pipeline
Fetch (or specify directory), ingest, transform, and export in a single command:
```bash
raxtik-etl pipeline --year 2024 --quarter 1 --output-dir ./data/output
```

---

## 📊 Exported Statistical Tables

The exported SQLite seed database contains precomputed distributions indexed for sub-millisecond query performance:

| Table Name | Description | Key Columns |
| :--- | :--- | :--- |
| `drug_reaction_stats` | Drug-Reaction co-occurrence counts and Proportional Reporting Ratio (PRR) | `drug_name`, `reaction_pt`, `co_occurrence_count`, `frequency`, `prr` |
| `drug_demographics` | Patient demographic distribution per drug | `drug_name`, `total_cases`, `mean_age`, `std_age`, `pct_male`, `pct_female` |
| `drug_indications` | Top indications per drug | `drug_name`, `indication_pt`, `indication_count`, `indication_pct` |
| `drug_routes` | Administration route frequencies per drug | `drug_name`, `route`, `route_count`, `route_pct` |
| `drug_outcomes` | Serious outcome metrics (Death, Hospitalization, Life-threatening) | `drug_name`, `death_count`, `hosp_count`, `life_threat_count`, `serious_outcome_pct` |
| `seed_metadata` | Pipeline version, timestamp, and provenance metadata | `key`, `value` |

---

## 🧪 Testing & Code Quality

Run tests, coverage, and linters:

```bash
# Run pytest test suite
pytest -v

# Run linting
ruff check .

# Autoformat code
ruff format .
```

---

## 📄 License

Licensed under the **[GNU Affero General Public License v3.0 (AGPL-3.0)](./LICENSE)**.
