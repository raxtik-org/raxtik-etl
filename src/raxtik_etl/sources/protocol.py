"""Source Adapter Protocol and Data Contracts for raxtik-etl.

Defines the decoupled source connector protocol. Connectors (e.g. raxtik-source-faers)
implement this protocol to extract raw data artifacts and stage them into canonical
DuckDB relations without raxtik-etl depending directly on source packages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

import duckdb


@dataclass(slots=True)
class SourceArtifact:
    """Represents an input data artifact (e.g., zip archive, folder, or API response)."""

    path: Path
    release: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SourceLoadResult:
    """Result returned by a source connector after extracting and staging into DuckDB."""

    source_name: str
    release: str
    signature_id: str
    source_files: List[Dict[str, Any]]
    reference_tables: Dict[str, List[Any]]  # Source-specific reference codelists
    row_counts: Dict[str, int]
    metadata: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class SourceAdapter(Protocol):
    """Protocol that all source connectors must satisfy."""

    source_name: str

    def extract_and_load(
        self, con: duckdb.DuckDBPyConnection, artifact: SourceArtifact
    ) -> SourceLoadResult:
        """Extracts source artifact and loads records into canonical DuckDB tables."""
        ...
