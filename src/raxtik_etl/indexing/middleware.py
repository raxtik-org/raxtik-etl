"""Tier-agnostic DuckDB Query Middleware & Materialization Engine.

Transparently rewrites `cases` and scoped child fact table views (`drug`, `reac`,
`outc`, `indi`, `ther`, `rpsr`) over a READ_ONLY Bronze database using the
derived sharded index — supporting both local files and 100% remote `httpfs`
streaming with zero mutation of underlying Bronze packages.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Set

import duckdb

from raxtik_etl.indexing.models import ResolutionPolicy
from raxtik_etl.indexing.state import build_resolved_state_sql
from raxtik_etl.sources.temporal import normalize_quarter


def _list_catalog_tables(con: duckdb.DuckDBPyConnection, catalog: str) -> Set[str]:
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_catalog = ?",
        [catalog],
    ).fetchall()
    return {str(r[0]) for r in rows}


def _winning_records_select_sql(
    state_source: str,
    period: str,
    as_of: Optional[str] = None,
) -> str:
    """Returns a SQL SELECT yielding `(case_id, winning_primary_id, winning_quarter)` for `period`."""
    if as_of is None:
        return (
            "SELECT\n"
            "    case_id,\n"
            "    latest_primary_id AS winning_primary_id,\n"
            "    latest_quarter AS winning_quarter\n"
            f"FROM {state_source}\n"
            f"WHERE latest_quarter = '{period}'"
        )
    return (
        "WITH bounded AS (\n"
        "    SELECT\n"
        "        case_id,\n"
        f"        list_filter(timeline, lambda x: x.quarter <= '{as_of}') AS tl\n"
        f"    FROM {state_source}\n"
        ")\n"
        "SELECT\n"
        "    case_id,\n"
        "    tl[1].primary_id AS winning_primary_id,\n"
        "    tl[1].quarter AS winning_quarter\n"
        "FROM bounded\n"
        f"WHERE len(tl) > 0 AND tl[1].quarter = '{period}'"
    )


def apply_tier_views(
    con: duckdb.DuckDBPyConnection,
    bronze_catalog: str,
    data_period: str,
    state_shard_uris: Sequence[str],
    policy: Optional[ResolutionPolicy] = None,
    as_of_period: Optional[str] = None,
    delta_uris: Sequence[str] = (),
) -> None:
    """Registers zero-copy tier-filtered views inside `con`'s writable default catalog.

    Assumes the Bronze DuckDB package is already attached under `bronze_catalog`
    (READ_ONLY). Creates:

    - `_index_state`: view over resolved `base_shards + ordered deltas` (local or HTTPS).
    - `_winning_records`: winning `(case_id, winning_primary_id, winning_quarter)`
      for `data_period` (optionally bounded by `as_of_period`).
    - `cases`: authoritative deduplicated cases for `data_period`.
    - Child fact views (`drug`, `reac`, `outc`, `indi`, `ther`, `rpsr`): scoped to
      `_winning_records` so drug/reaction counts never include superseded reports.
    - Pass-through views for `demo` (raw submissions), `_metadata`, `_data_quality_report`,
      and `_code_*` reference tables.
    """
    if not state_shard_uris:
        raise ValueError("state_shard_uris cannot be empty.")

    pol = policy or ResolutionPolicy()
    period = normalize_quarter(data_period)
    as_of = normalize_quarter(as_of_period) if as_of_period else None

    state_sql = build_resolved_state_sql(state_shard_uris, delta_uris)
    con.execute(f"CREATE OR REPLACE VIEW _index_state AS {state_sql};")  # nosec B608

    winners_sql = _winning_records_select_sql("_index_state", period, as_of)
    con.execute(f"CREATE OR REPLACE VIEW _winning_records AS {winners_sql};")  # nosec B608

    existing_tables = _list_catalog_tables(con, bronze_catalog)
    src_tbl = pol.source_table
    rk = pol.record_key

    if src_tbl in existing_tables:
        # Expose full raw physical reports via `demo` pass-through
        con.execute(
            f"CREATE OR REPLACE VIEW {src_tbl} AS SELECT * FROM {bronze_catalog}.{src_tbl};"  # nosec B608
        )
        # Expose deduplicated authoritative cases via `cases`
        con.execute(
            f"""
            CREATE OR REPLACE VIEW cases AS
            SELECT d.*
            FROM {bronze_catalog}.{src_tbl} d
            INNER JOIN _winning_records w
              ON TRIM(CAST(d.{rk} AS VARCHAR)) = w.winning_primary_id;
            """  # nosec B608
        )

    # Scope child fact tables to winning records so counts exclude superseded submissions
    child_set = set(pol.child_tables)
    for child in pol.child_tables:
        if child in existing_tables:
            con.execute(
                f"""
                CREATE OR REPLACE VIEW {child} AS
                SELECT t.*
                FROM {bronze_catalog}.{child} t
                INNER JOIN _winning_records w
                  ON TRIM(CAST(t.{rk} AS VARCHAR)) = w.winning_primary_id;
                """  # nosec B608
            )

    # Pass through metadata, quality reports, and reference codelist tables
    passthrough_skip = {src_tbl, "cases"} | child_set
    for tbl in sorted(existing_tables - passthrough_skip):
        if tbl.startswith("_"):
            con.execute(
                f"CREATE OR REPLACE VIEW {tbl} AS SELECT * FROM {bronze_catalog}.{tbl};"  # nosec B608
            )


def connect_with_tier_middleware(
    bronze_db_uri: str,
    data_period: str,
    state_shard_uris: Sequence[str],
    policy: Optional[ResolutionPolicy] = None,
    as_of_period: Optional[str] = None,
    enable_httpfs: bool = False,
    delta_uris: Sequence[str] = (),
) -> duckdb.DuckDBPyConnection:
    """Opens an in-memory DuckDB session with `bronze_db_uri` attached READ_ONLY
    and tier-filtered views mounted in the default catalog.

    Works identically for local `.duckdb` file paths and remote Hugging Face
    `https://...` URLs (when `enable_httpfs=True`).
    """
    con = duckdb.connect(":memory:")
    try:
        if enable_httpfs:
            con.execute("INSTALL httpfs; LOAD httpfs;")
        con.execute(f"ATTACH '{bronze_db_uri}' AS bronze_db (READ_ONLY);")
        apply_tier_views(
            con=con,
            bronze_catalog="bronze_db",
            data_period=data_period,
            state_shard_uris=state_shard_uris,
            policy=policy,
            as_of_period=as_of_period,
            delta_uris=delta_uris,
        )
        return con
    except Exception:
        con.close()
        raise


def materialize_filtered_package(
    bronze_db_path: Path | str,
    dest_db_path: Path | str,
    data_period: str,
    state_shard_uris: Sequence[str],
    policy: Optional[ResolutionPolicy] = None,
    tier: str = "silver",
    as_of_period: Optional[str] = None,
    delta_uris: Sequence[str] = (),
) -> Path:
    """Materializes a standalone, pre-filtered DuckDB package for a single period.

    Prunes superseded reports and orphan child rows into a portable DuckDB file
    that requires zero runtime index joins.
    """
    pol = policy or ResolutionPolicy()
    dest = Path(dest_db_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_dest = dest.parent / f".tmp_{dest.name}"
    if tmp_dest.exists():
        tmp_dest.unlink()

    con = duckdb.connect(tmp_dest.as_posix())
    try:
        bronze_uri = Path(bronze_db_path).as_posix()
        con.execute(f"ATTACH '{bronze_uri}' AS bronze_db (READ_ONLY);")
        existing_tables = _list_catalog_tables(con, "bronze_db")

        state_sql = build_resolved_state_sql(state_shard_uris, delta_uris)
        period = normalize_quarter(data_period)
        as_of = normalize_quarter(as_of_period) if as_of_period else None
        rk = pol.record_key

        winners_sql = _winning_records_select_sql(f"({state_sql})", period, as_of)
        con.execute(f"CREATE TEMP TABLE _winners AS {winners_sql};")  # nosec B608

        # Materialize filtered demo + cases
        if pol.source_table in existing_tables:
            con.execute(
                f"""
                CREATE TABLE {pol.source_table} AS
                SELECT d.*
                FROM bronze_db.{pol.source_table} d
                INNER JOIN _winners w
                  ON TRIM(CAST(d.{rk} AS VARCHAR)) = w.winning_primary_id;
                """  # nosec B608
            )
            con.execute(
                f"CREATE OR REPLACE VIEW cases AS SELECT * FROM {pol.source_table};"  # nosec B608
            )

        # Materialize filtered child fact tables
        child_set = set(pol.child_tables)
        for child in pol.child_tables:
            if child in existing_tables:
                con.execute(
                    f"""
                    CREATE TABLE {child} AS
                    SELECT t.*
                    FROM bronze_db.{child} t
                    INNER JOIN _winners w
                      ON TRIM(CAST(t.{rk} AS VARCHAR)) = w.winning_primary_id;
                    """  # nosec B608
                )

        # Copy metadata and reference tables, recording materialized tier
        for tbl in sorted(existing_tables - ({pol.source_table, "cases"} | child_set)):
            if tbl.startswith("_"):
                con.execute(f"CREATE TABLE {tbl} AS SELECT * FROM bronze_db.{tbl};")  # nosec B608

        if "_metadata" in existing_tables:
            con.execute("DELETE FROM _metadata WHERE key = 'tier';")
            con.execute("INSERT INTO _metadata (key, value) VALUES ('tier', ?);", [tier])

        con.execute("DETACH bronze_db;")
    except Exception:
        con.close()
        if tmp_dest.exists():
            tmp_dest.unlink()
        raise
    else:
        con.close()

    tmp_dest.replace(dest)
    return dest
