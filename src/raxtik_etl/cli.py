"""Typer CLI interface for raxtik-etl pipeline commands."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from raxtik_etl.packaging.builder import build_quarterly_package
from raxtik_etl.sdk import FAERS

app = typer.Typer(
    name="raxtik-etl",
    help="Enterprise-grade FAERS adverse event data platform & packaging CLI.",
    add_completion=False,
)
console = Console()
CACHE_DIR = Path("data/raw/archives_cache")


@app.command("build-package")
def build_package_cmd(
    source: str = typer.Option(
        "faers", "--source", "-s", help="Source connector name (e.g. faers)"
    ),
    release: str = typer.Option(
        "2004Q1", "--release", "-r", help="Quarter release identifier (e.g. 2004Q1)"
    ),
    zip_path: Optional[Path] = typer.Option(
        None, "--zip-path", "-z", help="Path to source archive/zip file"
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-o", help="Output package directory"
    ),
):
    """Build a standalone, self-describing Safety DuckDB and Parquet package."""
    release_clean = release.upper()
    archive_file = zip_path or (CACHE_DIR / f"{release_clean.lower()}_ascii.zip")

    if not archive_file.exists():
        console.print(f"[bold red]Source archive not found at {archive_file}.[/bold red]")
        raise typer.Exit(code=1)

    res = build_quarterly_package(
        release=release_clean,
        zip_path=archive_file,
        source_name=source,
        output_dir=output_dir,
    )
    console.print(
        Panel(
            f"Release: [bold]{res['release']}[/bold]\nSignature: {res['signature_id']}\nDuckDB: {res['duckdb_path']}\nParquet: {res['parquet_dir']}",
            title="Package Generated Successfully",
            style="green",
        )
    )


@app.command("inspect-package")
def inspect_package_cmd(
    release: str = typer.Option(
        "2004Q1", "--release", "-r", help="Quarter release identifier to inspect"
    ),
    package_dir: Optional[Path] = typer.Option(
        None, "--package-dir", "-p", help="Directory containing package files"
    ),
):
    """Inspect and display metadata and data quality report for a compiled package."""
    try:
        with FAERS(release=release, package_dir=package_dir) as faers:
            faers.print_summary()
    except Exception as e:
        console.print(f"[bold red]Failed to inspect package:[/bold red] {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
