# CLI Reference

The `raxtik-etl` CLI offers tools for compiling quarterly archives, performing longitudinal deduplication, and distributing packages via Hugging Face Hub.

---

## Commands Overview

| Command | Description |
|---|---|
| [`build-package`](#build-package) | Compiles a standalone DuckDB and Parquet package for a single quarterly release. |
| [`batch-build`](#batch-build) | Batch compiles packages for a continuous range of periods. |
| [`consolidate`](#consolidate) | Executes cross-period case deduplication and consolidates packages into a unified dataset. |
| [`inspect-package`](#inspect-package) | Displays metadata and data quality report for a single quarterly package. |
| [`inspect-consolidation`](#inspect-consolidation) | Displays reconciliation metrics for a consolidated multi-period package. |
| [`hf-download`](#hf-download) | Publicly streams and downloads compiled packages from Hugging Face Hub (zero auth). |
| [`hf-upload`](#hf-upload) | Uploads compiled DuckDB and Parquet packages to Hugging Face Hub (requires token). |

---

## Detailed Command Specifications

### `build-package`

```text
Usage: raxtik-etl build-package [OPTIONS]

Options:
  -s, --source      <str>   Source connector name [default: faers]
  -d, --data-period <str>   Quarterly data period identifier (e.g. 2004Q1) [default: 2004Q1]
  -z, --zip-path    <path>  Path to source archive/zip file
  -o, --output-dir  <path>  Destination package directory [default: data/packages]
  -f, --format      <str>   Package format: 'both', 'duckdb', or 'parquet' [default: both]
  --help                    Show help and exit.
```

### `batch-build`

```text
Usage: raxtik-etl batch-build [OPTIONS]

Options:
  --start          <str>   Starting data period (e.g. 2004Q1) [default: 2004Q1]
  --end            <str>   Ending data period (e.g. 2006Q4) [default: 2006Q4]
  -s, --source     <str>   Source connector name [default: faers]
  -o, --output-dir <path>  Destination directory [default: data/packages]
  --help                   Show help and exit.
```

### `consolidate`

```text
Usage: raxtik-etl consolidate [OPTIONS]

Options:
  --start          <str>   Starting period (e.g. 2004Q1) [default: 2004Q1]
  --end            <str>   Ending period (e.g. 2006Q4) [default: 2006Q4]
  -p, --package-dir<path>  Directory containing packages [default: data/packages]
  -n, --output-name<str>   Output database name [default: faers_2004_2006_consolidated]
  -o, --output-dir <path>  Destination directory [default: data/packages]
  --help                   Show help and exit.
```

### `inspect-package`

```text
Usage: raxtik-etl inspect-package [OPTIONS]

Options:
  -d, --data-period <str>   Quarterly data period identifier [default: 2004Q1]
  -p, --package-dir <path>  Directory containing package files
  --help                    Show help and exit.
```

### `inspect-consolidation`

```text
Usage: raxtik-etl inspect-consolidation [OPTIONS]

Options:
  -d, --db-path    <path>  Path to consolidated DuckDB package [default: data/packages/faers_2004_2006_consolidated.duckdb]
  --help                   Show help and exit.
```

### `hf-download`

```text
Usage: raxtik-etl hf-download [OPTIONS]

Options:
  -d, --data-period, -n, --name <str>   Data period or package name (e.g. 2004Q1) [default: 2004Q1]
  --repo-id                     <str>   Hugging Face dataset repo [default: raxtik-org/faers-safety-database]
  --dest-dir                    <path>  Destination folder [default: data/packages]
  -f, --force                           Overwrite existing local file
  --help                                Show help and exit.
```

### `hf-upload`

```text
Usage: raxtik-etl hf-upload [OPTIONS]

Options:
  -d, --data-period        <str>   Data period (e.g. 2004Q1) or range (e.g. 2007Q1..2026Q1)
  --start                  <str>   Starting quarter for batch upload
  --end                    <str>   Ending quarter for batch upload
  --repo-id                <str>   Hugging Face dataset repo [default: raxtik-org/faers-safety-database]
  -p, --package-dir        <path>  Directory containing packages [default: data/packages]
  -t, --token              <str>   Hugging Face write token (defaults to HF_TOKEN env var)
  --parquet/--no-parquet           Whether to include Parquet shards [default: True]
  --help                           Show help and exit.
```
