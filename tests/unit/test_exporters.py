"""Unit tests for SQLite and Parquet exporters."""

import sqlite3
from pathlib import Path

import dlt
import pyarrow.parquet as pq

from raxtik_etl.exporters.parquet_exporter import export_parquet
from raxtik_etl.exporters.sqlite_exporter import export_sqlite
from raxtik_etl.sources.faers.source import faers_source
from raxtik_etl.transformations.runner import run_transformations


def test_exporters(fixtures_dir: Path, temp_work_dir: Path):
    db_file = temp_work_dir / "export_test.duckdb"
    sqlite_file = temp_work_dir / "test_seed.sqlite"
    parquet_dir = temp_work_dir / "parquet"

    # Ingest & Transform
    pipeline = dlt.pipeline(
        pipeline_name="test_export_pipeline",
        destination=dlt.destinations.duckdb(str(db_file)),
        dataset_name="faers_raw",
    )
    pipeline.run(faers_source(data_dir=fixtures_dir))
    run_transformations(db_path=db_file, dataset_schema="faers_raw", verbose=False)

    # Test SQLite Export
    out_sqlite = export_sqlite(db_path=db_file, sqlite_output=sqlite_file, verbose=False)
    assert out_sqlite.exists()

    sq_con = sqlite3.connect(str(out_sqlite))
    cur = sq_con.cursor()
    tables = [
        r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    ]
    assert "drug_reaction_stats" in tables
    assert "drug_demographics" in tables
    assert "seed_metadata" in tables

    # Check indices exist
    indices = [
        r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    ]
    assert "idx_drug_reaction_drug" in indices

    sq_con.close()

    # Test Parquet Export
    out_pq = export_parquet(db_path=db_file, parquet_dir=parquet_dir, verbose=False)
    assert out_pq.exists()
    assert (parquet_dir / "drug_reaction_stats.parquet").exists()

    pq_table = pq.read_table(parquet_dir / "drug_reaction_stats.parquet")
    assert pq_table.num_rows > 0
