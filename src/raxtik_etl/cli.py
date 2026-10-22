"""Typer CLI interface for raxtik-etl pipeline commands."""

from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel

from raxtik_etl.distribution.huggingface import DEFAULT_HF_REPO
from raxtik_etl.longitudinal import (
    build_merged_longitudinal_package,
    get_longitudinal_summary_report,
)
from raxtik_etl.packaging.builder import PACKAGE_OUTPUT_DIR, build_quarterly_package
from raxtik_etl.sdk import FAERS

app = typer.Typer(
    name="raxtik-etl",
    help="Enterprise-grade FAERS adverse event data platform & packaging CLI.",
    add_completion=False,
)
console = Console()
CACHE_DIR = Path("data/raw/archives_cache")


def parse_quarter_range(start_quarter: str, end_quarter: str) -> List[str]:
    """Generates an inclusive list of quarterly releases between start and end (e.g. '2004Q1' to '2006Q4')."""
    start_clean = start_quarter.strip().upper()
    end_clean = end_quarter.strip().upper()

    start_y, start_q = int(start_clean[:4]), int(start_clean[-1])
    end_y, end_q = int(end_clean[:4]), int(end_clean[-1])

    quarters: List[str] = []
    y, q = start_y, start_q
    while (y < end_y) or (y == end_y and q <= end_q):
        quarters.append(f"{y}Q{q}")
        q += 1
        if q > 4:
            q = 1
            y += 1
    return quarters


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


@app.command("build-cohort")
def build_cohort_cmd(
    start: str = typer.Option("2004Q1", "--start", help="Starting quarter release (e.g. 2004Q1)"),
    end: str = typer.Option("2006Q4", "--end", help="Ending quarter release (e.g. 2006Q4)"),
    source: str = typer.Option("faers", "--source", "-s", help="Source connector name"),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-o", help="Output directory for packages"
    ),
):
    """Batch build standalone packages for every quarter in the specified range."""
    quarters = parse_quarter_range(start, end)
    console.print(
        f"[bold cyan]Building {len(quarters)} quarterly packages ({quarters[0]} to {quarters[-1]})...[/bold cyan]"
    )

    for q in quarters:
        archive_file = CACHE_DIR / f"{q.lower()}_ascii.zip"
        if not archive_file.exists():
            console.print(f"[bold red]Archive not found for {q}: {archive_file}[/bold red]")
            raise typer.Exit(code=1)
        build_quarterly_package(
            release=q,
            zip_path=archive_file,
            source_name=source,
            output_dir=output_dir,
        )

    console.print(f"[bold green]✓ Successfully built all {len(quarters)} packages.[/bold green]")


@app.command("merge-cohort")
def merge_cohort_cmd(
    start: str = typer.Option("2004Q1", "--start", help="Starting quarter release (e.g. 2004Q1)"),
    end: str = typer.Option("2006Q4", "--end", help="Ending quarter release (e.g. 2006Q4)"),
    package_dir: Optional[Path] = typer.Option(
        None, "--package-dir", "-p", help="Directory containing quarterly packages"
    ),
    output_name: Optional[str] = typer.Option(
        None,
        "--output-name",
        "-n",
        help="Merged output name (defaults to faers_{start}_{end}_merged)",
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-o", help="Destination folder for merged package"
    ),
):
    """Merge quarterly packages into a consolidated longitudinal dataset with cross-quarter deduplication."""
    quarters = parse_quarter_range(start, end)
    resolved_output_name = output_name or f"faers_{start}_{end}_merged".lower()
    res = build_merged_longitudinal_package(
        releases=quarters,
        package_dir=package_dir,
        output_name=resolved_output_name,
        output_dir=output_dir,
    )
    console.print(
        Panel(
            f"Merged Database: [bold]{res['output_duckdb']}[/bold]\n"
            f"Merged Parquet: [bold]{res['output_parquet']}[/bold]\n"
            f"Total Submissions: [cyan]{res['metrics'].get('total_raw_submissions')}[/cyan]\n"
            f"Deduplicated Unique Cases: [green]{res['metrics'].get('total_unique_cases')}[/green]\n"
            f"Cross-Quarter Cases: [yellow]{res['metrics'].get('cases_spanning_multiple_quarters')}[/yellow]\n"
            f"Duplicates Removed: [magenta]{res['metrics'].get('deduplicated_duplicate_reports_removed')} ({res['metrics'].get('deduplication_reduction_pct')})[/magenta]",
            title="Longitudinal Cohort Merged & Deduplicated",
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


@app.command("inspect-cohort")
def inspect_cohort_cmd(
    cohort: Optional[str] = typer.Option(
        None,
        "--cohort",
        "-c",
        help="Cohort name or identifier (e.g. 'faers_2004_2006_merged' or '2004_2006')",
    ),
    db_path: Optional[Path] = typer.Option(
        None,
        "--db-path",
        "-d",
        help="Direct path to merged DuckDB package file",
    ),
    package_dir: Optional[Path] = typer.Option(
        None,
        "--package-dir",
        "-p",
        help="Directory containing packages (defaults to data/packages or RAXTIK_PACKAGE_DIR)",
    ),
):
    """Inspect and display metrics for a merged longitudinal cohort package."""
    base_dir = package_dir or PACKAGE_OUTPUT_DIR
    target_path: Optional[Path] = None

    if db_path is not None:
        target_path = db_path
    elif cohort is not None:
        filename = cohort if cohort.endswith(".duckdb") else f"{cohort}.duckdb"
        if not filename.startswith("faers_") and not filename.startswith("/"):
            filename = f"faers_{filename}"
        candidate = base_dir / filename
        if not candidate.exists() and not filename.endswith("_merged.duckdb"):
            merged_candidate = base_dir / filename.replace(".duckdb", "_merged.duckdb")
            if merged_candidate.exists():
                candidate = merged_candidate
        target_path = candidate
    else:
        # Default fallback: check for existing merged package
        default_2004_2006 = base_dir / "faers_2004_2006_merged.duckdb"
        if default_2004_2006.exists():
            target_path = default_2004_2006
        else:
            merged_files = sorted(base_dir.glob("*merged*.duckdb"))
            target_path = merged_files[0] if merged_files else default_2004_2006

    if not target_path.exists():
        console.print(f"[bold red]Database not found at {target_path}[/bold red]")
        raise typer.Exit(code=1)
    report_table = get_longitudinal_summary_report(target_path)
    console.print(report_table)


@app.command("hf-download")
def hf_download_cmd(
    release: str = typer.Option(
        "2004Q1",
        "--release",
        "-r",
        help="Release identifier (e.g. 2004Q1 or faers_2004_2006_merged)",
    ),
    repo_id: str = typer.Option(
        DEFAULT_HF_REPO,
        "--repo-id",
        help="Hugging Face dataset repository (defaults to RAXTIK_HF_REPO)",
    ),
    dest_dir: Path = typer.Option(
        Path("data/packages"), "--dest-dir", "-d", help="Destination folder"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing local files"),
):
    """Download a compiled FAERS package from Hugging Face Hub (zero auth required)."""
    from raxtik_etl.distribution.huggingface import download_package_from_hf

    try:
        download_package_from_hf(
            release_or_name=release,
            dest_dir=dest_dir,
            repo_id=repo_id,
            force=force,
        )
    except Exception as e:
        console.print(f"[bold red]Download failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command("hf-upload")
def hf_upload_cmd(
    release: str = typer.Option(
        "2004Q1",
        "--release",
        "-r",
        help="Release identifier (e.g. 2004Q1 or faers_2004_2006_merged)",
    ),
    repo_id: str = typer.Option(
        DEFAULT_HF_REPO,
        "--repo-id",
        help="Hugging Face dataset repository (defaults to RAXTIK_HF_REPO)",
    ),
    package_dir: Path = typer.Option(
        Path("data/packages"), "--package-dir", "-p", help="Directory containing packages"
    ),
    token: Optional[str] = typer.Option(
        None, "--token", "-t", help="Hugging Face write access token (defaults to HF_TOKEN env var)"
    ),
    parquet: bool = typer.Option(
        True, "--parquet/--no-parquet", help="Whether to include Parquet shards"
    ),
):
    """Upload a compiled FAERS package to Hugging Face Hub (requires write token)."""
    from raxtik_etl.distribution.huggingface import upload_package_to_hf

    try:
        upload_package_to_hf(
            release_or_name=release,
            package_dir=package_dir,
            repo_id=repo_id,
            token=token,
            include_parquet=parquet,
        )
    except Exception as e:
        console.print(f"[bold red]Upload failed:[/bold red] {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
