"""Unit tests for the schema migration framework (canonical and source-specific)."""

from __future__ import annotations

import duckdb

from raxtik_etl.migrations.base import BaseMigration
from raxtik_etl.migrations.manager import MigrationManager


class CanonicalAddRxnormMigration(BaseMigration):
    revision = "1.1.0"
    source_name = None  # Generic canonical migration
    description = "Add standard rxnorm code to drug table"

    def upgrade(self, con: duckdb.DuckDBPyConnection) -> None:
        con.execute("ALTER TABLE drug ADD COLUMN IF NOT EXISTS rxnorm_id VARCHAR;")


class FaersSpecificIndicationMigration(BaseMigration):
    revision = "faers_2026_01"
    source_name = "faers"  # Source-specific migration
    description = "Create source-specific cleaned indication index"

    def upgrade(self, con: duckdb.DuckDBPyConnection) -> None:
        con.execute(
            "CREATE OR REPLACE VIEW faers_clean_indi AS SELECT *, upper(reported_indication) AS clean_indi FROM indi;"
        )


def test_migration_manager_linear_execution():
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE drug (primary_id VARCHAR, drug_name VARCHAR);")
    con.execute("CREATE TABLE indi (primary_id VARCHAR, reported_indication VARCHAR);")

    mgr = MigrationManager()
    mgr.register(CanonicalAddRxnormMigration())
    mgr.register(FaersSpecificIndicationMigration())

    # Initial ledger setup
    MigrationManager.init_migration_table(con)
    MigrationManager.record_migration(con, "1.0.0", None, "Initial 1.0.0 baseline")

    applied = MigrationManager.get_applied_revisions(con)
    assert applied == ["1.0.0"]

    # Apply migrations for FAERS source
    newly_applied = mgr.apply_pending_migrations(con, source_name="faers")
    assert "1.1.0" in newly_applied
    assert "faers_2026_01" in newly_applied

    # Check drug table has new rxnorm_id column
    cols = [col[0] for col in con.execute("DESCRIBE drug").fetchall()]
    assert "rxnorm_id" in cols

    # Check faers-specific view exists
    assert con.execute("SELECT * FROM faers_clean_indi").fetchall() == []

    # Second run should apply nothing (idempotent)
    second_run = mgr.apply_pending_migrations(con, source_name="faers")
    assert second_run == []
    con.close()
