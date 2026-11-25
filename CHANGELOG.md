# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0.dev3] - 2026-11-25

**Full Changelog**: https://github.com/raxtik-org/raxtik-etl/compare/v0.1.0.dev2...v0.1.0.dev3

### ✨ Added
- **Silver Tier Derived Deduplication Index (`raxtik_etl.indexing`)**: tier-agnostic append-only quarterly/annual ledgers, deterministic 16-shard hybrid base + delta state snapshots (`md5_u32` partitioning), automatic delta compaction, and SHA-256 period fingerprinting for idempotent re-runs.
- **Silver Query Middleware & SDK**: `tier="silver"` support in `BaseDataset` / `Dataset.from_hf()` (local, cached, and `remote=True`), `as_of_period` point-in-time queries, `case_timeline()`, and `materialize_tier()` for exporting filtered DuckDB packages.
- **Index CLI (`raxtik-etl index`)**: `build` (with `--cleanup-bronze`), `update`, `compact`, `verify` (full-rebuild bit-for-bit integrity check), `lookup`, and `upload` (with optimistic concurrency check and `--tag` / `--force` Hugging Face tagging).
- Experimental free-threaded Python `3.14t` CI job on Ubuntu and expanded test coverage (71%).

### 🐛 Fixed
- Preserved `NULL` / blank `CASEID` submissions via deterministic `REPORT:<primary_id>` fallback instead of dropping rows.
- Added `data_period DESC` total-order tie-breaker for cross-quarter republished `primary_id` records.
- Updated DuckDB `list_filter` expressions to DuckDB 2.0+ `lambda x:` syntax.
- Hardened `package_format_version` validation (`1.x`), raised `NotImplementedError` on `verify_checksum()` in remote mode, and fixed `_metadata` column insertion during materialization.

## [0.1.0.dev2] - 2026-11-19

**Full Changelog**: https://github.com/raxtik-org/raxtik-etl/compare/v0.1.0.dev1...v0.1.0.dev2

### Fixed
- Hardened `BaseDataset` DuckDB cursor draining using `fetchall()` for out-of-the-box compatibility with DuckDB 2.0.0+.

## [0.1.0.dev1] - 2026-11-19

**Full Changelog**: https://github.com/raxtik-org/raxtik-etl/compare/v0.1.0.dev0...v0.1.0.dev1

### Added
- Remote DuckDB querying support over Hugging Face Hub via `httpfs` without requiring prior full-package downloads (`connect_remote_hf_duckdb`).

### Changed
- Decoupled source connector case resolution and analytical summary SQL hooks.
- Standardized schema negotiation contract (`supported_schema_versions`).
- Added extensible schema migration framework (`raxtik_etl.migrations`) with internal ledger.
- Added data exporter & connector base interface (`raxtik_etl.exporters`).
- Hardened quarterly package and cohort staging using atomic promotions.
- Hardened download verification with SHA-256 validation.

## [0.1.0.dev0] - 2026-10-25

### Initial Release
- Canonical 7-entity pharmacovigilance data engine and longitudinal deduplication.
- Decoupled `SourceAdapter` protocol for external connectors (`raxtik-source-faers`).
- Dual presentation packaging into DuckDB relational databases and Parquet shards.
- Zero-copy Python Safety SDK with Polars DataFrames (`FAERS`).
- Hugging Face Hub remote distribution client (zero-auth streaming downloads).
- Automated CI quality matrix across Python 3.11–3.15 and multi-OS runners.
