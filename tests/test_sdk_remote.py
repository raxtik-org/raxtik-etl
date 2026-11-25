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


def test_sdk_accessors_and_summary(tmp_path):
    """Tests local BaseDataset table accessors, metadata, audit report, and summary."""
    import duckdb

    pkg = tmp_path / "faers_2004Q1.duckdb"
    con = duckdb.connect(pkg.as_posix())
    con.execute(
        """
        CREATE TABLE _metadata (key VARCHAR, value VARCHAR);
        INSERT INTO _metadata VALUES ('package_format_version', '1.0.0'), ('tier', 'bronze');
        CREATE TABLE _data_quality_report (metric_name VARCHAR, metric_value VARCHAR);
        INSERT INTO _data_quality_report VALUES ('row_count', '1');
        CREATE TABLE demo (primary_id VARCHAR, case_id VARCHAR);
        INSERT INTO demo VALUES ('101', 'C1');
        CREATE TABLE drug (primary_id VARCHAR, drugname VARCHAR);
        INSERT INTO drug VALUES ('101', 'ASPIRIN');
        CREATE TABLE reac (primary_id VARCHAR, pt VARCHAR);
        INSERT INTO reac VALUES ('101', 'HEADACHE');
        CREATE TABLE outc (primary_id VARCHAR, outc_cod VARCHAR);
        INSERT INTO outc VALUES ('101', 'OT');
        """
    )
    con.close()

    with BaseDataset(data_period="2004Q1", source="faers", package_dir=tmp_path) as ds:
        assert ds.package_format_version == "1.0.0"
        assert all(
            len(fn(limit=1)) == 1 for fn in (ds.reports, ds.drugs, ds.reactions, ds.outcomes)
        )
        assert ds.metadata()["tier"] == "bronze"
        assert ds.audit_report()["row_count"] == "1"
        ds.print_summary()


@pytest.mark.parametrize(
    ("ver", "match"),
    [
        ("2.0.0", "Unsupported package_format_version"),
        ("invalid", "Invalid package_format_version"),
    ],
)
def test_sdk_invalid_format_version(tmp_path, ver: str, match: str):
    """Rejects unsupported or malformed package_format_version values."""
    import duckdb

    pkg = tmp_path / "faers_2004Q2.duckdb"
    con = duckdb.connect(pkg.as_posix())
    con.execute("CREATE TABLE _metadata (key VARCHAR, value VARCHAR)")
    con.execute("INSERT INTO _metadata VALUES ('package_format_version', ?)", [ver])
    con.close()

    with pytest.raises(ValueError, match=match):
        BaseDataset(data_period="2004Q2", source="faers", package_dir=tmp_path)


def test_sdk_table_accessors_summary_and_version_validation(tmp_path):
    """Tests local BaseDataset accessors, summary output, and format version checks."""
    import duckdb

    pkg = tmp_path / "faers_2004Q1.duckdb"
    con = duckdb.connect(pkg.as_posix())
    con.execute("CREATE TABLE _metadata (key VARCHAR, value VARCHAR)")
    con.execute(
        "INSERT INTO _metadata VALUES ('package_format_version', '1.0.0'), ('tier', 'bronze')"
    )
    con.execute("CREATE TABLE _data_quality_report (metric_name VARCHAR, metric_value VARCHAR)")
    con.execute("INSERT INTO _data_quality_report VALUES ('row_count', '1')")
    con.execute("CREATE TABLE demo (primary_id VARCHAR, case_id VARCHAR)")
    con.execute("INSERT INTO demo VALUES ('101', 'C1')")
    con.execute("CREATE TABLE drug (primary_id VARCHAR, drugname VARCHAR)")
    con.execute("INSERT INTO drug VALUES ('101', 'ASPIRIN')")
    con.execute("CREATE TABLE reac (primary_id VARCHAR, pt VARCHAR)")
    con.execute("INSERT INTO reac VALUES ('101', 'HEADACHE')")
    con.execute("CREATE TABLE outc (primary_id VARCHAR, outc_cod VARCHAR)")
    con.execute("INSERT INTO outc VALUES ('101', 'OT')")
    con.close()

    with BaseDataset(data_period="2004Q1", source="faers", package_dir=tmp_path) as ds:
        assert ds.package_format_version == "1.0.0"
        assert len(ds.reports(limit=1)) == 1
        assert len(ds.drugs(limit=1)) == 1
        assert len(ds.reactions(limit=1)) == 1
        assert len(ds.outcomes(limit=1)) == 1
        assert ds.metadata()["tier"] == "bronze"
        assert ds.audit_report()["row_count"] == "1"
        ds.print_summary()

    # Unsupported major version (2.0.0)
    bad_major = tmp_path / "faers_2004Q2.duckdb"
    con = duckdb.connect(bad_major.as_posix())
    con.execute("CREATE TABLE _metadata (key VARCHAR, value VARCHAR)")
    con.execute("INSERT INTO _metadata VALUES ('package_format_version', '2.0.0')")
    con.close()
    with pytest.raises(ValueError, match="Unsupported package_format_version"):
        BaseDataset(data_period="2004Q2", source="faers", package_dir=tmp_path)

    # Malformed format version
    bad_fmt = tmp_path / "faers_2004Q3.duckdb"
    con = duckdb.connect(bad_fmt.as_posix())
    con.execute("CREATE TABLE _metadata (key VARCHAR, value VARCHAR)")
    con.execute("INSERT INTO _metadata VALUES ('package_format_version', 'invalid')")
    con.close()
    with pytest.raises(ValueError, match="Invalid package_format_version"):
        BaseDataset(data_period="2004Q3", source="faers", package_dir=tmp_path)
