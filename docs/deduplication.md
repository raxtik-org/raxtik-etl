# Cross-Quarter Case Deduplication Engine

In pharmacovigilance, patients and clinical reports evolve over time. An adverse event initially reported in 2004 may receive follow-up reports (`I_F_COD = 'F'`) months or years later as additional clinical findings or outcomes are documented.

---

## 1. Deduplication Principles

1. **Immutable Physical Submissions**:
   Every raw submission report is preserved in the physical fact tables (`demo`, `drug`, `reac`, etc.) with its source release metadata intact.
2. **Deterministic Latest Case Resolution**:
   The authoritative demographic and administrative state for each case is computed via deterministic hierarchy:
   ```sql
   ROW_NUMBER() OVER (
       PARTITION BY case_id
       ORDER BY
           canonical_case_version DESC,
           TRY_CAST(fda_date AS BIGINT) DESC NULLS LAST,
           TRY_CAST(manufacturer_date AS BIGINT) DESC NULLS LAST,
           TRY_CAST(primary_id AS BIGINT) DESC
   ) AS _rnk
   ```
3. **Longitudinal Case Lineage (`case_lineage`)**:
   Tracks each unique case over time:
   - `first_release` vs `latest_release`
   - `first_fda_date` vs `latest_fda_date`
   - `total_submissions_count`
   - `quarters_count`
   - `is_cross_quarter_case` (boolean flag for cases updated across quarter boundaries)
   - `initial_primary_id` vs `latest_primary_id`

---

## 2. 2004–2006 Empirical Cohort Benchmark

When running across 12 consecutive quarters (2004Q1 to 2006Q4):

```text
Total Raw Submissions:                  921,478
Authoritative Deduplicated Cases:       694,232
Duplicate / Follow-Up Reports Resolved: 227,246 (24.66%)
Cases Spanning Multiple Quarters:        88,443
Cases with Multiple Submissions:        153,829
Total Drug Records:                   3,446,641
Total Reaction Records:               3,835,804
Total Outcome Records:                  925,126
```
