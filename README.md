# raxtik-etl ⚡

[![Documentation Status](https://img.shields.io/readthedocs/raxtik-etl)](https://raxtik-etl.readthedocs.io/en/latest/)
[![CI](https://github.com/raxtik-org/raxtik-etl/actions/workflows/ci.yml/badge.svg)](https://github.com/raxtik-org/raxtik-etl/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/raxtik-org/raxtik-etl/graph/badge.svg?token=)](https://codecov.io/gh/raxtik-org/raxtik-etl)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](./LICENSE)
[![Python >= 3.11](https://img.shields.io/badge/python->=_3.11-blue.svg)](https://www.python.org/downloads/)

High-performance canonical pharmacovigilance (PV) data engine and packaging toolkit powered by **DuckDB** and **Polars**.

`raxtik-etl` provides canonical schema definitions, multi-version case deduplication algorithms, and self-describing dataset packaging (DuckDB & Parquet) for safety surveillance datasets. It is completely decoupled from source-specific ingestion logic via an extensible **Source Adapter Protocol**.

👉 **Architecture & Design**: See [Architecture Overview](docs/architecture.md) for plugin decoupling and internal pipeline design.

---

## 🏛️ Canonical Data Model & Entity Relationships

Every source connector projects raw records into an analytical star-schema architecture:

- **7 Core Fact Tables**: Normalized clinical entities (`demo`, `drug`, `reac`, `outc`, `indi`, `ther`, `rpsr`).
- **Authoritative Case View (`cases`)**: Deduplicates multi-version submissions across reporting periods (`case_id` / `canonical_case_version` / `fda_date`) and computes key safety flags (`has_serious_outcome`, `is_death`, `is_expedited`).
- **16 Reference Dimensions (`_code_*`)**: Embedded lookup tables mapping ISO country codes, ICH E2B(R2/R3) guidelines, and FDA clinical codelists.

### Entity Relationships & Composite Keys

| Table | Entity / Domain | Primary Key (Composite) | Foreign Key Relationship | Description |
| :--- | :--- | :--- | :--- | :--- |
| **`demo`** | Case Submissions & Demographics | `primary_id` | *(Root submission table)* | Patient age in decimal years, weight in kg, sex, country, receipt date. |
| **`drug`** | Drug Products & Regimens | `(primary_id, drug_seq)` | `primary_id` → `demo.primary_id` | Reported brand name, active substance, route, form, role code (`PS`, `SS`, `C`, `I`). |
| **`reac`** | Adverse Reactions | `(primary_id, reported_reaction_term)` | `primary_id` → `demo.primary_id` | MedDRA Preferred Terms (PT) describing adverse events. |
| **`outc`** | Patient Outcomes | `(primary_id, outc_code)` | `primary_id` → `demo.primary_id` | Clinical outcomes: Death (`DE`), Hospitalization (`HO`), Disability (`DS`), etc. |
| **`indi`** | Therapy Indications | `(primary_id, indi_drug_seq, reported_indication_term)` | `(primary_id, indi_drug_seq)` → `drug(primary_id, drug_seq)` | Medical conditions for which medications were prescribed. |
| **`ther`** | Therapy Timelines | `(primary_id, dsg_drug_seq)` | `(primary_id, dsg_drug_seq)` → `drug(primary_id, drug_seq)` | Therapy start date, end date, and duration in days. |
| **`rpsr`** | Report Sources | `(primary_id, rpsr_code)` | `primary_id` → `demo.primary_id` | Reporting channel: Health Professional (`HP`), Consumer (`CSM`), Study (`SDY`), etc. |
| **`cases`** | Authoritative Deduplicated View | `case_id` | Derived from `demo` | Precomputed deterministic resolution to latest report version per `case_id`. |

📖 **Visual Entity-Relationship Diagram**:
- 📊 **[Full Interactive ER Diagram (Mermaid)](ER_DIAGRAM.md)**
- 🌐 **[ReadTheDocs: Canonical Data Model](https://raxtik-etl.readthedocs.io/en/latest/schema/canonical_data_model.html)**
- 📚 **[Coded Values Reference](docs/schema/code_list_history.md)**

---

## 🌐 Precompiled Dataset on Hugging Face

All **91 quarterly packages** from **2004Q1 through 2026Q3** (20+ million safety reports) are compiled and publicly accessible on Hugging Face:
🔗 **[raxtik-org/faers-safety-database](https://huggingface.co/datasets/raxtik-org/faers-safety-database)**

Organized under `bronze/<YEAR>/` as standalone DuckDB databases (`.duckdb`) and ZSTD Parquet tables (`.parquet/`).

---

## 📦 Installation

```bash
pip install raxtik-etl raxtik-source-faers
```

For developer setup and contributing from source, see **[CONTRIBUTING.md](CONTRIBUTING.md)**.

---

## 🚀 Quickstart

### 1. Download or Build via CLI

```bash
# Recommended: Download precompiled package directly from Hugging Face Hub (zero auth required)
raxtik-etl download -d 2004Q1

# Inspect package schema and data quality indicators
raxtik-etl inspect -d 2004Q1

# Build a quarterly package locally from raw FDA archives
raxtik-etl build -d 2004Q1 --source faers
```

> [!NOTE]
> **Do I need to upload?**
> Standard users and researchers **never** need to use `raxtik-etl upload`. All 91 quarterly packages are already hosted and publicly accessible. The `upload` command is strictly for repository maintainers or organizations publishing custom builds to their own Hugging Face dataset repository (`--repo-id <org/repo>`).

👉 **CLI Reference**: See the full **[CLI Reference Guide](docs/cli_reference.md)** for all commands and parameters.

---

## 💻 Python SDK Usage

Load and query precompiled safety packages directly in Python:

```python
from raxtik_etl import FAERS

# 1. Default (Recommended): Downloads once, caches locally, and queries in milliseconds
with FAERS.from_hf("2024Q1") as faers:
    faers.print_summary()
    cases_df = faers.cases(limit=1000)
    drugs_df = faers.drugs(limit=1000)
    reactions_df = faers.reactions(limit=1000)

# 2. Zero Local Disk (Remote Streaming): Streams over HTTPS directly from Hugging Face
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

## 📚 Documentation & Guides

- [Canonical Data Model Specification](docs/schema/canonical_data_model.md): Unified star-schema facts, authoritative deduplicated view, and reference dimensions.
- [CLI Reference Guide](docs/cli_reference.md): Complete guide for `build`, `download`, `upload`, `inspect`, `consolidate`, and `sources`.
- [Quickstart Guide](docs/quickstart.md): Step-by-step tutorial for the Python SDK and command line.
- [Architecture & Design](docs/architecture.md): Decoupled plugin architecture and extensible adapter protocol.
- [Coded Values & Code-List History Reference](docs/schema/code_list_history.md): Official FDA CDER & ICH E2B(R2/R3) codelists across all eras.
- [Contributing Guide](CONTRIBUTING.md): Instructions for setting up development environments and submitting pull requests.

---

## 📄 License

Licensed under the **[GNU Affero General Public License v3.0 (AGPL-3.0)](./LICENSE)**.
Raw FDA data is in the public domain (US Government Work, 17 U.S.C. § 105). Derived packaged datasets are distributed under the [Open Data Commons Attribution License (ODC-By 1.0)](https://opendatacommons.org/licenses/by/1-0/).
