"""Package Builder for FAERS Quarterly Datasets.

Builds standalone, self-describing `faers_YYYYQX.duckdb` and partitioned `faers_YYYYQX.parquet/`
containing all 7 canonical tables, the deterministic `cases` view, and internal metadata tables.
Accepts any source adapter satisfying the SourceAdapter protocol via entry-point discovery.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import duckdb
from rich.console import Console

from raxtik_etl.schema.views import (
    get_active_substances_summary_view_sql,
    get_latest_cases_view_sql,
)
from raxtik_etl.sources.protocol import SourceAdapter, SourceArtifact
from raxtik_etl.sources.registry import get_source_adapter
from raxtik_etl.transformations.metadata import populate_package_metadata

console = Console()

PACKAGE_OUTPUT_DIR = Path("data/packages")
TABLES_TO_EXPORT = ["demo", "drug", "reac", "outc", "indi", "ther", "rpsr"]


def build_quarterly_package(
    release: str,
    zip_path: Path,
    source_name: str = "faers",
    adapter: Optional[SourceAdapter] = None,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Builds a standalone .duckdb and .parquet package for a specific quarterly release."""
    out_dir = output_dir or PACKAGE_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    release_clean = release.upper()
    duckdb_path = out_dir / f"{source_name}_{release_clean}.duckdb"
    parquet_dir = out_dir / f"{source_name}_{release_clean}.parquet"
    parquet_dir.mkdir(parents=True, exist_ok=True)

    if duckdb_path.exists():
        duckdb_path.unlink()

    console.print(
        f"[bold cyan]Building Safety Package [{source_name.upper()}] for {release_clean}...[/bold cyan]"
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

        # 4. Export all physical canonical tables to Parquet
        for table_name in TABLES_TO_EXPORT:
            table_parquet = parquet_dir / f"{table_name}.parquet"
            con.execute(
                f"COPY {table_name} TO '{table_parquet.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD);"
            )

        # 5. Extract summary metrics for manifest
        metrics = con.execute(
            "SELECT metric_name, metric_value FROM _data_quality_report"
        ).fetchall()
        metrics_dict = dict(metrics)

        console.print(
            f"[bold green]✓ Successfully built package:[/bold green] {duckdb_path.name} ({duckdb_path.stat().st_size / (1024 * 1024):.2f} MB)"
        )
        console.print(f"[bold green]✓ Exported Parquet shards to:[/bold green] {parquet_dir}")

        return {
            "release": release_clean,
            "signature_id": load_result.signature_id,
            "duckdb_path": duckdb_path.as_posix(),
            "parquet_dir": parquet_dir.as_posix(),
            "metrics": metrics_dict,
        }
    finally:
        con.close()
