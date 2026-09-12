"""Typer CLI interface for raxtik-etl pipeline commands."""

from pathlib import Path
from typing import Optional

import dlt
import typer
from rich.console import Console
from rich.panel import Panel

from raxtik_etl.config import (
    DEFAULT_DUCKDB_PATH,
    DEFAULT_SQLITE_PATH,
    RAW_DATA_DIR,
    ensure_directories,
)
from raxtik_etl.exporters.parquet_exporter import export_parquet
from raxtik_etl.exporters.sqlite_exporter import export_sqlite
from raxtik_etl.sources.faers.fetcher import download_quarterly_data
from raxtik_etl.sources.faers.source import faers_source
from raxtik_etl.transformations.runner import run_transformations

app = typer.Typer(
    name="raxtik-etl",
    help="Adverse event ETL pipeline for FDA FAERS using dlt & DuckDB.",
    add_completion=False,
)
console = Console()


@app.command()
def fetch(
    year: int = typer.Option(..., "--year", "-y", help="Quarter year (e.g. 2024)"),
    quarter: int = typer.Option(..., "--quarter", "-q", help="Quarter number (1-4)"),
    dest_dir: Optional[Path] = typer.Option(
        None, "--dest-dir", "-d", help="Target extraction directory"
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help="Re-download if already exists"),
):
    """Download and extract FDA FAERS quarterly ASCII data dump."""
    ensure_directories()
    console.print(f"[bold cyan]Fetching FDA FAERS data for {year} Q{quarter}...[/bold cyan]")
    try:
        out_dir = download_quarterly_data(
            year=year,
            quarter=quarter,
            dest_dir=dest_dir,
            overwrite=overwrite,
        )
        console.print(f"[bold green]✓ Download and extraction complete:[/bold green] {out_dir}")
    except Exception as e:
        console.print(f"[bold red]✗ Fetch failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def ingest(
    source_dir: Optional[Path] = typer.Option(
        None, "--source-dir", "-s", help="Directory containing FAERS ASCII .txt files"
    ),
    db_path: Optional[Path] = typer.Option(None, "--db-path", help="DuckDB database path override"),
    dataset_name: str = typer.Option(
        "faers_raw", "--dataset-name", help="DuckDB dataset/schema name"
    ),
):
    """Ingest FAERS ASCII files into DuckDB using dlt."""
    ensure_directories()
    data_path = source_dir if source_dir else RAW_DATA_DIR
    target_db = str(db_path) if db_path else str(DEFAULT_DUCKDB_PATH)

    console.print(f"[bold cyan]Starting dlt ingestion from[/bold cyan] {data_path}")
    console.print(f"[bold cyan]Target DuckDB database:[/bold cyan] {target_db}")

    pipeline = dlt.pipeline(
        pipeline_name="faers_pipeline",
        destination=dlt.destinations.duckdb(target_db),
        dataset_name=dataset_name,
    )

    source = faers_source(data_dir=data_path)
    load_info = pipeline.run(source)
    console.print(Panel(str(load_info), title="dlt Ingestion Summary", style="green"))


@app.command()
def transform(
    db_path: Optional[Path] = typer.Option(None, "--db-path", help="DuckDB database path override"),
    dataset_schema: str = typer.Option(
        "faers_raw", "--dataset-schema", help="Schema containing ingested raw data"
    ),
):
    """Execute SQL transformations for deduplication and statistical aggregation."""
    target_db = db_path if db_path else DEFAULT_DUCKDB_PATH
    console.print(f"[bold cyan]Running DuckDB transformations on[/bold cyan] {target_db}...")
    try:
        results = run_transformations(db_path=target_db, dataset_schema=dataset_schema)
        console.print("[bold green]✓ Transformations executed successfully![/bold green]")
        return results
    except Exception as e:
        console.print(f"[bold red]✗ Transformations failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def export(
    db_path: Optional[Path] = typer.Option(None, "--db-path", help="Source DuckDB database path"),
    format: str = typer.Option(
        "all", "--format", "-f", help="Export format: 'sqlite', 'parquet', or 'all'"
    ),
    sqlite_path: Optional[Path] = typer.Option(
        None, "--sqlite-path", help="SQLite output database path"
    ),
    parquet_dir: Optional[Path] = typer.Option(
        None, "--parquet-dir", help="Parquet output directory"
    ),
):
    """Export transformed seed data tables to SQLite and Parquet formats."""
    target_db = db_path if db_path else DEFAULT_DUCKDB_PATH
    format_lower = format.lower()

    if format_lower in ("sqlite", "all"):
        export_sqlite(db_path=target_db, sqlite_output=sqlite_path)

    if format_lower in ("parquet", "all"):
        export_parquet(db_path=target_db, parquet_dir=parquet_dir)


@app.command()
def pipeline(
    sample: bool = typer.Option(
        False, "--sample", help="Run pipeline using bundled sample fixtures"
    ),
    source_dir: Optional[Path] = typer.Option(
        None, "--source-dir", "-s", help="Directory with FAERS files"
    ),
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Fetch year"),
    quarter: Optional[int] = typer.Option(None, "--quarter", "-q", help="Fetch quarter"),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-o", help="Target output directory for seeds"
    ),
):
    """Run full end-to-end ETL pipeline: fetch/prepare -> ingest -> transform -> export."""
    ensure_directories()

    if sample:
        fixtures_dir = (
            Path(__file__).resolve().parent.parent.parent
            / "tests"
            / "fixtures"
            / "sample_faers_ascii"
        )
        data_dir = fixtures_dir
        console.print(
            f"[bold yellow]Running end-to-end pipeline in SAMPLE mode with fixtures from[/bold yellow] {fixtures_dir}"
        )
    elif year and quarter:
        data_dir = download_quarterly_data(year=year, quarter=quarter)
    elif source_dir:
        data_dir = Path(source_dir)
    else:
        data_dir = RAW_DATA_DIR

    out_base = output_dir if output_dir else DEFAULT_SQLITE_PATH.parent
    sqlite_out = out_base / "faers_seed.sqlite"
    parquet_out = out_base / "parquet"

    # 1. Ingest
    ingest(source_dir=data_dir, db_path=DEFAULT_DUCKDB_PATH, dataset_name="faers_raw")

    # 2. Transform
    transform(db_path=DEFAULT_DUCKDB_PATH, dataset_schema="faers_raw")

    # 3. Export
    export(
        db_path=DEFAULT_DUCKDB_PATH,
        format="all",
        sqlite_path=sqlite_out,
        parquet_dir=parquet_out,
    )
    console.print(
        Panel(
            "[bold green]🎉 raxtik-etl pipeline completed successfully![/bold green]", style="green"
        )
    )


if __name__ == "__main__":
    app()
