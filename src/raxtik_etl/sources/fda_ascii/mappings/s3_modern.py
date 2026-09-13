"""Signature S3 (Modern FAERS & AEMS: 2014Q3 - 2026Q2+) Canonical Mapping.

Maps raw S3 modern text files to canonical schema:
- DEMO: primaryid, caseid, caseversion, i_f_code, event_dt, mfr_dt, init_fda_dt, fda_dt,
        rept_cod, auth_num, mfr_num, mfr_sndr, lit_ref, age, age_cod, age_grp, sex, e_sub,
        wt, wt_cod, rept_dt, to_mfr, occp_cod, reporter_country, occr_country
- DRUG: primaryid, caseid, drug_seq, role_cod, drugname, prod_ai, val_vbm, route, dose_vbm,
        cum_dose_chr, cum_dose_unit, dechal, rechal, lot_num, exp_dt, nda_num, dose_amt,
        dose_unit, dose_form, dose_freq
- REAC: primaryid, caseid, pt, drug_rec_act
- OUTC: primaryid, caseid, outc_cod
- INDI: primaryid, caseid, indi_drug_seq, indi_pt
- THER: primaryid, caseid, dsg_drug_seq, start_dt, end_dt, dur, dur_cod
- RPSR: primaryid, caseid, rpsr_cod

Critical S3 Normalization Rules:
1. Centralized age/weight normalization using normalization.py (converting MON/WK/DY/HR and LBS/GMS)
2. No premature drug normalization: standard_concept_name = NULL, derivation_status = 'NOT_ATTEMPTED'
3. Preserves raw reported codes without hard-coding labels (labels resolved in _code_* dimensions)
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


def load_s3_demo(con: duckdb.DuckDBPyConnection, file_path: Path, release: str):
    """Loads S3 DEMO file into canonical demo table."""
    age_sql = get_standard_age_sql("age", "age_cod")
    wt_sql = get_standard_weight_sql("wt", "wt_cod")
    sex_label_sql = get_standard_sex_label_sql("sex")

    con.execute(f"""
        CREATE OR REPLACE TABLE demo AS
        SELECT
            CAST(primaryid AS VARCHAR) AS primary_id,
            CAST(caseid AS VARCHAR) AS case_id,
            TRY_CAST(caseversion AS INTEGER) AS fda_case_version,
            COALESCE(TRY_CAST(caseversion AS INTEGER), 1) AS canonical_case_version,
            'FDA_REPORTED' AS case_version_source,
            CAST(NULL AS VARCHAR) AS foll_seq,
            CAST(i_f_code AS VARCHAR) AS initial_or_followup_code,
            CAST(event_dt AS VARCHAR) AS event_date,
            CAST(mfr_dt AS VARCHAR) AS manufacturer_date,
            CAST(init_fda_dt AS VARCHAR) AS initial_fda_date,
            CAST(fda_dt AS VARCHAR) AS fda_date,
            CAST(rept_dt AS VARCHAR) AS report_date,
            CAST(rept_cod AS VARCHAR) AS report_code,
            CAST(e_sub AS VARCHAR) AS electronic_submission_flag,
            CAST(mfr_num AS VARCHAR) AS manufacturer_num,
            CAST(mfr_sndr AS VARCHAR) AS manufacturer_sender,
            CAST(auth_num AS VARCHAR) AS auth_num,
            CAST(lit_ref AS VARCHAR) AS lit_ref,
            CAST(to_mfr AS VARCHAR) AS to_mfr,
            TRY_CAST(age AS DOUBLE) AS reported_age,
            CAST(age_cod AS VARCHAR) AS reported_age_code,
            CAST(age_grp AS VARCHAR) AS reported_age_group_code,
            CAST(sex AS VARCHAR) AS reported_sex_code,
            TRY_CAST(wt AS DOUBLE) AS reported_weight,
            CAST(wt_cod AS VARCHAR) AS reported_weight_code,
            CAST(occp_cod AS VARCHAR) AS reporter_occupation_code,
            CAST(reporter_country AS VARCHAR) AS reporter_country,
            CAST(occr_country AS VARCHAR) AS occurrence_country,
            {age_sql} AS standard_age_years,
            {sex_label_sql} AS standard_sex_label,
            {wt_sql} AS standard_weight_kg,
            'FDA_FAERS_ASCII' AS _source_system,
            '{release}' AS _source_release,
            '{file_path.name}' AS _source_file,
            'S3' AS _source_signature_id,
            CURRENT_TIMESTAMP AS _ingested_at
        FROM read_csv('{file_path.as_posix()}', delim='$', header=True, all_varchar=True, quote='', escape='', ignore_errors=true, null_padding=true);
    """)


def load_s3_drug(con: duckdb.DuckDBPyConnection, file_path: Path, release: str):
    """Loads S3 DRUG file into canonical drug table."""
    con.execute(f"""
        CREATE OR REPLACE TABLE drug AS
        SELECT
            CAST(primaryid AS VARCHAR) AS primary_id,
            CAST(caseid AS VARCHAR) AS case_id,
            COALESCE(TRY_CAST(drug_seq AS INTEGER), 1) AS drug_seq,
            CAST(drugname AS VARCHAR) AS reported_drug_name,
            CAST(prod_ai AS VARCHAR) AS reported_active_ingredient,
            CAST(val_vbm AS VARCHAR) AS reported_validation_code,
            CAST(role_cod AS VARCHAR) AS role_code,
            CAST(route AS VARCHAR) AS route,
            CAST(dose_vbm AS VARCHAR) AS reported_dose_verbatim,
            TRY_CAST(dose_amt AS DOUBLE) AS dose_amount,
            CAST(dose_unit AS VARCHAR) AS dose_unit,
            CAST(dose_form AS VARCHAR) AS dose_form,
            CAST(dose_freq AS VARCHAR) AS dose_frequency,
            TRY_CAST(cum_dose_chr AS DOUBLE) AS cumulative_dose_amount,
            CAST(cum_dose_unit AS VARCHAR) AS cumulative_dose_unit,
            CAST(dechal AS VARCHAR) AS dechallenge_code,
            CAST(rechal AS VARCHAR) AS rechallenge_code,
            CAST(lot_num AS VARCHAR) AS lot_number,
            CAST(exp_dt AS VARCHAR) AS expiration_date,
            CAST(nda_num AS VARCHAR) AS nda_num,
            TRIM(UPPER(CAST(drugname AS VARCHAR))) AS structural_clean_drug_name,
            CAST(NULL AS VARCHAR) AS standard_concept_name,
            CAST(NULL AS VARCHAR) AS standard_concept_source,
            CAST(NULL AS VARCHAR) AS rxcui,
            'NOT_ATTEMPTED' AS derivation_status,
            'FDA_FAERS_ASCII' AS _source_system,
            '{release}' AS _source_release,
            '{file_path.name}' AS _source_file,
            'S3' AS _source_signature_id,
            CURRENT_TIMESTAMP AS _ingested_at
        FROM read_csv('{file_path.as_posix()}', delim='$', header=True, all_varchar=True, quote='', escape='', ignore_errors=true, null_padding=true);
    """)


def load_s3_reac(con: duckdb.DuckDBPyConnection, file_path: Path, release: str):
    """Loads S3 REAC file into canonical reac table."""
    con.execute(f"""
        CREATE OR REPLACE TABLE reac AS
        SELECT
            CAST(primaryid AS VARCHAR) AS primary_id,
            CAST(caseid AS VARCHAR) AS case_id,
            CAST(pt AS VARCHAR) AS reported_reaction_term,
            ROW_NUMBER() OVER (PARTITION BY primaryid) AS reaction_seq,
            CAST(drug_rec_act AS VARCHAR) AS drug_reaction_action,
            'FDA_FAERS_ASCII' AS _source_system,
            '{release}' AS _source_release,
            '{file_path.name}' AS _source_file,
            'S3' AS _source_signature_id,
            CURRENT_TIMESTAMP AS _ingested_at
        FROM read_csv('{file_path.as_posix()}', delim='$', header=True, all_varchar=True, quote='', escape='', ignore_errors=true, null_padding=true);
    """)


def load_s3_outc(con: duckdb.DuckDBPyConnection, file_path: Path, release: str):
    """Loads S3 OUTC file into canonical outc table."""
    con.execute(f"""
        CREATE OR REPLACE TABLE outc AS
        SELECT
            CAST(primaryid AS VARCHAR) AS primary_id,
            CAST(caseid AS VARCHAR) AS case_id,
            CAST(outc_cod AS VARCHAR) AS outcome_code,
            'FDA_FAERS_ASCII' AS _source_system,
            '{release}' AS _source_release,
            '{file_path.name}' AS _source_file,
            'S3' AS _source_signature_id,
            CURRENT_TIMESTAMP AS _ingested_at
        FROM read_csv('{file_path.as_posix()}', delim='$', header=True, all_varchar=True, quote='', escape='', ignore_errors=true, null_padding=true);
    """)


def load_s3_indi(con: duckdb.DuckDBPyConnection, file_path: Path, release: str):
    """Loads S3 INDI file into canonical indi table."""
    con.execute(f"""
        CREATE OR REPLACE TABLE indi AS
        SELECT
            CAST(primaryid AS VARCHAR) AS primary_id,
            CAST(caseid AS VARCHAR) AS case_id,
            COALESCE(TRY_CAST(indi_drug_seq AS INTEGER), 1) AS indication_drug_seq,
            CAST(indi_pt AS VARCHAR) AS reported_indication_term,
            'FDA_FAERS_ASCII' AS _source_system,
            '{release}' AS _source_release,
            '{file_path.name}' AS _source_file,
            'S3' AS _source_signature_id,
            CURRENT_TIMESTAMP AS _ingested_at
        FROM read_csv('{file_path.as_posix()}', delim='$', header=True, all_varchar=True, quote='', escape='', ignore_errors=true, null_padding=true);
    """)


def load_s3_ther(con: duckdb.DuckDBPyConnection, file_path: Path, release: str):
    """Loads S3 THER file into canonical ther table."""
    dur_sql = get_standard_duration_days_sql("dur", "dur_cod")
    con.execute(f"""
        CREATE OR REPLACE TABLE ther AS
        SELECT
            CAST(primaryid AS VARCHAR) AS primary_id,
            CAST(caseid AS VARCHAR) AS case_id,
            COALESCE(TRY_CAST(dsg_drug_seq AS INTEGER), 1) AS therapy_drug_seq,
            CAST(start_dt AS VARCHAR) AS start_date,
            CAST(end_dt AS VARCHAR) AS end_date,
            TRY_CAST(dur AS DOUBLE) AS reported_duration,
            CAST(dur_cod AS VARCHAR) AS reported_duration_code,
            {dur_sql} AS standard_duration_days,
            'FDA_FAERS_ASCII' AS _source_system,
            '{release}' AS _source_release,
            '{file_path.name}' AS _source_file,
            'S3' AS _source_signature_id,
            CURRENT_TIMESTAMP AS _ingested_at
        FROM read_csv('{file_path.as_posix()}', delim='$', header=True, all_varchar=True, quote='', escape='', ignore_errors=true, null_padding=true);
    """)


def load_s3_rpsr(con: duckdb.DuckDBPyConnection, file_path: Path, release: str):
    """Loads S3 RPSR file into canonical rpsr table."""
    con.execute(f"""
        CREATE OR REPLACE TABLE rpsr AS
        SELECT
            CAST(primaryid AS VARCHAR) AS primary_id,
            CAST(caseid AS VARCHAR) AS case_id,
            CAST(rpsr_cod AS VARCHAR) AS report_source_code,
            'FDA_FAERS_ASCII' AS _source_system,
            '{release}' AS _source_release,
            '{file_path.name}' AS _source_file,
            'S3' AS _source_signature_id,
            CURRENT_TIMESTAMP AS _ingested_at
        FROM read_csv('{file_path.as_posix()}', delim='$', header=True, all_varchar=True, quote='', escape='', ignore_errors=true, null_padding=true);
    """)
