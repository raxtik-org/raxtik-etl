"""Schema Migration Manager for DuckDB packages.

Manages migration registration, ledger tracking (_schema_migrations table),
and linear execution for canonical and source-dependent migrations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

import duckdb

from raxtik_etl.migrations.base import BaseMigration


class MigrationManager:
    """Discovers, tracks, and applies schema migrations across DuckDB packages."""

    def __init__(self) -> None:
        self._canonical_migrations: Dict[str, BaseMigration] = {}
        self._source_migrations: Dict[str, Dict[str, BaseMigration]] = {}

    def register(self, migration: BaseMigration) -> None:
        """Registers a migration into the engine.

        Args:
            migration: BaseMigration instance to register.
        """
        if migration.source_name:
            source = migration.source_name.lower()
            if source not in self._source_migrations:
                self._source_migrations[source] = {}
            self._source_migrations[source][migration.revision] = migration
        else:
            self._canonical_migrations[migration.revision] = migration

    @staticmethod
    def init_migration_table(con: duckdb.DuckDBPyConnection) -> None:
        """Ensures the _schema_migrations tracking table exists in the DuckDB database.

        Args:
            con: Active DuckDB database connection.
        """
        con.execute("""
            CREATE TABLE IF NOT EXISTS _schema_migrations (
                migration_id VARCHAR PRIMARY KEY,
                version VARCHAR,
                applied_at VARCHAR,
                description VARCHAR,
                source_name VARCHAR
            );
        """)

    @staticmethod
    def get_applied_revisions(con: duckdb.DuckDBPyConnection) -> List[str]:
        """Returns list of already applied migration revision IDs.

        Args:
            con: Active DuckDB database connection.

        Returns:
            List of applied migration IDs ordered chronologically by application timestamp.
        """
        MigrationManager.init_migration_table(con)
        rows = con.execute(
            "SELECT migration_id FROM _schema_migrations ORDER BY applied_at ASC"
        ).fetchall()
        return [r[0] for r in rows]

    @staticmethod
    def record_migration(
        con: duckdb.DuckDBPyConnection,
        revision: str,
        source_name: Optional[str] = None,
        description: str = "",
        version: Optional[str] = None,
    ) -> None:
        """Records an applied migration in the ledger.

        Args:
            con: Active DuckDB database connection.
            revision: Migration revision identifier.
            source_name: Optional connector name for source-specific migrations.
            description: Description of schema migration changes.
            version: Target version string.
        """
        MigrationManager.init_migration_table(con)
        con.execute(
            """
            INSERT OR REPLACE INTO _schema_migrations (migration_id, version, applied_at, description, source_name)
            VALUES (?, ?, ?, ?, ?);
            """,
            (
                revision,
                version or revision,
                datetime.now(timezone.utc).isoformat(),
                description,
                source_name,
            ),
        )

    def apply_pending_migrations(
        self,
        con: duckdb.DuckDBPyConnection,
        source_name: Optional[str] = None,
    ) -> List[str]:
        """Applies all registered pending migrations in linear order.

        Args:
            con: Active DuckDB database connection.
            source_name: Optional connector name for applying source-specific migrations.

        Returns:
            List of newly applied migration revision IDs.
        """
        self.init_migration_table(con)
        applied = set(self.get_applied_revisions(con))
        newly_applied: List[str] = []

        # 1. Apply pending canonical migrations
        for rev, mig in self._canonical_migrations.items():
            if rev not in applied:
                mig.upgrade(con)
                self.record_migration(
                    con,
                    revision=rev,
                    source_name=None,
                    description=mig.description,
                    version=rev,
                )
                applied.add(rev)
                newly_applied.append(rev)

        # 2. Apply pending source-specific migrations if applicable
        if source_name:
            source_key = source_name.lower()
            for rev, mig in self._source_migrations.get(source_key, {}).items():
                if rev not in applied:
                    mig.upgrade(con)
                    self.record_migration(
                        con,
                        revision=rev,
                        source_name=source_name,
                        description=mig.description,
                        version=rev,
                    )
                    applied.add(rev)
                    newly_applied.append(rev)

        return newly_applied


# Global default migration manager instance
migration_manager = MigrationManager()
