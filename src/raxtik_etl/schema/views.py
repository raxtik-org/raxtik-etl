"""Standard SQL View Definitions for FAERS Packages.

Defines the `cases` deterministic derived view over the physical `reports` / `demo` table,
resolving each CASEID to its latest authoritative version, without mutating underlying records.
"""

from __future__ import annotations

from raxtik_etl.schema.registry import CASE_RESOLUTION_VERSION


def get_latest_cases_view_sql() -> str:
    """Returns the SQL to create the `cases` view resolving the latest caseversion per case_id."""
    return f"""
    -- Case Resolution View (Version: {CASE_RESOLUTION_VERSION})
    -- Resolves the single latest authoritative version per case_id
    CREATE OR REPLACE VIEW cases AS
    WITH ranked_reports AS (
        SELECT
            *,
            ROW_NUMBER() OVER (
                PARTITION BY case_id
                ORDER BY
                    canonical_case_version DESC,
                    fda_date DESC NULLS LAST,
                    manufacturer_date DESC NULLS LAST,
                    primary_id DESC
            ) AS _rn
        FROM demo
    )
    SELECT * EXCLUDE (_rn)
    FROM ranked_reports
    WHERE _rn = 1;
    """


def get_active_substances_summary_view_sql() -> str:
    """Returns a view aggregating primary suspect drugs and adverse events per case."""
    return """
    CREATE OR REPLACE VIEW case_adverse_events_summary AS
    SELECT
        c.case_id,
        c.primary_id,
        c.canonical_case_version,
        c.event_date,
        c.standard_age_years,
        c.standard_sex_label,
        d.reported_drug_name AS primary_suspect_drug,
        d.reported_active_ingredient,
        r.reported_reaction_term AS reaction_term,
        o.outcome_code,
        co.outcome_label
    FROM cases c
    LEFT JOIN drug d
        ON c.primary_id = d.primary_id AND d.role_code = 'PS'
    LEFT JOIN reac r
        ON c.primary_id = r.primary_id
    LEFT JOIN outc o
        ON c.primary_id = o.primary_id
    LEFT JOIN _code_outcomes co
        ON o.outcome_code = co.outcome_code;
    """
