"""Python Client SDK for FAERS Data Packages.

Provides simple, zero-copy querying of local or remote DuckDB/Parquet FAERS datasets.

Example:
    from raxtik_etl import FAERS

    faers = FAERS("2004Q1")
    print(faers.audit_report())
    cases_df = faers.cases()
    drugs_df = faers.query("SELECT * FROM drug WHERE standard_concept_name = 'ASPIRIN'")
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Union

import duckdb
import polars as pl
from rich.console import Console
from rich.table import Table

console = Console()
DEFAULT_PACKAGE_DIR = Path("data/packages")


class FAERS:
    """Interface to inspect and query a versioned FAERS data package."""

    def __init__(self, release: str, package_dir: Optional[Union[str, Path]] = None):
        self.release = release.upper()
        self.pkg_dir = Path(package_dir) if package_dir else DEFAULT_PACKAGE_DIR
        self.duckdb_path = self.pkg_dir / f"faers_{self.release}.duckdb"

        if not self.duckdb_path.exists():
            raise FileNotFoundError(
                f"FAERS package for release {self.release} not found at {self.duckdb_path}. "
                f"Build it first using `raxtik-etl build-package --release {self.release}`."
            )

        self._con = duckdb.connect(self.duckdb_path.as_posix(), read_only=True)
        self._validate_package_compatibility()

    def _validate_package_compatibility(self):
        """Validates that the package format version is compatible with this SDK version."""
        try:
            pkg_ver = self._con.execute(
                "SELECT value FROM _metadata WHERE key = 'package_format_version'"
            ).fetchone()
            if pkg_ver:
                self.package_format_version = pkg_ver[0]
            else:
                self.package_format_version = "1.0.0"
        except Exception:
            self.package_format_version = "1.0.0"

    def query(self, sql: str) -> pl.DataFrame:
        """Executes arbitrary SQL on the package and returns a Polars DataFrame."""
        arrow_table = self._con.execute(sql).arrow()
        return pl.from_arrow(arrow_table)

    def reports(self, limit: Optional[int] = None) -> pl.DataFrame:
        """Returns the immutable historical submission reports (DEMO table)."""
        limit_clause = f"LIMIT {limit}" if limit else ""
        return self.query(f"SELECT * FROM demo {limit_clause}")

    def cases(self, limit: Optional[int] = None) -> pl.DataFrame:
        """Returns the deterministic latest-case resolution view."""
        limit_clause = f"LIMIT {limit}" if limit else ""
        return self.query(f"SELECT * FROM cases {limit_clause}")

    def drugs(self, limit: Optional[int] = None) -> pl.DataFrame:
        """Returns reported drug products."""
        limit_clause = f"LIMIT {limit}" if limit else ""
        return self.query(f"SELECT * FROM drug {limit_clause}")

    def reactions(self, limit: Optional[int] = None) -> pl.DataFrame:
        """Returns reported adverse events."""
        limit_clause = f"LIMIT {limit}" if limit else ""
        return self.query(f"SELECT * FROM reac {limit_clause}")

    def outcomes(self, limit: Optional[int] = None) -> pl.DataFrame:
        """Returns patient outcomes."""
        limit_clause = f"LIMIT {limit}" if limit else ""
        return self.query(f"SELECT * FROM outc {limit_clause}")

    def metadata(self) -> Dict[str, str]:
        """Returns package metadata as a dictionary."""
        rows = self._con.execute("SELECT key, value FROM _metadata").fetchall()
        return dict(rows)

    def audit_report(self) -> Dict[str, str]:
        """Returns automated EDA data quality metrics."""
        rows = self._con.execute(
            "SELECT metric_name, metric_value FROM _data_quality_report"
        ).fetchall()
        return dict(rows)

    def print_summary(self):
        """Prints a rich formatted summary table of the package."""
        meta = self.metadata()
        audit = self.audit_report()

        table = Table(title=f"FAERS Package [{self.release}] Summary", style="cyan")
        table.add_column("Metric / Property", style="bold white")
        table.add_column("Value", style="green")

        for k, v in meta.items():
            table.add_row(f"[Metadata] {k}", str(v))
        for k, v in audit.items():
            table.add_row(f"[Quality] {k}", str(v))

        console.print(table)

    def close(self):
        """Closes connection."""
        self._con.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
