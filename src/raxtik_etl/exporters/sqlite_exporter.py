"""SQLite Seed Database Exporter."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import duckdb
from rich.console import Console

from raxtik_etl.config import DEFAULT_DUCKDB_PATH, DEFAULT_SQLITE_PATH

console = Console()

SEED_TABLES = [
    "drug_reaction_stats",
    "drug_demographics",
    "drug_indications",
    "drug_routes",
    "drug_outcomes",
]

INDEX_DEFINITIONS = [
    "CREATE INDEX IF NOT EXISTS idx_drug_reaction_drug ON drug_reaction_stats(drug_name);",
    "CREATE INDEX IF NOT EXISTS idx_drug_reaction_pt ON drug_reaction_stats(reaction_pt);",
    "CREATE INDEX IF NOT EXISTS idx_drug_demo_drug ON drug_demographics(drug_name);",
    "CREATE INDEX IF NOT EXISTS idx_drug_indi_drug ON drug_indications(drug_name);",
    "CREATE INDEX IF NOT EXISTS idx_drug_indi_pt ON drug_indications(indication_pt);",
    "CREATE INDEX IF NOT EXISTS idx_drug_routes_drug ON drug_routes(drug_name);",
    "CREATE INDEX IF NOT EXISTS idx_drug_outcomes_drug ON drug_outcomes(drug_name);",
]


def export_sqlite(
    db_path: Optional[Path | str] = None,
    sqlite_output: Optional[Path | str] = None,
    dataset_schema: str = "faers_raw",
    tables: Optional[List[str]] = None,
    verbose: bool = True,
) -> Path:
    """
    Export transformed tables from DuckDB into an indexed SQLite seed file.

    Args:
        db_path: Source DuckDB database path.
        sqlite_output: Target SQLite database file path.
        dataset_schema: Schema where tables are located.
        tables: List of tables to export (defaults to SEED_TABLES).
        verbose: Log export progress.

    Returns:
        Path to the generated SQLite database.
    """
    src_path = Path(db_path) if db_path else DEFAULT_DUCKDB_PATH
    dest_path = Path(sqlite_output) if sqlite_output else DEFAULT_SQLITE_PATH

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_path.exists():
        dest_path.unlink()

    export_tables = tables or SEED_TABLES

    duck_con = duckdb.connect(str(src_path), read_only=True)
    sqlite_con = sqlite3.connect(str(dest_path))
    sqlite_cur = sqlite_con.cursor()

    exported_counts: Dict[str, int] = {}
    for table_name in export_tables:
        cursor_res = None
        for query in [
            f"SELECT * FROM {dataset_schema}.{table_name}",
            f"SELECT * FROM {table_name}",
        ]:
            try:
                cursor_res = duck_con.execute(query)
                break
            except Exception:
                continue

        if cursor_res is not None:
            col_names = [desc[0] for desc in cursor_res.description]
            rows = cursor_res.fetchall()

            # Create Table in SQLite
            cols_clause = ", ".join([f'"{col}"' for col in col_names])
            placeholders = ", ".join(["?"] * len(col_names))

            sqlite_cur.execute(f'DROP TABLE IF EXISTS "{table_name}";')
            sqlite_cur.execute(f'CREATE TABLE "{table_name}" ({cols_clause});')
            sqlite_cur.executemany(f'INSERT INTO "{table_name}" VALUES ({placeholders});', rows)

            exported_counts[table_name] = len(rows)
            if verbose:
                console.print(
                    f"[green]✓[/green] Exported table [bold]{table_name}[/bold] ({len(rows):,} rows)"
                )
        else:
            if verbose:
                console.print(
                    f"[yellow]⚠[/yellow] Skipping table {table_name}: not found in DuckDB."
                )

    # Create Indexes
    for idx_sql in INDEX_DEFINITIONS:
        try:
            sqlite_cur.execute(idx_sql)
        except Exception:
            pass

    # Write metadata table
    sqlite_cur.execute("""
        CREATE TABLE IF NOT EXISTS seed_metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    metadata_entries = [
        ("schema_version", "1.0.0"),
        ("exported_at", datetime.now(timezone.utc).isoformat()),
        ("source", "raxtik-etl (FDA FAERS)"),
        ("tables_exported", ",".join(exported_counts.keys())),
    ]
    sqlite_cur.executemany(
        "INSERT OR REPLACE INTO seed_metadata (key, value) VALUES (?, ?)",
        metadata_entries,
    )

    sqlite_con.commit()
    sqlite_con.close()
    duck_con.close()

    if verbose:
        console.print(
            f"[bold green]✓ Successfully generated SQLite seed bundle at:[/bold green] {dest_path}"
        )

    return dest_path
