# CLI Reference

The `raxtik-etl` CLI offers tools for compiling quarterly archives, performing longitudinal deduplication, and distributing packages via Hugging Face Hub.

---

## Commands Overview

| Command | Description |
|---|---|
| [`build-package`](#build-package) | Compiles a standalone DuckDB and Parquet package for a single quarterly release. |
| [`build-cohort`](#build-cohort) | Batch compiles packages for a continuous range of quarters. |
| [`merge-cohort`](#merge-cohort) | Executes cross-quarter case deduplication and merges quarters into a unified dataset. |
| [`inspect-package`](#inspect-package) | Displays metadata and data quality report for a single quarterly package. |
| [`inspect-cohort`](#inspect-cohort) | Displays reconciliation metrics for a merged longitudinal cohort. |
| [`hf-download`](#hf-download) | Publicly streams and downloads compiled packages from Hugging Face Hub (zero auth). |
| [`hf-upload`](#hf-upload) | Uploads compiled DuckDB and Parquet packages to Hugging Face Hub (requires token). |

---

## Detailed Command Specifications

### `build-package`

```text
Usage: raxtik-etl build-package [OPTIONS]

Options:
  -s, --source     <str>   Source connector name [default: faers]
  -r, --release    <str>   Quarter release identifier (e.g. 2004Q1) [default: 2004Q1]
  -z, --zip-path   <path>  Path to source archive/zip file
  -o, --output-dir <path>  Destination package directory [default: data/packages]
  --help                   Show help and exit.
```

### `build-cohort`

```text
Usage: raxtik-etl build-cohort [OPTIONS]

Options:
  --start          <str>   Starting quarter (e.g. 2004Q1) [default: 2004Q1]
  --end            <str>   Ending quarter (e.g. 2006Q4) [default: 2006Q4]
  -s, --source     <str>   Source connector name [default: faers]
  -o, --output-dir <path>  Destination directory [default: data/packages]
  --help                   Show help and exit.
```

### `merge-cohort`

```text
Usage: raxtik-etl merge-cohort [OPTIONS]

Options:
  --start          <str>   Starting quarter (e.g. 2004Q1) [default: 2004Q1]
  --end            <str>   Ending quarter (e.g. 2006Q4) [default: 2006Q4]
  -p, --package-dir<path>  Directory containing quarterly packages [default: data/packages]
  -n, --output-name<str>   Output database name [default: faers_2004_2006_merged]
  -o, --output-dir <path>  Destination directory [default: data/packages]
  --help                   Show help and exit.
```

### `inspect-package`

```text
Usage: raxtik-etl inspect-package [OPTIONS]

Options:
  -r, --release    <str>   Quarter release identifier [default: 2004Q1]
  -p, --package-dir<path>  Directory containing package files
  --help                   Show help and exit.
```

### `inspect-cohort`

```text
Usage: raxtik-etl inspect-cohort [OPTIONS]

Options:
  -d, --db-path    <path>  Path to merged DuckDB package [default: data/packages/faers_2004_2006_merged.duckdb]
  --help                   Show help and exit.
```

### `hf-download`

```text
Usage: raxtik-etl hf-download [OPTIONS]

Options:
  -r, --release    <str>   Release identifier (e.g. 2004Q1) [default: 2004Q1]
  --repo-id        <str>   Hugging Face dataset repo [default: vigilforms/faers-safety-database]
  -d, --dest-dir   <path>  Destination folder [default: data/packages]
  -f, --force              Overwrite existing local file
  --help                   Show help and exit.
```

### `hf-upload`

```text
Usage: raxtik-etl hf-upload [OPTIONS]

Options:
  -r, --release    <str>   Release identifier (e.g. 2004Q1) [default: 2004Q1]
  --repo-id        <str>   Hugging Face dataset repo [default: vigilforms/faers-safety-database]
  -p, --package-dir<path>  Directory containing packages [default: data/packages]
  -t, --token      <str>   Hugging Face write token (defaults to HF_TOKEN env var)
  --parquet/--no-parquet   Whether to include Parquet shards [default: True]
  --help                   Show help and exit.
```
