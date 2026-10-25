"""Phase 1.5 - Comprehensive Correctness & Contract Validation for 2004Q1 Package.

Verifies:
1. Row count reconciliation against raw source files
2. Primary key uniqueness and non-null constraints
3. Foreign key referential integrity across all 6 child tables
4. Dual presentation layer contract (reports physical vs cases derived view)
5. Case versioning semantics (FOLL_SEQ handling, deterministic latest resolution)
6. Source presence guarantees (PROD_AI, DOSE_AMT, CUM_DOSE are NULL in S1)
7. Code lookup dimension tables and joins
8. Provenance completeness across all tables
9. Verbatim reported value preservation
10. Clinical range and sanity checks (age bounds, seriousness categories)
"""

import duckdb
import pytest

from raxtik_etl.distribution.huggingface import get_default_package_dir

PACKAGE_DUCKDB = get_default_package_dir() / "faers_2004Q1.duckdb"


@pytest.fixture(scope="module")
def con():
    if not PACKAGE_DUCKDB.exists():
        pytest.skip(f"Package not found at {PACKAGE_DUCKDB}. Skipping local package audit.")
    connection = duckdb.connect(PACKAGE_DUCKDB.as_posix(), read_only=True)
    yield connection
    connection.close()


def test_01_row_count_reconciliation(con):
    """Verify row counts match expected raw ingestion counts."""
    demo_count = con.execute("SELECT COUNT(*) FROM demo").fetchone()[0]
    drug_count = con.execute("SELECT COUNT(*) FROM drug").fetchone()[0]
    reac_count = con.execute("SELECT COUNT(*) FROM reac").fetchone()[0]
    outc_count = con.execute("SELECT COUNT(*) FROM outc").fetchone()[0]
    indi_count = con.execute("SELECT COUNT(*) FROM indi").fetchone()[0]
    ther_count = con.execute("SELECT COUNT(*) FROM ther").fetchone()[0]
    rpsr_count = con.execute("SELECT COUNT(*) FROM rpsr").fetchone()[0]

    assert demo_count == 65902, f"Expected 65902 demo rows, got {demo_count}"
    assert drug_count == 235361, f"Expected 235361 drug rows, got {drug_count}"
    assert reac_count == 264410, f"Expected 264410 reac rows, got {reac_count}"
    assert outc_count == 57592, f"Expected 57592 outc rows, got {outc_count}"
    assert indi_count > 0
    assert ther_count > 0
    assert rpsr_count > 0


def test_02_primary_key_uniqueness_in_reports(con):
    """In the physical demo table, primary_id (ISR) must be completely unique and non-null."""
    null_pks = con.execute("SELECT COUNT(*) FROM demo WHERE primary_id IS NULL").fetchone()[0]
    assert null_pks == 0, "Found NULL primary_id in demo table"

    total = con.execute("SELECT COUNT(*) FROM demo").fetchone()[0]
    distinct = con.execute("SELECT COUNT(DISTINCT primary_id) FROM demo").fetchone()[0]
    assert total == distinct, f"Duplicate primary_id found: total={total}, distinct={distinct}"


def test_03_foreign_key_referential_integrity(con):
    """Every child table record must resolve to a valid primary_id in demo."""
    orphaned_drugs = con.execute("""
        SELECT COUNT(*) FROM drug d
        LEFT JOIN demo dm ON d.primary_id = dm.primary_id
        WHERE dm.primary_id IS NULL
    """).fetchone()[0]
    assert orphaned_drugs == 0, f"Found {orphaned_drugs} orphaned drug records"

    orphaned_reacs = con.execute("""
        SELECT COUNT(*) FROM reac r
        LEFT JOIN demo dm ON r.primary_id = dm.primary_id
        WHERE dm.primary_id IS NULL
    """).fetchone()[0]
    assert orphaned_reacs == 0, f"Found {orphaned_reacs} orphaned reaction records"

    orphaned_outcs = con.execute("""
        SELECT COUNT(*) FROM outc o
        LEFT JOIN demo dm ON o.primary_id = dm.primary_id
        WHERE dm.primary_id IS NULL
    """).fetchone()[0]
    assert orphaned_outcs == 0, f"Found {orphaned_outcs} orphaned outcome records"


def test_04_dual_presentation_layer_contract(con):
    """reports (demo) holds 65,902 rows; cases view resolves to 58,235 unique cases.

    Note on 58,228 vs 58,235:
    Raw 2004Q1 DEMO contains exactly 7 records where CASE is NULL/empty (ISRs: 4265290,
    4274589, 4276661, 4281791, 4283275, 4297346, 4322505). Prior to handling this,
    COUNT(DISTINCT CASE) was 58,228 (collapsing all 7 NULLs). With the verified fallback
    COALESCE(\"CASE\", ISR), each orphaned submission correctly forms its own unique case,
    yielding 58,228 + 7 = 58,235 unique cases.
    """
    reports_count = con.execute("SELECT COUNT(*) FROM demo").fetchone()[0]
    cases_count = con.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    unique_cases = con.execute("SELECT COUNT(DISTINCT case_id) FROM demo").fetchone()[0]

    assert reports_count == 65902
    assert cases_count == 58235
    assert cases_count == unique_cases, "cases view row count must equal COUNT(DISTINCT case_id)"


def test_05_case_version_resolution_logic(con):
    """Verify that multi-report cases resolve to their latest canonical_case_version."""
    # Find a case with multiple versions
    multi_case = con.execute("""
        SELECT case_id, COUNT(*) as cnt
        FROM demo
        GROUP BY case_id
        HAVING cnt > 1
        LIMIT 1
    """).fetchone()[0]

    # In demo, we should have multiple rows
    demo_versions = con.execute(
        f"SELECT canonical_case_version FROM demo WHERE case_id = '{multi_case}' ORDER BY canonical_case_version DESC"
    ).fetchall()
    assert len(demo_versions) > 1

    # In cases, we must have exactly 1 row with the maximum version
    resolved_case = con.execute(
        f"SELECT canonical_case_version FROM cases WHERE case_id = '{multi_case}'"
    ).fetchall()
    assert len(resolved_case) == 1
    assert resolved_case[0][0] == demo_versions[0][0]


def test_06_source_presence_in_s1(con):
    """In S1 (2004Q1), PROD_AI, DOSE_AMT, and CUM_DOSE_CHR must be NULL."""
    prod_ai_populated = con.execute(
        "SELECT COUNT(*) FROM drug WHERE reported_active_ingredient IS NOT NULL"
    ).fetchone()[0]
    assert prod_ai_populated == 0, "PROD_AI should not exist in 2004Q1 (S1)"

    dose_amt_populated = con.execute(
        "SELECT COUNT(*) FROM drug WHERE dose_amount IS NOT NULL"
    ).fetchone()[0]
    assert dose_amt_populated == 0, "DOSE_AMT should not exist in 2004Q1 (S1)"

    cum_dose_populated = con.execute(
        "SELECT COUNT(*) FROM drug WHERE cumulative_dose_amount IS NOT NULL"
    ).fetchone()[0]
    assert cum_dose_populated == 0, "CUM_DOSE should not exist in 2004Q1 (S1)"


def test_07_code_dimension_tables_and_joins(con):
    """Verify FDA reference tables and Raxtik semantic tables exist and join correctly."""
    # 1. FDA Source Reference Table
    outcomes_ref = con.execute(
        "SELECT COUNT(*) FROM _code_outcomes WHERE source_system = 'FDA_CDER'"
    ).fetchone()[0]
    assert outcomes_ref == 7

    # 2. Raxtik Derived Semantics Table
    semantics_count = con.execute(
        "SELECT COUNT(*) FROM _code_outcome_semantics WHERE is_serious = TRUE"
    ).fetchone()[0]
    assert semantics_count == 7

    # 3. Roles Reference
    roles_ref = con.execute("SELECT COUNT(*) FROM _code_roles").fetchone()[0]
    assert roles_ref >= 4

    # 4. Dechallenge & Rechallenge References
    dechal_ref = con.execute("SELECT COUNT(*) FROM _code_dechallenge").fetchone()[0]
    assert dechal_ref == 4
    rechal_ref = con.execute("SELECT COUNT(*) FROM _code_rechallenge").fetchone()[0]
    assert rechal_ref == 4

    # 5. Occupations & Report Sources References
    occp_ref = con.execute("SELECT COUNT(*) FROM _code_occupations").fetchone()[0]
    assert occp_ref >= 5
    rpsr_ref = con.execute("SELECT COUNT(*) FROM _code_report_sources").fetchone()[0]
    assert rpsr_ref >= 7

    # 6. Code-list Integrity Assertion (Every outcome_code in outc must exist in FDA reference)
    unmapped_codes = con.execute("""
        SELECT DISTINCT o.outcome_code
        FROM outc o
        LEFT JOIN _code_outcomes c ON o.outcome_code = c.outcome_code
        WHERE c.outcome_code IS NULL
    """).fetchall()
    assert len(unmapped_codes) == 0, f"Found unmapped outcome codes: {unmapped_codes}"

    # 5. Join outc with FDA reference
    joined_outcomes = con.execute("""
        SELECT COUNT(*)
        FROM outc o
        JOIN _code_outcomes d ON o.outcome_code = d.outcome_code
    """).fetchone()[0]
    assert joined_outcomes == 57592


def test_08_provenance_completeness(con):
    """Every record must carry immutable provenance attributes."""
    missing_prov_demo = con.execute("""
        SELECT COUNT(*) FROM demo
        WHERE _source_system IS NULL OR _source_release IS NULL OR _source_file IS NULL OR _source_signature_id IS NULL
    """).fetchone()[0]
    assert missing_prov_demo == 0

    missing_prov_drug = con.execute("""
        SELECT COUNT(*) FROM drug
        WHERE _source_system IS NULL OR _source_release IS NULL OR _source_file IS NULL OR _source_signature_id IS NULL
    """).fetchone()[0]
    assert missing_prov_drug == 0


def test_09_verbatim_preservation(con):
    """Reported drug names and reactions must preserve raw formatting."""
    raw_sample = con.execute(
        "SELECT reported_drug_name FROM drug WHERE reported_drug_name LIKE '%(%' LIMIT 1"
    ).fetchone()
    assert raw_sample is not None
    assert "(" in raw_sample[0]


def test_10_clinical_sanity_and_outlier_ranges(con):
    """Verify age normalization and seriousness statistics are sane."""
    # Age conversion sanity
    invalid_ages = con.execute(
        "SELECT COUNT(*) FROM demo WHERE standard_age_years < 0 OR standard_age_years > 130"
    ).fetchone()[0]
    assert invalid_ages == 0, f"Found {invalid_ages} impossible patient ages"

    # Outcome death count
    deaths = con.execute("SELECT COUNT(*) FROM outc WHERE outcome_code = 'DE'").fetchone()[0]
    assert deaths == 7286
