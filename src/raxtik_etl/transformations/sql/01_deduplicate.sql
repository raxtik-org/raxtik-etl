-- 01_deduplicate.sql: Deduplicate DEMO records by latest caseversion/fda_dt per caseid

CREATE OR REPLACE TABLE dedup_demo AS
WITH ranked AS (
    SELECT 
        primaryid,
        caseid,
        caseversion,
        i_f_cod,
        event_dt,
        mfr_dt,
        init_fda_dt,
        fda_dt,
        TRY_CAST(age AS DOUBLE) AS raw_age,
        UPPER(TRIM(COALESCE(age_cod, 'YR'))) AS age_cod,
        age_grp,
        UPPER(TRIM(COALESCE(sex, 'UNK'))) AS raw_sex,
        e_sub,
        TRY_CAST(wt AS DOUBLE) AS wt_val,
        wt_cod,
        rept_dt,
        occp_cod,
        reporter_country,
        occr_country,
        ROW_NUMBER() OVER (
            PARTITION BY COALESCE(caseid, primaryid)
            ORDER BY 
                TRY_CAST(caseversion AS INTEGER) DESC NULLS LAST,
                TRY_CAST(fda_dt AS BIGINT) DESC NULLS LAST,
                primaryid DESC
        ) AS rnk
    FROM demo
)
SELECT 
    primaryid,
    COALESCE(caseid, primaryid) AS caseid,
    caseversion,
    CASE 
        WHEN age_cod IN ('YR', 'YEAR', 'YEARS') THEN raw_age
        WHEN age_cod IN ('MON', 'MONTH', 'MONTHS') THEN raw_age / 12.0
        WHEN age_cod IN ('WK', 'WEEK', 'WEEKS') THEN raw_age / 52.0
        WHEN age_cod IN ('DY', 'DAY', 'DAYS') THEN raw_age / 365.25
        WHEN age_cod IN ('HR', 'HOUR', 'HOURS') THEN raw_age / 8766.0
        WHEN age_cod IN ('DEC', 'DECADE', 'DECADES') THEN raw_age * 10.0
        ELSE raw_age
    END AS age_years,
    CASE 
        WHEN raw_sex IN ('M', 'MALE', '1') THEN 'M'
        WHEN raw_sex IN ('F', 'FEMALE', '2') THEN 'F'
        ELSE 'UNK'
    END AS sex,
    COALESCE(reporter_country, occr_country, 'UNKNOWN') AS country,
    fda_dt
FROM ranked
WHERE rnk = 1;
