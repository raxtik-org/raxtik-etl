"""Signature S1 (Legacy AERS: 2004Q1 - 2012Q3) Canonical Mapping.

Maps raw AERS text files (ISR, CASE, FOLL_SEQ, GNDR_COD) to the canonical schema.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from raxtik_etl.transformations.normalization import (
    get_standard_age_sql,
    get_standard_duration_days_sql,
    get_standard_sex_label_sql,
    get_standard_weight_sql,
)


def load_s1_demo(con: duckdb.DuckDBPyConnection, file_path: Path, release: str):
    """Loads S1 DEMO file into canonical demo table."""
    age_sql = get_standard_age_sql("AGE", "AGE_COD")
    wt_sql = get_standard_weight_sql("WT", "WT_COD")
    sex_label_sql = get_standard_sex_label_sql("GNDR_COD")

    con.execute(f"""
        CREATE OR REPLACE TABLE demo AS
        SELECT
            CAST(ISR AS VARCHAR) AS primary_id,
            CAST(COALESCE("CASE", ISR) AS VARCHAR) AS case_id,
            CAST(NULL AS INTEGER) AS fda_case_version,
            CAST(COALESCE(TRY_CAST(FOLL_SEQ AS INTEGER) + 1, 1) AS INTEGER) AS canonical_case_version,
            'DERIVED_FROM_FOLL_SEQ' AS case_version_source,
            CAST(FOLL_SEQ AS VARCHAR) AS foll_seq,
            CAST(I_F_COD AS VARCHAR) AS initial_or_followup_code,
            CAST(EVENT_DT AS VARCHAR) AS event_date,
            CAST(MFR_DT AS VARCHAR) AS manufacturer_date,
            CAST(NULL AS VARCHAR) AS initial_fda_date,
            CAST(FDA_DT AS VARCHAR) AS fda_date,
            CAST(REPT_DT AS VARCHAR) AS report_date,
            CAST(REPT_COD AS VARCHAR) AS report_code,
            CAST(E_SUB AS VARCHAR) AS electronic_submission_flag,
            CAST(MFR_NUM AS VARCHAR) AS manufacturer_num,
            CAST(MFR_SNDR AS VARCHAR) AS manufacturer_sender,
            CAST(NULL AS VARCHAR) AS auth_num,
            CAST(NULL AS VARCHAR) AS lit_ref,
            CAST(TO_MFR AS VARCHAR) AS to_mfr,
            TRY_CAST(AGE AS DOUBLE) AS reported_age,
            CAST(AGE_COD AS VARCHAR) AS reported_age_code,
            CAST(NULL AS VARCHAR) AS reported_age_group_code,
            CAST(GNDR_COD AS VARCHAR) AS reported_sex_code,
            TRY_CAST(WT AS DOUBLE) AS reported_weight,
            CAST(WT_COD AS VARCHAR) AS reported_weight_code,
            CAST(OCCP_COD AS VARCHAR) AS reporter_occupation_code,
            CAST(NULL AS VARCHAR) AS reporter_country,
            CAST(NULL AS VARCHAR) AS occurrence_country,
            {age_sql} AS standard_age_years,
            {sex_label_sql} AS standard_sex_label,
            {wt_sql} AS standard_weight_kg,
            'FDA_FAERS_ASCII' AS _source_system,
            '{release}' AS _source_release,
            '{file_path.name}' AS _source_file,
            'S1' AS _source_signature_id,
            CURRENT_TIMESTAMP AS _ingested_at
        FROM read_csv('{file_path.as_posix()}', delim='$', header=True, all_varchar=True, quote='', escape='', ignore_errors=true, null_padding=true);
    """)


def load_s1_drug(con: duckdb.DuckDBPyConnection, file_path: Path, release: str):
    """Loads S1 DRUG file into canonical drug table."""
    con.execute(f"""
        CREATE OR REPLACE TABLE drug AS
        SELECT
            CAST(d.ISR AS VARCHAR) AS primary_id,
            CAST(dm.case_id AS VARCHAR) AS case_id,
            COALESCE(TRY_CAST(d.DRUG_SEQ AS INTEGER), 1) AS drug_seq,
            CAST(d.DRUGNAME AS VARCHAR) AS reported_drug_name,
            CAST(NULL AS VARCHAR) AS reported_active_ingredient,
            CAST(d.VAL_VBM AS VARCHAR) AS reported_validation_code,
            CAST(d.ROLE_COD AS VARCHAR) AS role_code,
            CAST(d.ROUTE AS VARCHAR) AS route,
            CAST(d.DOSE_VBM AS VARCHAR) AS reported_dose_verbatim,
            CAST(NULL AS DOUBLE) AS dose_amount,
            CAST(NULL AS VARCHAR) AS dose_unit,
            CAST(NULL AS VARCHAR) AS dose_form,
            CAST(NULL AS VARCHAR) AS dose_frequency,
            CAST(NULL AS DOUBLE) AS cumulative_dose_amount,
            CAST(NULL AS VARCHAR) AS cumulative_dose_unit,
            CAST(d.DECHAL AS VARCHAR) AS dechallenge_code,
            CAST(d.RECHAL AS VARCHAR) AS rechallenge_code,
            CAST(d.LOT_NUM AS VARCHAR) AS lot_number,
            CAST(d.EXP_DT AS VARCHAR) AS expiration_date,
            CAST(d.NDA_NUM AS VARCHAR) AS nda_num,
            TRIM(UPPER(CAST(d.DRUGNAME AS VARCHAR))) AS structural_clean_drug_name,
            CAST(NULL AS VARCHAR) AS standard_concept_name,
            CAST(NULL AS VARCHAR) AS standard_concept_source,
            CAST(NULL AS VARCHAR) AS rxcui,
            'NOT_ATTEMPTED' AS derivation_status,
            'FDA_FAERS_ASCII' AS _source_system,
            '{release}' AS _source_release,
            '{file_path.name}' AS _source_file,
            'S1' AS _source_signature_id,
            CURRENT_TIMESTAMP AS _ingested_at
        FROM read_csv('{file_path.as_posix()}', delim='$', header=True, all_varchar=True, quote='', escape='', ignore_errors=true, null_padding=true) d
        LEFT JOIN demo dm ON CAST(d.ISR AS VARCHAR) = dm.primary_id;
    """)


def load_s1_reac(con: duckdb.DuckDBPyConnection, file_path: Path, release: str):
    """Loads S1 REAC file into canonical reac table."""
    con.execute(f"""
        CREATE OR REPLACE TABLE reac AS
        SELECT
            CAST(r.ISR AS VARCHAR) AS primary_id,
            CAST(dm.case_id AS VARCHAR) AS case_id,
            CAST(r.PT AS VARCHAR) AS reported_reaction_term,
            ROW_NUMBER() OVER (PARTITION BY r.ISR) AS reaction_seq,
            CAST(NULL AS VARCHAR) AS drug_reaction_action,
            'FDA_FAERS_ASCII' AS _source_system,
            '{release}' AS _source_release,
            '{file_path.name}' AS _source_file,
            'S1' AS _source_signature_id,
            CURRENT_TIMESTAMP AS _ingested_at
        FROM read_csv('{file_path.as_posix()}', delim='$', header=True, all_varchar=True, quote='', escape='', ignore_errors=true, null_padding=true) r
        LEFT JOIN demo dm ON CAST(r.ISR AS VARCHAR) = dm.primary_id;
    """)


def load_s1_outc(con: duckdb.DuckDBPyConnection, file_path: Path, release: str):
    """Loads S1 OUTC file into canonical outc table."""
    con.execute(f"""
        CREATE OR REPLACE TABLE outc AS
        SELECT
            CAST(o.ISR AS VARCHAR) AS primary_id,
            CAST(dm.case_id AS VARCHAR) AS case_id,
            CAST(o.OUTC_COD AS VARCHAR) AS outcome_code,
            'FDA_FAERS_ASCII' AS _source_system,
            '{release}' AS _source_release,
            '{file_path.name}' AS _source_file,
            'S1' AS _source_signature_id,
            CURRENT_TIMESTAMP AS _ingested_at
        FROM read_csv('{file_path.as_posix()}', delim='$', header=True, all_varchar=True, quote='', escape='', ignore_errors=true, null_padding=true) o
        LEFT JOIN demo dm ON CAST(o.ISR AS VARCHAR) = dm.primary_id;
    """)


def load_s1_indi(con: duckdb.DuckDBPyConnection, file_path: Path, release: str):
    """Loads S1 INDI file into canonical indi table."""
    con.execute(f"""
        CREATE OR REPLACE TABLE indi AS
        SELECT
            CAST(i.ISR AS VARCHAR) AS primary_id,
            CAST(dm.case_id AS VARCHAR) AS case_id,
            COALESCE(TRY_CAST(i.DRUG_SEQ AS INTEGER), 1) AS indication_drug_seq,
            CAST(i.INDI_PT AS VARCHAR) AS reported_indication_term,
            'FDA_FAERS_ASCII' AS _source_system,
            '{release}' AS _source_release,
            '{file_path.name}' AS _source_file,
            'S1' AS _source_signature_id,
            CURRENT_TIMESTAMP AS _ingested_at
        FROM read_csv('{file_path.as_posix()}', delim='$', header=True, all_varchar=True, quote='', escape='', ignore_errors=true, null_padding=true) i
        LEFT JOIN demo dm ON CAST(i.ISR AS VARCHAR) = dm.primary_id;
    """)


def load_s1_ther(con: duckdb.DuckDBPyConnection, file_path: Path, release: str):
    """Loads S1 THER file into canonical ther table."""
    dur_sql = get_standard_duration_days_sql("t.DUR", "t.DUR_COD")
    con.execute(f"""
        CREATE OR REPLACE TABLE ther AS
        SELECT
            CAST(t.ISR AS VARCHAR) AS primary_id,
            CAST(dm.case_id AS VARCHAR) AS case_id,
            COALESCE(TRY_CAST(t.DRUG_SEQ AS INTEGER), 1) AS therapy_drug_seq,
            CAST(t.START_DT AS VARCHAR) AS start_date,
            CAST(t.END_DT AS VARCHAR) AS end_date,
            TRY_CAST(t.DUR AS DOUBLE) AS reported_duration,
            CAST(t.DUR_COD AS VARCHAR) AS reported_duration_code,
            {dur_sql} AS standard_duration_days,
            'FDA_FAERS_ASCII' AS _source_system,
            '{release}' AS _source_release,
            '{file_path.name}' AS _source_file,
            'S1' AS _source_signature_id,
            CURRENT_TIMESTAMP AS _ingested_at
        FROM read_csv('{file_path.as_posix()}', delim='$', header=True, all_varchar=True, quote='', escape='', ignore_errors=true, null_padding=true) t
        LEFT JOIN demo dm ON CAST(t.ISR AS VARCHAR) = dm.primary_id;
    """)


def load_s1_rpsr(con: duckdb.DuckDBPyConnection, file_path: Path, release: str):
    """Loads S1 RPSR file into canonical rpsr table."""
    con.execute(f"""
        CREATE OR REPLACE TABLE rpsr AS
        SELECT
            CAST(r.ISR AS VARCHAR) AS primary_id,
            CAST(dm.case_id AS VARCHAR) AS case_id,
            CAST(r.RPSR_COD AS VARCHAR) AS report_source_code,
            'FDA_FAERS_ASCII' AS _source_system,
            '{release}' AS _source_release,
            '{file_path.name}' AS _source_file,
            'S1' AS _source_signature_id,
            CURRENT_TIMESTAMP AS _ingested_at
        FROM read_csv('{file_path.as_posix()}', delim='$', header=True, all_varchar=True, quote='', escape='', ignore_errors=true, null_padding=true) r
        LEFT JOIN demo dm ON CAST(r.ISR AS VARCHAR) = dm.primary_id;
    """)
