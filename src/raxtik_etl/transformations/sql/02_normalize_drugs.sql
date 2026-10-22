-- 02_normalize_drugs.sql: Standardize drug names and primary suspect classifications

CREATE OR REPLACE TABLE dedup_drug AS
SELECT
    d.primaryid,
    COALESCE(d.caseid, m.caseid) AS caseid,
    d.drug_seq,
    UPPER(TRIM(COALESCE(d.role_cod, 'C'))) AS role_cod,
    CASE WHEN UPPER(TRIM(COALESCE(d.role_cod, ''))) = 'PS' THEN TRUE ELSE FALSE END AS is_primary_suspect,
    UPPER(TRIM(d.drugname)) AS drug_name,
    UPPER(TRIM(COALESCE(d.prod_ai, d.drugname))) AS active_ingredient,
    UPPER(TRIM(COALESCE(d.route, 'UNKNOWN'))) AS route,
    d.dose_vbm,
    d.dose_amt,
    d.dose_unit,
    d.dose_form,
    d.dose_freq
FROM drug d
JOIN dedup_demo m ON d.primaryid = m.primaryid
WHERE d.drugname IS NOT NULL AND TRIM(d.drugname) != '';
