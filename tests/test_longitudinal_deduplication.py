"""Tests for Longitudinal Cohort Merger and Cross-Quarter Case Deduplication."""

from pathlib import Path

import duckdb
import pytest

from raxtik_etl.cli import parse_quarter_range
from raxtik_etl.longitudinal.merger import get_longitudinal_summary_report


def test_parse_quarter_range():
    quarters = parse_quarter_range("2004Q1", "2006Q4")
    assert len(quarters) == 12
    assert quarters[0] == "2004Q1"
    assert quarters[-1] == "2006Q4"
    assert quarters[4] == "2005Q1"
    assert quarters[8] == "2006Q1"


def test_merged_cohort_deduplication_integrity():
    db_path = Path("data/packages/faers_2004_2006_merged.duckdb")
    if not db_path.exists():
        pytest.skip("Merged database not present on disk.")

    con = duckdb.connect(db_path.as_posix(), read_only=True)
    try:
        # 1. Assert exactly 1 row per case_id in cases table
        total_cases = con.execute("SELECT count(*) FROM cases").fetchone()[0]
        distinct_cases = con.execute("SELECT count(DISTINCT case_id) FROM cases").fetchone()[0]
        assert total_cases == distinct_cases
        assert total_cases == 694232

        # 2. Assert raw submissions in demo equals total raw submissions recorded
        total_demo = con.execute("SELECT count(*) FROM demo").fetchone()[0]
        assert total_demo == 921478

        # 3. Verify cross-quarter case count
        cross_quarter_cases = con.execute(
            "SELECT count(*) FROM case_lineage WHERE is_cross_quarter_case = TRUE"
        ).fetchone()[0]
        assert cross_quarter_cases == 88443

        # 4. Verify case_adverse_events_summary view runs without error
        sample_summary = con.execute(
            "SELECT case_id, primary_suspect_drug, reaction_term, quarters_count, is_cross_quarter_case FROM case_adverse_events_summary LIMIT 5"
        ).fetchall()
        assert len(sample_summary) == 5

        # 5. Verify quality report table
        summary_table = get_longitudinal_summary_report(db_path)
        assert summary_table is not None
    finally:
        con.close()
