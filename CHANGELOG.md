# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0.dev1] - 2026-10-31

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
