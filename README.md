# raxtik-etl ⚡

[![Documentation Status](https://readthedocs.org/projects/raxtik-etl/badge/?version=latest)](https://raxtik-etl.readthedocs.io/en/latest/?badge=latest)
[![CI](https://github.com/VigilForms/raxtik-etl/actions/workflows/ci.yml/badge.svg)](https://github.com/VigilForms/raxtik-etl/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/vigilforms-org/raxtik-etl/graph/badge.svg?token=)](https://codecov.io/gh/vigilforms-org/raxtik-etl)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](./LICENSE)
[![Python >= 3.11](https://img.shields.io/badge/python->=_3.11-blue.svg)](https://www.python.org/downloads/)

High-performance canonical pharmacovigilance (PV) data engine and packaging toolkit powered by **DuckDB** and **Polars**.

`raxtik-etl` provides the canonical schema definitions, deduplication algorithms, case resolution logic, and self-describing dataset packaging for safety surveillance datasets. It is completely decoupled from source-specific ingestion logic via an extensible **Source Adapter Protocol**.

---

## 🏗️ Architecture

```text
                    SOURCE CONNECTORS (Plugins)
                               │
               ┌───────────────┼───────────────┐
               ▼               ▼               ▼
      raxtik-source-faers  future-source   future-source
      (FDA AERS/FAERS)    (EudraVigilance)   (VigiBase)
               │
               │ implements SourceAdapter
               ▼
   ┌────────────────────────────────────────────────────────┐
   │                       raxtik-etl                       │
   │  1. Canonical Schemas (demo, drug, reac, outc, etc.)   │
   │  2. Deterministic Case Resolution & Deduplication      │
   │  3. Standardized Transformations & Unit Normalization  │
   │  4. Quality Control & Quality Summary Reporting        │
   │  5. Self-describing Packaging (DuckDB & Parquet)       │
   └───────────────────────────┬────────────────────────────┘
                               │
                               ▼
   ┌────────────────────────────────────────────────────────┐
   │                   Packaged Artifacts                   │
   │  - data/packages/faers_{release}.duckdb (Indexed SQL)  │
   │  - data/packages/faers_{release}.parquet/ (ZSTD Shards)│
   └───────────────────────────┬────────────────────────────┘
                               │
                               ▼
   ┌────────────────────────────────────────────────────────┐
   │                 Downstream Ecosystem                   │
   │  - vigilforms-data (Synthetic narratives, labs, E2B)   │
   │  - vigilforms-api  (Case search, signal detection)     │
   │  - raxtik-studio   (Interactive safety workbench)      │
   └────────────────────────────────────────────────────────┘
```

### Decoupled Source Plugins
`raxtik-etl` contains **zero** source-specific proprietary parsing, column aliases, or archive file logic. Connectors such as [`raxtik-source-faers`](https://github.com/VigilForms/raxtik-source-faers) implement the `SourceAdapter` protocol and register via Python entry points (`raxtik_etl.sources`).

---

## 🏛️ Canonical Data Model

Every source connector projects raw records into 7 canonical fact tables:

| Table | Description | Primary / Entity Keys | Key Standardized Columns |
| :--- | :--- | :--- | :--- |
| `demo` | Case submissions & demographics | `primary_id`, `case_id` | `standard_age_years`, `standard_sex_label`, `event_date`, `reporter_occupation_label` |
| `drug` | Reported drug exposures & regimens | `primary_id`, `drug_seq` | `drug_name`, `standard_role_label` (PS/SS/C/I), `route`, `dose_amt`, `dose_unit` |
| `reac` | Adverse events / reaction terms | `primary_id`, `pt` | `pt` (MedDRA Preferred Term) |
| `outc` | Seriousness outcome criteria | `primary_id`, `outc_code` | `outc_code`, `standard_outc_label` (DE, HO, LT, DS, CA, RI, OT) |
| `indi` | Clinical indications for therapy | `primary_id`, `indi_pt` | `indi_drug_seq`, `indi_pt` |
| `ther` | Therapy timelines & durations | `primary_id`, `dsg_drug_seq`| `start_date`, `end_date`, `duration_days` |
| `rpsr` | Adverse event report sources | `primary_id`, `rpsr_code` | `rpsr_code`, `standard_rpsr_label` |

### Authoritative Case View (`cases`)
In addition to raw submissions, `raxtik-etl` compiles a deduplicated, authoritative view:
- **`cases`**: Evaluates `CASE` / `CASEID` across multiple submission updates (`ISR` / `PRIMARYID`), selecting the latest authoritative report version (`FDA_DT`, `CASEVERSION`) and flagging expedited 15-day cases and serious adverse outcomes (`has_serious_outcome`, `is_death`).

---

## 🚀 Quickstart

### 1. Installation

Requires Python >= 3.11 (Python 3.13 recommended) and [`uv`](https://github.com/astral-sh/uv).

```bash
# Set local Python version
pyenv local 3.13.5

# Create virtual environment and install raxtik-etl
uv venv --python 3.13.5 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Install the FDA FAERS source connector plugin
uv pip install -e ../raxtik-source-faers
```

### 2. Build a Quarterly Package via CLI

Generate a standalone DuckDB database and ZSTD-compressed Parquet directory from a raw quarterly extract:

```bash
raxtik-etl build-package \
    --source faers \
    --release 2004Q1 \
    --zip-path data/raw/archives_cache/2004q1_ascii.zip \
    --output-dir data/packages
```

Output:
- `data/packages/faers_2004Q1.duckdb` (Indexed analytical database)
- `data/packages/faers_2004Q1.parquet/` (ZSTD-compressed columnar tables)

### 3. Inspect Package Metadata & Quality Metrics

```bash
raxtik-etl inspect-package --release 2004Q1 --package-dir data/packages
```

Displays package version, signature ID, fact record counts, and canonical data quality indicators.

---

## 💻 Python SDK Usage

Downstream applications can query packages using the high-performance `FAERS` client with zero-copy [Polars](https://pola.rs/) DataFrames:

```python
from raxtik_etl import FAERS

# Connect to the 2004Q1 compiled package
with FAERS(release="2004Q1", package_dir="data/packages") as faers:
    # 1. Print self-describing metadata & data quality report
    faers.print_summary()

    # 2. Retrieve authoritative resolved cases
    cases_df = faers.cases(limit=1000)
    print(
        cases_df.select(
            [
                "case_id",
                "primary_id",
                "canonical_case_version",
                "standard_age_years",
                "standard_sex_label",
                "has_serious_outcome",
            ]
        )
    )

    # 3. Query primary suspect drugs and reactions
    drugs_df = faers.drugs(primary_suspect_only=True)
    reactions_df = faers.reactions()
```

---

## 🔌 Implementing a Custom Source Adapter

Adding a new pharmacovigilance source (e.g., EudraVigilance, PMDA, or clinical trial safety feeds) requires zero changes to `raxtik-etl`:

1. Implement `raxtik_etl.sources.protocol.SourceAdapter`:
```python
from raxtik_etl.sources.protocol import SourceAdapter, SourceArtifact, SourceLoadResult
import duckdb


class MyCustomSourceAdapter:
    source_name: str = "my_pv_source"

    def extract_and_load(
        self, con: duckdb.DuckDBPyConnection, artifact: SourceArtifact
    ) -> SourceLoadResult:
        # 1. Extract raw files from artifact.path
        # 2. Project raw records into canonical staging tables:
        #    demo, drug, reac, outc, indi, ther, rpsr
        # 3. Return SourceLoadResult with row counts and provenance metadata
        ...
```

2. Register the entry point in your package's `pyproject.toml`:
```toml
[project.entry-points."raxtik_etl.sources"]
my_pv_source = "my_package.adapter:MyCustomSourceAdapter"
```

3. `raxtik-etl` will automatically discover and load the adapter:
```bash
raxtik-etl build-package --source my_pv_source --release 2024Q1 --zip-path /path/to/archive.zip
```

---

## 🧪 Testing & Code Quality

Run tests across the canonical engine:

```bash
# Run pytest test suite (25 unit and audit tests)
pytest tests/ -v

# Run linting and formatting
ruff check .
ruff format .
```

---

## 📚 Documentation & Guides

- [2004Q1 Dataset Integration & Usage Guide](docs/guides/2004q1_usage_guide.md): Downstream synthetic generation recipes for `vigilforms-data`.
- [FDA FAERS Official Data Dictionary](docs/fda_faers_official_data_dictionary.md): Field references across S1, S2, and S3 eras.
- [Historical Schema Evolution Audit](docs/schema/historical_schema_audit.md): Longitudinal schema analysis from 2004Q1 to 2026Q2.

---

## 📄 License

Licensed under the **[GNU Affero General Public License v3.0 (AGPL-3.0)](./LICENSE)**.
