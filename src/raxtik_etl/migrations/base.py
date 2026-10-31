"""Base classes for schema and view migrations.

Supports both canonical schema migrations (applicable across all sources) and
source-dependent migrations (e.g. FAERS-specific reference updates or derived views).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import duckdb


class BaseMigration(ABC):
    """Abstract base class for all schema migrations."""

    revision: str
    down_revision: Optional[str] = None
    source_name: Optional[str] = None  # None for canonical migrations, or 'faers', etc.
    description: str = ""

    @abstractmethod
    def upgrade(self, con: duckdb.DuckDBPyConnection) -> None:
        """Applies the migration forward to transform schema, reference data, or views.

        Args:
            con: Active DuckDB database connection.

        Returns:
            None
        """
        ...

    def downgrade(self, con: duckdb.DuckDBPyConnection) -> None:
        """(Optional) Rolls back the migration.

        Args:
            con: Active DuckDB database connection.

        Returns:
            None

        Raises:
            NotImplementedError: If migration does not implement downgrade operations.
        """
        raise NotImplementedError(f"Downgrade not implemented for migration '{self.revision}'")
