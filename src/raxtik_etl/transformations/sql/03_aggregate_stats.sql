-- 03_aggregate_stats.sql: Generate statistical seed tables for adverse event simulation

-- 1. Deduplicate Adverse Reactions (REAC)
CREATE OR REPLACE TABLE dedup_reac AS
SELECT DISTINCT
    r.primaryid,
    COALESCE(r.caseid, m.caseid) AS caseid,
    UPPER(TRIM(r.pt)) AS reaction_pt
FROM reac r
JOIN dedup_demo m ON r.primaryid = m.primaryid
WHERE r.pt IS NOT NULL AND TRIM(r.pt) != '';

-- 2. Deduplicate Indications (INDI)
CREATE OR REPLACE TABLE dedup_indi AS
SELECT DISTINCT
    i.primaryid,
    COALESCE(i.caseid, m.caseid) AS caseid,
    i.indi_drug_seq,
    UPPER(TRIM(i.indi_pt)) AS indication_pt
FROM indi i
JOIN dedup_demo m ON i.primaryid = m.primaryid
WHERE i.indi_pt IS NOT NULL AND TRIM(i.indi_pt) != '';

-- 3. Deduplicate Outcomes (OUTC)
CREATE OR REPLACE TABLE dedup_outc AS
SELECT DISTINCT
    o.primaryid,
    COALESCE(o.caseid, m.caseid) AS caseid,
    UPPER(TRIM(o.outc_cod)) AS outc_cod
FROM outc o
JOIN dedup_demo m ON o.primaryid = m.primaryid
WHERE o.outc_cod IS NOT NULL AND TRIM(o.outc_cod) != '';

-- 4. Drug-Reaction Co-occurrence & PRR Calculation
CREATE OR REPLACE TABLE drug_reaction_stats AS
WITH total_metrics AS (
    SELECT COUNT(DISTINCT primaryid) AS total_cases FROM dedup_demo
),
drug_totals AS (
    SELECT 
        drug_name,
        COUNT(DISTINCT primaryid) AS drug_total_cases
    FROM dedup_drug
    GROUP BY drug_name
),
reac_totals AS (
    SELECT 
        reaction_pt,
        COUNT(DISTINCT primaryid) AS reac_total_cases
    FROM dedup_reac
    GROUP BY reaction_pt
),
co_occurrences AS (
    SELECT 
        d.drug_name,
        r.reaction_pt,
        COUNT(DISTINCT d.primaryid) AS a_count
    FROM dedup_drug d
    JOIN dedup_reac r ON d.primaryid = r.primaryid
    GROUP BY d.drug_name, r.reaction_pt
)
SELECT 
    c.drug_name,
    c.reaction_pt,
    c.a_count AS co_occurrence_count,
    dt.drug_total_cases,
    rt.reac_total_cases,
    tm.total_cases,
    -- Co-occurrence relative frequency within drug cases
    ROUND((c.a_count * 1.0) / NULLIF(dt.drug_total_cases, 0), 4) AS frequency,
    -- Proportional Reporting Ratio (PRR)
    -- a = c.a_count
    -- b = dt.drug_total_cases - c.a_count
    -- c = rt.reac_total_cases - c.a_count
    -- d = (tm.total_cases - dt.drug_total_cases) - (rt.reac_total_cases - c.a_count)
    CASE 
        WHEN (tm.total_cases - dt.drug_total_cases) > 0 AND (rt.reac_total_cases - c.a_count) > 0 THEN
            ROUND(
                ((c.a_count * 1.0) / NULLIF(dt.drug_total_cases, 0)) /
                (((rt.reac_total_cases - c.a_count) * 1.0) / NULLIF(tm.total_cases - dt.drug_total_cases, 0)),
                4
            )
        ELSE 1.0
    END AS prr
FROM co_occurrences c
JOIN drug_totals dt ON c.drug_name = dt.drug_name
JOIN reac_totals rt ON c.reaction_pt = rt.reaction_pt
CROSS JOIN total_metrics tm
ORDER BY c.drug_name, c.a_count DESC;

-- 5. Drug Demographics Distribution
CREATE OR REPLACE TABLE drug_demographics AS
SELECT 
    d.drug_name,
    COUNT(DISTINCT d.primaryid) AS total_cases,
    ROUND(AVG(m.age_years), 2) AS mean_age,
    ROUND(COALESCE(STDDEV_SAMP(m.age_years), 0.0), 2) AS std_age,
    ROUND(MIN(m.age_years), 1) AS min_age,
    ROUND(MAX(m.age_years), 1) AS max_age,
    ROUND(COUNT(CASE WHEN m.sex = 'M' THEN 1 END) * 1.0 / NULLIF(COUNT(DISTINCT d.primaryid), 0), 4) AS pct_male,
    ROUND(COUNT(CASE WHEN m.sex = 'F' THEN 1 END) * 1.0 / NULLIF(COUNT(DISTINCT d.primaryid), 0), 4) AS pct_female,
    ROUND(COUNT(CASE WHEN m.sex NOT IN ('M', 'F') THEN 1 END) * 1.0 / NULLIF(COUNT(DISTINCT d.primaryid), 0), 4) AS pct_unknown_sex
FROM dedup_drug d
JOIN dedup_demo m ON d.primaryid = m.primaryid
GROUP BY d.drug_name
ORDER BY total_cases DESC;

-- 6. Drug Indications Distribution
CREATE OR REPLACE TABLE drug_indications AS
WITH drug_case_counts AS (
    SELECT drug_name, COUNT(DISTINCT primaryid) AS total_cases FROM dedup_drug GROUP BY drug_name
)
SELECT 
    d.drug_name,
    i.indication_pt,
    COUNT(DISTINCT d.primaryid) AS indication_count,
    ROUND(COUNT(DISTINCT d.primaryid) * 1.0 / NULLIF(dcc.total_cases, 0), 4) AS indication_pct
FROM dedup_drug d
JOIN dedup_indi i ON d.primaryid = i.primaryid
JOIN drug_case_counts dcc ON d.drug_name = dcc.drug_name
GROUP BY d.drug_name, i.indication_pt, dcc.total_cases
ORDER BY d.drug_name, indication_count DESC;

-- 7. Drug Administration Routes
CREATE OR REPLACE TABLE drug_routes AS
WITH drug_case_counts AS (
    SELECT drug_name, COUNT(DISTINCT primaryid) AS total_cases FROM dedup_drug GROUP BY drug_name
)
SELECT 
    d.drug_name,
    d.route,
    COUNT(DISTINCT d.primaryid) AS route_count,
    ROUND(COUNT(DISTINCT d.primaryid) * 1.0 / NULLIF(dcc.total_cases, 0), 4) AS route_pct
FROM dedup_drug d
JOIN drug_case_counts dcc ON d.drug_name = dcc.drug_name
WHERE d.route != 'UNKNOWN'
GROUP BY d.drug_name, d.route, dcc.total_cases
ORDER BY d.drug_name, route_count DESC;

-- 8. Drug Serious Outcomes Distribution
CREATE OR REPLACE TABLE drug_outcomes AS
SELECT 
    d.drug_name,
    COUNT(DISTINCT d.primaryid) AS total_cases,
    COUNT(DISTINCT CASE WHEN o.outc_cod = 'DE' THEN d.primaryid END) AS death_count,
    COUNT(DISTINCT CASE WHEN o.outc_cod = 'HO' THEN d.primaryid END) AS hosp_count,
    COUNT(DISTINCT CASE WHEN o.outc_cod = 'LT' THEN d.primaryid END) AS life_threat_count,
    COUNT(DISTINCT CASE WHEN o.outc_cod = 'DS' THEN d.primaryid END) AS disability_count,
    COUNT(DISTINCT CASE WHEN o.outc_cod = 'CA' THEN d.primaryid END) AS congen_anomaly_count,
    COUNT(DISTINCT CASE WHEN o.outc_cod = 'RI' THEN d.primaryid END) AS req_intervention_count,
    COUNT(DISTINCT CASE WHEN o.outc_cod = 'OT' THEN d.primaryid END) AS other_serious_count,
    ROUND(COUNT(DISTINCT o.primaryid) * 1.0 / NULLIF(COUNT(DISTINCT d.primaryid), 0), 4) AS serious_outcome_pct
FROM dedup_drug d
LEFT JOIN dedup_outc o ON d.primaryid = o.primaryid
GROUP BY d.drug_name
ORDER BY total_cases DESC;
