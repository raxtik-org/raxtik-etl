# Cross-Quarter Case Deduplication & Silver Index

In pharmacovigilance, safety reports evolve over time. An adverse event initially reported in one quarter may receive follow-up reports (`I_F_COD = 'F'`) months or years later as additional clinical findings or outcomes are documented.

---

## 1. Silver Tier Architecture (Derived Index)

Rather than rewriting and duplicating multi-gigabyte Bronze packages every quarter, `raxtik-etl` maintains a **derived Silver deduplication index** (`silver/index/`) alongside immutable Bronze packages:

- **Append-Only Ledgers (`ledger/`)**: Compact ZSTD Parquet extracts per quarter (`YYYYQX.parquet`), automatically compacted into annual ledgers (`YYYY.parquet`) once all 4 quarters complete.
- **Immutable Sharded Base Snapshots (`state/base/<snapshot_id>/`)**: 16 deterministic `md5_u32` Parquet shards storing each case's authoritative winning submission and full version timeline.
- **Immutable Complete-State Deltas (`state/deltas/`)**: Quarterly `index update` runs write a single delta file containing the complete resolved state for affected cases (zero base shard rewrites), automatically compacting once 4 deltas accumulate.
- **Mutable Active Pointer (`manifest.json`)**: Published snapshots and deltas are **immutable**; `manifest.json` is the **mutable publication pointer** referencing the active snapshot, generation, SHA-256 period fingerprints, and optimistic concurrency lineage.

---

## 2. Deterministic Resolution Policy

1. **Immutable Physical Submissions**: Every raw submission is preserved in Bronze fact tables (`demo`, `drug`, `reac`, `outc`, `indi`, `ther`, `rpsr`).
2. **Missing `CASEID` Preservation**: Submissions with `NULL` or blank `case_id` receive a deterministic `REPORT:<primary_id>` fallback key so no reports are silently dropped or merged.
3. **Total-Order Winning Submission Ranking**:
   ```sql
   ROW_NUMBER() OVER (
       PARTITION BY case_id
       ORDER BY
           COALESCE(canonical_case_version, 0) DESC,
           TRY_CAST(latest_regulatory_date AS BIGINT) DESC NULLS LAST,
           TRY_CAST(manufacturer_date AS BIGINT) DESC NULLS LAST,
           TRY_CAST(primary_id AS BIGINT) DESC NULLS LAST,
           primary_id DESC,
           data_period DESC
   ) = 1
   ```
   - `data_period DESC` guarantees deterministic ordering even when FDA republishes the exact same `primary_id` across quarterly archives.
   - `resolution_tie` flags cases where the top two submissions tied on version and regulatory/manufacturer dates before `primary_id` tie-breaking.
   - `is_cross_quarter` is computed as `MIN(data_period) <> MAX(data_period)`.
4. **Point-in-Time Resolution (`as_of_period`)**: Because every resolved row retains its full submission `timeline`, Silver queries can reconstruct exact historical case winners as of any quarter cutoff (e.g., `as_of_period="2020Q4"`).

---

## 3. Verified 91-Quarter Empirical Audit (`2004Q1` – `2026Q3`)

Independently audited across all **91 consecutive FDA AERS + FAERS quarters** (22.75 years) against `silver/index/` (`snap_2026Q3`):

| Metric | Verified Value | Notes |
|---|---:|---|
| **Indexed Quarters** | **91** | `2004Q1` through `2026Q3` |
| **Total Ledger Submissions** | **25,233,828** | `25,228,427` distinct `primary_id`s (`5,401` republished `primary_id` rows) |
| **Unique Resolved Cases (Silver)** | **21,054,158** | `100%` real FDA `CASEID`s (`0` `REPORT:` fallback entities) |
| **Additional / Follow-up Submissions Resolved** | **4,179,670** | **16.56%** of all submissions |
| **Multi-Period Cases (`MIN != MAX` quarter)** | **2,644,931** | **2,643,292** distinct-report follow-ups + **1,639** republished-only cases |
| **Audited Resolution Ties** | **17,469** | Deterministically resolved via `primary_id DESC, data_period DESC` |
| **Total Silver Index Size** | **441 MiB** | `127 MiB` ledgers + `315 MiB` across 16 shards (`<0.28%` shard spread) |

### Integrity Invariants Verified
- **Orphan state rows (`state ANTI JOIN ledger`)**: `0`
- **Missing state entities (`ledger ANTI JOIN state`)**: `0`
- **Independent reference winner check (`QUALIFY ROW_NUMBER()` vs. state shards)**: **`0` mismatches across all 21,054,158 cases**
- **Shard-by-shard `index verify` (`EXCEPT ALL` vs. full ledger rebuild)**: **PASSED**
