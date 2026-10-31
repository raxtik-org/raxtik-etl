# Architecture

`raxtik-etl` is a canonical pharmacovigilance data engine and packaging toolkit. It separates source-specific data extraction from canonical schemas, case deduplication, packaging, and querying.

---

## 1. Design & Separation of Concerns

The architecture separates responsibilities into three distinct layers:

- **Source Connectors** (e.g. `raxtik-source-faers`): Downloads raw files, handles source-specific parsing quirks, and maps them into canonical staging tables.
- **Canonical Engine** (`raxtik-etl`): Enforces the 7 canonical schemas, compiles the authoritative deduplication views, and packages standalone `.duckdb` and `.parquet` files.
- **Consumer Query Client** (`Dataset`): Reads precompiled packages in read-only mode, providing zero-copy Polars DataFrames and automated Hugging Face Hub streaming.

---

## 2. The Two Operating Modes

### Mode A: Querying Precompiled Data (Consumer Mode)
Data scientists and analysts querying packages only need `raxtik-etl`. They do not need raw source archives or parsing tools:

```python
from raxtik_etl import Dataset

# Automatically streams from Hugging Face Hub to ~/.cache/raxtik/packages
with Dataset.from_hf("2004Q1", source="faers") as ds:
    cases = ds.cases(limit=100)
    print(cases)
```

### Mode B: Building Packages from Raw Files (ETL Pipeline Mode)
Maintainers and pipeline runners compiling raw archives install `raxtik-etl` alongside the appropriate source plugin (such as `raxtik-source-faers`):

```bash
raxtik-etl build-package \
    --source faers \
    --data-period 2004Q1 \
    --zip-path data/raw/archives_cache/2004q1_ascii.zip \
    --output-dir data/packages
```

---

## 3. Extensible Plugin System

`raxtik-etl` contains zero source-specific proprietary parsing logic. Connectors plug into the engine using Python entry points:

### Source Adapter Protocol (`raxtik_etl.sources`)
Any source plugin implements `SourceAdapter`:

```python
from pathlib import Path
from typing import Any, Dict, List
import duckdb
from raxtik_etl.sources.protocol import SourceAdapter, SourceArtifact, SourceLoadResult


class CustomSourceAdapter(SourceAdapter):
    source_name: str = "custom_pv"
    supported_schema_versions: List[str] = ["1.0.0"]

    def supports_schema(self, schema_version: str) -> bool:
        return schema_version in self.supported_schema_versions

    def extract_and_load(
        self, con: duckdb.DuckDBPyConnection, artifact: SourceArtifact
    ) -> SourceLoadResult:
        # 1. Parse raw files from artifact.path
        # 2. Populate canonical tables in `con`: demo, drug, reac, outc, indi, ther, rpsr
        # 3. Return SourceLoadResult with row counts and provenance metadata
        ...

    def get_case_resolution_sql(self) -> str:
        # Deduplication rule for unique cases
        ...

    def get_case_lineage_sql(self) -> str:
        # Longitudinal submission history tracking
        ...

    def get_summary_views_sql(self) -> Dict[str, str]:
        # Analytical views with non-fanout pre-aggregation
        ...
```

Registered in `pyproject.toml`:
```toml
[project.entry-points."raxtik_etl.sources"]
custom_pv = "custom_package.adapter:CustomSourceAdapter"
```

### Specialized Client Protocol (`raxtik_etl.clients`)
Plugins can also register specialized client classes that subclass `BaseDataset`:

```toml
[project.entry-points."raxtik_etl.clients"]
faers = "raxtik_source_faers:FAERS"
```

When a user calls `Dataset(release="2004Q1", source="faers")`, the engine automatically instantiates the registered `FAERS` client. If no specialized client is registered, it falls back to `BaseDataset`.

---

## 4. The Canonical Data Model

Every source connector projects raw records into 7 canonical fact tables:

| Table | Entity | Primary Keys | Key Standardized Fields |
| :--- | :--- | :--- | :--- |
| **`demo`** | Case reports & demographics | `primary_id`, `case_id` | `standard_age_years`, `standard_sex_label`, `event_date`, `reporter_country` |
| **`drug`** | Drug exposures & regimens | `primary_id`, `drug_seq` | `reported_drug_name`, `standard_role_label` (`PS`, `SS`, `C`, `I`), `route`, `dose_amt` |
| **`reac`** | Adverse events / reactions | `primary_id`, `pt` | `pt` (MedDRA Preferred Term) |
| **`outc`** | Patient clinical outcomes | `primary_id`, `outc_code` | `outc_code`, `standard_outc_label` (`DE`, `HO`, `LT`, `DS`, `CA`, `RI`, `OT`) |
| **`indi`** | Therapy indications | `primary_id`, `indi_pt` | `indi_drug_seq`, `indi_pt` |
| **`ther`** | Therapy durations | `primary_id`, `dsg_drug_seq` | `start_date`, `end_date`, `duration_days` |
| **`rpsr`** | Report sources | `primary_id`, `rpsr_code` | `rpsr_code`, `standard_rpsr_label` |

### Authoritative Case View (`cases`)
A single adverse event case may receive multiple follow-up submissions across quarters. In addition to the immutable submission records in `demo`, each package includes a deterministic view:
- **`cases`**: Deduplicates by `case_id`, selecting the latest version based on version numbers and report dates (`canonical_case_version`, `fda_date`). It pre-computes flags like `has_serious_outcome` and `is_death`.

---

## 5. Schema Migrations & Version Upgrades

DuckDB packages include an internal ledger (`_schema_migrations` table) tracking applied revisions:

- **`raxtik_etl.migrations.BaseMigration`**: Base class for linear schema migrations. Supports both **canonical migrations** (affecting all datasets) and **source-dependent migrations** (affecting only a specific source connector).
- **`MigrationManager`**: Checks applied revisions and executes pending upgrades within transactions.

---

## 6. External Datasource Exporters & Connectors

The `raxtik_etl.exporters` module provides extensible interfaces for exporting canonical DuckDB data into downstream environments:

- **`BaseExporter`**: Abstract contract for exporting tables to external databases or formats (`export(con, destination, tables)`).
- **Extensible Architecture**: Designed for frictionless expansion to SQLite, Parquet, Arrow, and remote relational warehouses.

---

## 7. Storage & Caching Layout

### Package Structure
Each quarterly build creates two complementary presentation formats in the output directory:
- **`{source}_{release}.duckdb`**: Standalone indexed database containing all 7 fact tables, the `cases` view, and internal metadata (`_metadata`, `_schema_registry`, `_data_quality_report`, `_source_files`, `_code_*`).
- **`{source}_{release}.parquet/`**: Partitioned directory containing ZSTD-compressed Parquet files for each canonical table (`demo.parquet`, `drug.parquet`, etc.).

### Central Cache Location
When streaming packages from Hugging Face Hub using `Dataset.from_hf()`, packages are cached centrally in:
```text
~/.cache/raxtik/packages/{source}_{release}.duckdb
```
The cache location can be overridden using the `RAXTIK_CACHE_DIR` environment variable or the `package_dir` parameter.
