"""Parquet Seed Exporter for analytical workloads."""

from pathlib import Path
from typing import Dict, List, Optional

import duckdb
from rich.console import Console

from raxtik_etl.config import DEFAULT_DUCKDB_PATH, DEFAULT_PARQUET_DIR

console = Console()

SEED_TABLES = [
    "drug_reaction_stats",
    "drug_demographics",
    "drug_indications",
    "drug_routes",
    "drug_outcomes",
]


def export_parquet(
    db_path: Optional[Path | str] = None,
    parquet_dir: Optional[Path | str] = None,
    dataset_schema: str = "faers_raw",
    tables: Optional[List[str]] = None,
    verbose: bool = True,
) -> Path:
    """
    Export transformed tables from DuckDB into compressed Parquet files.

    Args:
        db_path: Source DuckDB database path.
        parquet_dir: Target directory for Parquet files.
        dataset_schema: Schema where tables are located.
        tables: List of tables to export (defaults to SEED_TABLES).
        verbose: Log export progress.

    Returns:
        Path to output directory containing Parquet files.
    """
    src_path = Path(db_path) if db_path else DEFAULT_DUCKDB_PATH
    dest_dir = Path(parquet_dir) if parquet_dir else DEFAULT_PARQUET_DIR

    dest_dir.mkdir(parents=True, exist_ok=True)
    export_tables = tables or SEED_TABLES

    duck_con = duckdb.connect(str(src_path), read_only=True)

    exported: Dict[str, Path] = {}
    for table_name in export_tables:
        out_file = dest_dir / f"{table_name}.parquet"
        success = False
        for query_target in [f"{dataset_schema}.{table_name}", f"{table_name}"]:
            try:
                duck_con.execute(
                    f"COPY {query_target} TO '{out_file.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)"
                )
                exported[table_name] = out_file
                success = True
                if verbose:
                    console.print(f"[green]✓[/green] Exported [bold]{out_file.name}[/bold]")
                break
            except Exception:
                continue

        if not success and verbose:
            console.print(f"[yellow]⚠[/yellow] Skipping {table_name}: not found in DuckDB.")

    duck_con.close()

    if verbose:
        console.print(
            f"[bold green]✓ Successfully generated Parquet seed files at:[/bold green] {dest_dir}"
        )

    return dest_dir
