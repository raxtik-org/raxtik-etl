"""Package Builder for Pharmacovigilance Quarterly Datasets.

Builds standalone, self-describing `{source}_{data_period}.duckdb` and partitioned
`{source}_{data_period}.parquet/` containing all 7 canonical tables, the deterministic
`cases` view, and internal metadata tables. Accepts any source adapter satisfying
the SourceAdapter protocol via entry-point discovery.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import duckdb
from rich.console import Console

from raxtik_etl.distribution.huggingface import get_default_package_dir
from raxtik_etl.migrations import migration_manager
from raxtik_etl.schema.registry import (
    CANONICAL_SCHEMA_VERSION,
    CANONICAL_TABLES,
)
from raxtik_etl.sources.protocol import SourceAdapter, SourceArtifact
from raxtik_etl.sources.registry import get_source_adapter
from raxtik_etl.transformations.metadata import populate_package_metadata

console = Console()

PACKAGE_OUTPUT_DIR = get_default_package_dir()
PACKAGE_FORMAT_VERSION = "1.0.0"
TABLES_TO_EXPORT = list(CANONICAL_TABLES)


def compute_sha256(filepath: Path | str) -> str:
    """Computes streaming SHA-256 checksum of a file.

    Args:
        filepath: Filesystem path to the target file.

    Returns:
        Hexadecimal SHA-256 digest string.
    """
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def validate_package_format(format_name: str) -> str:
    """Validates and normalizes package format argument ('both', 'duckdb', 'parquet').

    Args:
        format_name: Target package format ('both', 'duckdb', or 'parquet').

    Returns:
        Normalized lowercase format string.

    Raises:
        ValueError: If format_name is not one of the supported formats.
    """
    fmt = format_name.lower().strip()
    if fmt not in ("both", "duckdb", "parquet"):
        raise ValueError(
            f"Invalid format '{format_name}'. Supported options are 'both', 'duckdb', or 'parquet'."
        )
    return fmt


def resolve_package_paths(
    data_period: str,
    source_name: str,
    output_dir: Optional[Path] = None,
) -> tuple[Path, Path, Path, Path]:
    """Resolves target and temporary staging paths for DuckDB and Parquet packages.

    Args:
        data_period: Temporal coverage period identifier (e.g., '2004Q1').
        source_name: Connector name (e.g., 'faers').
        output_dir: Optional custom package output directory.

    Returns:
        Tuple of (duckdb_path, parquet_dir, tmp_duckdb, tmp_parquet).
    """
    out_dir = output_dir or PACKAGE_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    period_clean = data_period.upper().strip()
    duckdb_path = out_dir / f"{source_name}_{period_clean}.duckdb"
    parquet_dir = out_dir / f"{source_name}_{period_clean}.parquet"

    tmp_duckdb = out_dir / f".tmp_{duckdb_path.name}"
    tmp_parquet = out_dir / f".tmp_{parquet_dir.name}"

    if tmp_duckdb.exists():
        tmp_duckdb.unlink()
    if tmp_parquet.exists():
        shutil.rmtree(tmp_parquet, ignore_errors=True)

    return duckdb_path, parquet_dir, tmp_duckdb, tmp_parquet


def execute_package_pipeline(
    con: duckdb.DuckDBPyConnection,
    adapter: SourceAdapter,
    source_name: str,
    zip_path: Path,
    data_period: str,
) -> Any:
    """Executes the extraction, loading, metadata recording, and view attachment pipeline.

    Args:
        con: Active DuckDB database connection.
        adapter: SourceAdapter protocol implementation.
        source_name: Connector identifier.
        zip_path: Filesystem path to source archive file.
        data_period: Temporal coverage period identifier.

    Returns:
        SourceLoadResult from the adapter containing signature_id and reference tables.

    Raises:
        ValueError: If adapter does not support the active CANONICAL_SCHEMA_VERSION.
    """
    # 1. Validate adapter canonical schema compatibility
    if hasattr(adapter, "supports_schema") and not adapter.supports_schema(
        CANONICAL_SCHEMA_VERSION
    ):
        raise ValueError(
            f"Source adapter '{adapter.source_name}' does not support canonical schema version '{CANONICAL_SCHEMA_VERSION}'"
        )

    # 2. Extract and load canonical tables
    artifact = SourceArtifact(
        path=zip_path,
        data_period=data_period,
        target_schema_version=CANONICAL_SCHEMA_VERSION,
    )
    load_result = adapter.extract_and_load(con, artifact)

    # 3. Populate internal metadata tables and reference code tables dynamically
    source_etl_version = getattr(adapter, "etl_version", "1.0.0")
    source_lib_version = getattr(
        adapter,
        "source_version",
        getattr(adapter, "version", None),
    )
    populate_package_metadata(
        con=con,
        data_period=data_period,
        signature_id=load_result.signature_id,
        source_zip_path=zip_path,
        etl_version=source_etl_version,
        source_name=getattr(adapter, "source_name", source_name),
        source_version=source_lib_version,
        reference_tables=load_result.reference_tables,
        package_format_version=PACKAGE_FORMAT_VERSION,
    )

    # 4. Register and apply source schema migrations
    if hasattr(adapter, "get_migrations"):
        source_migs = adapter.get_migrations()
        if source_migs:
            for mig in source_migs:
                migration_manager.register(mig)
    migration_manager.apply_pending_migrations(
        con, source_name=getattr(adapter, "source_name", source_name)
    )

    # 5. Attach SQL views via source adapter hooks (deduplication & analytical views)
    if hasattr(adapter, "get_case_resolution_sql"):
        res_sql = adapter.get_case_resolution_sql()
        if res_sql:
            con.execute(res_sql)
    if hasattr(adapter, "get_summary_views_sql"):
        views = adapter.get_summary_views_sql()
        if views:
            for _view_name, view_sql in views.items():
                if view_sql:
                    con.execute(view_sql)

    return load_result


def export_canonical_tables_to_parquet(
    con: duckdb.DuckDBPyConnection,
    target_tables: Sequence[str],
    destination_dir: Path,
) -> None:
    """Exports physical canonical tables to compressed Parquet files.

    Args:
        con: Active DuckDB database connection.
        target_tables: List or tuple of canonical table names to export.
        destination_dir: Staging destination directory for Parquet files.

    Returns:
        None
    """
    destination_dir.mkdir(parents=True, exist_ok=True)
    for table_name in target_tables:
        table_parquet = destination_dir / f"{table_name}.parquet"
        con.execute(
            f"COPY {table_name} TO '{table_parquet.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD);"
        )
    console.print(
        f"[bold green]✓ Exported Parquet shards to staging:[/bold green] {destination_dir}"
    )


def promote_staging_artifacts(
    tmp_duckdb: Path,
    duckdb_path: Path,
    tmp_parquet: Path,
    parquet_dir: Path,
    format_clean: str,
) -> None:
    """Atomically promotes staging artifacts (.tmp_*) to final destination paths.

    Args:
        tmp_duckdb: Temporary staging path for compiled DuckDB file.
        duckdb_path: Final destination path for DuckDB file.
        tmp_parquet: Temporary staging path for Parquet directory.
        parquet_dir: Final destination path for Parquet directory.
        format_clean: Target format ('both', 'duckdb', or 'parquet').

    Returns:
        None
    """
    if format_clean in ("both", "duckdb"):
        tmp_duckdb.replace(duckdb_path)
    elif tmp_duckdb.exists():
        tmp_duckdb.unlink()

    if format_clean in ("both", "parquet"):
        if parquet_dir.exists():
            shutil.rmtree(parquet_dir, ignore_errors=True)
        tmp_parquet.replace(parquet_dir)
    elif tmp_parquet.exists():
        shutil.rmtree(tmp_parquet, ignore_errors=True)


def cleanup_source_archive(zip_path: Optional[Path]) -> None:
    """Removes temporary source archive zip or extracted directory to conserve disk space.

    Args:
        zip_path: Filesystem path to the source archive file or directory to delete.

    Returns:
        None
    """
    if zip_path and zip_path.exists():
        if zip_path.is_file():
            zip_path.unlink()
        elif zip_path.is_dir():
            shutil.rmtree(zip_path)
        console.print(f"[dim]✓ Deleted raw source ASCII archive:[/dim] {zip_path.name}")


def build_quarterly_package(
    data_period: str,
    zip_path: Path,
    source_name: str = "faers",
    adapter: Optional[SourceAdapter] = None,
    output_dir: Optional[Path] = None,
    format: str = "both",
    delete_ascii: bool = True,
) -> Dict[str, Any]:
    """Builds a standalone .duckdb and/or .parquet package for a specific quarterly release.

    Builds atomically via staging paths (.tmp_*) to prevent corrupting existing packages
    if an error or interruption occurs during extraction.

    Args:
        data_period: Temporal coverage period identifier (e.g., '2004Q1').
        zip_path: Path to source ASCII zip archive or extracted directory.
        source_name: Name of source connector (defaults to 'faers').
        adapter: Optional custom SourceAdapter instance.
        output_dir: Destination package directory (defaults to ~/.cache/raxtik/packages).
        format: Package format to generate: 'both', 'duckdb', or 'parquet' (defaults to 'both').
        delete_ascii: Whether to delete raw source archive/ASCII files after compilation (defaults to True).

    Returns:
        Dict with generated paths, signature, and metadata metrics.
    """
    period_clean = data_period.upper().strip()
    if not period_clean:
        raise ValueError("data_period (e.g. '2004Q1') must be provided.")

    format_clean = validate_package_format(format)
    duckdb_path, parquet_dir, tmp_duckdb, tmp_parquet = resolve_package_paths(
        data_period=period_clean,
        source_name=source_name,
        output_dir=output_dir,
    )

    console.print(
        f"[bold cyan]Building Safety Package [{source_name.upper()}] for {period_clean} (format: {format_clean})...[/bold cyan]"
    )
    con = duckdb.connect(tmp_duckdb.as_posix())

    try:
        active_adapter = adapter or get_source_adapter(source_name)
        load_result = execute_package_pipeline(
            con=con,
            adapter=active_adapter,
            source_name=source_name,
            zip_path=zip_path,
            data_period=period_clean,
        )

        if format_clean in ("both", "parquet"):
            export_canonical_tables_to_parquet(
                con=con,
                target_tables=CANONICAL_TABLES,
                destination_dir=tmp_parquet,
            )

        metrics = con.execute(
            "SELECT metric_name, metric_value FROM _data_quality_report"
        ).fetchall()
        metrics_dict = dict(metrics)

    except Exception:
        if tmp_duckdb.exists():
            tmp_duckdb.unlink()
        if tmp_parquet.exists():
            shutil.rmtree(tmp_parquet, ignore_errors=True)
        raise
    finally:
        con.close()

    promote_staging_artifacts(
        tmp_duckdb=tmp_duckdb,
        duckdb_path=duckdb_path,
        tmp_parquet=tmp_parquet,
        parquet_dir=parquet_dir,
        format_clean=format_clean,
    )

    if delete_ascii:
        cleanup_source_archive(zip_path)

    result: Dict[str, Any] = {
        "data_period": period_clean,
        "signature_id": load_result.signature_id,
        "metrics": metrics_dict,
        "format": format_clean,
    }

    if format_clean == "parquet":
        if duckdb_path.exists():
            duckdb_path.unlink()
        result["parquet_dir"] = parquet_dir.as_posix()
        console.print(
            f"[bold green]✓ Successfully built Parquet package for {period_clean}[/bold green]"
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
