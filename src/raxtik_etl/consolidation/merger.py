"""Multi-Period Consolidation & Cross-Period Case Deduplication Engine.

Provides functionality to:
1. Load multiple partition packages into a consolidated DuckDB database.
2. Build cross-period case lineage tracking initial vs latest submissions.
3. Resolve authoritative deduplicated cases across period boundaries.
4. Export consolidated Parquet shards and DuckDB packages.
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb
from rich.console import Console
from rich.table import Table

from raxtik_etl.packaging.builder import PACKAGE_OUTPUT_DIR
from raxtik_etl.schema.registry import CANONICAL_TABLES
from raxtik_etl.sources.registry import get_source_adapter

console = Console()


def validate_and_normalize_data_periods(data_periods: List[str]) -> List[str]:
    """Validates period inputs, ensuring non-empty, valid format, deduplicated, and chronologically ordered.

    Args:
        data_periods: List of temporal period identifiers (e.g., ['2004Q1', '2005Q2']).

    Returns:
        List of deduplicated, chronologically sorted period strings.

    Raises:
        ValueError: If data_periods is empty or contains malformed period formats.
    """
    if not data_periods:
        raise ValueError("Data periods list cannot be empty. Please provide at least one period.")

    pattern = re.compile(r"^(\d{4})Q([1-4])$")
    normalized: List[str] = []
    seen = set()

    for p in data_periods:
        clean = p.strip().upper()
        if not pattern.match(clean):
            raise ValueError(
                f"Invalid period identifier '{p}'. Expected format 'YYYYQX' (e.g. '2004Q1')."
            )
        if clean not in seen:
            seen.add(clean)
            normalized.append(clean)

    # Sort chronologically by year and quarter
    normalized.sort(key=lambda x: (int(x[:4]), int(x[-1])))
    return normalized


def build_consolidated_package(
    data_periods: List[str],
    package_dir: Optional[Path] = None,
    output_name: str = "faers_2004_2006_consolidated",
    output_dir: Optional[Path] = None,
    source_name: str = "faers",
) -> Dict[str, Any]:
    """Merges individual partition packages into a unified, deduplicated consolidated dataset.

    Executes cross-period deduplication, longitudinal case lineage tracking,
    and materializes authoritative latest case snapshots.

    Args:
        data_periods: List of quarterly data period identifiers, e.g. ['2004Q1', '2004Q2', ..., '2006Q4'].
        package_dir: Directory containing individual quarterly packages (default data/packages).
        output_name: Base name for output database and parquet folder.
        output_dir: Destination folder for consolidated package.
        source_name: Connector name (defaults to 'faers').

    Returns:
        Dict containing paths to output_duckdb, output_parquet, and reconciliation metrics.

    Raises:
        FileNotFoundError: If individual quarterly Parquet or DuckDB packages do not exist.
        ValueError: If data_periods list is empty or invalid.
    """
    pkg_dir = package_dir or PACKAGE_OUTPUT_DIR
    out_dir = output_dir or PACKAGE_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    periods_clean = validate_and_normalize_data_periods(data_periods)
    duckdb_path = out_dir / f"{output_name}.duckdb"
    parquet_dir = out_dir / f"{output_name}.parquet"

    # Temporary staging paths for atomic promotion
    tmp_duckdb = out_dir / f".tmp_{duckdb_path.name}"
    tmp_parquet = out_dir / f".tmp_{parquet_dir.name}"

    if tmp_duckdb.exists():
        tmp_duckdb.unlink()
    if tmp_parquet.exists():
        shutil.rmtree(tmp_parquet, ignore_errors=True)

    console.print(
        f"[bold cyan]Consolidating Packages [{periods_clean[0]} .. {periods_clean[-1]}] ({len(periods_clean)} periods)...[/bold cyan]"
    )

    con = duckdb.connect(tmp_duckdb.as_posix())

    try:
        # 1. Merge each canonical fact table from individual Parquet files
        for table_name in CANONICAL_TABLES:
            parquet_files: List[str] = []
            for rel in periods_clean:
                p_file = pkg_dir / f"{source_name}_{rel}.parquet" / f"{table_name}.parquet"
                if not p_file.exists():
                    raise FileNotFoundError(
                        f"Missing quarterly Parquet shard for {rel}: {p_file}. Build quarterly package first."
                    )
                parquet_files.append(p_file.as_posix())

            files_sql = ", ".join(f"'{f}'" for f in parquet_files)
            console.print(f"  [dim]Consolidating table:[/dim] [bold]{table_name}[/bold]")
            con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_parquet([{files_sql}]);")

        # 2. Copy reference codelists from the first quarterly package
        first_pkg_db = pkg_dir / f"{source_name}_{periods_clean[0]}.duckdb"
        if first_pkg_db.exists():
            con.execute(f"ATTACH '{first_pkg_db.as_posix()}' AS ref_pkg (READ_ONLY);")
            ref_tables = [
                "_code_roles",
                "_code_outcomes",
                "_code_outcome_semantics",
                "_code_occupations",
                "_code_report_sources",
                "_code_dechallenge",
                "_code_rechallenge",
            ]
            for rt in ref_tables:
                con.execute(f"CREATE TABLE {rt} AS SELECT * FROM ref_pkg.{rt};")
            con.execute("DETACH ref_pkg;")

        # 3. Resolve adapter and build Longitudinal Case Lineage Table
        active_adapter = get_source_adapter(source_name)
        console.print("  [dim]Computing longitudinal case lineage across quarters...[/dim]")
        con.execute(active_adapter.get_case_lineage_sql())

        # 4. Resolve Deduplicated Authoritative Cases Table (materialized for cohort query performance)
        console.print("  [dim]Resolving authoritative deduplicated cases...[/dim]")
        con.execute(active_adapter.get_case_resolution_sql())
        con.execute(
            """
            CREATE OR REPLACE TABLE cases_mat AS SELECT * FROM cases;
            DROP VIEW cases;
            ALTER TABLE cases_mat RENAME TO cases;
            """
        )

        # 5. Build Analytical Views via Adapter
        for _v_name, v_sql in active_adapter.get_summary_views_sql().items():
            con.execute(v_sql)

        # 6. Compute Quality Report & Deduplication Statistics
        def _scalar(sql: str, default: int = 0) -> int:
            row = con.execute(sql).fetchone()
            return int(row[0]) if row is not None else default

        total_reports = _scalar("SELECT count(*) FROM demo")
        total_unique_cases = _scalar("SELECT count(*) FROM cases")
        cross_quarter_cases = _scalar(
            "SELECT count(*) FROM case_lineage WHERE is_cross_quarter_case = TRUE"
        )
        multi_sub_cases = _scalar(
            "SELECT count(*) FROM case_lineage WHERE total_submissions_count > 1"
        )
        total_drugs = _scalar("SELECT count(*) FROM drug")
        total_reacs = _scalar("SELECT count(*) FROM reac")
        total_outcs = _scalar("SELECT count(*) FROM outc")

        dedup_diff = total_reports - total_unique_cases
        dedup_pct = (dedup_diff / total_reports * 100) if total_reports > 0 else 0.0

        con.execute(
            """
            CREATE OR REPLACE TABLE _consolidation_quality_report (
                metric_name VARCHAR PRIMARY KEY,
                metric_value VARCHAR
            );
            """
        )

        metrics = [
            ("period_start", periods_clean[0]),
            ("period_end", periods_clean[-1]),
            ("total_periods", str(len(periods_clean))),
            ("total_raw_submissions", str(total_reports)),
            ("total_unique_cases", str(total_unique_cases)),
            ("deduplicated_duplicate_reports_removed", str(dedup_diff)),
            ("deduplication_reduction_pct", f"{dedup_pct:.2f}%"),
            ("cases_with_multiple_submissions", str(multi_sub_cases)),
            ("cases_spanning_multiple_quarters", str(cross_quarter_cases)),
            ("total_drug_records", str(total_drugs)),
            ("total_reaction_records", str(total_reacs)),
            ("total_outcome_records", str(total_outcs)),
            ("consolidated_at", datetime.now(timezone.utc).isoformat()),
        ]

        for m_name, m_val in metrics:
            con.execute("INSERT INTO _consolidation_quality_report VALUES (?, ?)", (m_name, m_val))

        # 7. Export Merged Parquet Shards
        console.print(
            f"  [dim]Exporting consolidated Parquet shards to staging {tmp_parquet}...[/dim]"
        )
        tmp_parquet.mkdir(parents=True, exist_ok=True)
        for tbl in list(CANONICAL_TABLES) + ["cases", "case_lineage"]:
            tbl_parquet = tmp_parquet / f"{tbl}.parquet"
            con.execute(
                f"COPY {tbl} TO '{tbl_parquet.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD);"
            )

    except Exception:
        if tmp_duckdb.exists():
            tmp_duckdb.unlink()
        if tmp_parquet.exists():
            shutil.rmtree(tmp_parquet, ignore_errors=True)
        raise
    finally:
        con.close()

    # 8. Atomically promote staging artifacts
    tmp_duckdb.replace(duckdb_path)
    if parquet_dir.exists():
        shutil.rmtree(parquet_dir, ignore_errors=True)
    tmp_parquet.replace(parquet_dir)

    console.print(
        f"[bold green]✓ Successfully built consolidated dataset:[/bold green] {duckdb_path.name} ({duckdb_path.stat().st_size / (1024 * 1024):.2f} MB)"
    )

    return {
        "output_duckdb": duckdb_path.as_posix(),
        "output_parquet": parquet_dir.as_posix(),
        "metrics": dict(metrics),
    }


def get_consolidation_summary_report(db_path: Path | str) -> Table:
    """Generates a rich formatted table summarizing the consolidated dataset metrics.

    Args:
        db_path: Path to the consolidated DuckDB package file.

    Returns:
        rich.table.Table: Formatted table with metric names and values from `_consolidation_quality_report`.
    """
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute(
            "SELECT metric_name, metric_value FROM _consolidation_quality_report"
        ).fetchall()
        tbl = Table(title="Consolidated Multi-Period Package Summary", style="cyan")
        tbl.add_column("Metric / Property", style="bold white")
        tbl.add_column("Value", style="green")
        for k, v in rows:
            tbl.add_row(k, v)
        return tbl
    finally:
        con.close()
