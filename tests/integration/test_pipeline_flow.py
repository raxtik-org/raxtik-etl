"""End-to-end integration test and zero-regression gate for raxtik-etl.

Verifies:
1. Entry-point discovery discovers "faers" without direct package imports.
2. CLI build-package builds 2004Q1 package via entry-point adapter.
3. Frozen baseline contract:
   - demo: 65,902
   - cases: 58,235
   - drug: 235,361
   - reac: 264,410
   - outc: 57,592
   - indi: 78,639
   - ther: 84,964
   - rpsr: 78,306
   - Total fact sum: 865,174
4. CLI inspect-package displays complete summary report.
"""

from pathlib import Path

import duckdb
import pytest
from typer.testing import CliRunner

from raxtik_etl.cli import app
from raxtik_etl.sources.registry import get_available_sources, get_source_adapter

runner = CliRunner()

ARCHIVE_PATH = Path("data/raw/archives_cache/2004q1_ascii.zip")


def test_zero_regression_pipeline_via_entrypoint_discovery(tmp_path: Path):
    available = get_available_sources()
    if "faers" not in available or not ARCHIVE_PATH.exists():
        pytest.skip(
            "Integration pipeline test requires raxtik-source-faers and local raw archive cache."
        )

    # 1. Verify entry-point discovery finds 'faers' without hardcoded imports
    assert "faers" in available

    # 2. Verify adapter instance satisfies protocol
    adapter = get_source_adapter("faers")
    assert adapter.source_name == "faers"

    # 3. Execute package build via CLI using entry-point adapter
    out_dir = tmp_path / "packages"
    out_dir.mkdir(parents=True, exist_ok=True)

    result = runner.invoke(
        app,
        [
            "build-package",
            "--source",
            "faers",
            "--release",
            "2004Q1",
            "--zip-path",
            str(ARCHIVE_PATH),
            "--output-dir",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0, f"CLI build-package failed: {result.stdout}"

    duckdb_path = out_dir / "faers_2004Q1.duckdb"
    parquet_dir = out_dir / "faers_2004Q1.parquet"
    assert duckdb_path.exists()
    assert parquet_dir.exists()

    # 4. Zero-Regression Gate: Assert exact frozen baseline counts
    con = duckdb.connect(duckdb_path.as_posix(), read_only=True)

    def _get_count(tbl: str) -> int:
        row = con.execute(f"SELECT count(*) FROM {tbl}").fetchone()
        assert row is not None
        return int(row[0])

    counts = {
        tbl: _get_count(tbl)
        for tbl in ["demo", "cases", "drug", "reac", "outc", "indi", "ther", "rpsr"]
    }

    assert counts["demo"] == 65902, f"demo count mismatch: {counts['demo']}"
    assert counts["cases"] == 58235, f"cases count mismatch: {counts['cases']}"
    assert counts["drug"] == 235361, f"drug count mismatch: {counts['drug']}"
    assert counts["reac"] == 264410, f"reac count mismatch: {counts['reac']}"
    assert counts["outc"] == 57592, f"outc count mismatch: {counts['outc']}"
    assert counts["indi"] == 78639, f"indi count mismatch: {counts['indi']}"
    assert counts["ther"] == 84964, f"ther count mismatch: {counts['ther']}"
    assert counts["rpsr"] == 78306, f"rpsr count mismatch: {counts['rpsr']}"

    total_facts = sum(
        counts[tbl] for tbl in ["demo", "drug", "reac", "outc", "indi", "ther", "rpsr"]
    )
    assert total_facts == 865174, f"Total fact sum mismatch: {total_facts} != 865,174"

    con.close()

    # 5. Verify CLI inspect-package
    inspect_res = runner.invoke(
        app,
        [
            "inspect-package",
            "--release",
            "2004Q1",
            "--package-dir",
            str(out_dir),
        ],
    )
    assert inspect_res.exit_code == 0, f"CLI inspect-package failed: {inspect_res.stdout}"
    assert "865174" in inspect_res.stdout or "65902" in inspect_res.stdout
