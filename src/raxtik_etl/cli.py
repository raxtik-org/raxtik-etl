import os
import re
import shutil
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, List, Optional

import duckdb
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from raxtik_etl.consolidation import (
    build_consolidated_package,
    get_consolidation_summary_report,
)
from raxtik_etl.distribution.huggingface import (
    DEFAULT_HF_REPO,
    DEFAULT_HTTP_TIMEOUT,
    download_package_from_hf,
    get_default_package_dir,
    tag_hf_dataset,
    upload_package_to_hf,
)
from raxtik_etl.indexing import (
    ResolutionPolicy,
    ShardedStateIndex,
    build_resolved_state_sql,
    compute_source_fingerprint,
    get_default_index_dir,
    upload_index_to_hf,
)
from raxtik_etl.packaging.builder import (
    PACKAGE_OUTPUT_DIR,
    PackageFormat,
    build_quarterly_package,
    compute_sha256,
)
from raxtik_etl.sdk import Dataset
from raxtik_etl.sources import find_cached_archive, parse_quarter_range
from raxtik_etl.sources.registry import (
    SourcePluginNotFoundError,
    get_available_sources,
    get_source_adapter,
)
from raxtik_etl.sources.temporal import normalize_quarter

app = typer.Typer(
    name="raxtik-etl",
    help="Enterprise-grade FAERS adverse event data platform & packaging CLI.",
    add_completion=False,
)
console = Console()
CACHE_DIR = Path(
    os.environ.get("FAERS_CACHE_DIR", Path.home() / ".cache" / "raxtik" / "raw_archives")
)


@app.command("build-package", hidden=True)
def build_package_cmd(
    source: str = typer.Option(
        "faers", "--source", "-s", help="Source connector name (e.g. faers)"
    ),
    data_period: str = typer.Option(
        ...,
        "--data-period",
        "-d",
        help="Quarterly data period identifier (e.g. 2004Q1)",
    ),
    zip_path: Optional[Path] = typer.Option(
        None, "--zip-path", "-z", help="Path to source archive/zip file"
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Output package directory (defaults to ~/.cache/raxtik/packages)",
    ),
    format: PackageFormat = typer.Option(
        PackageFormat.BOTH,
        "--format",
        "-f",
        help="Output format: 'both', 'duckdb', or 'parquet'",
    ),
    delete_ascii: bool = typer.Option(
        True,
        "--delete-ascii/--no-delete-ascii",
        help="Automatically delete raw downloaded ASCII files after packaging (default: True)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing local package files and re-build (default: False)",
    ),
) -> None:
    """Builds a standalone DuckDB and/or Parquet package for a single quarterly data period."""
    # 1. Resolve source connector dynamically from plugin registry
    try:
        adapter = get_source_adapter(source)
    except SourcePluginNotFoundError as e:
        console.print(f"[bold red]{e}[/bold red]")
        raise typer.Exit(code=1)

    period_clean = data_period.upper().strip()
    target_pkg_dir = output_dir or PACKAGE_OUTPUT_DIR
    target_duckdb = target_pkg_dir / f"{source}_{period_clean}.duckdb"
    target_parquet = target_pkg_dir / f"{source}_{period_clean}.parquet"

    needs_duckdb = format in (PackageFormat.BOTH, PackageFormat.DUCKDB)
    needs_parquet = format in (PackageFormat.BOTH, PackageFormat.PARQUET)
    already_built = (not needs_duckdb or target_duckdb.exists()) and (
        not needs_parquet or target_parquet.exists()
    )

    if already_built and not force:
        console.print(
            f"[bold green]Package for {period_clean} already compiled locally at {target_pkg_dir}[/bold green]"
        )
        msg_lines = [
            f"Data Period: [bold]{period_clean}[/bold]",
            f"Format: {format.value}",
        ]
        if needs_duckdb and target_duckdb.exists():
            msg_lines.append(f"DuckDB: {target_duckdb.as_posix()}")
            msg_lines.append(f"SHA-256: {compute_sha256(target_duckdb)}")
        if needs_parquet and target_parquet.exists():
            msg_lines.append(f"Parquet: {target_parquet.as_posix()}")

        console.print(
            Panel(
                "\n".join(msg_lines),
                title="Package Already Exists (Use --force to rebuild)",
                style="cyan",
            )
        )
        return

    archive_file: Optional[Path] = None
    if zip_path:
        if not zip_path.exists():
            console.print(f"[bold red]Specified zip path not found: {zip_path}[/bold red]")
            raise typer.Exit(code=1)
        archive_file = zip_path
    else:
        archive_file = find_cached_archive(CACHE_DIR, period_clean, source)
        if archive_file:
            console.print(f"[dim]✓ Using local source archive:[/dim] {archive_file.name}")
        elif hasattr(adapter, "fetch_archive"):
            console.print(
                f"[bold cyan]Raw archive not found locally. Fetching {period_clean} via \\[{adapter.source_name}] connector...[/bold cyan]"
            )
            try:
                archive_file = adapter.fetch_archive(data_period=period_clean, dest_dir=CACHE_DIR)
            except Exception as dl_err:
                console.print(
                    f"[bold red]Failed to download {period_clean} via \\[{adapter.source_name}] connector: {dl_err}[/bold red]"
                )
                raise typer.Exit(code=1)
        else:
            console.print(
                f"[bold red]Source archive not found in {CACHE_DIR}, and connector '{adapter.source_name}' does not implement remote fetching.[/bold red]"
            )
            raise typer.Exit(code=1)

    res = build_quarterly_package(
        data_period=period_clean,
        zip_path=archive_file,
        source_name=source,
        adapter=adapter,
        output_dir=output_dir,
        format=format,
        delete_ascii=delete_ascii,
    )
    msg_lines = [
        f"Data Period: [bold]{res['data_period']}[/bold]",
        f"Signature: {res['signature_id']}",
        f"Format: {res['format']}",
    ]
    if "duckdb_path" in res:
        msg_lines.append(f"DuckDB: {res['duckdb_path']}")
    if "parquet_dir" in res:
        msg_lines.append(f"Parquet: {res['parquet_dir']}")
    if "sha256" in res:
        msg_lines.append(f"SHA-256: {res['sha256']}")

    console.print(
        Panel(
            "\n".join(msg_lines),
            title="Package Generated Successfully",
            style="green",
        )
    )


@app.command("build")
def build_cmd(
    data_period: Optional[str] = typer.Option(
        None,
        "--data-period",
        "-d",
        help="Quarterly period (e.g. 2004Q1) or range (e.g. 2004Q1..2004Q4)",
    ),
    start: Optional[str] = typer.Option(None, "--start", help="Starting period for batch build"),
    end: Optional[str] = typer.Option(None, "--end", help="Ending period for batch build"),
    source: str = typer.Option("faers", "--source", "-s", help="Source connector name"),
    zip_path: Optional[Path] = typer.Option(None, "--zip-path", "-z", help="Path to archive file"),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Output package directory (defaults to ~/.cache/raxtik/packages)",
    ),
    format: PackageFormat = typer.Option(
        PackageFormat.BOTH,
        "--format",
        "-f",
        help="Output format: 'both', 'duckdb', or 'parquet'",
    ),
    delete_ascii: bool = typer.Option(
        True,
        "--delete-ascii/--no-delete-ascii",
        help="Automatically delete raw downloaded ASCII files after packaging",
    ),
    force: bool = typer.Option(
        False, "--force", help="Overwrite existing local files and re-build"
    ),
    upload: bool = typer.Option(
        False,
        "--upload",
        help="Upload each package to Hugging Face Hub immediately after building",
    ),
    clean_local: bool = typer.Option(
        False,
        "--clean-local",
        help="Delete local compiled package after uploading to prevent disk space exhaustion",
    ),
    batch_size_gb: float = typer.Option(
        2.0,
        "--batch-size-gb",
        help="Target batch size in GB before committing to Hugging Face (default: 2.0 GB)",
    ),
    repo_id: str = typer.Option(
        DEFAULT_HF_REPO,
        "--repo-id",
        help="Hugging Face dataset repository (used when --upload is active)",
    ),
    tag: Optional[str] = typer.Option(
        None,
        "--tag",
        help="Git tag to create on Hugging Face dataset after upload completes",
    ),
    token: Optional[str] = typer.Option(
        None,
        "--token",
        "-t",
        help="Hugging Face write token (defaults to HF_TOKEN env var)",
    ),
) -> None:
    """Build standalone DuckDB and/or Parquet package(s) for a single quarter or range."""
    if start and end:
        batch_build_cmd(
            start=start,
            end=end,
            source=source,
            output_dir=output_dir,
            format=format,
            delete_ascii=delete_ascii,
            upload=upload,
            clean_local=clean_local,
            repo_id=repo_id,
            tag=tag,
            token=token,
            force=force,
            batch_size_gb=batch_size_gb,
        )
    elif data_period and (".." in data_period or ":" in data_period):
        sep = ".." if ".." in data_period else ":"
        parts = data_period.split(sep)
        batch_build_cmd(
            start=parts[0].strip(),
            end=parts[1].strip(),
            source=source,
            output_dir=output_dir,
            format=format,
            delete_ascii=delete_ascii,
            upload=upload,
            clean_local=clean_local,
            repo_id=repo_id,
            tag=tag,
            token=token,
            force=force,
            batch_size_gb=batch_size_gb,
        )
    elif data_period:
        build_package_cmd(
            source=source,
            data_period=data_period,
            zip_path=zip_path,
            output_dir=output_dir,
            format=format,
            delete_ascii=delete_ascii,
            force=force,
        )
    else:
        console.print(
            "[bold red]Error: You must specify --data-period (e.g. 2004Q1) or both --start and --end to build a package.[/bold red]"
        )
        raise typer.Exit(code=1)


def _get_process_rss_mb() -> float:
    import resource

    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return (rss / (1024 * 1024)) if sys.platform == "darwin" else (rss / 1024)


def _calculate_package_size(pkg_dir: Path, source: str, quarter: str) -> int:
    """Calculates disk size in bytes for a compiled DuckDB and/or Parquet package."""
    total = 0
    p_duck = pkg_dir / f"{source}_{quarter}.duckdb"
    p_parq = pkg_dir / f"{source}_{quarter}.parquet"
    if p_duck.exists():
        total += p_duck.stat().st_size
    if p_parq.exists():
        for pf in p_parq.glob("*.parquet"):
            total += pf.stat().st_size
    return total


def _resolve_quarter_archive(
    adapter: Any,
    quarter: str,
    source: str,
    force: bool,
) -> tuple[Optional[Path], float]:
    """Resolves local cached archive or downloads via source adapter."""

    archive_file = find_cached_archive(CACHE_DIR, quarter, source)
    if force and archive_file and archive_file.exists():
        archive_file.unlink(missing_ok=True)
        archive_file = None

    if archive_file and archive_file.exists():
        console.print(f"[dim]✓ Using local source archive for {quarter}:[/dim] {archive_file.name}")
        return archive_file, 0.0

    if not hasattr(adapter, "fetch_archive"):
        console.print(f"[bold red]Archive not found for {quarter} in {CACHE_DIR}[/bold red]")
        return None, 0.0

    console.print(
        f"[bold cyan]Fetching {quarter} via \\[{adapter.source_name}] connector...[/bold cyan]"
    )
    t0 = time.perf_counter()
    try:
        source_cache = CACHE_DIR / source
        source_cache.mkdir(parents=True, exist_ok=True)
        archive_file = adapter.fetch_archive(data_period=quarter, dest_dir=source_cache)
        return archive_file, time.perf_counter() - t0
    except Exception as dl_err:
        console.print(
            f"[yellow]Could not download {quarter} from source: {dl_err}. Skipping.[/yellow]"
        )
        return None, 0.0


def _flush_hf_batch(
    batch_quarters: List[str],
    batch_bytes: int,
    target_pkg_dir: Path,
    repo_id: str,
    source: str,
    token: Optional[str],
    clean_local: bool,
) -> float:
    """Uploads accumulated package batch to Hugging Face Hub in a single bulk commit."""

    if not batch_quarters:
        return 0.0

    t_flush_start = time.perf_counter()
    upload_package_to_hf(
        data_period_or_name=batch_quarters,
        package_dir=target_pkg_dir,
        repo_id=repo_id,
        source_name=source,
        token=token,
    )
    t_flush = time.perf_counter() - t_flush_start
    console.print(
        f"[bold green]✓ Pushed bulk commit for {batch_quarters[0]}..{batch_quarters[-1]} "
        f"({len(batch_quarters)} quarters, {batch_bytes / (1024 * 1024):.1f} MB) in {t_flush:.1f}s.[/bold green]"
    )
    if clean_local:
        for q_done in batch_quarters:
            p_duck = target_pkg_dir / f"{source}_{q_done}.duckdb"
            p_parq = target_pkg_dir / f"{source}_{q_done}.parquet"
            p_duck.unlink(missing_ok=True)
            if p_parq.exists():
                shutil.rmtree(p_parq, ignore_errors=True)
        console.print(
            f"[dim]✓ Cleaned local package files for {batch_quarters[0]}..{batch_quarters[-1]} to free disk space.[/dim]"
        )
    return t_flush


@app.command("batch-build", hidden=True)
def batch_build_cmd(
    start: str = typer.Option("2004Q1", "--start", help="Starting data period (e.g. 2004Q1)"),
    end: str = typer.Option("2006Q4", "--end", help="Ending data period (e.g. 2006Q4)"),
    source: str = typer.Option("faers", "--source", "-s", help="Source connector name"),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Output directory for packages (defaults to ~/.cache/raxtik/packages)",
    ),
    format: PackageFormat = typer.Option(
        PackageFormat.BOTH,
        "--format",
        "-f",
        help="Output format: 'both', 'duckdb', or 'parquet'",
    ),
    delete_ascii: bool = typer.Option(
        True,
        "--delete-ascii/--no-delete-ascii",
        help="Automatically delete raw downloaded ASCII files after packaging (default: True)",
    ),
    upload: bool = typer.Option(
        False,
        "--upload",
        help="Upload each package to Hugging Face Hub immediately after building",
    ),
    clean_local: bool = typer.Option(
        False,
        "--clean-local",
        help="Delete local compiled package after uploading to prevent disk space exhaustion",
    ),
    repo_id: str = typer.Option(
        DEFAULT_HF_REPO,
        "--repo-id",
        help="Hugging Face dataset repository (used when --upload is active)",
    ),
    tag: Optional[str] = typer.Option(
        None,
        "--tag",
        help="Git tag to create on Hugging Face dataset after all packages are uploaded",
    ),
    token: Optional[str] = typer.Option(
        None,
        "--token",
        "-t",
        help="Hugging Face write token (defaults to HF_TOKEN env var)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing local files and re-build packages",
    ),
    batch_size_gb: float = typer.Option(
        2.0,
        "--batch-size-gb",
        help="Target batch size in GB before committing to Hugging Face in one single commit (default: 2.0 GB)",
    ),
):
    """Batch build standalone packages for every quarter in the specified range."""

    try:
        adapter = get_source_adapter(source)
    except SourcePluginNotFoundError as e:
        console.print(f"[bold red]{e}[/bold red]")
        raise typer.Exit(code=1)

    quarters = parse_quarter_range(start, end)
    console.print(
        f"[bold cyan]Building {len(quarters)} quarterly packages ({quarters[0]} to {quarters[-1]})...[/bold cyan]"
    )

    t_batch_start = time.perf_counter()
    total_dl_sec = 0.0
    total_build_sec = 0.0
    total_upload_sec = 0.0

    built_count = 0
    target_pkg_dir = output_dir or get_default_package_dir()
    batch_quarters: List[str] = []
    batch_bytes = 0
    max_batch_bytes = int(batch_size_gb * 1024 * 1024 * 1024)

    def _flush():
        nonlocal batch_quarters, batch_bytes, total_upload_sec
        if upload and batch_quarters:
            flush_sec = _flush_hf_batch(
                batch_quarters=batch_quarters,
                batch_bytes=batch_bytes,
                target_pkg_dir=target_pkg_dir,
                repo_id=repo_id,
                source=source,
                token=token,
                clean_local=clean_local,
            )
            total_upload_sec += flush_sec
        batch_quarters = []
        batch_bytes = 0

    for q in quarters:
        t_q_start = time.perf_counter()
        existing_duckdb = target_pkg_dir / f"{source}_{q}.duckdb"
        existing_parquet = target_pkg_dir / f"{source}_{q}.parquet"

        if (existing_duckdb.exists() or existing_parquet.exists()) and not force:
            console.print(
                f"[bold green]Package for {q} already compiled locally at {target_pkg_dir}[/bold green]"
            )
            built_count += 1
            batch_quarters.append(q)
            batch_bytes += _calculate_package_size(target_pkg_dir, source, q)
            if batch_bytes >= max_batch_bytes:
                _flush()
            continue

        archive_file, t_dl = _resolve_quarter_archive(adapter, q, source, force)
        if not archive_file:
            continue
        total_dl_sec += t_dl

        t_b0 = time.perf_counter()
        build_quarterly_package(
            data_period=q,
            zip_path=archive_file,
            source_name=source,
            adapter=adapter,
            output_dir=output_dir,
            format=format,
            delete_ascii=delete_ascii,
        )
        t_build = time.perf_counter() - t_b0
        total_build_sec += t_build
        built_count += 1

        batch_quarters.append(q)
        batch_bytes += _calculate_package_size(target_pkg_dir, source, q)

        t_total = time.perf_counter() - t_q_start
        console.print(
            f"[dim]Metrics for {q}: Download={t_dl:.1f}s | Build={t_build:.1f}s | "
            f"Batch buffer={len(batch_quarters)} quarters ({batch_bytes / (1024 * 1024):.1f} MB / {batch_size_gb:.1f} GB) | "
            f"Peak RSS={_get_process_rss_mb():.1f} MB | Total={t_total:.1f}s[/dim]"
        )

        if batch_bytes >= max_batch_bytes:
            _flush()

    _flush()

    if upload and tag and built_count > 0:
        try:
            tag_hf_dataset(repo_id=repo_id, tag=tag, token=token, force=force)
        except Exception as e:
            console.print(f"[bold yellow]Warning: could not create tag '{tag}': {e}[/bold yellow]")

    total_wall_clock = time.perf_counter() - t_batch_start

    summary_table = Table(title=f"Batch Build & Upload Summary ({quarters[0]}..{quarters[-1]})")
    summary_table.add_column("Stage / Metric", style="cyan", no_wrap=True)
    summary_table.add_column("Value", style="magenta")

    summary_table.add_row("Total Quarters Processed", f"{built_count} / {len(quarters)}")
    summary_table.add_row(
        "Total Wall-Clock Time",
        f"{total_wall_clock:.1f}s ({total_wall_clock / 60:.2f} min)",
    )
    summary_table.add_row(
        "Cumulative Download Time",
        f"{total_dl_sec:.1f}s ({total_dl_sec / 60:.2f} min)",
    )
    summary_table.add_row(
        "Cumulative Transformation Time",
        f"{total_build_sec:.1f}s ({total_build_sec / 60:.2f} min)",
    )
    if upload:
        summary_table.add_row(
            "Cumulative Upload Time",
            f"{total_upload_sec:.1f}s ({total_upload_sec / 60:.2f} min)",
        )
        summary_table.add_row("Target HF Repository", repo_id)
        if tag:
            summary_table.add_row("Release Tag", tag)
    summary_table.add_row("Peak Memory RSS", f"{_get_process_rss_mb():.1f} MB")

    console.print(summary_table)
    console.print(
        f"[bold green]✓ Successfully processed all {len(quarters)} packages.[/bold green]"
    )


@app.command("consolidate")
def consolidate_cmd(
    start: str = typer.Option("2004Q1", "--start", help="Starting data period (e.g. 2004Q1)"),
    end: str = typer.Option("2006Q4", "--end", help="Ending data period (e.g. 2006Q4)"),
    package_dir: Optional[Path] = typer.Option(
        None, "--package-dir", "-p", help="Directory containing individual packages"
    ),
    output_name: Optional[str] = typer.Option(
        None,
        "--output-name",
        "-n",
        help="Consolidated output name (defaults to faers_{start}_{end}_consolidated)",
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-o", help="Destination folder for consolidated package"
    ),
) -> None:
    """Consolidate multiple partition packages into a unified dataset with cross-period deduplication."""
    quarters = parse_quarter_range(start, end)
    resolved_output_name = output_name or f"faers_{start}_{end}_consolidated".lower()
    res = build_consolidated_package(
        data_periods=quarters,
        package_dir=package_dir,
        output_name=resolved_output_name,
        output_dir=output_dir,
    )
    console.print(
        Panel(
            f"Consolidated Database: [bold]{res['output_duckdb']}[/bold]\n"
            f"Consolidated Parquet: [bold]{res['output_parquet']}[/bold]\n"
            f"Total Submissions: [cyan]{res['metrics'].get('total_raw_submissions')}[/cyan]\n"
            f"Deduplicated Unique Cases: [green]{res['metrics'].get('total_unique_cases')}[/green]\n"
            f"Cross-Quarter Cases: [yellow]{res['metrics'].get('cases_spanning_multiple_quarters')}[/yellow]\n"
            f"Duplicates Removed: [magenta]{res['metrics'].get('deduplicated_duplicate_reports_removed')} ({res['metrics'].get('deduplication_reduction_pct')})[/magenta]",
            title="Multi-Period Package Consolidated & Deduplicated",
            style="green",
        )
    )


@app.command("inspect")
def inspect_cmd(
    target: Optional[str] = typer.Argument(
        None,
        help="Quarter identifier (e.g. '2004Q1') or path to DuckDB package file",
    ),
    data_period: Optional[str] = typer.Option(
        None,
        "--data-period",
        "-d",
        help="Quarterly data period identifier to inspect (e.g. 2004Q1)",
    ),
    source: str = typer.Option("faers", "--source", "-s", help="Source identifier"),
    package_dir: Optional[Path] = typer.Option(
        None, "--package-dir", "-p", help="Directory containing package files"
    ),
    db_path: Optional[Path] = typer.Option(
        None, "--db-path", help="Direct path to DuckDB database file"
    ),
) -> None:
    """Inspect metadata, row counts, and data quality metrics for any package or database."""
    chosen = target or data_period
    candidate_path = db_path or (Path(chosen) if chosen and Path(chosen).exists() else None)

    if candidate_path and candidate_path.exists():
        # Auto-detect database structure by introspecting internal catalog tables
        tables: set[str] = set()
        try:
            con = duckdb.connect(str(candidate_path), read_only=True)
            tables = {
                r[0]
                for r in con.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
                ).fetchall()
            }
            con.close()
        except duckdb.Error as err:
            console.print(
                f"[yellow]Warning: Could not introspect database catalog in '{candidate_path.name}': {err}[/yellow]"
            )

        # Case A: Consolidated dataset contains _consolidation_quality_report and case_lineage
        if "_consolidation_quality_report" in tables or "case_lineage" in tables:
            report_table = get_consolidation_summary_report(candidate_path)
            console.print(report_table)
            return
        # Case B: Quarterly package contains _package_metadata
        elif "_package_metadata" in tables or any(
            candidate_path.stem.upper().endswith(f"Q{q}") for q in range(1, 5)
        ):
            with Dataset(
                package_dir=candidate_path.parent,
                data_period=candidate_path.stem.split("_")[-1],
                source=source,
            ) as ds:
                ds.print_summary()
                return
        else:
            # Case C: Generic DuckDB database fallback: report row counts for all tables

            tbl_report = Table(title=f"Database Summary: {candidate_path.name}", style="cyan")
            tbl_report.add_column("Table Name", style="bold white")
            tbl_report.add_column("Row Count", style="green")
            con = duckdb.connect(str(candidate_path), read_only=True)
            try:
                for tbl in sorted(tables):
                    row = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()  # nosec B608
                    cnt = row[0] if row is not None else 0
                    tbl_report.add_row(tbl, f"{cnt:,}")
            finally:
                con.close()
            console.print(tbl_report)
            return

    period = chosen or "2004Q1"
    try:
        with Dataset(data_period=period, source=source, package_dir=package_dir) as ds:
            ds.print_summary()
    except Exception as e:
        console.print(f"[bold red]Failed to inspect package:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command("inspect-package", hidden=True)
def inspect_package_cmd(
    data_period: str = typer.Option(
        "2004Q1",
        "--data-period",
        "-d",
        help="Quarterly data period identifier to inspect (e.g. 2004Q1)",
    ),
    source: str = typer.Option("faers", "--source", "-s", help="Source identifier"),
    package_dir: Optional[Path] = typer.Option(
        None, "--package-dir", "-p", help="Directory containing package files"
    ),
) -> None:
    """Inspect and display metadata and data quality report for a compiled package."""
    try:
        with Dataset(data_period=data_period, source=source, package_dir=package_dir) as ds:
            ds.print_summary()
    except Exception as e:
        console.print(f"[bold red]Failed to inspect package:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command("inspect-consolidation", hidden=True)
def inspect_consolidation_cmd(
    name: Optional[str] = typer.Option(
        None,
        "--name",
        "-n",
        help="Consolidated package name (e.g. 'faers_2004_2006_consolidated' or '2004_2006')",
    ),
    db_path: Optional[Path] = typer.Option(
        None,
        "--db-path",
        "-d",
        help="Direct path to consolidated DuckDB package file",
    ),
    package_dir: Optional[Path] = typer.Option(
        None,
        "--package-dir",
        "-p",
        help="Directory containing packages (defaults to data/packages or RAXTIK_PACKAGE_DIR)",
    ),
):
    """Inspect and display metrics for a consolidated multi-period package."""
    base_dir = package_dir or PACKAGE_OUTPUT_DIR
    target_path: Optional[Path] = None

    if db_path is not None:
        target_path = db_path
    elif name is not None:
        filename = name if name.endswith(".duckdb") else f"{name}.duckdb"
        if not filename.startswith("faers_") and not filename.startswith("/"):
            filename = f"faers_{filename}"
        candidate = base_dir / filename
        if not candidate.exists() and not filename.endswith("_consolidated.duckdb"):
            merged_candidate = base_dir / filename.replace(".duckdb", "_consolidated.duckdb")
            if merged_candidate.exists():
                candidate = merged_candidate
        target_path = candidate
    else:
        # Default fallback: check for existing consolidated package
        default_2004_2006 = base_dir / "faers_2004_2006_consolidated.duckdb"
        if default_2004_2006.exists():
            target_path = default_2004_2006
        else:
            merged_files = sorted(base_dir.glob("*consolidated*.duckdb"))
            target_path = merged_files[0] if merged_files else default_2004_2006

    if not target_path.exists():
        console.print(f"[bold red]Database not found at {target_path}[/bold red]")
        raise typer.Exit(code=1)
    report_table = get_consolidation_summary_report(target_path)
    console.print(report_table)


@app.command("hf-download", hidden=True)
def hf_download_cmd(
    data_period_or_name: str = typer.Option(
        "2004Q1",
        "--name",
        "-n",
        "--data-period",
        "-d",
        help="Data period identifier or package name (e.g. 2004Q1 or faers_2004_2006_consolidated)",
    ),
    repo_id: str = typer.Option(
        DEFAULT_HF_REPO,
        "--repo-id",
        help="Hugging Face dataset repository (defaults to RAXTIK_HF_REPO)",
    ),
    dest_dir: Optional[Path] = typer.Option(
        None, "--dest-dir", help="Destination folder (defaults to ~/.cache/raxtik/packages)"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing local files"),
    timeout: int = typer.Option(
        DEFAULT_HTTP_TIMEOUT,
        "--timeout",
        "-t",
        help="HTTP timeout in seconds (defaults to RAXTIK_HTTP_TIMEOUT or 120)",
    ),
    revision: Optional[str] = typer.Option(
        None,
        "--revision",
        help="Git revision or tag on Hugging Face (defaults to package version tag or 'main')",
    ),
) -> None:
    """Download a compiled FAERS package from Hugging Face Hub (zero auth required)."""

    try:
        download_package_from_hf(
            data_period_or_name=data_period_or_name,
            dest_dir=dest_dir,
            repo_id=repo_id,
            force=force,
            timeout=timeout,
            revision=revision,
            tier="bronze",
        )
    except Exception as e:
        console.print(f"[bold red]Download failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command("download")
def download_cmd(
    data_period_or_name: str = typer.Option(
        "2004Q1",
        "--name",
        "-n",
        "--data-period",
        "-d",
        help="Data period identifier or package name (e.g. 2004Q1 or faers_2004_2006_consolidated)",
    ),
    repo_id: str = typer.Option(
        DEFAULT_HF_REPO,
        "--repo-id",
        help="Hugging Face dataset repository (defaults to RAXTIK_HF_REPO)",
    ),
    dest_dir: Optional[Path] = typer.Option(
        None, "--dest-dir", help="Destination folder (defaults to ~/.cache/raxtik/packages)"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing local files"),
    timeout: int = typer.Option(
        DEFAULT_HTTP_TIMEOUT,
        "--timeout",
        "-t",
        help="HTTP timeout in seconds (defaults to RAXTIK_HTTP_TIMEOUT or 120)",
    ),
    revision: Optional[str] = typer.Option(
        None,
        "--revision",
        help="Git revision or tag on Hugging Face (defaults to package version tag or 'main')",
    ),
) -> None:
    """Download pre-compiled safety packages from Hugging Face Hub (zero auth required)."""
    hf_download_cmd(
        data_period_or_name=data_period_or_name,
        repo_id=repo_id,
        dest_dir=dest_dir,
        force=force,
        timeout=timeout,
        revision=revision,
    )


@app.command("hf-upload", hidden=True)
def hf_upload_cmd(
    data_period: Optional[str] = typer.Option(
        None,
        "--data-period",
        "-d",
        help="Single data period (e.g. 2004Q1) or range (e.g. 2007Q1..2026Q1)",
    ),
    start: Optional[str] = typer.Option(
        None, "--start", help="Starting quarter for batch upload (e.g. 2007Q1)"
    ),
    end: Optional[str] = typer.Option(
        None, "--end", help="Ending quarter for batch upload (e.g. 2026Q1)"
    ),
    source: str = typer.Option(
        "faers", "--source", "-s", help="Source name prefix (defaults to 'faers')"
    ),
    repo_id: str = typer.Option(
        DEFAULT_HF_REPO,
        "--repo-id",
        help="Hugging Face dataset repository (defaults to RAXTIK_HF_REPO)",
    ),
    package_dir: Optional[Path] = typer.Option(
        None,
        "--package-dir",
        "-p",
        help="Directory containing packages (defaults to ~/.cache/raxtik/packages)",
    ),
    token: Optional[str] = typer.Option(
        None, "--token", "-t", help="Hugging Face write access token (defaults to HF_TOKEN env var)"
    ),
    parquet: bool = typer.Option(
        True, "--parquet/--no-parquet", help="Whether to include Parquet shards"
    ),
    tag: Optional[str] = typer.Option(
        None,
        "--tag",
        help="Git tag to create/attach on Hugging Face dataset (e.g. '0.1.0.dev1' or 'v0.1.0')",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force overwrite existing tags and remote files on Hugging Face",
    ),
) -> None:
    """Upload compiled packages to Hugging Face Hub (supports single data period or quarter range)."""

    if start and end:
        quarters = parse_quarter_range(start, end)
    elif data_period and (".." in data_period or ":" in data_period):
        sep = ".." if ".." in data_period else ":"
        parts = data_period.split(sep)
        quarters = parse_quarter_range(parts[0], parts[1])
    elif data_period:
        quarters = [data_period.strip()]
    else:
        console.print(
            "[bold red]Please specify either --data-period (e.g. 2004Q1 or 2007Q1..2026Q1) or --start and --end (e.g. --start 2007Q1 --end 2026Q1).[/bold red]"
        )
        raise typer.Exit(code=1)

    tier = "bronze"
    console.print(
        f"[bold cyan]Uploading {len(quarters)} package(s) (tier: {tier}) to Hugging Face Hub ({repo_id})...[/bold cyan]"
    )
    success_count = 0
    fail_count = 0

    for q in quarters:
        try:
            upload_package_to_hf(
                data_period_or_name=q,
                package_dir=package_dir,
                repo_id=repo_id,
                source_name=source,
                token=token,
                include_parquet=parquet,
                force=force,
                tier=tier,
            )
            success_count += 1
        except FileNotFoundError as fnf:
            console.print(f"[yellow]Skipping {q}: {fnf}[/yellow]")
            fail_count += 1
        except Exception as e:
            console.print(f"[bold red]Failed uploading {q}:[/bold red] {e}")
            fail_count += 1

    if tag and success_count > 0:
        try:
            tag_hf_dataset(repo_id=repo_id, tag=tag, token=token, force=force)
        except Exception as tag_err:
            console.print(
                f"[bold yellow]Warning: could not create tag '{tag}': {tag_err}[/bold yellow]"
            )

    if fail_count > 0:
        console.print(
            f"[bold yellow]Batch upload finished: {success_count} succeeded, {fail_count} skipped/failed.[/bold yellow]"
        )
    else:
        console.print(
            f"[bold green]✓ Successfully uploaded all {success_count} package(s) to Hugging Face Hub.[/bold green]"
        )


@app.command("upload")
def upload_cmd(
    data_period: Optional[str] = typer.Option(
        None,
        "--data-period",
        "-d",
        help="Single data period (e.g. 2004Q1) or range (e.g. 2007Q1..2026Q1)",
    ),
    start: Optional[str] = typer.Option(
        None, "--start", help="Starting quarter for batch upload (e.g. 2007Q1)"
    ),
    end: Optional[str] = typer.Option(
        None, "--end", help="Ending quarter for batch upload (e.g. 2026Q1)"
    ),
    source: str = typer.Option(
        "faers", "--source", "-s", help="Source name prefix (defaults to 'faers')"
    ),
    repo_id: str = typer.Option(
        DEFAULT_HF_REPO,
        "--repo-id",
        help="Hugging Face dataset repository (defaults to RAXTIK_HF_REPO)",
    ),
    package_dir: Optional[Path] = typer.Option(
        None,
        "--package-dir",
        "-p",
        help="Directory containing packages (defaults to ~/.cache/raxtik/packages)",
    ),
    token: Optional[str] = typer.Option(
        None, "--token", "-t", help="Hugging Face write access token (defaults to HF_TOKEN env var)"
    ),
    parquet: bool = typer.Option(
        True, "--parquet/--no-parquet", help="Whether to include Parquet shards"
    ),
    tag: Optional[str] = typer.Option(
        None,
        "--tag",
        help="Git tag to create/attach on Hugging Face dataset (e.g. '0.1.0.dev1' or 'v0.1.0')",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force overwrite existing tags and remote files on Hugging Face",
    ),
) -> None:
    """Upload compiled safety packages to Hugging Face Hub (supports single quarter or range)."""
    hf_upload_cmd(
        data_period=data_period,
        start=start,
        end=end,
        source=source,
        repo_id=repo_id,
        package_dir=package_dir,
        token=token,
        parquet=parquet,
        tag=tag,
        force=force,
    )


@app.command("sources")
def sources_cmd() -> None:
    """List installed safety data source connectors (e.g. FAERS)."""

    sources = get_available_sources()
    if not sources:
        console.print("[yellow]No source connectors installed in environment.[/yellow]")
        return

    table = Table(title="Installed Source Connectors", style="cyan")
    table.add_column("Source Name", style="bold green")
    table.add_column("Adapter Class", style="white")
    table.add_column("Remote Fetching", style="magenta")

    for name, cls in sources.items():
        can_fetch = "Yes" if hasattr(cls, "fetch_archive") else "No"
        table.add_row(name, f"{cls.__module__}.{cls.__name__}", can_fetch)

    console.print(table)


index_app = typer.Typer(
    name="index",
    help="Build, incrementally update, compact, verify, and publish tier-agnostic derived deduplication indexes.",
    add_completion=False,
)
app.add_typer(index_app, name="index")


def _resolve_cli_policy(source: str, shards: int) -> Any:
    """Resolves ResolutionPolicy from installed source adapter (or canonical default)."""

    try:
        adapter = get_source_adapter(source)
        policy = (
            adapter.get_resolution_policy()
            if hasattr(adapter, "get_resolution_policy")
            else ResolutionPolicy()
        )
    except SourcePluginNotFoundError:
        policy = ResolutionPolicy()
    return replace(policy, shard_count=shards)


def _find_bronze_package(pkg_dir: Path, source: str, period: str) -> Path:
    """Locates local Bronze `.duckdb` or `.parquet` package, auto-downloading from HF if missing."""
    db_path = pkg_dir / f"{source}_{period}.duckdb"
    if db_path.exists():
        return db_path
    pq_path = pkg_dir / f"{source}_{period}.parquet"
    if pq_path.exists():
        return pq_path

    console.print(
        f"  [cyan]Bronze package {source}_{period} not found locally — downloading from Hugging Face...[/cyan]"
    )
    return download_package_from_hf(
        data_period_or_name=period,
        dest_dir=pkg_dir,
        repo_id=DEFAULT_HF_REPO,
        source_name=source,
        tier="bronze",
    )


def _discover_local_periods(pkg_dir: Path, source: str) -> List[str]:
    """Discovers all locally available quarterly periods for `source` in `pkg_dir`."""

    pattern = re.compile(rf"^{re.escape(source)}_(\d{{4}}Q[1-4])\.(duckdb|parquet)$", re.IGNORECASE)
    found = set()
    if pkg_dir.exists():
        for entry in pkg_dir.iterdir():
            m = pattern.match(entry.name)
            if m:
                found.add(m.group(1).upper())
    return sorted(found)


@index_app.command("build")
def index_build_cmd(
    source: str = typer.Option("faers", "--source", "-s", help="Source identifier (e.g. faers)"),
    tier: str = typer.Option("silver", "--tier", help="Target index tier (e.g. silver, gold)"),
    data_period: Optional[str] = typer.Option(
        None,
        "--data-period",
        "-d",
        help="Single quarter to index (e.g. 2004Q1). Alternative to --start/--end.",
    ),
    start: Optional[str] = typer.Option(
        None,
        "--start",
        help="Optional start quarter for a range (e.g. 2004Q1). If omitted, indexes all local packages.",
    ),
    end: Optional[str] = typer.Option(
        None, "--end", help="Optional end quarter for a range (e.g. 2026Q3)."
    ),
    package_dir: Optional[Path] = typer.Option(
        None, "--package-dir", "-p", help="Directory containing Bronze packages."
    ),
    index_dir: Optional[Path] = typer.Option(
        None,
        "--index-dir",
        help="Destination directory for index files (defaults to ~/.cache/raxtik/indexes/<source>/<tier>).",
    ),
    shards: int = typer.Option(16, "--shards", help="Number of hash shards (default: 16)."),
    compact: bool = typer.Option(
        True,
        "--compact/--no-compact",
        help="Compact completed 4-quarter years into annual ledgers.",
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Re-extract existing period ledgers if already present."
    ),
    cleanup_bronze: bool = typer.Option(
        False,
        "--cleanup-bronze",
        help="Delete each downloaded Bronze package immediately after extracting its ledger (keeps disk small for 91-quarter builds).",
    ),
) -> None:
    """Deterministically builds a fresh immutable tier index snapshot from Bronze packages."""
    pkg_dir = package_dir or get_default_package_dir()
    idx_root = index_dir or get_default_index_dir(source=source, tier=tier)
    policy = _resolve_cli_policy(source, shards)
    state = ShardedStateIndex(idx_root, tier=tier, source=source, policy=policy)

    if data_period and (start or end):
        console.print(
            "[bold red]Use either --data-period for a single quarter or --start/--end for a range, not both.[/bold red]"
        )
        raise typer.Exit(code=1)
    elif data_period:
        periods = [normalize_quarter(data_period)]
    elif start and end:
        periods = parse_quarter_range(start, end)
    elif start or end:
        console.print("[bold red]Both --start and --end must be specified together.[/bold red]")
        raise typer.Exit(code=1)
    else:
        periods = _discover_local_periods(pkg_dir, source.lower())

    if not periods:
        console.print(f"[bold red]No Bronze packages found for '{source}' in {pkg_dir}.[/bold red]")
        raise typer.Exit(code=1)

    console.print(
        f"[bold cyan]Building {tier} index for {source} ({len(periods)} periods: {periods[0]}..{periods[-1]})...[/bold cyan]"
    )
    period_fingerprints: dict[str, str] = {}
    for period in periods:
        src_pkg = _find_bronze_package(pkg_dir, source.lower(), period)
        period_fingerprints[period] = compute_source_fingerprint(src_pkg)
        try:
            state.ledger.extract_period_ledger(src_pkg, period, overwrite=overwrite)
            console.print(f"  [dim]Extracted ledger:[/dim] {period}")
        except FileExistsError:
            console.print(f"  [dim]Ledger already exists (skipped):[/dim] {period}")
        if cleanup_bronze and src_pkg.exists():
            if src_pkg.is_dir():
                shutil.rmtree(src_pkg, ignore_errors=True)
            else:
                src_pkg.unlink(missing_ok=True)

    if compact:
        compacted = state.ledger.compact_completed_years(remove_quarterly=True)
        for c in compacted:
            console.print(f"  [green]Compacted annual ledger:[/green] {c.name}")

    manifest = state.build_from_ledgers(periods=periods, period_fingerprints=period_fingerprints)
    snap = manifest.active_snapshot
    console.print(
        Panel(
            f"Snapshot ID: [bold]{snap.snapshot_id}[/bold]\n"
            f"Tier / Source: {manifest.tier} / {manifest.source}\n"
            f"Indexed Periods: {len(snap.indexed_periods)} ({snap.indexed_periods[0]} .. {snap.indexed_periods[-1]})\n"
            f"Total Submissions: {snap.total_submissions:,}\n"
            f"Unique Entities (Cases): {snap.total_entities:,}\n"
            f"Cross-Quarter Cases: {snap.cross_period_entities:,}\n"
            f"State Shards: {snap.shard_count} ({idx_root / snap.state_dir})",
            title="Index Snapshot Committed",
            style="green",
        )
    )


@index_app.command("update")
def index_update_cmd(
    data_period: str = typer.Option(
        ..., "--data-period", "-d", help="Incoming quarter to append (e.g. 2026Q4)."
    ),
    source: str = typer.Option("faers", "--source", "-s", help="Source identifier (e.g. faers)"),
    tier: str = typer.Option("silver", "--tier", help="Target index tier (e.g. silver, gold)"),
    package_dir: Optional[Path] = typer.Option(
        None, "--package-dir", "-p", help="Directory containing Bronze packages."
    ),
    index_dir: Optional[Path] = typer.Option(
        None, "--index-dir", help="Local index root directory."
    ),
    shards: int = typer.Option(16, "--shards", help="Number of hash shards (default: 16)."),
    compact: bool = typer.Option(
        True,
        "--compact/--no-compact",
        help="Compact completed 4-quarter years into annual ledgers.",
    ),
    replace: bool = typer.Option(
        False, "--replace", help="Replace prior entries for this period (for reprocessed releases)."
    ),
) -> None:
    """Incrementally updates the index with a single incoming quarter (never scans historical Bronze)."""

    pkg_dir = package_dir or get_default_package_dir()
    idx_root = index_dir or get_default_index_dir(source=source, tier=tier)
    period = normalize_quarter(data_period)
    src_pkg = _find_bronze_package(pkg_dir, source.lower(), period)

    policy = _resolve_cli_policy(source, shards)
    state = ShardedStateIndex(idx_root, tier=tier, source=source, policy=policy)
    manifest = state.update_with_period(
        source_path=src_pkg,
        data_period=period,
        compact_years=compact,
        replace_period=replace,
    )
    snap = manifest.active_snapshot
    console.print(
        Panel(
            f"New Snapshot: [bold]{snap.snapshot_id}[/bold] (parent: {snap.parent_snapshot_id})\n"
            f"Indexed Periods: {len(snap.indexed_periods)}\n"
            f"Total Submissions: {snap.total_submissions:,}\n"
            f"Unique Entities: {snap.total_entities:,}\n"
            f"Cross-Quarter Cases: {snap.cross_period_entities:,}",
            title=f"Incremental Index Update ({period})",
            style="green",
        )
    )


@index_app.command("compact")
def index_compact_cmd(
    source: str = typer.Option("faers", "--source", "-s", help="Source identifier"),
    tier: str = typer.Option("silver", "--tier", help="Index tier"),
    index_dir: Optional[Path] = typer.Option(
        None, "--index-dir", help="Local index root directory."
    ),
    keep_quarterly: bool = typer.Option(
        False, "--keep-quarterly", help="Retain quarterly ledger files after annual compaction."
    ),
) -> None:
    """Compacts completed 4-quarter years in `ledger/` and merges accumulated state deltas into a new base snapshot."""
    idx_root = index_dir or get_default_index_dir(source=source, tier=tier)
    state = ShardedStateIndex(idx_root, tier=tier, source=source)

    compacted_ledgers = state.ledger.compact_completed_years(remove_quarterly=not keep_quarterly)
    for p in compacted_ledgers:
        console.print(f"[green]✓ Compacted annual ledger:[/green] {p}")

    manifest = state.load_manifest()
    compacted_state = False
    if manifest is not None and manifest.active_snapshot.active_delta_files:
        new_manifest = state.compact_state_deltas()
        compacted_state = True
        console.print(
            f"[green]✓ Compacted state deltas into immutable base snapshot:[/green] "
            f"{new_manifest.active_snapshot_id} (gen={new_manifest.generation})"
        )

    if not compacted_ledgers and not compacted_state:
        console.print(
            "[yellow]Nothing to compact (no completed 4-quarter years or pending state deltas).[/yellow]"
        )


@index_app.command("verify")
def index_verify_cmd(
    source: str = typer.Option("faers", "--source", "-s", help="Source identifier"),
    tier: str = typer.Option("silver", "--tier", help="Index tier"),
    index_dir: Optional[Path] = typer.Option(
        None, "--index-dir", help="Local index root directory."
    ),
) -> None:
    """Verifies logical rebuild equality by rebuilding from ledgers and comparing canonical state."""

    idx_root = index_dir or get_default_index_dir(source=source, tier=tier)
    state = ShardedStateIndex(idx_root, tier=tier, source=source)
    active = state.load_manifest()
    if active is None:
        console.print(f"[bold red]No manifest.json found at {idx_root}.[/bold red]")
        raise typer.Exit(code=1)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)
        (tmp_root / "ledger").symlink_to((idx_root / "ledger").resolve())
        rebuilder = ShardedStateIndex(
            tmp_root, tier=active.tier, source=active.source, policy=active.policy
        )
        rebuilt = rebuilder.build_from_ledgers(
            snapshot_label="verify",
            periods=active.active_snapshot.indexed_periods,
        )

        active_base = [(idx_root / rel).as_posix() for rel in active.active_snapshot.shard_files]
        active_deltas = [
            (idx_root / rel).as_posix() for rel in active.active_snapshot.active_delta_files
        ]
        rebuilt_base = [(tmp_root / rel).as_posix() for rel in rebuilt.active_snapshot.shard_files]

        shard_count = len(active_base)
        con = duckdb.connect(":memory:")
        try:
            for shard_idx, (a_shard, r_shard) in enumerate(
                zip(active_base, rebuilt_base, strict=True)
            ):
                if active_deltas:
                    resolved_a = build_resolved_state_sql([a_shard], active_deltas)
                    shard_a_sql = (
                        f"SELECT * FROM ({resolved_a}) "
                        f"WHERE CAST(('0x' || substr(md5(case_id), 1, 8)) AS UBIGINT) % {shard_count} = {shard_idx}"
                    )
                else:
                    shard_a_sql = f"SELECT * FROM read_parquet('{a_shard}')"
                shard_r_sql = f"SELECT * FROM read_parquet('{r_shard}')"
                diff_row = con.execute(
                    f"""
                    SELECT COUNT(*) FROM (
                        (({shard_a_sql}) EXCEPT ALL ({shard_r_sql}))
                        UNION ALL
                        (({shard_r_sql}) EXCEPT ALL ({shard_a_sql}))
                    )
                    """  # nosec B608
                ).fetchone()
                if diff_row is None or int(diff_row[0]) != 0:
                    console.print(
                        f"[bold red]Logical state mismatch detected in shard {shard_idx:02d} vs. full ledger rebuild![/bold red]"
                    )
                    raise typer.Exit(code=1)
        finally:
            con.close()

    console.print(
        f"[bold green]✓ Verification passed:[/bold green] Active snapshot "
        f"{active.active_snapshot_id} (gen={active.generation}, "
        f"{len(active.active_snapshot.active_delta_files)} deltas, "
        f"{active.active_snapshot.total_entities:,} entities) matches full ledger rebuild logically."
    )


@index_app.command("lookup")
def index_lookup_cmd(
    case_id: str = typer.Option(..., "--case-id", "-c", help="Case ID to inspect."),
    source: str = typer.Option("faers", "--source", "-s", help="Source identifier"),
    tier: str = typer.Option("silver", "--tier", help="Index tier"),
    index_dir: Optional[Path] = typer.Option(
        None, "--index-dir", help="Local index root directory."
    ),
    snapshot: Optional[str] = typer.Option(
        None, "--snapshot", help="Optional historical snapshot ID."
    ),
) -> None:
    """Performs an O(1) single-shard lookup and displays the full case submission timeline."""

    idx_root = index_dir or get_default_index_dir(source=source, tier=tier)
    state = ShardedStateIndex(idx_root, tier=tier, source=source)
    record = state.get_case_timeline(case_id.strip(), snapshot_id=snapshot)
    if record is None:
        console.print(f"[yellow]Case '{case_id}' not found in {tier} index.[/yellow]")
        raise typer.Exit(code=1)

    tbl = Table(
        title=f"Case Timeline: {record['case_id']} (Winner: {record['latest_primary_id']} @ {record['latest_quarter']})",
        style="cyan",
    )
    tbl.add_column("Rank", style="bold yellow")
    tbl.add_column("Quarter", style="green")
    tbl.add_column("Version", style="white")
    tbl.add_column("Primary ID", style="bold white")
    tbl.add_column("FDA Date", style="dim")
    tbl.add_column("Mfr Date", style="dim")

    timeline: Any = record["timeline"]
    for idx, entry in enumerate(timeline, start=1):
        tbl.add_row(
            f"#{idx}" + (" ★" if idx == 1 else ""),
            str(entry["quarter"]),
            str(entry["version"]),
            str(entry["primary_id"]),
            str(entry["fda_date"]),
            str(entry["mfr_date"]),
        )
    console.print(tbl)


@index_app.command("upload")
def index_upload_cmd(
    source: str = typer.Option("faers", "--source", "-s", help="Source identifier"),
    tier: str = typer.Option("silver", "--tier", help="Index tier"),
    index_dir: Optional[Path] = typer.Option(
        None, "--index-dir", help="Local index root directory."
    ),
    repo_id: str = typer.Option(DEFAULT_HF_REPO, "--repo-id", help="Hugging Face dataset repo ID."),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Hugging Face write token."),
    tag: Optional[str] = typer.Option(
        None,
        "--tag",
        help="Optional Git tag to attach on Hugging Face dataset (e.g. 'v0.1.0.dev3' or 'v0.1.0').",
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing Hugging Face tag if present."
    ),
) -> None:
    """Uploads the local `{tier}/index/` folder to Hugging Face Hub."""
    idx_root = index_dir or get_default_index_dir(source=source, tier=tier)
    url = upload_index_to_hf(
        index_root=idx_root, repo_id=repo_id, tier=tier, token=token, tag=tag, force=force
    )
    console.print(f"[bold green]✓ Published {tier} index to Hugging Face:[/bold green] {url}")


if __name__ == "__main__":
    app()
