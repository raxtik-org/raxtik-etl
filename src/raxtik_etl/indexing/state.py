"""Hybrid Base + Immutable Delta Segment State Index & Incremental Resolution Engine.

Implements Option C (Iceberg-inspired Base Snapshots + LSM-inspired Delta Segments):
    <index_root>/state/base/<snapshot_id>/shard_00..NN.parquet
    <index_root>/state/deltas/delta_<snapshot_id>.parquet

Core invariants:
1. Existing published files are NEVER overwritten in place (strict immutability).
2. Complete-state-per-case_id delta invariant: every row in a delta segment holds
   the COMPLETE resolved state (including full `timeline` and `resolution_tie`)
   for that changed/new `case_id`, so latest-delta-wins is 100% lossless.
3. Idempotent reprocessing: re-ingesting an already-indexed period with the same
   source fingerprint is a no-op (no duplicate delta, no generation bump).
4. Compaction equivalence: compacting `base + deltas` into a new immutable base
   snapshot produces the exact same canonical logical state as querying un-compacted.
5. Cross-runtime deterministic partitioning via `md5_u32` (UTF-8).
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import duckdb

from raxtik_etl.indexing.ledger import LedgerManager
from raxtik_etl.indexing.models import (
    IndexManifest,
    ResolutionPolicy,
    SnapshotRecord,
    utc_now_iso,
)
from raxtik_etl.sources.temporal import normalize_quarter


def compute_shard_id(entity_id: str, shard_count: int) -> int:
    """Computes deterministic shard index using `md5_u32` (UTF-8).

    Matches the DuckDB SQL expression:
        `(('0x' || substr(md5(case_id), 1, 8))::UBIGINT % shard_count)::INTEGER`
    """
    digest = hashlib.md5(entity_id.encode("utf-8"), usedforsecurity=False).hexdigest()
    return int(digest[:8], 16) % shard_count


def compute_source_fingerprint(source_path: Path | str) -> str:
    """Computes a deterministic SHA-256 fingerprint for a Bronze file or directory."""
    src = Path(source_path)
    h = hashlib.sha256()
    if src.is_dir():
        for child in sorted(p for p in src.rglob("*") if p.is_file()):
            h.update(child.relative_to(src).as_posix().encode("utf-8"))
            with child.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
    else:
        with src.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
    return h.hexdigest()


def _shard_sql_expr(column: str, shard_count: int) -> str:
    return f"(('0x' || substr(md5({column}), 1, 8))::UBIGINT % {shard_count})::INTEGER"


def _order_by_sql(policy: ResolutionPolicy) -> str:
    terms = [
        "canonical_case_version DESC NULLS LAST",
        "latest_regulatory_date DESC NULLS LAST",
        "manufacturer_date DESC NULLS LAST",
    ]
    if policy.numeric_record_key_tiebreaker:
        terms.append("TRY_CAST(primary_id AS BIGINT) DESC NULLS LAST")
    terms.append("primary_id DESC")
    return ", ".join(terms)


def _resolution_tie_sql() -> str:
    """TRUE iff top 2 candidates tied on all substantive ranking fields (version, fda_date, mfr_date)."""
    return (
        "(len(timeline) >= 2 "
        "AND timeline[1].version IS NOT DISTINCT FROM timeline[2].version "
        "AND timeline[1].fda_date IS NOT DISTINCT FROM timeline[2].fda_date "
        "AND timeline[1].mfr_date IS NOT DISTINCT FROM timeline[2].mfr_date)"
    )


def _shard_filename(shard_idx: int, shard_count: int) -> str:
    width = max(2, len(str(shard_count - 1)))
    return f"shard_{shard_idx:0{width}d}.parquet"


def build_resolved_state_sql(
    base_shard_uris: Sequence[str],
    delta_uris: Sequence[str] = (),
) -> str:
    """Returns a SQL SELECT resolving `base_shards + ordered deltas` (latest delta wins per case_id).

    Relies on the complete-state-per-case_id delta invariant.
    """
    if not base_shard_uris:
        raise ValueError("base_shard_uris cannot be empty.")
    base_sql = ", ".join(f"'{u}'" for u in base_shard_uris)
    if not delta_uris:
        return f"SELECT * FROM read_parquet([{base_sql}])"

    layers = [f"SELECT *, 0 AS _delta_seq FROM read_parquet([{base_sql}])"]
    for seq, d_uri in enumerate(delta_uris, start=1):
        layers.append(f"SELECT *, {seq} AS _delta_seq FROM read_parquet('{d_uri}')")
    union_sql = "\nUNION ALL\n".join(layers)
    return (
        f"WITH _stacked_state AS (\n{union_sql}\n)\n"
        "SELECT * EXCLUDE (_delta_seq)\n"
        "FROM _stacked_state\n"
        "QUALIFY ROW_NUMBER() OVER (PARTITION BY case_id ORDER BY _delta_seq DESC) = 1"
    )


class ShardedStateIndex:
    """Manages immutable base snapshots + complete-state delta segments + periodic compaction."""

    def __init__(
        self,
        index_root: Path | str,
        tier: str = "silver",
        source: str = "faers",
        policy: Optional[ResolutionPolicy] = None,
    ) -> None:
        self.index_root = Path(index_root)
        self.tier = tier.lower().strip()
        self.source = source.lower().strip()
        self.policy = policy or ResolutionPolicy()
        self.base_root = self.index_root / "state" / "base"
        self.deltas_root = self.index_root / "state" / "deltas"
        self.snapshots_dir = self.index_root / "snapshots"
        self.manifest_path = self.index_root / "manifest.json"
        self.ledger = LedgerManager(self.index_root, policy=self.policy)

    def load_manifest(self) -> Optional[IndexManifest]:
        if not self.manifest_path.exists():
            return None
        return IndexManifest.load(self.manifest_path)

    def _next_snapshot_id(self, label: str, existing_history: List[str]) -> str:
        base = f"snap_{label}"
        if (
            base not in existing_history
            and not (self.base_root / base).exists()
            and not (self.deltas_root / f"delta_{base}.parquet").exists()
        ):
            return base
        rev = 2
        while (
            f"{base}_r{rev}" in existing_history
            or (self.base_root / f"{base}_r{rev}").exists()
            or (self.deltas_root / f"delta_{base}_r{rev}.parquet").exists()
        ):
            rev += 1
        return f"{base}_r{rev}"

    def _compute_metrics_from_uris(
        self,
        con: duckdb.DuckDBPyConnection,
        base_uris: Sequence[str],
        delta_uris: Sequence[str],
    ) -> Tuple[int, int, int]:
        state_sql = build_resolved_state_sql(base_uris, delta_uris)
        row = con.execute(
            f"""
            SELECT
                COALESCE(SUM(submissions_count), 0)::BIGINT,
                COUNT(*)::BIGINT,
                COALESCE(SUM(CASE WHEN is_cross_quarter THEN 1 ELSE 0 END), 0)::BIGINT
            FROM ({state_sql})
            """  # nosec B608
        ).fetchone()
        if row is None:
            return (0, 0, 0)
        return (int(row[0]), int(row[1]), int(row[2]))

    def _write_manifest_commit(
        self,
        snapshot_id: str,
        parent_snapshot_id: Optional[str],
        generation: int,
        rel_state_dir: str,
        rel_shards: List[str],
        rel_deltas: List[str],
        indexed_periods: List[str],
        period_fingerprints: Dict[str, str],
        existing_history: List[str],
    ) -> IndexManifest:
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        base_uris = [(self.index_root / rel).as_posix() for rel in rel_shards]
        delta_uris = [(self.index_root / rel).as_posix() for rel in rel_deltas]

        con = duckdb.connect(":memory:")
        try:
            total_subs, total_entities, cross_entities = self._compute_metrics_from_uris(
                con, base_uris, delta_uris
            )
        finally:
            con.close()

        rel_ledgers = [f"ledger/{p.name}" for p in self.ledger.list_ledger_files()]
        now = utc_now_iso()

        snap_record = SnapshotRecord(
            snapshot_id=snapshot_id,
            parent_snapshot_id=parent_snapshot_id,
            generation=generation,
            tier=self.tier,
            source=self.source,
            created_at=now,
            indexed_periods=sorted(set(indexed_periods)),
            state_dir=rel_state_dir,
            shard_count=self.policy.shard_count,
            shard_files=rel_shards,
            active_delta_files=rel_deltas,
            ledger_files=rel_ledgers,
            total_submissions=total_subs,
            total_entities=total_entities,
            cross_period_entities=cross_entities,
            period_fingerprints=dict(period_fingerprints),
            partitioning=self.policy.partitioning_spec(),
            resolution_policy_version=self.policy.policy_version,
        )
        snap_record.save(self.snapshots_dir / f"{snapshot_id}.json")

        history = list(existing_history) + [snapshot_id]
        manifest = IndexManifest(
            tier=self.tier,
            source=self.source,
            active_snapshot_id=snapshot_id,
            generation=generation,
            updated_at=now,
            policy=self.policy,
            active_snapshot=snap_record,
            snapshot_history=history,
        )
        manifest.save(self.manifest_path)
        return manifest

    def build_from_ledgers(
        self,
        snapshot_label: Optional[str] = None,
        period_fingerprints: Optional[Dict[str, str]] = None,
    ) -> IndexManifest:
        """Deterministically builds a fresh immutable base snapshot from all ledger files."""
        ledger_files = self.ledger.list_ledger_files()
        if not ledger_files:
            raise FileNotFoundError(
                f"No ledger Parquet files found in {self.ledger.ledger_dir}. "
                "Extract at least one period ledger first."
            )

        indexed_periods = self.ledger.list_indexed_periods()
        prev_manifest = self.load_manifest()
        existing_history = prev_manifest.snapshot_history if prev_manifest else []
        parent_id = prev_manifest.active_snapshot_id if prev_manifest else None
        generation = (prev_manifest.generation + 1) if prev_manifest else 1
        merged_fingerprints = (
            dict(prev_manifest.active_snapshot.period_fingerprints) if prev_manifest else {}
        )
        if period_fingerprints:
            merged_fingerprints.update(period_fingerprints)

        label = snapshot_label or (indexed_periods[-1] if indexed_periods else "initial")
        snapshot_id = self._next_snapshot_id(label, existing_history)

        self.base_root.mkdir(parents=True, exist_ok=True)
        tmp_snap_dir = self.base_root / f".tmp_{snapshot_id}"
        if tmp_snap_dir.exists():
            shutil.rmtree(tmp_snap_dir)
        tmp_snap_dir.mkdir(parents=True, exist_ok=True)

        files_sql = ", ".join(f"'{p.as_posix()}'" for p in ledger_files)
        order_sql = _order_by_sql(self.policy)
        tie_sql = _resolution_tie_sql()
        shard_expr = _shard_sql_expr("case_id", self.policy.shard_count)
        shard_filenames: List[str] = []

        con = duckdb.connect(":memory:")
        try:
            con.execute(
                f"""
                CREATE TEMP TABLE _all_entries AS
                SELECT
                    case_id,
                    primary_id,
                    data_period,
                    canonical_case_version,
                    latest_regulatory_date,
                    manufacturer_date,
                    {shard_expr} AS _shard_id
                FROM (
                    SELECT DISTINCT
                        case_id,
                        primary_id,
                        data_period,
                        canonical_case_version,
                        latest_regulatory_date,
                        manufacturer_date
                    FROM read_parquet([{files_sql}])
                )
                """  # nosec B608
            )

            for s_idx in range(self.policy.shard_count):
                fname = _shard_filename(s_idx, self.policy.shard_count)
                shard_filenames.append(fname)
                out_file = tmp_snap_dir / fname

                con.execute(
                    f"""
                    COPY (
                        WITH grouped AS (
                            SELECT
                                case_id,
                                MIN(data_period) AS first_quarter,
                                LIST(
                                    STRUCT_PACK(
                                        quarter := data_period,
                                        version := canonical_case_version,
                                        primary_id := primary_id,
                                        fda_date := latest_regulatory_date,
                                        mfr_date := manufacturer_date
                                    )
                                    ORDER BY {order_sql}
                                ) AS timeline
                            FROM _all_entries
                            WHERE _shard_id = {s_idx}
                            GROUP BY case_id
                        )
                        SELECT
                            case_id,
                            timeline[1].primary_id AS latest_primary_id,
                            timeline[1].quarter AS latest_quarter,
                            first_quarter,
                            len(timeline)::INTEGER AS submissions_count,
                            (first_quarter <> timeline[1].quarter) AS is_cross_quarter,
                            {tie_sql} AS resolution_tie,
                            timeline
                        FROM grouped
                        ORDER BY case_id
                    ) TO '{out_file.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD);
                    """  # nosec B608
                )
        except Exception:
            shutil.rmtree(tmp_snap_dir, ignore_errors=True)
            raise
        finally:
            con.close()

        final_snap_dir = self.base_root / snapshot_id
        tmp_snap_dir.replace(final_snap_dir)
        rel_state_dir = f"state/base/{snapshot_id}"
        rel_shards = [f"{rel_state_dir}/{name}" for name in shard_filenames]

        return self._write_manifest_commit(
            snapshot_id=snapshot_id,
            parent_snapshot_id=parent_id,
            generation=generation,
            rel_state_dir=rel_state_dir,
            rel_shards=rel_shards,
            rel_deltas=[],
            indexed_periods=indexed_periods,
            period_fingerprints=merged_fingerprints,
            existing_history=existing_history,
        )

    def compact_state_deltas(self, snapshot_label: Optional[str] = None) -> IndexManifest:
        """Merges the active base snapshot + accumulated delta segments into a fresh immutable base.

        Guaranteed to produce the exact same canonical logical state as the un-compacted
        base + deltas representation.
        """
        prev_manifest = self.load_manifest()
        if prev_manifest is None:
            raise FileNotFoundError(f"No manifest.json found at {self.manifest_path}")

        prev_snap = prev_manifest.active_snapshot
        if not prev_snap.active_delta_files:
            return prev_manifest

        base_uris = [(self.index_root / rel).as_posix() for rel in prev_snap.shard_files]
        delta_uris = [(self.index_root / rel).as_posix() for rel in prev_snap.active_delta_files]
        resolved_sql = build_resolved_state_sql(base_uris, delta_uris)

        label = snapshot_label or f"{prev_snap.indexed_periods[-1]}_compacted"
        snapshot_id = self._next_snapshot_id(label, prev_manifest.snapshot_history)
        generation = prev_manifest.generation + 1

        self.base_root.mkdir(parents=True, exist_ok=True)
        tmp_snap_dir = self.base_root / f".tmp_{snapshot_id}"
        if tmp_snap_dir.exists():
            shutil.rmtree(tmp_snap_dir)
        tmp_snap_dir.mkdir(parents=True, exist_ok=True)

        shard_expr = _shard_sql_expr("case_id", self.policy.shard_count)
        shard_filenames: List[str] = []

        con = duckdb.connect(":memory:")
        try:
            con.execute(
                f"""
                CREATE TEMP TABLE _merged_state AS
                SELECT *, {shard_expr} AS _shard_id
                FROM ({resolved_sql})
                """  # nosec B608
            )
            for s_idx in range(self.policy.shard_count):
                fname = _shard_filename(s_idx, self.policy.shard_count)
                shard_filenames.append(fname)
                out_file = tmp_snap_dir / fname
                con.execute(
                    f"""
                    COPY (
                        SELECT * EXCLUDE (_shard_id)
                        FROM _merged_state
                        WHERE _shard_id = {s_idx}
                        ORDER BY case_id
                    ) TO '{out_file.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD);
                    """  # nosec B608
                )
        except Exception:
            shutil.rmtree(tmp_snap_dir, ignore_errors=True)
            raise
        finally:
            con.close()

        final_snap_dir = self.base_root / snapshot_id
        tmp_snap_dir.replace(final_snap_dir)
        rel_state_dir = f"state/base/{snapshot_id}"
        rel_shards = [f"{rel_state_dir}/{name}" for name in shard_filenames]

        return self._write_manifest_commit(
            snapshot_id=snapshot_id,
            parent_snapshot_id=prev_snap.snapshot_id,
            generation=generation,
            rel_state_dir=rel_state_dir,
            rel_shards=rel_shards,
            rel_deltas=[],
            indexed_periods=prev_snap.indexed_periods,
            period_fingerprints=prev_snap.period_fingerprints,
            existing_history=prev_manifest.snapshot_history,
        )

    def update_with_period(
        self,
        source_path: Path | str,
        data_period: str,
        compact_years: bool = True,
        replace_period: bool = False,
        auto_compact_deltas: bool = True,
    ) -> IndexManifest:
        """Incrementally updates the index with a single incoming period using a delta segment.

        Invariants:
        - Idempotent: if `data_period` is already indexed with the same source fingerprint
          (and `replace_period=False`), returns the existing manifest without writing a new
          delta or incrementing `generation`.
        - Zero base shard rewrites on normal quarterly updates: writes ONE immutable delta
          file (`state/deltas/delta_<snapshot_id>.parquet`) containing the COMPLETE resolved
          state for every changed/new `case_id`.
        - Automatically compacts `base + deltas` into a fresh immutable base once
          `len(active_delta_files) >= policy.delta_compaction_threshold`.
        """
        period = normalize_quarter(data_period)
        fingerprint = compute_source_fingerprint(source_path)
        prev_manifest = self.load_manifest()

        # Idempotence & conflict guard
        if prev_manifest is not None and period in prev_manifest.active_snapshot.indexed_periods:
            existing_fp = prev_manifest.active_snapshot.period_fingerprints.get(period)
            if not replace_period:
                if existing_fp == fingerprint:
                    return prev_manifest
                raise ValueError(
                    f"Period {period} is already indexed with a different source fingerprint "
                    f"(existing={existing_fp}, incoming={fingerprint}). "
                    "Pass replace_period=True to explicitly reprocess this period."
                )

        # 1. Extract incoming period into append-only ledger
        incoming_ledger = self.ledger.extract_period_ledger(
            source_path=source_path,
            data_period=period,
            overwrite=replace_period,
        )

        # Bootstrap cleanly if no base snapshot exists yet
        if prev_manifest is None:
            if compact_years:
                self.ledger.compact_completed_years(remove_quarterly=True)
            return self.build_from_ledgers(
                snapshot_label=period,
                period_fingerprints={period: fingerprint},
            )

        prev_snap = prev_manifest.active_snapshot
        if prev_snap.shard_count != self.policy.shard_count:
            raise ValueError(
                f"Shard count mismatch: existing snapshot has {prev_snap.shard_count} shards, "
                f"policy specifies {self.policy.shard_count}. Run build_from_ledgers() to reshard."
            )

        # Explicit replacement of a historical period cleanly rebuilds a fresh immutable base
        # so removed cases (e.g. retracted records) are never left behind in older base shards.
        if replace_period:
            if compact_years:
                self.ledger.compact_completed_years(remove_quarterly=True)
            updated_fps = dict(prev_snap.period_fingerprints)
            updated_fps[period] = fingerprint
            return self.build_from_ledgers(
                snapshot_label=f"{period}_replaced",
                period_fingerprints=updated_fps,
            )

        # 2. Normal incremental update: write ONE complete-state delta segment (ZERO base rewrites!)
        snapshot_id = self._next_snapshot_id(period, prev_manifest.snapshot_history)
        generation = prev_manifest.generation + 1

        self.deltas_root.mkdir(parents=True, exist_ok=True)
        delta_filename = f"delta_{snapshot_id}.parquet"
        delta_path = self.deltas_root / delta_filename
        tmp_delta = self.deltas_root / f".tmp_{delta_filename}"
        if tmp_delta.exists():
            tmp_delta.unlink()

        base_uris = [(self.index_root / rel).as_posix() for rel in prev_snap.shard_files]
        prior_delta_uris = [
            (self.index_root / rel).as_posix() for rel in prev_snap.active_delta_files
        ]
        current_state_sql = build_resolved_state_sql(base_uris, prior_delta_uris)
        order_sql = _order_by_sql(self.policy)
        tie_sql = _resolution_tie_sql()

        con = duckdb.connect(":memory:")
        try:
            con.execute(
                f"""
                CREATE TEMP TABLE _incoming AS
                SELECT
                    case_id,
                    primary_id,
                    data_period,
                    canonical_case_version,
                    latest_regulatory_date,
                    manufacturer_date
                FROM read_parquet('{incoming_ledger.as_posix()}')
                """  # nosec B608
            )

            # Resolve ONLY touched + brand-new case_ids into a complete-state delta Parquet
            con.execute(
                f"""
                COPY (
                    WITH touched_ids AS (
                        SELECT DISTINCT case_id FROM _incoming
                    ),
                    existing_touched AS (
                        SELECT s.case_id, s.timeline
                        FROM ({current_state_sql}) s
                        INNER JOIN touched_ids t ON s.case_id = t.case_id
                    ),
                    existing_entries AS (
                        SELECT
                            e.case_id,
                            entry.primary_id AS primary_id,
                            entry.quarter AS data_period,
                            entry.version AS canonical_case_version,
                            entry.fda_date AS latest_regulatory_date,
                            entry.mfr_date AS manufacturer_date
                        FROM existing_touched e,
                        UNNEST(e.timeline) AS u(entry)
                    ),
                    combined_entries AS (
                        SELECT DISTINCT
                            case_id,
                            primary_id,
                            data_period,
                            canonical_case_version,
                            latest_regulatory_date,
                            manufacturer_date
                        FROM (
                            SELECT * FROM existing_entries
                            UNION ALL
                            SELECT * FROM _incoming
                        )
                    ),
                    grouped AS (
                        SELECT
                            case_id,
                            MIN(data_period) AS first_quarter,
                            LIST(
                                STRUCT_PACK(
                                    quarter := data_period,
                                    version := canonical_case_version,
                                    primary_id := primary_id,
                                    fda_date := latest_regulatory_date,
                                    mfr_date := manufacturer_date
                                )
                                ORDER BY {order_sql}
                            ) AS timeline
                        FROM combined_entries
                        GROUP BY case_id
                    )
                    SELECT
                        case_id,
                        timeline[1].primary_id AS latest_primary_id,
                        timeline[1].quarter AS latest_quarter,
                        first_quarter,
                        len(timeline)::INTEGER AS submissions_count,
                        (first_quarter <> timeline[1].quarter) AS is_cross_quarter,
                        {tie_sql} AS resolution_tie,
                        timeline
                    FROM grouped
                    ORDER BY case_id
                ) TO '{tmp_delta.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD);
                """  # nosec B608
            )
        except Exception:
            tmp_delta.unlink(missing_ok=True)
            raise
        finally:
            con.close()

        tmp_delta.replace(delta_path)

        if compact_years:
            self.ledger.compact_completed_years(remove_quarterly=True)

        new_deltas = list(prev_snap.active_delta_files) + [f"state/deltas/{delta_filename}"]
        updated_fps = dict(prev_snap.period_fingerprints)
        updated_fps[period] = fingerprint
        indexed_periods = sorted(set(prev_snap.indexed_periods) | {period})

        manifest = self._write_manifest_commit(
            snapshot_id=snapshot_id,
            parent_snapshot_id=prev_snap.snapshot_id,
            generation=generation,
            rel_state_dir=prev_snap.state_dir,
            rel_shards=list(prev_snap.shard_files),
            rel_deltas=new_deltas,
            indexed_periods=indexed_periods,
            period_fingerprints=updated_fps,
            existing_history=prev_manifest.snapshot_history,
        )

        if auto_compact_deltas and len(new_deltas) >= self.policy.delta_compaction_threshold:
            manifest = self.compact_state_deltas(snapshot_label=f"{period}_compacted")

        return manifest

    def get_case_timeline(
        self, case_id: str, snapshot_id: Optional[str] = None
    ) -> Optional[Dict[str, object]]:
        """Performs an O(1) targeted lookup (single base shard + active deltas) for a case timeline."""
        manifest = self.load_manifest()
        if manifest is None:
            return None

        if snapshot_id is None:
            snap = manifest.active_snapshot
        else:
            snap = SnapshotRecord.load(self.snapshots_dir / f"{snapshot_id}.json")

        shard_idx = compute_shard_id(case_id, snap.shard_count)
        base_shard = self.index_root / snap.state_dir / _shard_filename(shard_idx, snap.shard_count)
        if not base_shard.exists():
            return None

        delta_uris = [(self.index_root / rel).as_posix() for rel in snap.active_delta_files]
        state_sql = build_resolved_state_sql([base_shard.as_posix()], delta_uris)

        con = duckdb.connect(":memory:")
        try:
            row = con.execute(
                f"""
                SELECT
                    case_id,
                    latest_primary_id,
                    latest_quarter,
                    first_quarter,
                    submissions_count,
                    is_cross_quarter,
                    resolution_tie,
                    timeline
                FROM ({state_sql})
                WHERE case_id = ?
                """,  # nosec B608
                [case_id],
            ).fetchone()
            if row is None:
                return None
            return {
                "case_id": row[0],
                "latest_primary_id": row[1],
                "latest_quarter": row[2],
                "first_quarter": row[3],
                "submissions_count": row[4],
                "is_cross_quarter": row[5],
                "resolution_tie": row[6],
                "timeline": row[7],
            }
        finally:
            con.close()
