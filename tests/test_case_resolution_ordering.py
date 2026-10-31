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
from raxtik_source_faers.adapter import FAERSAdapter

from raxtik_etl.consolidation import validate_and_normalize_releases


@pytest.fixture
def memory_db():
    con = duckdb.connect(":memory:")
    yield con
    con.close()


def test_cohort_release_input_validation():
    # 1. Empty list
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_and_normalize_releases([])

    # 2. Invalid format
    with pytest.raises(ValueError, match="Invalid quarter release identifier"):
        validate_and_normalize_releases(["2004Q5"])

    with pytest.raises(ValueError, match="Invalid quarter release identifier"):
        validate_and_normalize_releases(["invalid_quarter"])

    # 3. Deduplication and sorting
    input_releases = ["2005Q2", "2004Q1", "2005Q1", "2004Q1", "2004Q3"]
    normalized = validate_and_normalize_releases(input_releases)
    assert normalized == ["2004Q1", "2004Q3", "2005Q1", "2005Q2"]


def test_case_resolution_ordering_rules(memory_db):
    con = memory_db
    adapter = FAERSAdapter()

    # Create synthetic demo table
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
            initial_or_followup_code VARCHAR,
            _source_release VARCHAR
        );
    """)

    # Populate test cases
    test_rows = [
        # Case C1: Version precedence (Version 2 wins over later date)
        ("101", "C1", 1, "20050101", "20041201", "20040101", 30.0, "Female", "I", "2004Q1"),
        ("102", "C1", 2, "20040601", "20040501", "20040101", 30.0, "Female", "F", "2004Q2"),
        # Case C2: Date precedence (Versions equal, later fda_date wins)
        ("201", "C2", 1, "20040101", "20031201", "20030101", 45.0, "Male", "I", "2004Q1"),
        ("202", "C2", 1, "20040901", "20040801", "20030101", 45.0, "Male", "F", "2004Q3"),
        # Case C3: Manufacturer date tie-breaker (Version and fda_date equal, later manufacturer_date wins)
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

    # Execute adapter case resolution
    con.execute(adapter.get_case_resolution_sql())

    resolved = con.execute("SELECT case_id, primary_id FROM cases ORDER BY case_id").fetchall()
    resolved_dict = dict(resolved)

    # Assert exact deterministic resolution
    assert resolved_dict["C1"] == "102", "Case C1: Higher version (2 vs 1) must win"
    assert resolved_dict["C2"] == "202", "Case C2: Later fda_date (20040901 vs 20040101) must win"
    assert resolved_dict["C3"] == "302", (
        "Case C3: Later manufacturer_date (20041215 vs 20041101) must win"
    )
    assert resolved_dict["C4"] == "409", (
        "Case C4: Higher numeric primary_id (409 vs 401) must win tie-breaker"
    )
    assert resolved_dict["C5"] == "502", "Case C5: Valid version 1 must win over NULL version"
    assert resolved_dict["C6"] == "602", "Case C6: Valid date must win over NULL date"


def test_analytical_summary_view_zero_cartesian_fanout(memory_db):
    """Verifies that a report with multiple suspect drugs, reactions, and outcomes

    produces EXACTLY 1 row per case in case_adverse_events_summary without multiplying counts.
    """
    con = memory_db
    adapter = FAERSAdapter()

    # 1. Setup tables
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
            _source_release VARCHAR
        );
        CREATE TABLE drug (
            primary_id VARCHAR,
            reported_drug_name VARCHAR,
            structural_clean_drug_name VARCHAR,
            role_code VARCHAR
        );
        CREATE TABLE reac (
            primary_id VARCHAR,
            reported_reaction_term VARCHAR
        );
        CREATE TABLE outc (
            primary_id VARCHAR,
            outcome_code VARCHAR
        );
        CREATE TABLE _code_outcomes (
            outcome_code VARCHAR PRIMARY KEY,
            outcome_label VARCHAR
        );
    """)

    con.execute("""
        INSERT INTO _code_outcomes VALUES
        ('DE', 'Death'),
        ('HO', 'Hospitalization - Initial or Prolonged');
    """)

    # 2. Insert 1 report with multiple 1-to-many child rows:
    # 2 Primary Suspect drugs ('PS') + 1 Concomitant ('C')
    # 3 Distinct Reactions
    # 2 Distinct Outcomes
    # (In buggy Cartesian join: 2 * 3 * 2 = 12 rows!)
    con.execute("""
        INSERT INTO demo VALUES ('99901', 'CASE_MULTI', 1, '20200101', '20191201', '20191101', 55.0, 'Female', '2020Q1');
    """)
    con.execute("""
        INSERT INTO drug VALUES
        ('99901', 'ASPIRIN', 'ASPIRIN', 'PS'),
        ('99901', 'WARFARIN', 'WARFARIN', 'PS'),
        ('99901', 'METFORMIN', 'METFORMIN', 'C');
    """)
    con.execute("""
        INSERT INTO reac VALUES
        ('99901', 'GASTROINTESTINAL HAEMORRHAGE'),
        ('99901', 'ANAEMIA'),
        ('99901', 'HYPOTENSION');
    """)
    con.execute("""
        INSERT INTO outc VALUES
        ('99901', 'HO'),
        ('99901', 'DE');
    """)

    # 3. Create cases view and summary view via adapter
    con.execute(adapter.get_case_resolution_sql())
    for _view_name, view_sql in adapter.get_summary_views_sql().items():
        con.execute(view_sql)

    # 4. Verify ZERO fan-out: exactly 1 row returned!
    summary_rows = con.execute("""
        SELECT * FROM case_adverse_events_summary WHERE case_id = 'CASE_MULTI';
    """).fetchall()

    assert len(summary_rows) == 1, (
        f"Expected exactly 1 row for case, got {len(summary_rows)} (Cartesian fan-out!)"
    )

    # Verify column values
    row = con.execute("""
        SELECT
            case_id,
            primary_suspect_drugs,
            reaction_terms,
            reaction_count,
            outcome_codes,
            has_death,
            has_hospitalization,
            has_life_threatening
        FROM case_adverse_events_summary
        WHERE case_id = 'CASE_MULTI';
    """).fetchone()

    case_id, ps_drugs, reacs, reac_cnt, outc_codes, has_de, has_ho, has_lt = row
    assert case_id == "CASE_MULTI"
    assert set(ps_drugs) == {"ASPIRIN", "WARFARIN"}, (
        "Only 'PS' suspect drugs should be in primary_suspect_drugs"
    )
    assert "METFORMIN" not in ps_drugs, "Concomitant drugs must not be in primary_suspect_drugs"
    assert reac_cnt == 3
    assert set(reacs) == {"GASTROINTESTINAL HAEMORRHAGE", "ANAEMIA", "HYPOTENSION"}
    assert set(outc_codes) == {"HO", "DE"}
    assert has_de is True, "has_death flag must be True"
    assert has_ho is True, "has_hospitalization flag must be True"
    assert has_lt is False, "has_life_threatening flag must be False"
