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
from typing import Any

import duckdb

from raxtik_etl.reference import (
    FDA_DECHALLENGE_REFERENCE,
    FDA_OCCUPATIONS_REFERENCE,
    FDA_OUTCOMES_REFERENCE,
    FDA_RECHALLENGE_REFERENCE,
    FDA_REPORT_SOURCES_REFERENCE,
    FDA_ROLES_REFERENCE,
    RAXTIK_OUTCOME_SEMANTICS,
)
from raxtik_etl.schema.registry import (
    CANONICAL_SCHEMA_VERSION,
    CASE_RESOLUTION_VERSION,
    PACKAGE_FORMAT_VERSION,
    REFERENCE_DATA_VERSION,
    SCHEMA_REGISTRY,
)


def populate_package_metadata(
    con: duckdb.DuckDBPyConnection,
    release: str,
    signature_id: str,
    source_zip_path: Path,
    etl_version: str = "0.1.0",
):
    """Creates and populates all internal metadata and reference code lookup tables in DuckDB."""

    # 1. _metadata (Machine-readable Package Contract & Lineage)
    con.execute("""
        CREATE OR REPLACE TABLE _metadata (
            key VARCHAR PRIMARY KEY,
            value VARCHAR,
            description VARCHAR
        );
    """)
    metadata_entries = [
        ("dataset_name", "FDA_FAERS_AEMS", "FDA Adverse Event Reporting System Data Distribution"),
        ("release_quarter", release, "Quarterly extract release identifier"),
        (
            "package_format_version",
            PACKAGE_FORMAT_VERSION,
            "Raxtik Package Container Format Specification Version",
        ),
        ("source_schema_signature", signature_id, "Physical extract header signature (S1, S2, S3)"),
        ("canonical_schema_version", CANONICAL_SCHEMA_VERSION, "Raxtik Canonical Schema Version"),
        (
            "case_resolution_version",
            CASE_RESOLUTION_VERSION,
            "Latest Case Resolution Logic Version",
        ),
        (
            "reference_data_version",
            REFERENCE_DATA_VERSION,
            "Version of embedded FDA reference dictionaries",
        ),
        ("etl_version", etl_version, "Software version of raxtik-etl pipeline"),
        ("built_at", datetime.now(timezone.utc).isoformat(), "Timestamp package was compiled"),
        (
            "source_data_license",
            "US Government Work / Public Domain (17 U.S.C. § 105)",
            "License of raw FDA adverse event observations",
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
            s1_source_field VARCHAR,
            s2_source_field VARCHAR,
            s3_source_field VARCHAR,
            description VARCHAR
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
            e.s1_source_field,
            e.s2_source_field,
            e.s3_source_field,
            e.description,
        )
        for e in SCHEMA_REGISTRY
    ]
    con.executemany(
        "INSERT INTO _schema_registry VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);", registry_rows
    )

    # 3. _schema_migrations
    con.execute("""
        CREATE OR REPLACE TABLE _schema_migrations (
            migration_id VARCHAR PRIMARY KEY,
            version VARCHAR,
            applied_at VARCHAR,
            description VARCHAR
        );
    """)
    con.execute(f"""
        INSERT INTO _schema_migrations VALUES (
            'M001_INITIAL_CANONICAL',
            '{CANONICAL_SCHEMA_VERSION}',
            '{datetime.now(timezone.utc).isoformat()}',
            'Initial canonical 7-table schema with dual presentation (reports/cases)'
        );
    """)

    # 4. Official FDA Reference Tables (_code_*) & Raxtik Semantics
    _populate_reference_dimensions(con)

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


def _populate_reference_dimensions(con: duckdb.DuckDBPyConnection):
    """Installs official FDA CDER reference tables and Raxtik semantic interpretation tables."""

    # 1. Official FDA Outcomes Reference (_code_outcomes)
    con.execute("""
        CREATE OR REPLACE TABLE _code_outcomes (
            outcome_code VARCHAR PRIMARY KEY,
            outcome_label VARCHAR,
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
        "INSERT INTO _code_outcomes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
        [
            (
                e.code,
                e.label,
                e.definition,
                e.source_system,
                e.source_document,
                e.reference_version,
                e.valid_from,
                e.valid_to,
                e.is_active,
            )
            for e in FDA_OUTCOMES_REFERENCE
        ],
    )

    # 2. Raxtik-Derived Clinical Semantics (_code_outcome_semantics)
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

    # 3. Official FDA Drug Roles (_code_roles)
    con.execute("""
        CREATE OR REPLACE TABLE _code_roles (
            role_code VARCHAR PRIMARY KEY,
            role_label VARCHAR,
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
        "INSERT INTO _code_roles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
        [
            (
                e.code,
                e.label,
                e.definition,
                e.source_system,
                e.source_document,
                e.reference_version,
                e.valid_from,
                e.valid_to,
                e.is_active,
            )
            for e in FDA_ROLES_REFERENCE
        ],
    )

    # 4. Official FDA Reporter Occupations (_code_occupations)
    con.execute("""
        CREATE OR REPLACE TABLE _code_occupations (
            occupation_code VARCHAR PRIMARY KEY,
            occupation_label VARCHAR,
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
        "INSERT INTO _code_occupations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
        [
            (
                e.code,
                e.label,
                e.definition,
                e.source_system,
                e.source_document,
                e.reference_version,
                e.valid_from,
                e.valid_to,
                e.is_active,
            )
            for e in FDA_OCCUPATIONS_REFERENCE
        ],
    )

    # 5. Official FDA Report Sources (_code_report_sources)
    con.execute("""
        CREATE OR REPLACE TABLE _code_report_sources (
            report_source_code VARCHAR PRIMARY KEY,
            report_source_label VARCHAR,
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
        "INSERT INTO _code_report_sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
        [
            (
                e.code,
                e.label,
                e.definition,
                e.source_system,
                e.source_document,
                e.reference_version,
                e.valid_from,
                e.valid_to,
                e.is_active,
            )
            for e in FDA_REPORT_SOURCES_REFERENCE
        ],
    )

    # 6. Official FDA Dechallenge (_code_dechallenge)
    con.execute("""
        CREATE OR REPLACE TABLE _code_dechallenge (
            dechallenge_code VARCHAR PRIMARY KEY,
            dechallenge_label VARCHAR,
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
        "INSERT INTO _code_dechallenge VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
        [
            (
                e.code,
                e.label,
                e.definition,
                e.source_system,
                e.source_document,
                e.reference_version,
                e.valid_from,
                e.valid_to,
                e.is_active,
            )
            for e in FDA_DECHALLENGE_REFERENCE
        ],
    )

    # 7. Official FDA Rechallenge (_code_rechallenge)
    con.execute("""
        CREATE OR REPLACE TABLE _code_rechallenge (
            rechallenge_code VARCHAR PRIMARY KEY,
            rechallenge_label VARCHAR,
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
        "INSERT INTO _code_rechallenge VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
        [
            (
                e.code,
                e.label,
                e.definition,
                e.source_system,
                e.source_document,
                e.reference_version,
                e.valid_from,
                e.valid_to,
                e.is_active,
            )
            for e in FDA_RECHALLENGE_REFERENCE
        ],
    )
