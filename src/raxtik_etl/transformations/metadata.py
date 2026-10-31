"""Self-describing Metadata, Dimensions, Data Quality Profiler (EDA Audit), and Registry Generator.

Populates the internal tables in every quarterly DuckDB package:
- _metadata: Release info, versions, timestamps, hashes
- _schema_registry: Complete column dictionary and transformation categories
- _schema_migrations: Migration ledger
- _data_quality_report: Automated EDA profiling (missingness %, outcome counts, totals)
- _source_files: File sizes, SHA-256 hashes, record counts
- Reference tables: _code_outcomes, _code_outcome_semantics, _code_roles, _code_occupations, _code_report_sources, _code_dechallenge, _code_rechallenge
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb

from raxtik_etl import __version__
from raxtik_etl.reference import RAXTIK_OUTCOME_SEMANTICS
from raxtik_etl.schema.registry import (
    CANONICAL_SCHEMA_VERSION,
    SCHEMA_REGISTRY,
)


def populate_package_metadata(
    con: duckdb.DuckDBPyConnection,
    data_period: str,
    signature_id: str,
    source_zip_path: Path,
    etl_version: Optional[str] = None,
    engine_version: Optional[str] = None,
    source_name: Optional[str] = None,
    source_version: Optional[str] = None,
    reference_tables: Optional[Dict[str, List[Any]]] = None,
    package_format_version: str = "1.0.0",
) -> None:
    """Creates and populates all internal metadata and reference code lookup tables in DuckDB.

    Installs the following internal diagnostic and contract tables:
    1. `_metadata`: Key-value manifest documenting package format version, canonical schema version,
       source versions, dataset licensing, and compilation timestamps.
    2. `_schema_registry`: Physical catalog registering all canonical entities, field definitions, data types,
       nullability constraints, origin classifications, and schema evolution categories.
    3. `_migrations`: Audit journal tracking applied schema evolution migrations.
    4. `_provenance`: High-level data lineage documenting upstream extract source files, signatures, and timestamps.
    5. `_data_quality_report`: Summary metrics capturing total records, deduplicated counts, and validation checks.
    6. `_source_files`: Inventory of raw archive files, byte sizes, and cryptographic SHA-256 digests.
    7. Reference lookup tables (`_code_*`) dynamically installed from the source adapter.
    8. `_code_outcome_semantics`: Universal clinical seriousness and severity hierarchy based on ICH E2B.

    Args:
        con: Active DuckDB database connection.
        data_period: Temporal coverage period identifier (e.g. '2004Q1').
        signature_id: Upstream physical extract header signature identifier (e.g. 'S1', 'S2', 'S3').
        source_zip_path: Filesystem path to the raw source archive zip file.
        etl_version: Transformation/pipeline logic version of the source adapter.
        engine_version: Software version of the raxtik-etl packaging engine.
        source_name: Identifier of the source connector (e.g. 'faers').
        source_version: Upstream connector library release version.
        reference_tables: Mapping of reference table names to codelist dataclass entries provided by the adapter.
        package_format_version: Version specification of the Raxtik package container format.

    Returns:
        None
    """
    actual_period = data_period.upper().strip()
    actual_engine_version = engine_version or __version__
    actual_etl_version = etl_version or CANONICAL_SCHEMA_VERSION
    actual_source_name = source_name or "faers"
    dataset_name = (
        "FDA_FAERS_AEMS"
        if actual_source_name.lower() == "faers"
        else f"{actual_source_name.upper()}_AEMS"
    )

    # 1. _metadata (Machine-readable Package Contract & Lineage)
    con.execute("""
        CREATE OR REPLACE TABLE _metadata (
            key VARCHAR PRIMARY KEY,
            value VARCHAR,
            description VARCHAR
        );
    """)
    metadata_entries = [
        ("dataset_name", dataset_name, "Adverse Event Reporting System Data Distribution"),
        ("data_period", actual_period, "Temporal extract period identifier"),
        (
            "package_format_version",
            package_format_version,
            "Raxtik Package Container Format Specification Version",
        ),
        ("source_name", actual_source_name, "Source data connector identifier"),
        (
            "source_version",
            source_version or "unknown",
            "Connector software library release version",
        ),
        ("source_schema_signature", signature_id, "Physical extract header signature"),
        ("canonical_schema_version", CANONICAL_SCHEMA_VERSION, "Raxtik Canonical Schema Version"),
        (
            "etl_version",
            actual_etl_version,
            "Transformation and pipeline logic version of data source",
        ),
        (
            "engine_version",
            actual_engine_version,
            "Software version of raxtik-etl packaging engine",
        ),
        ("built_at", datetime.now(timezone.utc).isoformat(), "Timestamp package was compiled"),
        (
            "source_data_license",
            "US Government Work / Public Domain (17 U.S.C. § 105)",
            "License of raw adverse event observations",
        ),
        (
            "package_license",
            "Open Data Commons Attribution License (ODC-By 1.0)",
            "License of compiled, structured relational dataset",
        ),
        ("code_license", "AGPL-3.0", "License of raxtik-etl transformation software"),
    ]
    con.executemany("INSERT INTO _metadata VALUES (?, ?, ?);", metadata_entries)

    # 2. _schema_registry
    con.execute("""
        CREATE OR REPLACE TABLE _schema_registry (
            field_name VARCHAR,
            entity VARCHAR,
            data_type VARCHAR,
            is_nullable BOOLEAN,
            value_origin VARCHAR,
            category VARCHAR,
            description VARCHAR,
            is_primary_key BOOLEAN,
            foreign_key VARCHAR,
            PRIMARY KEY (entity, field_name)
        );
    """)
    registry_rows = [
        (
            e.field_name,
            e.entity,
            e.data_type,
            e.is_nullable,
            e.value_origin.value,
            e.category.value,
            e.description,
            e.is_primary_key,
            e.foreign_key,
        )
        for e in SCHEMA_REGISTRY
    ]
    con.executemany(
        "INSERT INTO _schema_registry VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);", registry_rows
    )

    # 3. _schema_migrations
    con.execute("""
        CREATE OR REPLACE TABLE _schema_migrations (
            migration_id VARCHAR PRIMARY KEY,
            version VARCHAR,
            applied_at VARCHAR,
            description VARCHAR,
            source_name VARCHAR
        );
    """)
    con.execute(f"""
        INSERT INTO _schema_migrations VALUES (
            'M001_INITIAL_CANONICAL',
            '{CANONICAL_SCHEMA_VERSION}',
            '{datetime.now(timezone.utc).isoformat()}',
            'Initial canonical 7-table schema with dual presentation (reports/cases)',
            '{actual_source_name}'
        );
    """)

    # 4. Reference Tables (_code_*) & Raxtik Semantics
    _populate_reference_dimensions(con, reference_tables=reference_tables)

    def _scalar(sql: str, default: Any = 0) -> Any:
        row = con.execute(sql).fetchone()
        return row[0] if row is not None else default

    # 5. _data_quality_report (Automated EDA Profiling)
    total_reports = _scalar("SELECT COUNT(*) FROM demo;")
    total_cases = _scalar("SELECT COUNT(DISTINCT case_id) FROM demo;")
    total_drugs = _scalar("SELECT COUNT(*) FROM drug;")
    total_reactions = _scalar("SELECT COUNT(*) FROM reac;")
    total_outcomes = _scalar("SELECT COUNT(*) FROM outc;")

    missing_age_pct = _scalar("""
        SELECT ROUND(AVG(CASE WHEN reported_age IS NULL THEN 1.0 ELSE 0.0 END) * 100, 2) FROM demo;
    """)

    missing_sex_pct = _scalar("""
        SELECT ROUND(AVG(CASE WHEN reported_sex_code IS NULL OR reported_sex_code IN ('UNK', 'NS') THEN 1.0 ELSE 0.0 END) * 100, 2) FROM demo;
    """)

    death_outcomes = _scalar("""
        SELECT COUNT(*) FROM outc WHERE outcome_code = 'DE';
    """)

    hosp_outcomes = _scalar("""
        SELECT COUNT(*) FROM outc WHERE outcome_code = 'HO';
    """)

    con.execute("""
        CREATE OR REPLACE TABLE _data_quality_report (
            metric_name VARCHAR PRIMARY KEY,
            metric_value VARCHAR,
            metric_category VARCHAR,
            profiled_at VARCHAR
        );
    """)
    now_ts = datetime.now(timezone.utc).isoformat()
    quality_metrics = [
        ("total_reports", str(total_reports), "COUNTS", now_ts),
        ("total_unique_cases", str(total_cases), "COUNTS", now_ts),
        ("total_drug_entries", str(total_drugs), "COUNTS", now_ts),
        ("total_reactions", str(total_reactions), "COUNTS", now_ts),
        ("total_outcomes", str(total_outcomes), "COUNTS", now_ts),
        ("missing_age_percentage", f"{missing_age_pct}%", "MISSINGNESS", now_ts),
        ("missing_sex_percentage", f"{missing_sex_pct}%", "MISSINGNESS", now_ts),
        ("death_outcome_count", str(death_outcomes), "DISTRIBUTIONS", now_ts),
        ("hospitalization_outcome_count", str(hosp_outcomes), "DISTRIBUTIONS", now_ts),
    ]
    con.executemany("INSERT INTO _data_quality_report VALUES (?, ?, ?, ?);", quality_metrics)

    # 6. _source_files
    zip_sha256 = hashlib.sha256(source_zip_path.read_bytes()).hexdigest()
    con.execute("""
        CREATE OR REPLACE TABLE _source_files (
            filename VARCHAR PRIMARY KEY,
            byte_size BIGINT,
            sha256 VARCHAR,
            table_type VARCHAR,
            row_count BIGINT
        );
    """)
    con.execute(f"""
        INSERT INTO _source_files VALUES (
            '{source_zip_path.name}',
            {source_zip_path.stat().st_size},
            '{zip_sha256}',
            'RAW_ARCHIVE_ZIP',
            {total_reports}
        );
    """)


def _populate_reference_dimensions(
    con: duckdb.DuckDBPyConnection,
    reference_tables: Optional[Dict[str, List[Any]]] = None,
) -> None:
    """Installs reference codelist tables from source adapter and Raxtik semantic interpretation tables.

    Dynamically populates two categories of reference dimensions:
    1. Source-Provided Reference Tables (`_code_*`):
       Constructs physical lookup tables for all codelists supplied by the source adapter
       (e.g., `_code_roles`, `_code_outcomes`, `_code_occupations`, `_code_report_sources`,
       `_code_dechallenge`, `_code_rechallenge`). Each table contains primary key `code`,
       human-readable `label`, `definition`, and temporal validity windows (`valid_from`, `valid_to`).
    2. Raxtik Universal Clinical Semantics (`_code_outcome_semantics`):
       Installs agency-agnostic clinical severity hierarchies and ICH E2B seriousness categories
       mapped to patient outcomes, facilitating cross-source standardized pharmacovigilance analytics.

    Args:
        con: Active DuckDB database connection.
        reference_tables: Optional dictionary mapping physical table names (e.g. '_code_outcomes')
            to lists of ReferenceCodeEntry objects supplied by the source adapter.

    Returns:
        None
    """
    # 1. Source-Provided Reference Tables (_code_*)
    for table_name, entries in (reference_tables or {}).items():
        if not entries:
            continue
        con.execute(f"""
            CREATE OR REPLACE TABLE {table_name} (
                code VARCHAR PRIMARY KEY,
                label VARCHAR,
                definition VARCHAR,
                source_system VARCHAR,
                source_document VARCHAR,
                reference_version VARCHAR,
                valid_from VARCHAR,
                valid_to VARCHAR,
                is_active BOOLEAN
            );
        """)
        con.executemany(
            f"INSERT INTO {table_name} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
            [
                (
                    getattr(e, "code", getattr(e, "outcome_code", getattr(e, "role_code", ""))),
                    getattr(e, "label", getattr(e, "outcome_label", getattr(e, "role_label", ""))),
                    getattr(e, "definition", ""),
                    getattr(e, "source_system", ""),
                    getattr(e, "source_document", ""),
                    getattr(e, "reference_version", "1.0.0"),
                    getattr(e, "valid_from", ""),
                    getattr(e, "valid_to", None),
                    getattr(e, "is_active", True),
                )
                for e in entries
            ],
        )

    # 2. Raxtik-Derived Universal Clinical Semantics (_code_outcome_semantics)
    con.execute("""
        CREATE OR REPLACE TABLE _code_outcome_semantics (
            outcome_code VARCHAR PRIMARY KEY,
            is_serious BOOLEAN,
            ich_seriousness_category VARCHAR,
            severity_rank INTEGER,
            raxtik_semantics_version VARCHAR,
            semantic_source VARCHAR
        );
    """)
    con.executemany(
        "INSERT INTO _code_outcome_semantics VALUES (?, ?, ?, ?, ?, ?);",
        [
            (
                s.outcome_code,
                s.is_serious,
                s.ich_seriousness_category,
                s.severity_rank,
                s.raxtik_semantics_version,
                s.semantic_source,
            )
            for s in RAXTIK_OUTCOME_SEMANTICS
        ],
    )
