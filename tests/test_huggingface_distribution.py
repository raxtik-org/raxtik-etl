"""Tests for Hugging Face distribution module."""

from pathlib import Path

import pytest

from raxtik_etl.distribution.huggingface import (
    DEFAULT_HF_REPO,
    download_package_from_hf,
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
    monkeypatch.delenv("HUGGINGFACE_HUB_TOKEN", raising=False)

    fake_pkg = tmp_path / "faers_2004Q1.duckdb"
    fake_pkg.write_bytes(b"dummy")

    with pytest.raises((ValueError, ImportError)):
        upload_package_to_hf("2004Q1", package_dir=tmp_path, token=None)
