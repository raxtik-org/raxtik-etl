"""Longitudinal Cohort Merger & Cross-Quarter Case Deduplication Engine.

Provides functionality to:
1. Load multiple quarterly packages into a consolidated DuckDB database.
2. Build cross-quarter case lineage tracking initial vs latest submissions.
3. Resolve authoritative deduplicated cases across quarter boundaries.
4. Export consolidated Parquet shards and DuckDB packages.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb
from rich.console import Console
from rich.table import Table

from raxtik_etl.packaging.builder import PACKAGE_OUTPUT_DIR, TABLES_TO_EXPORT

console = Console()


def build_merged_longitudinal_package(
    releases: List[str],
    package_dir: Optional[Path] = None,
    output_name: str = "faers_2004_2006_merged",
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Merges individual quarterly packages into a unified, deduplicated longitudinal dataset.

    Args:
        releases: List of quarterly release identifiers, e.g. ['2004Q1', '2004Q2', ..., '2006Q4']
        package_dir: Directory containing individual quarterly packages (default data/packages)
        output_name: Base name for output database and parquet folder
        output_dir: Destination folder for merged package

    Returns:
        Dict with paths and summary metrics.
    """
    pkg_dir = package_dir or PACKAGE_OUTPUT_DIR
    out_dir = output_dir or PACKAGE_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    releases_clean = [r.upper() for r in releases]
    duckdb_path = out_dir / f"{output_name}.duckdb"
    parquet_dir = out_dir / f"{output_name}.parquet"
    parquet_dir.mkdir(parents=True, exist_ok=True)

    if duckdb_path.exists():
        duckdb_path.unlink()

    console.print(
        f"[bold cyan]Merging Longitudinal Cohort [{releases_clean[0]} .. {releases_clean[-1]}] ({len(releases_clean)} quarters)...[/bold cyan]"
    )

    con = duckdb.connect(duckdb_path.as_posix())

    try:
        # 1. Merge each canonical fact table from individual Parquet files
        for table_name in TABLES_TO_EXPORT:
            parquet_files: List[str] = []
            for rel in releases_clean:
                p_file = pkg_dir / f"faers_{rel}.parquet" / f"{table_name}.parquet"
                if not p_file.exists():
                    raise FileNotFoundError(
                        f"Missing quarterly Parquet shard for {rel}: {p_file}. Build quarterly package first."
                    )
                parquet_files.append(p_file.as_posix())

            files_sql = ", ".join(f"'{f}'" for f in parquet_files)
            console.print(f"  [dim]Consolidating table:[/dim] [bold]{table_name}[/bold]")
            con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_parquet([{files_sql}]);")

        # 2. Copy reference codelists from the first quarterly package
        first_pkg_db = pkg_dir / f"faers_{releases_clean[0]}.duckdb"
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

        # 3. Build Longitudinal Case Lineage Table
        console.print("  [dim]Computing longitudinal case lineage across quarters...[/dim]")
        con.execute(
            """
            CREATE OR REPLACE TABLE case_lineage AS
            SELECT
                case_id,
                COUNT(DISTINCT primary_id) AS total_submissions_count,
                COUNT(DISTINCT _source_release) AS quarters_count,
                MIN(_source_release) AS first_release,
                MAX(_source_release) AS latest_release,
                MIN(TRY_CAST(fda_date AS BIGINT)) AS first_fda_date,
                MAX(TRY_CAST(fda_date AS BIGINT)) AS latest_fda_date,
                MIN(canonical_case_version) AS min_case_version,
                MAX(canonical_case_version) AS max_case_version,
                BOOL_OR(initial_or_followup_code = 'F') AS has_followup,
                (COUNT(DISTINCT _source_release) > 1) AS is_cross_quarter_case,
                FIRST(primary_id ORDER BY canonical_case_version ASC, TRY_CAST(fda_date AS BIGINT) ASC, TRY_CAST(primary_id AS BIGINT) ASC) AS initial_primary_id,
                FIRST(primary_id ORDER BY canonical_case_version DESC, TRY_CAST(fda_date AS BIGINT) DESC, TRY_CAST(primary_id AS BIGINT) DESC) AS latest_primary_id
            FROM demo
            GROUP BY case_id;
            """
        )

        # 4. Resolve Deduplicated Authoritative Cases Table (1 row per unique case_id)
        console.print("  [dim]Resolving authoritative deduplicated cases...[/dim]")
        con.execute(
            """
            CREATE OR REPLACE TABLE cases AS
            WITH ranked AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (
                        PARTITION BY case_id
                        ORDER BY
                            canonical_case_version DESC,
                            TRY_CAST(fda_date AS BIGINT) DESC NULLS LAST,
                            TRY_CAST(manufacturer_date AS BIGINT) DESC NULLS LAST,
                            TRY_CAST(primary_id AS BIGINT) DESC
                    ) AS _rnk
                FROM demo
            )
            SELECT * EXCLUDE (_rnk)
            FROM ranked
            WHERE _rnk = 1;
            """
        )

        # 5. Build Comprehensive Longitudinal View
        con.execute(
            """
            CREATE OR REPLACE VIEW case_adverse_events_summary AS
            SELECT
                c.case_id,
                c.primary_id,
                c.canonical_case_version,
                c.event_date,
                c.standard_age_years,
                c.standard_sex_label,
                c._source_release AS latest_release,
                l.first_release,
                l.quarters_count,
                l.total_submissions_count,
                l.is_cross_quarter_case,
                d.reported_drug_name AS primary_suspect_drug,
                d.structural_clean_drug_name,
                r.reported_reaction_term AS reaction_term,
                o.outcome_code,
                co.outcome_label
            FROM cases c
            JOIN case_lineage l ON c.case_id = l.case_id
            LEFT JOIN drug d
                ON c.primary_id = d.primary_id AND d.role_code = 'PS'
            LEFT JOIN reac r
                ON c.primary_id = r.primary_id
            LEFT JOIN outc o
                ON c.primary_id = o.primary_id
            LEFT JOIN _code_outcomes co
                ON o.outcome_code = co.outcome_code;
            """
        )

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
            CREATE OR REPLACE TABLE _longitudinal_quality_report (
                metric_name VARCHAR PRIMARY KEY,
                metric_value VARCHAR
            );
            """
        )

        metrics = [
            ("cohort_start", releases_clean[0]),
            ("cohort_end", releases_clean[-1]),
            ("total_quarters", str(len(releases_clean))),
            ("total_raw_submissions", str(total_reports)),
            ("total_unique_cases", str(total_unique_cases)),
            ("deduplicated_duplicate_reports_removed", str(dedup_diff)),
            ("deduplication_reduction_pct", f"{dedup_pct:.2f}%"),
            ("cases_with_multiple_submissions", str(multi_sub_cases)),
            ("cases_spanning_multiple_quarters", str(cross_quarter_cases)),
            ("total_drug_records", str(total_drugs)),
            ("total_reaction_records", str(total_reacs)),
            ("total_outcome_records", str(total_outcs)),
            ("merged_at", datetime.now(timezone.utc).isoformat()),
        ]

        for m_name, m_val in metrics:
            con.execute("INSERT INTO _longitudinal_quality_report VALUES (?, ?)", (m_name, m_val))

        # 7. Export Merged Parquet Shards
        console.print(f"  [dim]Exporting merged Parquet shards to {parquet_dir}...[/dim]")
        for tbl in TABLES_TO_EXPORT + ["cases", "case_lineage"]:
            tbl_parquet = parquet_dir / f"{tbl}.parquet"
            con.execute(
                f"COPY {tbl} TO '{tbl_parquet.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD);"
            )

        console.print(
            f"[bold green]✓ Successfully built merged longitudinal dataset:[/bold green] {duckdb_path.name} ({duckdb_path.stat().st_size / (1024 * 1024):.2f} MB)"
        )

        return {
            "output_duckdb": duckdb_path.as_posix(),
            "output_parquet": parquet_dir.as_posix(),
            "metrics": dict(metrics),
        }
    finally:
        con.close()


def get_longitudinal_summary_report(db_path: Path | str) -> Table:
    """Generates a rich formatted table summarizing the longitudinal dataset metrics."""
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute(
            "SELECT metric_name, metric_value FROM _longitudinal_quality_report"
        ).fetchall()
        tbl = Table(title="FAERS Longitudinal Cohort Deduplication & Summary", style="cyan")
        tbl.add_column("Metric / Property", style="bold white")
        tbl.add_column("Value", style="green")
        for k, v in rows:
            tbl.add_row(k, v)
        return tbl
    finally:
        con.close()
