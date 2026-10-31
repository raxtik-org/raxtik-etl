"""Base interfaces and data structures for external data exporters and connectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import duckdb


@dataclass(slots=True)
class ExportResult:
    """Represents the outcome of exporting dataset tables to an external sink.

    Attributes:
        target_type: Format or technology type of the external sink (e.g. 'sqlite', 'postgres').
        destination: Filesystem path or connection URI where data was exported.
        exported_tables: List of canonical table names successfully exported.
        total_rows: Total count of records transferred across all exported tables.
        metadata: Additional diagnostic statistics or sink-specific execution properties.
    """

    target_type: str
    destination: str
    exported_tables: List[str]
    total_rows: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseExporter(ABC):
    """Abstract base class for exporting DuckDB canonical datasets to external data sources/sinks."""

    target_type: str

    @abstractmethod
    def export(
        self,
        con: duckdb.DuckDBPyConnection,
        destination: Any,
        tables: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> ExportResult:
        """Exports specified tables from DuckDB connection to the target datasource.

        Args:
            con: Active DuckDB connection containing tables to export.
            destination: Target path, file, or connection handle for exported data.
            tables: Optional list of table names to export. If omitted, exports all tables.
            **kwargs: Additional sink-specific options (e.g. chunk size, batch parameters).

        Returns:
            ExportResult detailing tables exported, total row counts, and target location.
        """
        ...
