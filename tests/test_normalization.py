"""Unit tests for centralized clinical & structural normalization rules."""

import duckdb
import pytest

from raxtik_etl.transformations.normalization import (
    get_age_group_label_sql,
    get_age_unit_label_sql,
    get_cumulative_dose_unit_label_sql,
    get_date_precision_sql,
    get_dechallenge_label_sql,
    get_dose_frequency_label_sql,
    get_drug_name_source_label_sql,
    get_drug_role_label_sql,
    get_duration_unit_label_sql,
    get_initial_or_followup_label_sql,
    get_outcome_is_serious_sql,
    get_outcome_label_sql,
    get_rechallenge_label_sql,
    get_report_source_label_sql,
    get_report_type_label_sql,
    get_reporter_occupation_label_sql,
    get_standard_age_sql,
    get_standard_date_sql,
    get_standard_duration_days_sql,
    get_standard_sex_label_sql,
    get_standard_weight_sql,
    get_weight_unit_label_sql,
)


def test_standard_age_normalization():
    con = duckdb.connect()
    age_sql = get_standard_age_sql("age_val", "age_unit")

    query = f"""
        WITH sample AS (
            SELECT '45' AS age_val, 'YR' AS age_unit UNION ALL
            SELECT '24', 'MON' UNION ALL
            SELECT '5', 'DEC' UNION ALL
            SELECT '52.1429', 'WK' UNION ALL
            SELECT '365.25', 'DY' UNION ALL
            SELECT '8766.0', 'HR' UNION ALL
            SELECT '200', 'YR' UNION ALL   -- Out of bounds (> 125)
            SELECT '-5', 'YR' UNION ALL    -- Negative age (< 0)
            SELECT '50', 'UNKNOWN' UNION ALL
            SELECT NULL, 'YR'
        )
        SELECT {age_sql} AS std_age FROM sample
    """
    results = [row[0] for row in con.execute(query).fetchall()]
    con.close()

    assert results[0] == 45.0
    assert results[1] == 2.0
    assert results[2] == 50.0
    assert results[3] == pytest.approx(1.0, rel=1e-4)
    assert results[4] == pytest.approx(1.0, rel=1e-4)
    assert results[5] == pytest.approx(1.0, rel=1e-4)
    assert results[6] is None
    assert results[7] is None
    assert results[8] is None
    assert results[9] is None


def test_standard_weight_normalization():
    con = duckdb.connect()
    wt_sql = get_standard_weight_sql("wt_val", "wt_unit")

    query = f"""
        WITH sample AS (
            SELECT '70' AS wt_val, 'KG' AS wt_unit UNION ALL
            SELECT '100', 'LBS' UNION ALL
            SELECT '5000', 'GMS' UNION ALL
            SELECT '70', 'STONE' UNION ALL
            SELECT NULL, 'KG'
        )
        SELECT {wt_sql} AS std_wt FROM sample
    """
    results = [row[0] for row in con.execute(query).fetchall()]
    con.close()

    assert results[0] == 70.0
    assert results[1] == pytest.approx(45.3592, rel=1e-3)
    assert results[2] == 5.0
    assert results[3] is None
    assert results[4] is None


def test_standard_sex_label_normalization():
    con = duckdb.connect()
    sex_sql = get_standard_sex_label_sql("sex_raw")

    query = f"""
        WITH sample AS (
            SELECT 'M' AS sex_raw UNION ALL
            SELECT 'F' UNION ALL
            SELECT 'UNK' UNION ALL
            SELECT 'NS' UNION ALL
            SELECT 'OTHER' UNION ALL
            SELECT NULL
        )
        SELECT {sex_sql} AS std_sex FROM sample
    """
    results = [row[0] for row in con.execute(query).fetchall()]
    con.close()

    assert results[0] == "Male"
    assert results[1] == "Female"
    assert results[2] == "Unknown"
    assert results[3] == "Unknown"
    assert results[4] is None
    assert results[5] is None


def test_standard_duration_days_normalization():
    con = duckdb.connect()
    dur_sql = get_standard_duration_days_sql("dur_val", "dur_unit")

    query = f"""
        WITH sample AS (
            SELECT '1' AS dur_val, 'YR' AS dur_unit UNION ALL
            SELECT '2', 'MON' UNION ALL
            SELECT '3', 'WK' UNION ALL
            SELECT '10', 'DY' UNION ALL
            SELECT '48', 'HR' UNION ALL
            SELECT '5', 'SEC' UNION ALL
            SELECT NULL, 'DY'
        )
        SELECT {dur_sql} AS std_dur FROM sample
    """
    results = [row[0] for row in con.execute(query).fetchall()]
    con.close()

    assert results[0] == 365.25
    assert results[1] == pytest.approx(60.875, rel=1e-3)
    assert results[2] == 21.0
    assert results[3] == 10.0
    assert results[4] == 2.0
    assert results[5] == pytest.approx(5.0 / 86400.0)
    assert results[6] is None


def test_declarative_config_override():
    """Verify custom factors and bounds can be injected into the generators."""
    custom_bounds = (0.0, 50.0)
    custom_age_sql = get_standard_age_sql(
        "age_val", "age_unit", factors={"YR": 1.0}, bounds=custom_bounds
    )
    con = duckdb.connect()
    res = con.execute(
        f"SELECT {custom_age_sql} FROM (SELECT '60' AS age_val, 'YR' AS age_unit)"
    ).fetchone()[0]
    con.close()
    assert res is None  # 60 > 50 -> NULL


def test_standard_date_normalization():
    """Verify exact, partial (month, year), invalid, and empty date parsing."""
    import datetime

    con = duckdb.connect()
    date_sql = get_standard_date_sql("d_raw")
    prec_sql = get_date_precision_sql("d_raw")

    query = f"""
        WITH sample AS (
            SELECT '20040315' AS d_raw UNION ALL
            SELECT '200403' UNION ALL
            SELECT '20040300' UNION ALL
            SELECT '2004' UNION ALL
            SELECT '20040000' UNION ALL
            SELECT ' 20040315 ' UNION ALL
            SELECT '20040231' UNION ALL
            SELECT 'GARBAGE' UNION ALL
            SELECT '' UNION ALL
            SELECT NULL
        )
        SELECT {date_sql} AS std_date, {prec_sql} AS prec FROM sample
    """
    results = con.execute(query).fetchall()
    con.close()

    assert results[0] == (datetime.date(2004, 3, 15), "EXACT")
    assert results[1] == (datetime.date(2004, 3, 1), "YEAR_MONTH")
    assert results[2] == (datetime.date(2004, 3, 1), "YEAR_MONTH")
    assert results[3] == (datetime.date(2004, 1, 1), "YEAR_ONLY")
    assert results[4] == (datetime.date(2004, 1, 1), "YEAR_ONLY")
    assert results[5] == (datetime.date(2004, 3, 15), "EXACT")
    assert results[6] == (None, "INVALID")
    assert results[7] == (None, "INVALID")
    assert results[8] == (None, None)
    assert results[9] == (None, None)


def test_human_readable_label_normalizations():
    """Verify initial/followup, occupation, report type, drug role, dechal, rechal, outcome, and source mappings."""
    con = duckdb.connect()
    if_sql = get_initial_or_followup_label_sql("if_code")
    occp_sql = get_reporter_occupation_label_sql("occp_code")
    rept_sql = get_report_type_label_sql("rept_code")
    role_sql = get_drug_role_label_sql("role_code")
    dechal_sql = get_dechallenge_label_sql("dechal")
    rechal_sql = get_rechallenge_label_sql("rechal")
    outc_sql = get_outcome_label_sql("outc")
    serious_sql = get_outcome_is_serious_sql("outc")
    rpsr_sql = get_report_source_label_sql("rpsr")

    query = f"""
        SELECT
            {if_sql} AS if_lbl,
            {occp_sql} AS occp_lbl,
            {rept_sql} AS rept_lbl,
            {role_sql} AS role_lbl,
            {dechal_sql} AS dechal_lbl,
            {rechal_sql} AS rechal_lbl,
            {outc_sql} AS outc_lbl,
            {serious_sql} AS is_serious,
            {rpsr_sql} AS rpsr_lbl
        FROM (
            SELECT
                'I' AS if_code,
                'MD' AS occp_code,
                'EXP' AS rept_code,
                'PS' AS role_code,
                'Y' AS dechal,
                'N' AS rechal,
                'DE' AS outc,
                'HP' AS rpsr
        )
    """
    res = con.execute(query).fetchone()
    con.close()

    assert res == (
        "Initial",
        "Physician",
        "Expedited (15-Day)",
        "Primary Suspect",
        "Positive",
        "Negative",
        "Death",
        True,
        "Health Professional",
    )


def test_extended_fda_codelist_normalizations():
    """Verify age groups, drug name sources, dose frequencies, cumulative units, duration units, and combination product reports."""
    con = duckdb.connect()
    age_grp_sql = get_age_group_label_sql("age_grp")
    val_vbm_sql = get_drug_name_source_label_sql("val_vbm")
    dose_freq_sql = get_dose_frequency_label_sql("dose_freq")
    cum_unit_sql = get_cumulative_dose_unit_label_sql("cum_unit")
    cum_unit_num_sql = get_cumulative_dose_unit_label_sql("cum_unit_num")
    dur_unit_sql = get_duration_unit_label_sql("dur_unit")
    rept_5day_sql = get_report_type_label_sql("rept_5day")
    rept_30day_sql = get_report_type_label_sql("rept_30day")
    age_unit_sql = get_age_unit_label_sql("age_unit")
    wt_unit_sql = get_weight_unit_label_sql("wt_unit")

    query = f"""
        SELECT
            {age_grp_sql} AS age_grp_lbl,
            {val_vbm_sql} AS val_vbm_lbl,
            {dose_freq_sql} AS dose_freq_lbl,
            {cum_unit_sql} AS cum_unit_lbl,
            {cum_unit_num_sql} AS cum_unit_num_lbl,
            {dur_unit_sql} AS dur_unit_lbl,
            {rept_5day_sql} AS rept_5day_lbl,
            {rept_30day_sql} AS rept_30day_lbl,
            {age_unit_sql} AS age_unit_lbl,
            {wt_unit_sql} AS wt_unit_lbl
        FROM (
            SELECT
                'A' AS age_grp,
                '1' AS val_vbm,
                'BID' AS dose_freq,
                'MG' AS cum_unit,
                '003' AS cum_unit_num,
                'DAY' AS dur_unit,
                '5DAY' AS rept_5day,
                '30DAY' AS rept_30day,
                'YR' AS age_unit,
                'KG' AS wt_unit
        )
    """
    res = con.execute(query).fetchone()
    con.close()

    assert res == (
        "Adult",
        "Validated Trade Name",
        "Twice a day",
        "Milligram(s)",
        "Milligram(s)",
        "Days",
        "5-Day (Combination Product)",
        "30-Day (Combination Product)",
        "Years",
        "Kilograms",
    )
