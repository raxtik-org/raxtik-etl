"""Base source adapter providing extensible defaults for source connectors.

Implements default lifecycle stubs, validation hooks, and helper methods
satisfying the SourceAdapter protocol. Source connectors (e.g. FAERS, VAERS)
can subclass BaseSourceAdapter and override only their dataset-specific methods.
"""

from __future__ import annotations

from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Collection,
    Dict,
    List,
    Mapping,
    Optional,
    Set,
    Union,
)

from raxtik_etl.schema.registry import CANONICAL_SCHEMA_VERSION
from raxtik_etl.sources.discovery import find_files_by_entity
from raxtik_etl.sources.protocol import SourceAdapter
from raxtik_etl.sources.temporal import normalize_quarter

if TYPE_CHECKING:
    from raxtik_etl.migrations.base import BaseMigration


class BaseSourceAdapter(SourceAdapter):
    """Abstract base adapter providing default implementations for SourceAdapter.

    Attributes:
        source_name: Standardized source identifier (e.g. 'faers', 'vaers').
        etl_version: Version of the ETL logic for this source connector.
        source_version: PyPI/library release version of the connector.
        supported_schema_versions: List of canonical schema versions supported.
    """

    source_name: str = "base"
    etl_version: str = "1.0.0"
    source_version: Optional[str] = None
    supported_schema_versions: List[str] = [CANONICAL_SCHEMA_VERSION]

    def supports_schema(self, schema_version: str) -> bool:
        """Checks if this source connector can produce the requested canonical schema version.

        Args:
            schema_version: Semantic canonical schema version (e.g. '1.0.0').

        Returns:
            True if supported, False otherwise.
        """
        return schema_version in self.supported_schema_versions

    def get_migrations(self) -> List[BaseMigration]:
        """Default implementation returning no migrations. Override if connector has migrations."""
        return []

    def get_summary_views_sql(self) -> Dict[str, str]:
        """Default implementation returning no pre-aggregated summary views. Override if applicable."""
        return {}

    def normalize_data_period(self, period_or_filename: Union[str, Path]) -> str:
        """Helper to normalize data period string (e.g. '2004q1' -> '2004Q1')."""
        return normalize_quarter(period_or_filename)

    def compute_sha256(self, filepath: Union[Path, str]) -> str:
        """Helper to compute streaming SHA-256 digest of a file."""
        from raxtik_etl.packaging.builder import compute_sha256

        return compute_sha256(filepath)

    def find_files_by_entity(
        self,
        directory: Union[Path, str],
        prefix_to_entity: Mapping[str, str],
        pattern: str = "*.txt",
    ) -> Dict[str, List[Path]]:
        """Helper to discover and categorize physical extract files by entity."""
        return find_files_by_entity(directory, prefix_to_entity, pattern=pattern)

    def validate_extract_file(
        self,
        file_path: Union[Path, str],
        required_columns: Optional[Collection[str]] = None,
        delimiter: str = "$",
    ) -> Set[str]:
        """Validates that extract file exists, is non-empty, and contains expected headers."""
        from raxtik_etl.sources.validation import validate_extract_file

        return validate_extract_file(
            file_path, required_columns=required_columns, delimiter=delimiter
        )
