"""Pytest shared test fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to sample FAERS ASCII test fixtures."""
    return Path(__file__).parent / "fixtures" / "sample_faers_ascii"


@pytest.fixture
def temp_work_dir(tmp_path: Path) -> Path:
    """Provide a clean temporary directory for test pipelines."""
    return tmp_path
