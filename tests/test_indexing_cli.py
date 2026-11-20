"""CLI integration tests for `raxtik-etl index build | update | compact | verify | lookup`."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import duckdb
from typer.testing import CliRunner

from raxtik_etl.cli import app

runner = CliRunner()


def _create_bronze_pkg(
    db_path: Path,
    rows: List[Tuple[str, str, Optional[int], Optional[str], Optional[str]]],
) -> Path:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(db_path.as_posix())
    try:
        con.execute(
            """
            CREATE TABLE demo (
                primary_id VARCHAR,
                case_id VARCHAR,
                canonical_case_version INTEGER,
                latest_regulatory_date VARCHAR,
                manufacturer_date VARCHAR
            );
            """
        )
        con.executemany("INSERT INTO demo VALUES (?, ?, ?, ?, ?);", rows)
    finally:
        con.close()
    return db_path


def test_cli_index_build_update_verify_and_lookup(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "packages"
    idx_dir = tmp_path / "silver_index"

    _create_bronze_pkg(
        pkg_dir / "faers_2004Q1.duckdb",
        [("101", "C99", 1, "20040115", None), ("102", "C100", 1, "20040201", None)],
    )
    _create_bronze_pkg(
        pkg_dir / "faers_2004Q2.duckdb",
        [("150", "C99", 2, "20040510", None)],
    )
    _create_bronze_pkg(
        pkg_dir / "faers_2004Q3.duckdb",
        [("180", "C99", 3, "20040810", None)],
    )

    # 1. `index build` across 2004Q1..2004Q2
    res_build = runner.invoke(
        app,
        [
            "index",
            "build",
            "--source",
            "faers",
            "--tier",
            "silver",
            "--start",
            "2004Q1",
            "--end",
            "2004Q2",
            "--package-dir",
            pkg_dir.as_posix(),
            "--index-dir",
            idx_dir.as_posix(),
            "--shards",
            "4",
        ],
    )
    assert res_build.exit_code == 0, res_build.output
    assert "Index Snapshot Committed" in res_build.output

    # 2. `index update` incrementally with 2004Q3
    res_update = runner.invoke(
        app,
        [
            "index",
            "update",
            "--data-period",
            "2004Q3",
            "--source",
            "faers",
            "--tier",
            "silver",
            "--package-dir",
            pkg_dir.as_posix(),
            "--index-dir",
            idx_dir.as_posix(),
            "--shards",
            "4",
        ],
    )
    assert res_update.exit_code == 0, res_update.output
    assert "snap_2004Q3" in res_update.output

    # 3. `index verify` confirms incremental == full rebuild bit-for-bit
    res_verify = runner.invoke(
        app,
        [
            "index",
            "verify",
            "--source",
            "faers",
            "--tier",
            "silver",
            "--index-dir",
            idx_dir.as_posix(),
        ],
    )
    assert res_verify.exit_code == 0, res_verify.output
    assert "Verification passed" in res_verify.output

    # 4. `index lookup` prints full 3-version timeline for C99
    res_lookup = runner.invoke(
        app,
        [
            "index",
            "lookup",
            "--case-id",
            "C99",
            "--source",
            "faers",
            "--tier",
            "silver",
            "--index-dir",
            idx_dir.as_posix(),
        ],
    )
    assert res_lookup.exit_code == 0, res_lookup.output
    assert "180" in res_lookup.output
    assert "150" in res_lookup.output
    assert "101" in res_lookup.output
