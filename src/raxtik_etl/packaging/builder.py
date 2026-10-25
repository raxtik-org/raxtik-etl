"""Package Builder for FAERS Quarterly Datasets.

Builds standalone, self-describing `faers_YYYYQX.duckdb` and partitioned `faers_YYYYQX.parquet/`
containing all 7 canonical tables, the deterministic `cases` view, and internal metadata tables.
Accepts any source adapter satisfying the SourceAdapter protocol via entry-point discovery.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

import duckdb
from rich.console import Console

from raxtik_etl.distribution.huggingface import get_default_package_dir
from raxtik_etl.schema.views import (
    get_active_substances_summary_view_sql,
    get_latest_cases_view_sql,
)
from raxtik_etl.sources.protocol import SourceAdapter, SourceArtifact
from raxtik_etl.sources.registry import get_source_adapter
from raxtik_etl.transformations.metadata import populate_package_metadata

console = Console()

PACKAGE_OUTPUT_DIR = get_default_package_dir()
TABLES_TO_EXPORT = ["demo", "drug", "reac", "outc", "indi", "ther", "rpsr"]


def compute_sha256(filepath: Path | str) -> str:
    """Computes streaming SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def build_quarterly_package(
    release: str,
    zip_path: Path,
    source_name: str = "faers",
    adapter: Optional[SourceAdapter] = None,
    output_dir: Optional[Path] = None,
    format: str = "both",
    delete_ascii: bool = True,
) -> Dict[str, Any]:
    """Builds a standalone .duckdb and/or .parquet package for a specific quarterly release.

    Args:
        release: Release quarter identifier, e.g. '2004Q1'
        zip_path: Path to source ASCII zip archive or extracted directory
        source_name: Name of source connector (defaults to 'faers')
        adapter: Optional custom SourceAdapter instance
        output_dir: Destination package directory (defaults to ~/.cache/raxtik/packages)
        format: Package format to generate: 'both', 'duckdb', or 'parquet' (defaults to 'both')
        delete_ascii: Whether to delete raw source archive/ASCII files after compilation (defaults to True)

    Returns:
        Dict with generated paths, signature, and metadata metrics.
    """
    format_clean = format.lower().strip()
    if format_clean not in ("both", "duckdb", "parquet"):
        raise ValueError(
            f"Invalid format '{format}'. Supported options are 'both', 'duckdb', or 'parquet'."
        )

    out_dir = output_dir or PACKAGE_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    release_clean = release.upper()
    duckdb_path = out_dir / f"{source_name}_{release_clean}.duckdb"
    parquet_dir = out_dir / f"{source_name}_{release_clean}.parquet"

    if duckdb_path.exists():
        duckdb_path.unlink()
    sha_p = duckdb_path.with_suffix(".duckdb.sha256")
    if sha_p.exists():
        sha_p.unlink()
    if parquet_dir.exists():
        shutil.rmtree(parquet_dir, ignore_errors=True)

    console.print(
        f"[bold cyan]Building Safety Package [{source_name.upper()}] for {release_clean} (format: {format_clean})...[/bold cyan]"
    )
    con = duckdb.connect(duckdb_path.as_posix())

    try:
        # 1. Resolve source connector and extract artifact
        active_adapter = adapter or get_source_adapter(source_name)
        artifact = SourceArtifact(path=zip_path, release=release_clean)
        load_result = active_adapter.extract_and_load(con, artifact)

        # 2. Populate internal metadata tables and reference code tables (_metadata, _code_*, etc.)
        populate_package_metadata(
            con=con,
            release=release_clean,
            signature_id=load_result.signature_id,
            source_zip_path=zip_path,
        )

        # 3. Attach SQL views (cases latest-version view and analytical views)
        con.execute(get_latest_cases_view_sql())
        con.execute(get_active_substances_summary_view_sql())

        # 4. Export physical canonical tables to Parquet if requested
        if format_clean in ("both", "parquet"):
            parquet_dir.mkdir(parents=True, exist_ok=True)
            for table_name in TABLES_TO_EXPORT:
                table_parquet = parquet_dir / f"{table_name}.parquet"
                con.execute(
                    f"COPY {table_name} TO '{table_parquet.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD);"
                )
            console.print(f"[bold green]✓ Exported Parquet shards to:[/bold green] {parquet_dir}")

        # 5. Extract summary metrics for manifest
        metrics = con.execute(
            "SELECT metric_name, metric_value FROM _data_quality_report"
        ).fetchall()
        metrics_dict = dict(metrics)

    finally:
        con.close()

    # 6. Clean up raw downloaded ASCII archive if requested
    if delete_ascii and zip_path and zip_path.exists():
        if zip_path.is_file():
            zip_path.unlink()
        elif zip_path.is_dir():
            shutil.rmtree(zip_path)
        console.print(f"[dim]✓ Deleted raw source ASCII archive:[/dim] {zip_path.name}")

    result: Dict[str, Any] = {
        "release": release_clean,
        "signature_id": load_result.signature_id,
        "metrics": metrics_dict,
        "format": format_clean,
    }

    # 7. Finalize outputs based on format
    if format_clean == "parquet":
        if duckdb_path.exists():
            duckdb_path.unlink()
        result["parquet_dir"] = parquet_dir.as_posix()
        console.print(
            f"[bold green]✓ Successfully built Parquet package for {release_clean}[/bold green]"
        )
    else:
        sha256_val = compute_sha256(duckdb_path)
        result["duckdb_path"] = duckdb_path.as_posix()
        result["sha256"] = sha256_val
        if format_clean == "both":
            result["parquet_dir"] = parquet_dir.as_posix()
        console.print(
            f"[bold green]✓ Successfully built package:[/bold green] {duckdb_path.name} "
            f"({duckdb_path.stat().st_size / (1024 * 1024):.2f} MB, SHA-256: [bold]{sha256_val[:12]}[/bold])"
        )

    return result
