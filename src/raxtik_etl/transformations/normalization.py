"""Centralized Structural Normalization SQL Expressions.

Universal structural transformations for:
- Patient age (standard_age_years with clinical validity bounding 0.0 to 125.0)
- Patient weight (standard_weight_kg)
- Clean string formatting
"""

from __future__ import annotations


def get_standard_age_sql(age_col: str, unit_col: str) -> str:
    """Returns SQL expression for normalized patient age in decimal years (bounded 0.0 to 125.0)."""
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
    """Returns SQL expression for normalized patient weight in kilograms."""
    return f"""
    CASE
        WHEN {unit_col} = 'KG' THEN TRY_CAST({wt_col} AS DOUBLE)
        WHEN {unit_col} = 'LBS' THEN TRY_CAST({wt_col} AS DOUBLE) * 0.45359237
        WHEN {unit_col} = 'GMS' THEN TRY_CAST({wt_col} AS DOUBLE) / 1000.0
        ELSE NULL
    END
    """


def get_standard_sex_label_sql(sex_col: str) -> str:
    """Returns standard human-readable sex string."""
    return f"""
    CASE
        WHEN {sex_col} = 'M' THEN 'Male'
        WHEN {sex_col} = 'F' THEN 'Female'
        WHEN {sex_col} IN ('UNK', 'NS') THEN 'Unknown'
        ELSE NULL
    END
    """


def get_standard_duration_days_sql(dur_col: str, unit_col: str) -> str:
    """Returns SQL expression for therapy duration normalized to days."""
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
