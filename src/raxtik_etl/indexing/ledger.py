"""Tiered append-only submission ledger manager for the RAXTIK Indexing Engine.

Extracts lightweight resolution metadata from immutable Bronze packages into
append-only quarterly Parquet files and automatically compacts completed
4-quarter years into immutable annual Parquet files (`YYYY.parquet`).
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

import duckdb

from raxtik_etl.indexing.models import ResolutionPolicy
from raxtik_etl.sources.temporal import normalize_quarter

QUARTERLY_LEDGER_RE = re.compile(r"^(\d{4})Q([1-4])\.parquet$")
ANNUAL_LEDGER_RE = re.compile(r"^(\d{4})\.parquet$")


class LedgerManager:
    """Manages tiered append-only submission ledgers under `<index_root>/ledger/`."""

    def __init__(self, index_root: Path | str, policy: Optional[ResolutionPolicy] = None) -> None:
        self.index_root = Path(index_root)
        self.ledger_dir = self.index_root / "ledger"
        self.policy = policy or ResolutionPolicy()

    def ensure_dirs(self) -> None:
        self.ledger_dir.mkdir(parents=True, exist_ok=True)

    def _describe_columns(self, con: duckdb.DuckDBPyConnection, relation_sql: str) -> Set[str]:
        rows = con.execute(f"DESCRIBE SELECT * FROM {relation_sql}").fetchall()  # nosec B608
        return {str(r[0]).lower() for r in rows}

    def extract_period_ledger(
        self,
        source_path: Path | str,
        data_period: str,
        overwrite: bool = False,
    ) -> Path:
        """Extracts resolution metadata for a single period into `ledger/<PERIOD>.parquet`.

        Supports reading from either a compiled `.duckdb` package, a `.parquet` directory
        containing `<source_table>.parquet`, or a direct `.parquet` file.

        Args:
            source_path: Path to the Bronze `.duckdb` file, `.parquet` directory, or `.parquet` file.
            data_period: Period identifier (e.g. `'2004Q1'`).
            overwrite: If False and the quarterly ledger (or its compacted annual ledger) already
                exists, raises FileExistsError to preserve append-only immutability.

        Returns:
            Path to the written quarterly ledger Parquet file.
        """
        self.ensure_dirs()
        period = normalize_quarter(data_period)
        year = period[:4]
        annual_path = self.ledger_dir / f"{year}.parquet"
        target_path = self.ledger_dir / f"{period}.parquet"

        if not overwrite:
            if target_path.exists():
                raise FileExistsError(
                    f"Ledger for period {period} already exists at {target_path}. "
                    "Pass overwrite=True to explicitly re-extract."
                )
            if annual_path.exists():
                raise FileExistsError(
                    f"Annual compacted ledger for year {year} already exists at {annual_path}. "
                    "Pass overwrite=True to explicitly re-extract."
                )

        src = Path(source_path)
        if not src.exists():
            raise FileNotFoundError(f"Source package not found: {src}")

        tmp_path = self.ledger_dir / f".tmp_{period}.parquet"
        if tmp_path.exists():
            tmp_path.unlink()

        con = duckdb.connect(":memory:")
        try:
            if src.is_dir():
                parquet_file = src / f"{self.policy.source_table}.parquet"
                if not parquet_file.exists():
                    raise FileNotFoundError(
                        f"Expected table parquet file not found: {parquet_file}"
                    )
                relation_sql = f"read_parquet('{parquet_file.as_posix()}')"
            elif src.suffix.lower() == ".parquet":
                relation_sql = f"read_parquet('{src.as_posix()}')"
            else:
                con.execute(f"ATTACH '{src.as_posix()}' AS bronze_pkg (READ_ONLY);")
                relation_sql = f"bronze_pkg.{self.policy.source_table}"

            cols = self._describe_columns(con, relation_sql)
            ek = self.policy.entity_key.lower()
            rk = self.policy.record_key.lower()
            if ek not in cols or rk not in cols:
                raise ValueError(
                    f"Required columns ({self.policy.entity_key}, {self.policy.record_key}) "
                    f"missing from {src}. Available: {sorted(cols)}"
                )

            vc = self.policy.version_column.lower()
            rd = self.policy.regulatory_date_column.lower()
            md = self.policy.manufacturer_date_column.lower()

            version_expr = (
                f"TRY_CAST({self.policy.version_column} AS INTEGER)"
                if vc in cols
                else "CAST(NULL AS INTEGER)"
            )
            reg_date_expr = (
                f"NULLIF(TRIM(CAST({self.policy.regulatory_date_column} AS VARCHAR)), '')"
                if rd in cols
                else "CAST(NULL AS VARCHAR)"
            )
            mfr_date_expr = (
                f"NULLIF(TRIM(CAST({self.policy.manufacturer_date_column} AS VARCHAR)), '')"
                if md in cols
                else "CAST(NULL AS VARCHAR)"
            )

            extract_sql = f"""
                COPY (
                    SELECT DISTINCT
                        COALESCE(
                            NULLIF(TRIM(CAST({self.policy.entity_key} AS VARCHAR)), ''),
                            'REPORT:' || TRIM(CAST({self.policy.record_key} AS VARCHAR))
                        ) AS case_id,
                        TRIM(CAST({self.policy.record_key} AS VARCHAR)) AS primary_id,
                        '{period}' AS data_period,
                        {version_expr} AS canonical_case_version,
                        {reg_date_expr} AS latest_regulatory_date,
                        {mfr_date_expr} AS manufacturer_date
                    FROM {relation_sql}
                    WHERE {self.policy.record_key} IS NOT NULL
                      AND TRIM(CAST({self.policy.record_key} AS VARCHAR)) <> ''
                    ORDER BY case_id, primary_id
                ) TO '{tmp_path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD);
            """  # nosec B608

            con.execute(extract_sql)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink()
            raise
        finally:
            con.close()

        tmp_path.replace(target_path)
        return target_path

    def compact_completed_years(self, remove_quarterly: bool = True) -> List[Path]:
        """Compacts any year having all 4 quarterly ledgers (`Q1..Q4`) into `YYYY.parquet`.

        Args:
            remove_quarterly: If True, removes the 4 source quarterly files after atomic
                promotion of the annual Parquet file.

        Returns:
            List of newly compacted annual Parquet file paths.
        """
        if not self.ledger_dir.exists():
            return []

        by_year: Dict[str, Dict[str, Path]] = defaultdict(dict)
        for path in sorted(self.ledger_dir.glob("*.parquet")):
            match = QUARTERLY_LEDGER_RE.match(path.name)
            if match:
                year, quarter = match.group(1), match.group(2)
                by_year[year][quarter] = path

        compacted: List[Path] = []
        con = duckdb.connect(":memory:")
        try:
            for year, q_map in sorted(by_year.items()):
                if set(q_map.keys()) != {"1", "2", "3", "4"}:
                    continue

                annual_path = self.ledger_dir / f"{year}.parquet"
                tmp_annual = self.ledger_dir / f".tmp_{year}.parquet"
                if tmp_annual.exists():
                    tmp_annual.unlink()

                q_files = [q_map[q].as_posix() for q in ("1", "2", "3", "4")]
                files_sql = ", ".join(f"'{f}'" for f in q_files)

                con.execute(
                    f"""
                    COPY (
                        SELECT
                            case_id,
                            primary_id,
                            data_period,
                            canonical_case_version,
                            latest_regulatory_date,
                            manufacturer_date
                        FROM read_parquet([{files_sql}])
                        ORDER BY data_period, case_id, primary_id
                    ) TO '{tmp_annual.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD);
                    """  # nosec B608
                )
                tmp_annual.replace(annual_path)
                compacted.append(annual_path)

                if remove_quarterly:
                    for q in ("1", "2", "3", "4"):
                        q_map[q].unlink(missing_ok=True)
        finally:
            con.close()

        return compacted

    def list_ledger_files(self) -> List[Path]:
        """Returns sorted list of active ledger Parquet files (annual + quarterly)."""
        if not self.ledger_dir.exists():
            return []
        return sorted(
            p
            for p in self.ledger_dir.glob("*.parquet")
            if not p.name.startswith(".tmp_")
            and (QUARTERLY_LEDGER_RE.match(p.name) or ANNUAL_LEDGER_RE.match(p.name))
        )

    def list_indexed_periods(self) -> List[str]:
        """Reads distinct `data_period` identifiers present across all active ledger files."""
        files = self.list_ledger_files()
        if not files:
            return []
        files_sql = ", ".join(f"'{f.as_posix()}'" for f in files)
        con = duckdb.connect(":memory:")
        try:
            rows = con.execute(
                f"SELECT DISTINCT data_period FROM read_parquet([{files_sql}]) ORDER BY data_period"  # nosec B608
            ).fetchall()
            return [str(r[0]) for r in rows]
        finally:
            con.close()
