"""Tests for Longitudinal Cohort Merger and Cross-Quarter Case Deduplication."""

import duckdb
import pytest

from raxtik_etl.cli import parse_quarter_range
from raxtik_etl.consolidation import get_consolidation_summary_report


@pytest.mark.parametrize(
    ("start", "end", "expected_count", "first", "last"),
    [
        ("2004Q1", "2006Q4", 12, "2004Q1", "2006Q4"),
        ("2020Q1", "2020Q1", 1, "2020Q1", "2020Q1"),
        ("2020Q1", "2020Q4", 4, "2020Q1", "2020Q4"),
    ],
)
def test_parse_quarter_range(
    start: str, end: str, expected_count: int, first: str, last: str
) -> None:
    quarters = parse_quarter_range(start, end)
    assert len(quarters) == expected_count
    assert quarters[0] == first
    assert quarters[-1] == last


def test_merged_cohort_deduplication_integrity():
    from raxtik_etl.distribution.huggingface import get_default_package_dir

    db_path = get_default_package_dir() / "faers_2004_2006_consolidated.duckdb"
    if not db_path.exists():
        pytest.skip("Consolidated database not present on disk.")

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
        summary_table = get_consolidation_summary_report(db_path)
        assert summary_table is not None
    finally:
        con.close()
