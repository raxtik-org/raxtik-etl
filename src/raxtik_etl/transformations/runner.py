"""Transformation runner for executing SQL transformations on DuckDB."""

from pathlib import Path
from typing import Dict, Optional

import duckdb
from rich.console import Console
from rich.table import Table

from raxtik_etl.config import DEFAULT_DUCKDB_PATH

SQL_DIR = Path(__file__).resolve().parent / "sql"
console = Console()

TRANSFORMATION_SCRIPTS = [
    "01_deduplicate.sql",
    "02_normalize_drugs.sql",
    "03_aggregate_stats.sql",
]


def run_transformations(
    db_path: Optional[Path | str] = None,
    dataset_schema: str = "faers_raw",
    verbose: bool = True,
) -> Dict[str, int]:
    """
    Execute transformation scripts against DuckDB database.

    Args:
        db_path: Path to the DuckDB intermediate database.
        dataset_schema: Schema where dlt loaded raw data (e.g. 'faers_raw' or 'main').
        verbose: Print rich table summary.

    Returns:
        Dict mapping created table names to their row counts.
    """
    path = Path(db_path) if db_path else DEFAULT_DUCKDB_PATH
    if not path.exists():
        raise FileNotFoundError(f"DuckDB database not found at {path}. Run ingest first.")

    con = duckdb.connect(str(path))

    # Check if raw tables are in a specific schema and set search path
    schemas = [
        r[0] for r in con.execute("SELECT schema_name FROM information_schema.schemata").fetchall()
    ]
    if dataset_schema in schemas:
        con.execute(f"SET search_path = '{dataset_schema},main'")

    for script_name in TRANSFORMATION_SCRIPTS:
        script_file = SQL_DIR / script_name
        if not script_file.exists():
            raise FileNotFoundError(f"Transformation SQL script not found: {script_file}")

        sql_content = script_file.read_text(encoding="utf-8")
        con.execute(sql_content)

    # Collect row counts of transformed tables
    transformed_tables = [
        "dedup_demo",
        "dedup_drug",
        "dedup_reac",
        "dedup_indi",
        "dedup_outc",
        "drug_reaction_stats",
        "drug_demographics",
        "drug_indications",
        "drug_routes",
        "drug_outcomes",
    ]

    results: Dict[str, int] = {}
    for tbl in transformed_tables:
        try:
            row = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()
            if row is not None:
                results[tbl] = int(row[0])
        except Exception:
            pass

    con.close()

    if verbose:
        table_summary = Table(title="DuckDB Transformed Tables Summary", style="cyan")
        table_summary.add_column("Table Name", style="bold white")
        table_summary.add_column("Row Count", justify="right", style="green")
        for name, count in results.items():
            table_summary.add_row(name, f"{count:,}")
        console.print(table_summary)

    return results
