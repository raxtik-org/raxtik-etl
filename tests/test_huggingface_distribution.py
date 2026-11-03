"""Tests for Hugging Face distribution module."""

from pathlib import Path

import pytest

from raxtik_etl.distribution.huggingface import (
    DEFAULT_HF_REPO,
    download_package_from_hf,
    get_hf_path_candidates,
    upload_package_to_hf,
)


def test_hf_repo_default(monkeypatch):
    import os

    expected = os.getenv("RAXTIK_HF_REPO", "raxtik-org/faers-safety-database")
    assert DEFAULT_HF_REPO == expected


def test_download_package_local_hit(tmp_path: Path):
    # If the file already exists locally, download should immediately return it
    fake_pkg = tmp_path / "faers_2004Q1.duckdb"
    fake_pkg.write_bytes(b"dummy")

    result = download_package_from_hf("2004Q1", dest_dir=tmp_path, force=False)
    assert result == fake_pkg
    assert result.read_bytes() == b"dummy"


def test_upload_package_requires_token(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)

    fake_pkg = tmp_path / "faers_2004Q1.duckdb"
    fake_pkg.write_bytes(b"dummy")

    with pytest.raises((ValueError, ImportError)):
        upload_package_to_hf("2004Q1", package_dir=tmp_path, token=None)


def test_dataset_from_hf(tmp_path: Path):
    import duckdb

    from raxtik_etl import Dataset

    fake_pkg = tmp_path / "faers_2004Q1.duckdb"
    con = duckdb.connect(fake_pkg.as_posix())
    con.execute("CREATE TABLE demo (primary_id VARCHAR, case_id VARCHAR)")
    con.execute("CREATE TABLE cases (case_id VARCHAR, primary_id VARCHAR)")
    con.execute("INSERT INTO cases VALUES ('101', '101_1')")
    con.close()

    with Dataset.from_hf("2004Q1", source="faers", package_dir=tmp_path) as ds:
        df = ds.cases()
        assert len(df) == 1
        assert df["case_id"][0] == "101"


def test_get_default_package_dir_custom_env(monkeypatch, tmp_path: Path):
    from raxtik_etl.distribution.huggingface import get_default_package_dir

    custom_dir = tmp_path / "custom_cache"
    monkeypatch.setenv("RAXTIK_CACHE_DIR", str(custom_dir))
    assert get_default_package_dir() == custom_dir


def test_cli_hf_upload_batch_range(tmp_path: Path, monkeypatch):
    from typer.testing import CliRunner

    from raxtik_etl.cli import app

    runner = CliRunner()
    # Test batch upload requiring arguments
    res = runner.invoke(app, ["hf-upload"])
    assert res.exit_code != 0
    assert "Please specify either --data-period" in res.output

    # Test batch upload range where files don't exist: should skip with warnings instead of crashing
    res_range = runner.invoke(
        app,
        [
            "hf-upload",
            "--start",
            "2007Q1",
            "--end",
            "2007Q2",
            "--token",
            "fake_token",
            "--package-dir",
            str(tmp_path),
        ],
    )
    assert res_range.exit_code == 0
    assert "Uploading 2 package(s)" in res_range.output
    assert "Batch upload finished" in res_range.output


def test_resolve_hf_revision(monkeypatch):
    from raxtik_etl.distribution.huggingface import resolve_hf_revision

    # Explicit revision takes priority
    assert resolve_hf_revision("raxtik-org/faers-safety-database", revision="v1.0.0") == "v1.0.0"

    # Environment variable takes priority if revision is None
    monkeypatch.setenv("RAXTIK_HF_REVISION", "v2.0.0")
    assert resolve_hf_revision("raxtik-org/faers-safety-database") == "v2.0.0"

    # Fallback to 'main' when tag does not exist
    monkeypatch.delenv("RAXTIK_HF_REVISION", raising=False)
    assert resolve_hf_revision("nonexistent-org/nonexistent-repo-12345") == "main"


def test_upload_package_tiered_layout(tmp_path: Path, monkeypatch):
    """Verify that uploading with tier='bronze' produces 'bronze/2004/faers_2004Q1.duckdb'."""
    pkg_file = tmp_path / "faers_2004Q1.duckdb"
    pkg_file.write_bytes(b"mock duckdb binary")
    sha_file = tmp_path / "faers_2004Q1.duckdb.sha256"
    sha_file.write_text("a" * 64)

    p_dir = tmp_path / "faers_2004Q1.parquet"
    p_dir.mkdir()
    (p_dir / "demo.parquet").write_bytes(b"mock parquet")

    captured_operations = []

    class DummyApi:
        def __init__(self, token=None):
            self.token = token

        def create_commit(self, repo_id, repo_type, operations, commit_message):
            captured_operations.extend(operations)

    import huggingface_hub

    monkeypatch.setattr(huggingface_hub, "HfApi", DummyApi)

    upload_package_to_hf(
        "2004Q1",
        package_dir=tmp_path,
        token="dummy_token",
        include_parquet=True,
        tier="bronze",
    )

    repo_paths = [op.path_in_repo for op in captured_operations]
    assert "bronze/2004/faers_2004Q1.duckdb" in repo_paths
    assert "bronze/2004/faers_2004Q1.duckdb.sha256" in repo_paths
    assert "bronze/2004/faers_2004Q1.parquet/demo.parquet" in repo_paths


def test_cli_tiered_upload_and_download_aliases(tmp_path: Path):
    """Verify that 'upload' and 'download' aliases work cleanly and route internally."""
    from typer.testing import CliRunner

    from raxtik_etl.cli import app

    runner = CliRunner()
    # Test upload alias with --help
    res_up = runner.invoke(app, ["upload", "--help"])
    assert res_up.exit_code == 0
    assert "--data-period" in res_up.output

    # Test download alias with --help
    res_down = runner.invoke(app, ["download", "--help"])
    assert res_down.exit_code == 0
    assert "--data-period" in res_down.output


@pytest.mark.parametrize(
    ("filename", "subfolder", "tier", "expected"),
    [
        (
            "faers_2004Q1.duckdb",
            "2004",
            "bronze",
            [
                "bronze/2004/faers_2004Q1.duckdb",
                "bronze/faers_2004Q1.duckdb",
                "2004/faers_2004Q1.duckdb",
                "faers_2004Q1.duckdb",
            ],
        ),
        (
            "faers_2004Q1.duckdb",
            "2004",
            None,
            [
                "2004/faers_2004Q1.duckdb",
                "faers_2004Q1.duckdb",
            ],
        ),
        (
            "faers_consolidated.duckdb",
            None,
            "silver",
            [
                "silver/faers_consolidated.duckdb",
                "faers_consolidated.duckdb",
            ],
        ),
        (
            "faers_root.duckdb",
            None,
            None,
            [
                "faers_root.duckdb",
            ],
        ),
    ],
)
def test_get_hf_path_candidates_parametrized(filename, subfolder, tier, expected):
    candidates = get_hf_path_candidates(filename=filename, subfolder=subfolder, tier=tier)
    assert candidates == expected
