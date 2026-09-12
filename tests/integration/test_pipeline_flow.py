"""Integration test for full raxtik-etl pipeline CLI and runner."""

from pathlib import Path

from typer.testing import CliRunner

from raxtik_etl.cli import app

runner = CliRunner()


def test_full_pipeline_sample_run(temp_work_dir: Path):
    sqlite_target = temp_work_dir / "sample_out" / "faers_seed.sqlite"
    parquet_target = temp_work_dir / "sample_out" / "parquet"

    result = runner.invoke(
        app,
        [
            "pipeline",
            "--sample",
            "--output-dir",
            str(temp_work_dir / "sample_out"),
        ],
    )
    assert result.exit_code == 0
    assert sqlite_target.exists()
    assert parquet_target.exists()
