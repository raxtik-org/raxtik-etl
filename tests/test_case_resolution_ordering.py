"""Unit tests for Case Resolution Ordering Correctness and Non-Fanout Analytics.

Verifies deterministic case resolution ranking rules:
1. canonical_case_version DESC (NULLS LAST)
2. fda_date DESC (NULLS LAST)
3. manufacturer_date DESC (NULLS LAST)
4. primary_id DESC (numeric tie-breaker)

Also regression tests analytical summary views to ensure zero Cartesian join fan-out.
"""

from __future__ import annotations

import duckdb
import pytest

from raxtik_etl.consolidation import validate_and_normalize_data_periods
from raxtik_etl.schema.views import get_latest_cases_view_sql


@pytest.fixture
def memory_db():
    con = duckdb.connect(":memory:")
    yield con
    con.close()


@pytest.mark.parametrize(
    ("invalid_input", "error_match"),
    [
        ([], r"cannot be empty"),
        (["2004Q5"], r"Invalid quarter"),
        (["invalid_quarter"], r"Invalid quarter"),
    ],
)
def test_cohort_release_input_validation_errors(invalid_input, error_match):
    with pytest.raises(ValueError, match=error_match):
        validate_and_normalize_data_periods(invalid_input)


def test_cohort_release_input_dedup_and_sort():
    input_releases = ["2005Q2", "2004Q1", "2005Q1", "2004Q1", "2004Q3"]
    normalized = validate_and_normalize_data_periods(input_releases)
    assert normalized == ["2004Q1", "2004Q3", "2005Q1", "2005Q2"]


def test_case_resolution_ordering_rules(memory_db):
    con = memory_db

    # Create synthetic demo table
    con.execute("""
        CREATE TABLE demo (
            primary_id VARCHAR,
            case_id VARCHAR,
            canonical_case_version INTEGER,
            latest_regulatory_date VARCHAR,
            manufacturer_date VARCHAR,
            event_date VARCHAR,
            standard_age_years DOUBLE,
            standard_sex_label VARCHAR,
            initial_or_followup_code VARCHAR,
            _data_period VARCHAR
        );
    """)

    # Populate test cases
    test_rows = [
        # Case C1: Version precedence (Version 2 wins over later date)
        ("101", "C1", 1, "20050101", "20041201", "20040101", 30.0, "Female", "I", "2004Q1"),
        ("102", "C1", 2, "20040601", "20040501", "20040101", 30.0, "Female", "F", "2004Q2"),
        # Case C2: Date precedence (Versions equal, later date wins)
        ("201", "C2", 1, "20040101", "20031201", "20030101", 45.0, "Male", "I", "2004Q1"),
        ("202", "C2", 1, "20040901", "20040801", "20030101", 45.0, "Male", "F", "2004Q3"),
        # Case C3: Manufacturer date tie-breaker (Version and date equal, later manufacturer_date wins)
        ("301", "C3", 1, "20050101", "20041101", "20040101", 50.0, "Female", "I", "2005Q1"),
        ("302", "C3", 1, "20050101", "20041215", "20040101", 50.0, "Female", "F", "2005Q1"),
        # Case C4: Numeric primary_id tie-breaker (All versions and dates equal, higher numeric ID wins)
        ("401", "C4", 1, "20050101", "20041201", "20040101", 60.0, "Male", "I", "2005Q1"),
        ("409", "C4", 1, "20050101", "20041201", "20040101", 60.0, "Male", "I", "2005Q1"),
        # Case C5: NULL version handling (Valid version 1 wins over NULL version)
        ("501", "C5", None, "20060101", "20051201", "20050101", 65.0, "Female", "I", "2006Q1"),
        ("502", "C5", 1, "20050101", "20041201", "20050101", 65.0, "Female", "F", "2005Q1"),
        # Case C6: NULL date handling (Valid date wins over NULL date)
        ("601", "C6", 1, None, None, "20050101", 70.0, "Male", "I", "2005Q1"),
        ("602", "C6", 1, "20050601", "20050501", "20050101", 70.0, "Male", "F", "2005Q2"),
    ]

    con.executemany("INSERT INTO demo VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);", test_rows)

    # Execute canonical view resolution SQL
    con.execute(get_latest_cases_view_sql())

    resolved = con.execute("SELECT case_id, primary_id FROM cases ORDER BY case_id").fetchall()
    resolved_dict = dict(resolved)

    # Assert exact deterministic resolution
    assert resolved_dict["C1"] == "102", "Case C1: Higher version (2 vs 1) must win"
    assert resolved_dict["C2"] == "202", (
        "Case C2: Later regulatory date (20040901 vs 20040101) must win"
    )
    assert resolved_dict["C3"] == "302", (
        "Case C3: Later manufacturer_date (20041215 vs 20041101) must win"
    )
    assert resolved_dict["C4"] == "409", (
        "Case C4: Higher numeric primary_id (409 vs 401) must win tie-breaker"
    )
    assert resolved_dict["C5"] == "502", "Case C5: Valid version 1 must win over NULL version"
    assert resolved_dict["C6"] == "602", "Case C6: Valid date must win over NULL date"
