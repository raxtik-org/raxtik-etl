"""Source Adapter Protocol and Data Contracts for raxtik-etl.

Defines the decoupled source connector protocol. Connectors (e.g. raxtik-source-faers)
implement this protocol to extract raw data artifacts and stage them into canonical
DuckDB relations without raxtik-etl depending directly on source packages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol, runtime_checkable

import duckdb

if TYPE_CHECKING:
    from raxtik_etl.migrations.base import BaseMigration


@dataclass(slots=True)
class SourceArtifact:
    """Represents an input data artifact provided to a source adapter.

    Attributes:
        path: Local filesystem path to the raw source data file, zip archive, or directory.
        data_period: The temporal coverage period of the data extract (e.g., calendar quarter
            '2004Q1' for FAERS, calendar year '2024' for VAERS, or 'full').
        target_schema_version: Target canonical schema version to compile into (e.g., '1.0.0').
        metadata: Additional source-specific extraction context or configuration options
            (e.g. custom encoding, delimiter override).
    """

    path: Path
    data_period: Optional[str] = None
    target_schema_version: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SourceLoadResult:
    """Result returned by a source connector after extracting and staging into DuckDB.

    Attributes:
        source_name: Standardized source identifier (e.g. 'faers', 'vaers').
        data_period: The temporal coverage period corresponding to the loaded records (e.g., '2004Q1').
        signature_id: Identifier for the physical file format or schema variant detected
            in the raw extract (e.g. 'S1_LEGACY_ASCII', 'CSV_V2').
        source_files: Metadata list of source files parsed, including individual row counts and file sizes.
        reference_tables: Lookup/codelist tables provided by the source (e.g. '_code_roles', '_code_outcomes')
            to be materialized alongside fact tables in DuckDB.
        row_counts: Mapping of canonical table names (e.g. 'demo', 'drug') to loaded row counts.
        schema_version: Canonical schema version produced by the loader (defaults to '1.0.0').
        metadata: Provenance metadata, parser statistics, or license declarations.
    """

    source_name: str
    data_period: str
    signature_id: str
    source_files: List[Dict[str, Any]]
    reference_tables: Dict[str, List[Any]]  # Source-specific reference codelists
    row_counts: Dict[str, int]
    schema_version: str = "1.0.0"
    metadata: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class SourceAdapter(Protocol):
    """Protocol that all source connectors must satisfy.

    Attributes:
        source_name: Machine-readable lowercase identifier of the data source (e.g., 'faers', 'vaers').
        etl_version: Version of the data extraction, transformation, normalization, and deduplication
            pipeline logic for this source (e.g. '1.0.0'). This is independent of the connector's
            PyPI release version.
        source_version: (Optional) Semantic version of the connector software library (e.g., '0.1.0').
        supported_schema_versions: List of canonical schema versions this adapter can output (e.g. ['1.0.0']).
    """

    source_name: str
    etl_version: str
    supported_schema_versions: List[str]
    source_version: Optional[str] = None

    def supports_schema(self, schema_version: str) -> bool:
        """Checks if this source connector can produce the requested canonical schema version.

        Args:
            schema_version: Semantic canonical schema version (e.g. '1.0.0').

        Returns:
            True if supported, False otherwise.
        """
        ...

    def extract_and_load(
        self, con: duckdb.DuckDBPyConnection, artifact: SourceArtifact
    ) -> SourceLoadResult:
        """Extracts source artifact and loads records into canonical DuckDB tables.

        Args:
            con: Active DuckDB database connection.
            artifact: SourceArtifact instance specifying file location and metadata.

        Returns:
            SourceLoadResult containing loaded counts, signature, and reference codelists.
        """
        ...

    def fetch_archive(self, data_period: str, dest_dir: Path) -> Path:
        """(Optional) Downloads or discovers raw archive for the given data period.

        Args:
            data_period: Temporal coverage period (e.g. '2004Q1').
            dest_dir: Destination folder for downloaded archive.

        Returns:
            Path to downloaded archive file or directory.
        """
        ...

    def get_case_resolution_sql(self) -> str:
        """Returns SQL that resolves latest/authoritative cases per unique case ID.

        Returns:
            DDL SQL string (e.g. CREATE OR REPLACE VIEW cases AS ...).
        """
        ...

    def get_case_lineage_sql(self) -> str:
        """Returns SQL creating the 'case_lineage' table tracking follow-up counts and timeline.

        Returns:
            DDL SQL string creating case_lineage table.
        """
        ...

    def get_summary_views_sql(self) -> Dict[str, str]:
        """Returns mapping of view_name -> SQL for pre-aggregated analytical views.

        Returns:
            Mapping of view names to their corresponding CREATE VIEW SQL statements.
        """
        ...

    def get_migrations(self) -> List[BaseMigration]:
        """(Optional) Returns source-specific schema migration scripts.

        Returns:
            List of BaseMigration instances specific to this source.
        """
        ...
