"""Unit tests for FAERS dlt source and ingestion into DuckDB."""

from pathlib import Path

import dlt
import duckdb

from raxtik_etl.sources.faers.source import faers_source


def test_dlt_source_ingestion(fixtures_dir: Path, temp_work_dir: Path):
    db_file = temp_work_dir / "test_faers.duckdb"
    pipeline = dlt.pipeline(
        pipeline_name="test_faers_pipeline",
        destination=dlt.destinations.duckdb(str(db_file)),
        dataset_name="faers_raw",
    )

    source = faers_source(data_dir=fixtures_dir)
    info = pipeline.run(source)
    assert not info.has_failed_jobs

    # Check duckdb tables
    con = duckdb.connect(str(db_file))
    demo_count = con.execute("SELECT COUNT(*) FROM faers_raw.demo").fetchone()[0]
    drug_count = con.execute("SELECT COUNT(*) FROM faers_raw.drug").fetchone()[0]
    reac_count = con.execute("SELECT COUNT(*) FROM faers_raw.reac").fetchone()[0]
    outc_count = con.execute("SELECT COUNT(*) FROM faers_raw.outc").fetchone()[0]
    indi_count = con.execute("SELECT COUNT(*) FROM faers_raw.indi").fetchone()[0]
    con.close()

    assert demo_count == 5
    assert drug_count == 5
    assert reac_count == 5
    assert outc_count == 4
    assert indi_count == 5
