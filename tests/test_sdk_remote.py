from unittest.mock import MagicMock, patch

import pytest

from raxtik_etl import Dataset, __version__
from raxtik_etl.sdk import BaseDataset


def test_sdk_remote_flag_initialization():
    """Tests that BaseDataset initializes correctly with remote=True."""
    with patch("duckdb.connect") as mock_connect:
        mock_con = MagicMock()
        mock_con.execute.return_value.fetchall.return_value = [("1.0.0",)]
        mock_connect.return_value = mock_con

        ds = BaseDataset(
            data_period="2024Q1",
            source="faers",
            remote=True,
            revision=f"v{__version__}",
        )

        assert ds.remote is True
        assert ds._remote_url is not None
        assert "bronze/2024/faers_2024Q1.duckdb" in ds._remote_url
        assert f"v{__version__}" in ds._remote_url

        # Verify httpfs was loaded and ATTACH executed
        mock_con.execute.assert_any_call("INSTALL httpfs; LOAD httpfs;")
        mock_con.execute.assert_any_call(f"ATTACH '{ds._remote_url}' AS faers (READ_ONLY);")
        mock_con.execute.assert_any_call("USE faers;")


def test_sdk_remote_from_hf_factory():
    """Tests that Dataset.from_hf passes remote=True through to instance."""
    with patch("duckdb.connect") as mock_connect:
        mock_con = MagicMock()
        mock_con.execute.return_value.fetchall.return_value = [("1.0.0",)]
        mock_connect.return_value = mock_con

        ds = Dataset.from_hf("2024Q1", source="faers", remote=True, revision=f"v{__version__}")
        assert ds.remote is True

        # Checksum behavior on remote datasets
        with pytest.raises(NotImplementedError, match="Pass `remote=False` to download"):
            ds.compute_sha256()

        with pytest.raises(NotImplementedError, match="Pass `remote=False` to download"):
            ds.verify_checksum()


def test_sdk_remote_rate_limit_retry_warning():
    """Tests that rate-limiting errors (429) trigger warnings and retry logic."""
    with patch("duckdb.connect") as mock_connect:
        mock_con = MagicMock()
        meta_cursor = MagicMock()
        meta_cursor.fetchall.return_value = [("1.0.0",)]
        # Fail first with 429, then succeed
        mock_con.execute.side_effect = [
            None,  # INSTALL httpfs
            Exception("HTTP 429 Too Many Requests"),
            None,  # ATTACH on retry
            None,  # USE faers
            meta_cursor,  # metadata check
        ]
        mock_connect.return_value = mock_con

        with pytest.warns(UserWarning, match="rate-limiting or congestion"):
            ds = BaseDataset(
                data_period="2024Q1",
                source="faers",
                remote=True,
                revision=f"v{__version__}",
            )
            assert ds.remote is True
