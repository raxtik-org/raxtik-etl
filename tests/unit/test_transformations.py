"""Unit tests for DuckDB SQL transformations."""

from pathlib import Path

import dlt
import duckdb

from raxtik_etl.sources.faers.source import faers_source
from raxtik_etl.transformations.runner import run_transformations


def test_sql_transformations(fixtures_dir: Path, temp_work_dir: Path):
    db_file = temp_work_dir / "transform_test.duckdb"

    # 1. Ingest fixtures
    pipeline = dlt.pipeline(
        pipeline_name="test_transform_pipeline",
        destination=dlt.destinations.duckdb(str(db_file)),
        dataset_name="faers_raw",
    )
    source = faers_source(data_dir=fixtures_dir)
    pipeline.run(source)

    # 2. Run transformations
    results = run_transformations(db_path=db_file, dataset_schema="faers_raw", verbose=False)

    assert "dedup_demo" in results
    assert "dedup_drug" in results
    assert "drug_reaction_stats" in results
    assert "drug_demographics" in results
    assert "drug_indications" in results
    assert "drug_routes" in results
    assert "drug_outcomes" in results

    # Case 10000002 had 2 versions (version 1 and version 2). Deduplication should leave 4 unique cases.
    assert results["dedup_demo"] == 4

    # Check drug_reaction_stats content
    con = duckdb.connect(str(db_file))
    aspirin_stats = con.execute(
        "SELECT reaction_pt, co_occurrence_count, prr FROM faers_raw.drug_reaction_stats WHERE drug_name = 'ASPIRIN'"
    ).fetchall()
    con.close()

    assert len(aspirin_stats) > 0
    # Check that Gastrointestinal haemorrhage is present for Aspirin
    reactions = [r[0] for r in aspirin_stats]
    assert "GASTROINTESTINAL HAEMORRHAGE" in reactions
