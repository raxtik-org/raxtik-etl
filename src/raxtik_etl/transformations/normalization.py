"""Centralized Structural Normalization SQL Expressions.

Universal structural transformations for:
- Patient age (standard_age_years with clinical validity bounding 0.0 to 125.0)
- Patient weight (standard_weight_kg)
- Clean string formatting
"""

from __future__ import annotations


def get_standard_age_sql(age_col: str, unit_col: str) -> str:
    """Returns SQL expression for normalized patient age in decimal years (bounded 0.0 to 125.0).

    Args:
        age_col: Column name containing the reported age numeric value.
        unit_col: Column name containing the age measurement unit code ('YR', 'MON', 'DY', etc.).

    Returns:
        SQL CASE expression returning age in decimal years or NULL if invalid/out-of-bounds.
    """
    return f"""
    CASE
        WHEN {unit_col} = 'YR' AND TRY_CAST({age_col} AS DOUBLE) BETWEEN 0.0 AND 125.0 THEN TRY_CAST({age_col} AS DOUBLE)
        WHEN {unit_col} = 'DEC' AND TRY_CAST({age_col} AS DOUBLE) * 10.0 BETWEEN 0.0 AND 125.0 THEN TRY_CAST({age_col} AS DOUBLE) * 10.0
        WHEN {unit_col} = 'MON' AND TRY_CAST({age_col} AS DOUBLE) / 12.0 BETWEEN 0.0 AND 125.0 THEN TRY_CAST({age_col} AS DOUBLE) / 12.0
        WHEN {unit_col} = 'WK' AND TRY_CAST({age_col} AS DOUBLE) / 52.1429 BETWEEN 0.0 AND 125.0 THEN TRY_CAST({age_col} AS DOUBLE) / 52.1429
        WHEN {unit_col} = 'DY' AND TRY_CAST({age_col} AS DOUBLE) / 365.25 BETWEEN 0.0 AND 125.0 THEN TRY_CAST({age_col} AS DOUBLE) / 365.25
        WHEN {unit_col} = 'HR' AND TRY_CAST({age_col} AS DOUBLE) / 8766.0 BETWEEN 0.0 AND 125.0 THEN TRY_CAST({age_col} AS DOUBLE) / 8766.0
        ELSE NULL
    END
    """


def get_standard_weight_sql(wt_col: str, unit_col: str) -> str:
    """Returns SQL expression for normalized patient weight in kilograms.

    Args:
        wt_col: Column name containing the reported weight numeric value.
        unit_col: Column name containing the weight unit code ('KG', 'LBS', 'GMS').

    Returns:
        SQL CASE expression returning weight in decimal kilograms or NULL if unknown.
    """
    return f"""
    CASE
        WHEN {unit_col} = 'KG' THEN TRY_CAST({wt_col} AS DOUBLE)
        WHEN {unit_col} = 'LBS' THEN TRY_CAST({wt_col} AS DOUBLE) * 0.45359237
        WHEN {unit_col} = 'GMS' THEN TRY_CAST({wt_col} AS DOUBLE) / 1000.0
        ELSE NULL
    END
    """


def get_standard_sex_label_sql(sex_col: str) -> str:
    """Returns standard human-readable sex string.

    Args:
        sex_col: Column name containing the reported sex code ('M', 'F', 'UNK', 'NS').

    Returns:
        SQL CASE expression returning standard sex label ('Male', 'Female', 'Unknown') or NULL.
    """
    return f"""
    CASE
        WHEN {sex_col} = 'M' THEN 'Male'
        WHEN {sex_col} = 'F' THEN 'Female'
        WHEN {sex_col} IN ('UNK', 'NS') THEN 'Unknown'
        ELSE NULL
    END
    """


def get_standard_duration_days_sql(dur_col: str, unit_col: str) -> str:
    """Returns SQL expression for therapy duration normalized to days.

    Args:
        dur_col: Column name containing reported therapy duration value.
        unit_col: Column name containing duration unit code ('YR', 'MON', 'WK', 'DY', 'HR').

    Returns:
        SQL CASE expression returning therapy duration in decimal days or NULL.
    """
    return f"""
    CASE
        WHEN {unit_col} = 'YR' THEN TRY_CAST({dur_col} AS DOUBLE) * 365.25
        WHEN {unit_col} = 'MON' THEN TRY_CAST({dur_col} AS DOUBLE) * 30.4375
        WHEN {unit_col} = 'WK' THEN TRY_CAST({dur_col} AS DOUBLE) * 7.0
        WHEN {unit_col} = 'DY' THEN TRY_CAST({dur_col} AS DOUBLE)
        WHEN {unit_col} = 'HR' THEN TRY_CAST({dur_col} AS DOUBLE) / 24.0
        ELSE NULL
    END
    """
