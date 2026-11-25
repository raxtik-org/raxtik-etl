# CLI Reference

The `raxtik-etl` CLI offers tools for compiling quarterly archives, performing cross-quarter case deduplication, inspecting schema data quality, and managing packages.

---

## Commands Overview

| Command | Description |
|---|---|
| [`build`](#build) | Unified compilation command for single quarters or ranges, with automated downloading, packaging, and optional Hugging Face upload. |
| [`download`](#download) | Streams and downloads compiled packages from Hugging Face Hub (zero auth required). |
| [`upload`](#upload) | Uploads compiled DuckDB and Parquet packages to Hugging Face Hub (maintainers / custom repos). |
| [`inspect`](#inspect) | Displays metadata, schema signatures, and data quality indicators for packages or consolidated databases. |
| [`consolidate`](#consolidate) | Executes cross-quarter case deduplication and consolidates quarterly packages into a unified dataset. |
| [`index`](#index) | Builds, incrementally updates, compacts, verifies, queries, and publishes the Silver Tier derived deduplication index. |
| [`sources`](#sources) | Lists registered source connector plugins discovered via Python entry points (`raxtik_etl.sources`). |

---

## Detailed Command Specifications

### `build`

Compiles raw pharmacovigilance archives into standalone DuckDB databases and ZSTD-compressed Parquet directory shards. Handles both single quarters (via `-d`) and multi-quarter ranges (via `--start` and `--end`).

```text
Usage: raxtik-etl build [OPTIONS]

Options:
  -d, --data-period     <str>   Single quarter identifier (e.g. 2004Q1).
  --start               <str>   Starting quarter for range build (e.g. 2004Q1).
  --end                 <str>   Ending quarter for range build (e.g. 2026Q3).
  -s, --source          <str>   Source connector plugin [default: faers].
  -z, --zip-path        <path>  Path to explicit source archive (single quarter only).
  -o, --output-dir      <path>  Output package directory [default: ~/.cache/raxtik/packages].
  -f, --format          <str>   Package format: 'both', 'duckdb', or 'parquet' [default: both].
  --delete-ascii / --no-delete  Whether to delete extracted ASCII files after build [default: True].
  --upload / --no-upload        Upload completed packages to Hugging Face Hub [default: False].
  --clean-local                 Delete local package artifacts after upload [default: False].
  --batch-size-gb       <float> In-flight staging buffer threshold before upload flushing [default: 2.5].
  --repo-id             <str>   Hugging Face dataset repository ID [default: raxtik-org/faers-safety-database].
  --tag                 <str>   Git tag or revision for upload [default: v0.1.0.dev1].
  -t, --token           <str>   Hugging Face API token (defaults to HF_TOKEN env var).
  --help                        Show help and exit.
```

**Examples:**
```bash
# Build a single quarter
raxtik-etl build -d 2004Q1

# Batch build a range with upload and local disk cleanup (maintainers)
raxtik-etl build \
    --start 2004Q1 \
    --end 2026Q3 \
    --upload \
    --clean-local \
    --batch-size-gb 2.5 \
    --tag v0.1.0.dev1
```

---

### `download`

Downloads compiled DuckDB and Parquet packages from Hugging Face Hub directly into local cache.

```text
Usage: raxtik-etl download [OPTIONS]

Options:
  -d, --data-period, -n, --name <str>   Data period (e.g. 2004Q1) [required].
  -s, --source                  <str>   Source connector [default: faers].
  --repo-id                     <str>   Hugging Face dataset repo [default: raxtik-org/faers-safety-database].
  --dest-dir                    <path>  Destination folder [default: ~/.cache/raxtik/packages].
  -f, --force                           Force re-download even if already present.
  --help                                Show help and exit.
```

**Example:**
```bash
raxtik-etl download -d 2004Q1
```

---

### `upload`

Uploads locally compiled quarterly packages to Hugging Face Hub under the structured bronze directory hierarchy (`bronze/<YEAR>/`).

> [!NOTE]
> Standard users and researchers do not need this command. The official packages are already hosted at [raxtik-org/faers-safety-database](https://huggingface.co/datasets/raxtik-org/faers-safety-database). Use `upload` only if you maintain a custom dataset build or fork.

```text
Usage: raxtik-etl upload [OPTIONS]

Options:
  -d, --data-period        <str>   Single quarter (e.g. 2004Q1) or range (e.g. 2004Q1..2006Q4).
  --start                  <str>   Starting quarter for batch upload.
  --end                    <str>   Ending quarter for batch upload.
  -s, --source             <str>   Source connector [default: faers].
  -p, --package-dir        <path>  Directory containing compiled packages [default: ~/.cache/raxtik/packages].
  --repo-id                <str>   Hugging Face dataset repository [default: raxtik-org/faers-safety-database].
  -t, --token              <str>   Hugging Face write token (defaults to HF_TOKEN env var).
  --tag                    <str>   Release tag to associate with upload.
  --clean-local                    Remove local files after successful upload.
  --parquet / --no-parquet         Upload Parquet table shards alongside DuckDB [default: True].
  --help                           Show help and exit.
```

---

### `inspect`

Inspects a quarterly package or consolidated dataset, printing metadata, canonical record counts, and data quality indicators.

```text
Usage: raxtik-etl inspect [OPTIONS]

Options:
  -d, --data-period <str>   Quarterly data period identifier (e.g. 2004Q1).
  -s, --source      <str>   Source connector [default: faers].
  -p, --package-dir <path>  Directory containing package files.
  --db-path         <path>  Direct path to DuckDB database file.
  --help                    Show help and exit.
```

---

### `consolidate`

Executes cross-quarter case deduplication and reconciles multi-version follow-up reports across multiple quarters into a unified consolidated database.

```text
Usage: raxtik-etl consolidate [OPTIONS]

Options:
  --start          <str>   Starting period (e.g. 2004Q1).
  --end            <str>   Ending period (e.g. 2006Q4).
  -s, --source     <str>   Source connector name [default: faers].
  -p, --package-dir<path>  Directory containing input packages.
  -n, --output-name<str>   Output database base name [default: faers_2004_2006_consolidated].
  -o, --output-dir <path>  Destination directory [default: ~/.cache/raxtik/packages].
  --help                   Show help and exit.
```

---

### `index`

Manages the tier-agnostic derived deduplication index (`silver/index/`) built from immutable Bronze packages.

| Subcommand | Description |
|---|---|
| `raxtik-etl index build` | Deterministically builds a fresh immutable base snapshot across a range (`--start`, `--end`, optional `--cleanup-bronze`, `--overwrite`, `--shards`). |
| `raxtik-etl index update` | Incrementally ingests a single `--data-period` as a complete-state delta (idempotent via SHA-256 fingerprint; auto-compacts at 4 deltas; `--replace-period` to reprocess historical quarters). |
| `raxtik-etl index compact` | Compacts completed annual ledgers (`YYYY.parquet`) and merges active deltas into a fresh immutable base snapshot. |
| `raxtik-etl index verify` | Rebuilds canonical state from ledgers and verifies bit-for-bit logical equality shard-by-shard (`EXCEPT ALL`). |
| `raxtik-etl index lookup` | Prints the full multi-quarter submission timeline and winning report for `--case-id`. |
| `raxtik-etl index upload` | Publishes `{tier}/index/` to Hugging Face Hub in a single commit with optimistic concurrency checking and optional `--tag` / `--force`. |

**Examples:**
```bash
# Build full 91-quarter Silver index with automatic Bronze cleanup
raxtik-etl index build --source faers --tier silver --start 2004Q1 --end 2026Q3 --cleanup-bronze

# Incrementally add a new quarter
raxtik-etl index update --data-period 2026Q4 --source faers --tier silver

# Verify integrity & look up a case timeline
raxtik-etl index verify --source faers --tier silver
raxtik-etl index lookup --case-id 12345678 --source faers --tier silver

# Publish to Hugging Face Hub and attach a release tag
export HF_TOKEN="hf_..."
raxtik-etl index upload --source faers --tier silver --tag v0.1.0
```

---

### `sources`

Lists all installed and discovered pharmacovigilance source adapters.

```text
Usage: raxtik-etl sources [OPTIONS]
```
