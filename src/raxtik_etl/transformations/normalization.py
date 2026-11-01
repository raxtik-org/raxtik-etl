"""Centralized Clinical & Structural Normalization Rules.

Universal structural transformations for:
- Patient age (standard_age_years with clinical validity bounding 0.0 to 125.0)
- Patient weight (standard_weight_kg)
- Sex and gender label mapping
- Therapy duration normalized to days
"""

from __future__ import annotations

from typing import Final, Mapping

# -----------------------------------------------------------------------------
# Declarative Normalization Configurations
# -----------------------------------------------------------------------------

CLINICAL_AGE_BOUNDS: Final[tuple[float, float]] = (0.0, 125.0)

# Multipliers to convert reported age into standard decimal years
AGE_UNIT_FACTORS: Final[dict[str, float]] = {
    "YR": 1.0,
    "DEC": 10.0,
    "MON": 1.0 / 12.0,
    "WK": 1.0 / 52.1429,
    "DY": 1.0 / 365.25,
    "HR": 1.0 / 8766.0,
}

# Multipliers to convert reported weight into standard kilograms
WEIGHT_UNIT_FACTORS: Final[dict[str, float]] = {
    "KG": 1.0,
    "LBS": 0.45359237,
    "GMS": 1.0 / 1000.0,
}

# Mapping from reported raw sex/gender codes to canonical human-readable labels
SEX_LABEL_MAPPING: Final[dict[str, str]] = {
    "M": "Male",
    "F": "Female",
    "UNK": "Unknown",
    "NS": "Unknown",
}

# Mapping from reported initial/followup codes to human-readable labels
INITIAL_OR_FOLLOWUP_LABEL_MAPPING: Final[dict[str, str]] = {
    "I": "Initial",
    "F": "Followup",
}

# Mapping from reporter occupation codes to human-readable labels
OCCUPATION_LABEL_MAPPING: Final[dict[str, str]] = {
    "MD": "Physician",
    "PH": "Pharmacist",
    "OT": "Other Health-Professional",
    "LW": "Lawyer",
    "CN": "Consumer",
}

# Mapping from report type codes to human-readable labels
REPORT_TYPE_LABEL_MAPPING: Final[dict[str, str]] = {
    "EXP": "Expedited (15-Day)",
    "PER": "Periodic",
    "DIR": "Direct",
}

# Mapping from drug role codes to human-readable labels
DRUG_ROLE_LABEL_MAPPING: Final[dict[str, str]] = {
    "PS": "Primary Suspect",
    "SS": "Secondary Suspect",
    "C": "Concomitant",
    "I": "Interacting",
}

# Mapping from dechallenge codes to human-readable labels
DECHALLENGE_LABEL_MAPPING: Final[dict[str, str]] = {
    "Y": "Positive",
    "N": "Negative",
    "U": "Unknown",
    "D": "Does Not Apply",
}

# Mapping from rechallenge codes to human-readable labels
RECHALLENGE_LABEL_MAPPING: Final[dict[str, str]] = {
    "Y": "Positive",
    "N": "Negative",
    "U": "Unknown",
    "D": "Does Not Apply",
}

# Mapping from outcome codes to human-readable labels
OUTCOME_LABEL_MAPPING: Final[dict[str, str]] = {
    "DE": "Death",
    "LT": "Life-Threatening",
    "HO": "Hospitalization - Initial or Prolonged",
    "DS": "Disability",
    "CA": "Congenital Anomaly",
    "RI": "Required Intervention to Prevent Permanent Impairment/Damage",
    "OT": "Other",
}

# Mapping from report source codes to human-readable labels
REPORT_SOURCE_LABEL_MAPPING: Final[dict[str, str]] = {
    "FGN": "Foreign",
    "SDY": "Study",
    "LIT": "Literature",
    "CSM": "Consumer",
    "HP": "Health Professional",
    "UF": "User Facility",
    "CR": "Company Representative",
    "DT": "Distributor",
    "OTH": "Other",
}

# Multipliers to convert reported therapy duration into decimal days
DURATION_UNIT_FACTORS: Final[dict[str, float]] = {
    "YR": 365.25,
    "MON": 30.4375,
    "WK": 7.0,
    "DY": 1.0,
    "DAY": 1.0,
    "HR": 1.0 / 24.0,
    "MIN": 1.0 / 1440.0,
    "SEC": 1.0 / 86400.0,
}


# -----------------------------------------------------------------------------
# Dynamic SQL Expression Generators
# -----------------------------------------------------------------------------


def get_standard_age_sql(
    age_col: str,
    unit_col: str,
    factors: Mapping[str, float] = AGE_UNIT_FACTORS,
    bounds: tuple[float, float] = CLINICAL_AGE_BOUNDS,
) -> str:
    """Returns SQL expression for normalized patient age in decimal years.

    Args:
        age_col: Column name containing the reported age numeric value.
        unit_col: Column name containing the age measurement unit code ('YR', 'MON', 'DY', etc.).
        factors: Mapping of unit codes to year multiplication factors.
        bounds: (min_age, max_age) clinical validity bounding range.

    Returns:
        SQL CASE expression returning age in decimal years or NULL if invalid/out-of-bounds.
    """
    min_age, max_age = bounds
    branches = []
    for unit, factor in factors.items():
        if factor == 1.0:
            calc = f"TRY_CAST({age_col} AS DOUBLE)"
        else:
            calc = f"TRY_CAST({age_col} AS DOUBLE) * {factor}"
        branches.append(
            f"WHEN {unit_col} = '{unit}' AND {calc} BETWEEN {min_age} AND {max_age} THEN {calc}"
        )

    branch_sql = "\n        ".join(branches)
    return f"""CASE
        {branch_sql}
        ELSE NULL
    END"""


def get_standard_weight_sql(
    wt_col: str,
    unit_col: str,
    factors: Mapping[str, float] = WEIGHT_UNIT_FACTORS,
) -> str:
    """Returns SQL expression for normalized patient weight in kilograms.

    Args:
        wt_col: Column name containing the reported weight numeric value.
        unit_col: Column name containing the weight unit code ('KG', 'LBS', 'GMS').
        factors: Mapping of unit codes to kilogram multiplication factors.

    Returns:
        SQL CASE expression returning weight in decimal kilograms or NULL if unknown.
    """
    branches = []
    for unit, factor in factors.items():
        if factor == 1.0:
            calc = f"TRY_CAST({wt_col} AS DOUBLE)"
        else:
            calc = f"TRY_CAST({wt_col} AS DOUBLE) * {factor}"
        branches.append(f"WHEN {unit_col} = '{unit}' THEN {calc}")

    branch_sql = "\n        ".join(branches)
    return f"""CASE
        {branch_sql}
        ELSE NULL
    END"""


def get_standard_sex_label_sql(
    sex_col: str,
    mapping: Mapping[str, str] = SEX_LABEL_MAPPING,
) -> str:
    """Returns standard human-readable sex string.

    Args:
        sex_col: Column name containing the reported sex code ('M', 'F', 'UNK', 'NS').
        mapping: Mapping from reported sex code to standard label.

    Returns:
        SQL CASE expression returning standard sex label ('Male', 'Female', 'Unknown') or NULL.
    """
    branches = [f"WHEN {sex_col} = '{code}' THEN '{label}'" for code, label in mapping.items()]
    branch_sql = "\n        ".join(branches)
    return f"""CASE
        {branch_sql}
        ELSE NULL
    END"""


def get_standard_duration_days_sql(
    dur_col: str,
    unit_col: str,
    factors: Mapping[str, float] = DURATION_UNIT_FACTORS,
) -> str:
    """Returns SQL expression for therapy duration normalized to days.

    Args:
        dur_col: Column name containing reported therapy duration value.
        unit_col: Column name containing duration unit code ('YR', 'MON', 'WK', 'DY', 'HR').
        factors: Mapping of unit codes to days multiplication factors.

    Returns:
        SQL CASE expression returning therapy duration in decimal days or NULL.
    """
    branches = []
    for unit, factor in factors.items():
        if factor == 1.0:
            calc = f"TRY_CAST({dur_col} AS DOUBLE)"
        else:
            calc = f"TRY_CAST({dur_col} AS DOUBLE) * {factor}"
        branches.append(f"WHEN {unit_col} = '{unit}' THEN {calc}")

    branch_sql = "\n        ".join(branches)
    return f"""CASE
        {branch_sql}
        ELSE NULL
    END"""


def get_standard_date_sql(date_col: str) -> str:
    """Returns SQL expression for standard parsed/imputed DATE.

    Imputation Strategy:
    - 8-digit exact YYYYMMDD: parsed directly to DATE.
    - Year + Month (YYYYMM or YYYYMM00): imputed to 1st of month (YYYY-MM-01).
    - Year only (YYYY or YYYY0000): imputed to Jan 1st of year (YYYY-01-01).
    - Unparsable or invalid dates: NULL.

    Args:
        date_col: Column name or expression containing raw date string.

    Returns:
        SQL CASE expression returning a DATE or NULL.
    """
    clean = f"NULLIF(TRIM(CAST({date_col} AS VARCHAR)), '')"
    return f"""CASE
        WHEN TRY_STRPTIME({clean}, '%Y%m%d') IS NOT NULL
            THEN TRY_CAST(TRY_STRPTIME({clean}, '%Y%m%d') AS DATE)
        WHEN REGEXP_MATCHES({clean}, '^[12][0-9]{{3}}(0[1-9]|1[0-2])(00)?$')
            THEN TRY_CAST(TRY_STRPTIME(SUBSTR({clean}, 1, 6) || '01', '%Y%m%d') AS DATE)
        WHEN REGEXP_MATCHES({clean}, '^[12][0-9]{{3}}(0000)?$')
            THEN TRY_CAST(TRY_STRPTIME(SUBSTR({clean}, 1, 4) || '0101', '%Y%m%d') AS DATE)
        ELSE NULL
    END"""


def get_date_precision_sql(date_col: str) -> str:
    """Returns SQL expression for date precision audit classification.

    Classifications:
    - 'EXACT': Valid 8-digit calendar date (YYYYMMDD).
    - 'YEAR_MONTH': Missing day, imputed to 1st of month.
    - 'YEAR_ONLY': Missing month and day, imputed to Jan 1st.
    - 'INVALID': Non-empty date string that could not be parsed.
    - NULL: Missing / empty date.

    Args:
        date_col: Column name or expression containing raw date string.

    Returns:
        SQL CASE expression returning precision label VARCHAR or NULL.
    """
    clean = f"NULLIF(TRIM(CAST({date_col} AS VARCHAR)), '')"
    return f"""CASE
        WHEN {clean} IS NULL THEN NULL
        WHEN TRY_STRPTIME({clean}, '%Y%m%d') IS NOT NULL
            THEN 'EXACT'
        WHEN REGEXP_MATCHES({clean}, '^[12][0-9]{{3}}(0[1-9]|1[0-2])(00)?$')
            THEN 'YEAR_MONTH'
        WHEN REGEXP_MATCHES({clean}, '^[12][0-9]{{3}}(0000)?$')
            THEN 'YEAR_ONLY'
        ELSE 'INVALID'
    END"""


def get_initial_or_followup_label_sql(
    code_col: str,
    mapping: Mapping[str, str] = INITIAL_OR_FOLLOWUP_LABEL_MAPPING,
) -> str:
    """Returns SQL expression for human-readable initial or followup label."""
    clean = f"UPPER(TRIM(CAST({code_col} AS VARCHAR)))"
    branches = [f"WHEN {clean} = '{code}' THEN '{label}'" for code, label in mapping.items()]
    branch_sql = "\n        ".join(branches)
    return f"""CASE
        {branch_sql}
        ELSE NULL
    END"""


def get_reporter_occupation_label_sql(
    code_col: str,
    mapping: Mapping[str, str] = OCCUPATION_LABEL_MAPPING,
) -> str:
    """Returns SQL expression for human-readable reporter occupation label."""
    clean = f"UPPER(TRIM(CAST({code_col} AS VARCHAR)))"
    branches = [f"WHEN {clean} = '{code}' THEN '{label}'" for code, label in mapping.items()]
    branch_sql = "\n        ".join(branches)
    return f"""CASE
        {branch_sql}
        ELSE NULL
    END"""


def get_report_type_label_sql(
    code_col: str,
    mapping: Mapping[str, str] = REPORT_TYPE_LABEL_MAPPING,
) -> str:
    """Returns SQL expression for human-readable report type label."""
    clean = f"UPPER(TRIM(CAST({code_col} AS VARCHAR)))"
    branches = [f"WHEN {clean} = '{code}' THEN '{label}'" for code, label in mapping.items()]
    branch_sql = "\n        ".join(branches)
    return f"""CASE
        {branch_sql}
        ELSE NULL
    END"""


def get_drug_role_label_sql(
    code_col: str,
    mapping: Mapping[str, str] = DRUG_ROLE_LABEL_MAPPING,
) -> str:
    """Returns SQL expression for human-readable drug suspect role label."""
    clean = f"UPPER(TRIM(CAST({code_col} AS VARCHAR)))"
    branches = [f"WHEN {clean} = '{code}' THEN '{label}'" for code, label in mapping.items()]
    branch_sql = "\n        ".join(branches)
    return f"""CASE
        {branch_sql}
        ELSE NULL
    END"""


def get_dechallenge_label_sql(
    code_col: str,
    mapping: Mapping[str, str] = DECHALLENGE_LABEL_MAPPING,
) -> str:
    """Returns SQL expression for human-readable dechallenge outcome label."""
    clean = f"UPPER(TRIM(CAST({code_col} AS VARCHAR)))"
    branches = [f"WHEN {clean} = '{code}' THEN '{label}'" for code, label in mapping.items()]
    branch_sql = "\n        ".join(branches)
    return f"""CASE
        {branch_sql}
        ELSE NULL
    END"""


def get_rechallenge_label_sql(
    code_col: str,
    mapping: Mapping[str, str] = RECHALLENGE_LABEL_MAPPING,
) -> str:
    """Returns SQL expression for human-readable rechallenge outcome label."""
    clean = f"UPPER(TRIM(CAST({code_col} AS VARCHAR)))"
    branches = [f"WHEN {clean} = '{code}' THEN '{label}'" for code, label in mapping.items()]
    branch_sql = "\n        ".join(branches)
    return f"""CASE
        {branch_sql}
        ELSE NULL
    END"""


def get_outcome_label_sql(
    code_col: str,
    mapping: Mapping[str, str] = OUTCOME_LABEL_MAPPING,
) -> str:
    """Returns SQL expression for human-readable patient outcome label."""
    clean = f"UPPER(TRIM(CAST({code_col} AS VARCHAR)))"
    branches = [f"WHEN {clean} = '{code}' THEN '{label}'" for code, label in mapping.items()]
    branch_sql = "\n        ".join(branches)
    return f"""CASE
        {branch_sql}
        ELSE NULL
    END"""


def get_outcome_is_serious_sql(code_col: str) -> str:
    """Returns SQL boolean expression for patient outcome seriousness criterion."""
    clean = f"UPPER(TRIM(CAST({code_col} AS VARCHAR)))"
    return f"""CASE
        WHEN {clean} IN ('DE', 'LT', 'HO', 'DS', 'CA', 'RI') THEN TRUE
        WHEN {clean} = 'OT' THEN FALSE
        ELSE NULL
    END"""


def get_report_source_label_sql(
    code_col: str,
    mapping: Mapping[str, str] = REPORT_SOURCE_LABEL_MAPPING,
) -> str:
    """Returns SQL expression for human-readable report source channel label."""
    clean = f"UPPER(TRIM(CAST({code_col} AS VARCHAR)))"
    branches = [f"WHEN {clean} = '{code}' THEN '{label}'" for code, label in mapping.items()]
    branch_sql = "\n        ".join(branches)
    return f"""CASE
        {branch_sql}
        ELSE NULL
    END"""
