"""Integration test for raxtik-etl packaging CLI."""

from pathlib import Path

from typer.testing import CliRunner

from raxtik_etl.cli import app

runner = CliRunner()


def test_build_and_inspect_package(tmp_path: Path):
    out_dir = tmp_path / "packages"
    out_dir.mkdir(parents=True, exist_ok=True)

    result = runner.invoke(
        app,
        [
            "build-package",
            "--release",
            "2004Q1",
            "--output-dir",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0
    assert (out_dir / "faers_2004Q1.duckdb").exists()
    assert (out_dir / "faers_2004Q1.parquet").exists()

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
    assert inspect_res.exit_code == 0
