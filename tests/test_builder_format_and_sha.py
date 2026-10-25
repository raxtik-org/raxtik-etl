"""Tests for Package Builder format options, ASCII cleanup flag, and SHA-256 verification."""

from pathlib import Path

import duckdb
import pytest

from raxtik_etl.packaging.builder import (
    build_quarterly_package,
    compute_sha256,
)
from raxtik_etl.sdk import BaseDataset
from raxtik_etl.sources.protocol import SourceAdapter, SourceArtifact, SourceLoadResult


class MockAdapter(SourceAdapter):
    source_name: str = "mock"

    def extract_and_load(
        self, con: duckdb.DuckDBPyConnection, artifact: SourceArtifact
    ) -> SourceLoadResult:
        con.execute("""
            CREATE TABLE demo (
                primary_id VARCHAR,
                case_id VARCHAR,
                canonical_case_version INTEGER,
                fda_date VARCHAR,
                manufacturer_date VARCHAR,
                event_date VARCHAR,
                standard_age_years DOUBLE,
                standard_sex_label VARCHAR,
                reported_age DOUBLE,
                reported_sex_code VARCHAR
            );
        """)
        con.execute(
            "INSERT INTO demo VALUES ('1', '101', 1, '2004-01-01', '2004-01-01', '2004-01-01', 45.0, 'Male', 45.0, 'M');"
        )

        con.execute("""
            CREATE TABLE drug (
                primary_id VARCHAR,
                role_code VARCHAR,
                reported_drug_name VARCHAR,
                reported_active_ingredient VARCHAR
            );
        """)
        con.execute("INSERT INTO drug VALUES ('1', 'PS', 'ASPIRIN', 'ASPIRIN');")

        con.execute("""
            CREATE TABLE reac (
                primary_id VARCHAR,
                reported_reaction_term VARCHAR
            );
        """)
        con.execute("INSERT INTO reac VALUES ('1', 'HEADACHE');")

        con.execute("""
            CREATE TABLE outc (
                primary_id VARCHAR,
                case_id VARCHAR,
                outcome_code VARCHAR
            );
        """)
        con.execute("INSERT INTO outc VALUES ('1', '101', 'HO');")

        for tbl in ["indi", "ther", "rpsr"]:
            con.execute(f"CREATE TABLE {tbl} (primary_id VARCHAR);")
            con.execute(f"INSERT INTO {tbl} VALUES ('1');")

        return SourceLoadResult(
            source_name=self.source_name,
            release=artifact.release or "2024Q1",
            signature_id="S1",
            source_files=[],
            reference_tables={},
            row_counts={tbl: 1 for tbl in ["demo", "drug", "reac", "outc", "indi", "ther", "rpsr"]},
        )


def test_compute_sha256(tmp_path: Path):
    f = tmp_path / "sample.txt"
    f.write_text("hello raxtik safety dataset")
    sha = compute_sha256(f)
    assert len(sha) == 64
    assert sha == compute_sha256(f)


def test_builder_format_duckdb_only(tmp_path: Path):
    dummy_zip = tmp_path / "mock_2024q1.zip"
    dummy_zip.write_bytes(b"mock_zip_content")

    out_dir = tmp_path / "packages"
    res = build_quarterly_package(
        release="2024Q1",
        zip_path=dummy_zip,
        source_name="mock",
        adapter=MockAdapter(),
        output_dir=out_dir,
        format="duckdb",
        delete_ascii=False,
    )

    duckdb_file = Path(res["duckdb_path"])
    assert duckdb_file.exists()
    assert "sha256" in res
    assert len(res["sha256"]) == 64
    assert not (out_dir / "mock_2024Q1.duckdb.sha256").exists()
    assert "parquet_dir" not in res
    assert not (out_dir / "mock_2024Q1.parquet").exists()
    assert dummy_zip.exists()  # delete_ascii was False


def test_builder_format_parquet_only(tmp_path: Path):
    dummy_zip = tmp_path / "mock_2024q1.zip"
    dummy_zip.write_bytes(b"mock_zip_content")

    out_dir = tmp_path / "packages"
    res = build_quarterly_package(
        release="2024Q1",
        zip_path=dummy_zip,
        source_name="mock",
        adapter=MockAdapter(),
        output_dir=out_dir,
        format="parquet",
        delete_ascii=False,
    )

    parquet_dir = Path(res["parquet_dir"])
    assert parquet_dir.exists()
    assert (parquet_dir / "demo.parquet").exists()
    assert "duckdb_path" not in res
    assert not (out_dir / "mock_2024Q1.duckdb").exists()


def test_builder_format_both_and_cleanup(tmp_path: Path):
    dummy_zip = tmp_path / "mock_2024q1.zip"
    dummy_zip.write_bytes(b"mock_zip_content")

    out_dir = tmp_path / "packages"
    res = build_quarterly_package(
        release="2024Q1",
        zip_path=dummy_zip,
        source_name="mock",
        adapter=MockAdapter(),
        output_dir=out_dir,
        format="both",
        delete_ascii=True,
    )

    assert Path(res["duckdb_path"]).exists()
    assert Path(res["parquet_dir"]).exists()
    assert "sha256" in res
    assert len(res["sha256"]) == 64
    assert not (out_dir / "mock_2024Q1.duckdb.sha256").exists()
    assert not dummy_zip.exists()  # deleted because delete_ascii=True


def test_builder_invalid_format(tmp_path: Path):
    dummy_zip = tmp_path / "mock_2024q1.zip"
    dummy_zip.write_bytes(b"mock_zip_content")

    with pytest.raises(ValueError, match="Invalid format"):
        build_quarterly_package(
            release="2024Q1",
            zip_path=dummy_zip,
            source_name="mock",
            adapter=MockAdapter(),
            output_dir=tmp_path / "packages",
            format="invalid_format",
        )


def test_sha256_verification_sdk(tmp_path: Path):
    # Setup package
    pkg_file = tmp_path / "mock_2024Q1.duckdb"
    con = duckdb.connect(pkg_file.as_posix())
    con.execute("CREATE TABLE demo (id VARCHAR)")
    con.close()

    real_sha = compute_sha256(pkg_file)

    ds = BaseDataset(
        release="2024Q1",
        source="mock",
        package_dir=tmp_path,
    )
    assert ds.compute_sha256() == real_sha
    assert ds.verify_checksum(real_sha) is True

    # Bad sha raises ValueError
    with pytest.raises(ValueError, match="Checksum verification failed"):
        ds.verify_checksum("bad_sha_hash_12345")
    ds.close()

    # Companion .sha256 file automatic verification
    sha_file = tmp_path / "mock_2024Q1.duckdb.sha256"
    sha_file.write_text(f"{real_sha}  mock_2024Q1.duckdb\n")
    ds2 = BaseDataset(release="2024Q1", source="mock", package_dir=tmp_path)
    assert ds2.verify_checksum() is True
    ds2.close()
