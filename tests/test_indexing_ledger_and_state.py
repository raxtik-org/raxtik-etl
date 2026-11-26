"""Unit tests for the Tier-Agnostic Indexing Engine (Ledger + Sharded CoW State)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import duckdb
import pytest

from raxtik_etl.indexing import (
    LedgerManager,
    ResolutionPolicy,
    ShardedStateIndex,
    compute_shard_id,
)


def _create_bronze_duckdb(
    db_path: Path,
    rows: List[Tuple[str, str, Optional[int], Optional[str], Optional[str]]],
) -> Path:
    """Creates a minimal canonical Bronze DuckDB package with a `demo` table."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(db_path.as_posix())
    try:
        con.execute(
            """
            CREATE TABLE demo (
                primary_id VARCHAR,
                case_id VARCHAR,
                canonical_case_version INTEGER,
                latest_regulatory_date VARCHAR,
                manufacturer_date VARCHAR
            );
            """
        )
        con.executemany("INSERT INTO demo VALUES (?, ?, ?, ?, ?);", rows)
        con.execute("CHECKPOINT;")
    finally:
        con.close()
    return db_path


def test_ledger_extraction_and_tiered_annual_compaction(tmp_path: Path) -> None:
    bronze_dir = tmp_path / "bronze"
    index_root = tmp_path / "silver" / "index"
    ledger = LedgerManager(index_root)

    q1 = _create_bronze_duckdb(
        bronze_dir / "faers_2004Q1.duckdb",
        [("101", "C1", 1, "20040115", "20040110")],
    )
    q2 = _create_bronze_duckdb(
        bronze_dir / "faers_2004Q2.duckdb",
        [("102", "C2", 1, "20040415", "20040410")],
    )
    q3 = _create_bronze_duckdb(
        bronze_dir / "faers_2004Q3.duckdb",
        [("103", "C3", 1, "20040715", "20040710")],
    )
    q4 = _create_bronze_duckdb(
        bronze_dir / "faers_2004Q4.duckdb",
        [("104", "C4", 1, "20041015", "20041010")],
    )
    q5 = _create_bronze_duckdb(
        bronze_dir / "faers_2005Q1.duckdb",
        [("201", "C1", 2, "20050115", "20050110")],
    )

    ledger.extract_period_ledger(q1, "2004Q1")
    # Append-only guard prevents accidental overwrite
    with pytest.raises(FileExistsError):
        ledger.extract_period_ledger(q1, "2004Q1")

    ledger.extract_period_ledger(q2, "2004Q2")
    ledger.extract_period_ledger(q3, "2004Q3")

    # Incomplete year (only 3 quarters) must NOT compact yet
    assert ledger.compact_completed_years() == []
    assert [p.name for p in ledger.list_ledger_files()] == [
        "2004Q1.parquet",
        "2004Q2.parquet",
        "2004Q3.parquet",
    ]

    # 4th quarter completes 2004 -> compacts to 2004.parquet
    ledger.extract_period_ledger(q4, "2004Q4")
    compacted = ledger.compact_completed_years()
    assert [p.name for p in compacted] == ["2004.parquet"]

    # Adding 2005Q1 keeps 2004.parquet untouched and appends 2005Q1.parquet
    ledger.extract_period_ledger(q5, "2005Q1")
    assert [p.name for p in ledger.list_ledger_files()] == [
        "2004.parquet",
        "2005Q1.parquet",
    ]
    assert ledger.list_indexed_periods() == [
        "2004Q1",
        "2004Q2",
        "2004Q3",
        "2004Q4",
        "2005Q1",
    ]


def test_incremental_updates_preserve_full_timeline_and_snapshots(tmp_path: Path) -> None:
    bronze_dir = tmp_path / "bronze"
    index_root = tmp_path / "silver" / "index"
    policy = ResolutionPolicy(shard_count=4)
    state = ShardedStateIndex(index_root, tier="silver", source="faers", policy=policy)

    # 2004Q1: C99 v1, C_STAY v1
    p_2004q1 = _create_bronze_duckdb(
        bronze_dir / "faers_2004Q1.duckdb",
        [
            ("101", "C99", 1, "20040115", "20040110"),
            ("500", "C_STAY", 1, "20040201", "20040120"),
        ],
    )
    m1 = state.update_with_period(p_2004q1, "2004Q1")
    assert m1.active_snapshot_id == "snap_2004Q1"
    assert m1.active_snapshot.total_entities == 2
    assert m1.active_snapshot.total_submissions == 2
    assert m1.active_snapshot.cross_period_entities == 0

    # 2005Q2: C99 v2 (cross-year update!), C_LATE arrives with v2 first
    p_2005q2 = _create_bronze_duckdb(
        bronze_dir / "faers_2005Q2.duckdb",
        [
            ("150", "C99", 2, "20050601", "20050520"),
            ("902", "C_LATE", 2, "20050501", "20050420"),
        ],
    )
    m2 = state.update_with_period(p_2005q2, "2005Q2")
    assert m2.active_snapshot_id == "snap_2005Q2"
    assert m2.active_snapshot.parent_snapshot_id == "snap_2004Q1"

    # 2005Q4: C99 v3, plus out-of-order late arrival of C_LATE v1!
    p_2005q4 = _create_bronze_duckdb(
        bronze_dir / "faers_2005Q4.duckdb",
        [
            ("180", "C99", 3, "20051112", "20051101"),
            ("901", "C_LATE", 1, "20050101", "20041220"),
        ],
    )
    state.update_with_period(p_2005q4, "2005Q4")

    # 2006Q2: C99 v4
    p_2006q2 = _create_bronze_duckdb(
        bronze_dir / "faers_2006Q2.duckdb",
        [
            ("205", "C99", 4, "20060510", "20060501"),
        ],
    )
    m4 = state.update_with_period(p_2006q2, "2006Q2")
    assert m4.active_snapshot.total_entities == 3
    assert m4.active_snapshot.total_submissions == 7
    assert (
        m4.active_snapshot.cross_period_entities == 2
    )  # C99 (2004Q1..2006Q2) and C_LATE (2005Q2 & 2005Q4)

    # Verify full timeline preservation for C99 (all 4 quarters including in-between!)
    c99 = state.get_case_timeline("C99")
    assert c99 is not None
    assert c99["latest_primary_id"] == "205"
    assert c99["latest_quarter"] == "2006Q2"
    assert c99["first_quarter"] == "2004Q1"
    assert c99["submissions_count"] == 4
    assert c99["is_cross_quarter"] is True
    assert [entry["primary_id"] for entry in c99["timeline"]] == ["205", "180", "150", "101"]
    assert [entry["quarter"] for entry in c99["timeline"]] == [
        "2006Q2",
        "2005Q4",
        "2005Q2",
        "2004Q1",
    ]

    # Verify out-of-order late arrival did NOT demote C_LATE v2!
    c_late = state.get_case_timeline("C_LATE")
    assert c_late is not None
    assert c_late["latest_primary_id"] == "902"
    assert c_late["submissions_count"] == 2

    # Verify immutable snapshot time-travel: snap_2004Q1 still shows C99 winner = 101!
    c99_2004 = state.get_case_timeline("C99", snapshot_id="snap_2004Q1")
    assert c99_2004 is not None
    assert c99_2004["latest_primary_id"] == "101"
    assert c99_2004["submissions_count"] == 1

    # Verify vectorized DuckDB time-bounded resolution as of 2005Q3 -> winner is 150 (2005Q2)
    from raxtik_etl.indexing import build_resolved_state_sql

    shard_idx = compute_shard_id("C99", policy.shard_count)
    shard_file = index_root / m4.active_snapshot.state_dir / f"shard_{shard_idx:02d}.parquet"
    delta_files = [(index_root / rel).as_posix() for rel in m4.active_snapshot.active_delta_files]
    resolved_sql = build_resolved_state_sql([shard_file.as_posix()], delta_files)
    con = duckdb.connect(":memory:")
    try:
        winner_2005q3 = con.execute(
            f"""
            SELECT list_filter(timeline, lambda x: x.quarter <= '2005Q3')[1].primary_id
            FROM ({resolved_sql})
            WHERE case_id = 'C99'
            """
        ).fetchone()
        assert winner_2005q3 == ("150",)
    finally:
        con.close()


def test_rebuild_from_ledgers_matches_incremental_bit_for_bit(tmp_path: Path) -> None:
    bronze_dir = tmp_path / "bronze"
    index_root = tmp_path / "silver" / "index"
    policy = ResolutionPolicy(shard_count=8)
    state = ShardedStateIndex(index_root, tier="silver", source="faers", policy=policy)

    periods = [
        ("2004Q1", [("101", "C1", 1, "20040101", None), ("102", "C2", 1, "20040201", None)]),
        ("2004Q2", [("201", "C1", 2, "20040501", None), ("202", "C3", None, "20040601", None)]),
        ("2004Q3", [("301", "C3", 1, "20040701", None), ("302", "C4", 1, "20040801", "20040715")]),
        ("2004Q4", [("401", "C4", 1, "20040801", "20040801"), ("402", "C1", 3, "20041101", None)]),
    ]

    last_inc = None
    for period, rows in periods:
        pkg = _create_bronze_duckdb(bronze_dir / f"faers_{period}.duckdb", rows)
        last_inc = state.update_with_period(pkg, period)

    assert last_inc is not None
    # Now rebuild completely from scratch from compacted annual ledger!
    rebuilt = state.build_from_ledgers(snapshot_label="rebuild_check")
    assert rebuilt.active_snapshot.total_entities == last_inc.active_snapshot.total_entities
    assert rebuilt.active_snapshot.total_submissions == last_inc.active_snapshot.total_submissions
    assert (
        rebuilt.active_snapshot.cross_period_entities
        == last_inc.active_snapshot.cross_period_entities
    )

    from raxtik_etl.indexing import build_resolved_state_sql

    inc_base = [(index_root / rel).as_posix() for rel in last_inc.active_snapshot.shard_files]
    inc_deltas = [
        (index_root / rel).as_posix() for rel in last_inc.active_snapshot.active_delta_files
    ]
    reb_base = [(index_root / rel).as_posix() for rel in rebuilt.active_snapshot.shard_files]

    inc_sql = build_resolved_state_sql(inc_base, inc_deltas)
    reb_sql = build_resolved_state_sql(reb_base, ())

    con = duckdb.connect(":memory:")
    try:
        inc_rows = con.execute(f"SELECT * FROM ({inc_sql}) ORDER BY case_id").fetchall()
        reb_rows = con.execute(f"SELECT * FROM ({reb_sql}) ORDER BY case_id").fetchall()
        assert inc_rows == reb_rows
    finally:
        con.close()


def test_replace_period_reprocesses_corrected_quarter(tmp_path: Path) -> None:
    bronze_dir = tmp_path / "bronze"
    index_root = tmp_path / "silver" / "index"
    state = ShardedStateIndex(
        index_root, tier="silver", source="faers", policy=ResolutionPolicy(shard_count=4)
    )

    p1 = _create_bronze_duckdb(
        bronze_dir / "faers_2024Q1.duckdb",
        [("1001", "C1", 1, "20240101", None), ("1002", "C_BAD", 1, "20240105", None)],
    )
    p2 = _create_bronze_duckdb(
        bronze_dir / "faers_2024Q2.duckdb",
        [("2001", "C1", 2, "20240501", None)],
    )
    state.update_with_period(p1, "2024Q1")
    state.update_with_period(p2, "2024Q2")

    # FDA reissues 2024Q1 fixing C1's primary_id and removing C_BAD
    p1_fixed = _create_bronze_duckdb(
        bronze_dir / "faers_2024Q1_fixed.duckdb",
        [("1099", "C1", 1, "20240101", None)],
    )
    state.update_with_period(p1_fixed, "2024Q1", replace_period=True)

    # C_BAD should be completely gone, C1 should have [2001@2024Q2, 1099@2024Q1]
    assert state.get_case_timeline("C_BAD") is None
    c1 = state.get_case_timeline("C1")
    assert c1 is not None
    assert [e["primary_id"] for e in c1["timeline"]] == ["2001", "1099"]
    assert c1["latest_primary_id"] == "2001"


def test_delta_accumulation_and_compaction_equivalence(tmp_path: Path) -> None:
    """Verifies Option C: zero base rewrites during delta accumulation + exact compaction equivalence."""
    from raxtik_etl.indexing import build_resolved_state_sql

    bronze_dir = tmp_path / "bronze"
    index_root = tmp_path / "silver" / "index"
    policy = ResolutionPolicy(shard_count=4, delta_compaction_threshold=3)
    state = ShardedStateIndex(index_root, tier="silver", source="faers", policy=policy)

    p1 = _create_bronze_duckdb(
        bronze_dir / "faers_2004Q1.duckdb", [("101", "C1", 1, "20040101", None)]
    )
    p2 = _create_bronze_duckdb(
        bronze_dir / "faers_2004Q2.duckdb", [("201", "C1", 2, "20040501", None)]
    )
    p3 = _create_bronze_duckdb(
        bronze_dir / "faers_2004Q3.duckdb",
        [("301", "C1", 3, "20040801", None), ("302", "C2", 1, "20040805", None)],
    )
    p4 = _create_bronze_duckdb(
        bronze_dir / "faers_2004Q4.duckdb", [("401", "C2", 2, "20041101", None)]
    )

    m1 = state.update_with_period(p1, "2004Q1")
    base_dir_initial = m1.active_snapshot.state_dir
    assert m1.active_snapshot.active_delta_files == []

    # Q2 and Q3 accumulate deltas WITHOUT rewriting base_dir_initial!
    m2 = state.update_with_period(p2, "2004Q2")
    assert m2.active_snapshot.state_dir == base_dir_initial
    assert len(m2.active_snapshot.active_delta_files) == 1

    m3 = state.update_with_period(p3, "2004Q3")
    assert m3.active_snapshot.state_dir == base_dir_initial
    assert len(m3.active_snapshot.active_delta_files) == 2

    # Capture logical state BEFORE compaction (base + 2 deltas)
    con = duckdb.connect(":memory:")
    try:
        pre_sql = build_resolved_state_sql(
            [(index_root / r).as_posix() for r in m3.active_snapshot.shard_files],
            [(index_root / r).as_posix() for r in m3.active_snapshot.active_delta_files],
        )
        pre_rows = con.execute(f"SELECT * FROM ({pre_sql}) ORDER BY case_id").fetchall()

        # Compact explicitly and verify EXACT logical equivalence!
        m3_comp = state.compact_state_deltas()
        assert m3_comp.active_snapshot.active_delta_files == []
        assert m3_comp.active_snapshot.state_dir != base_dir_initial

        post_sql = build_resolved_state_sql(
            [(index_root / r).as_posix() for r in m3_comp.active_snapshot.shard_files],
            (),
        )
        post_rows = con.execute(f"SELECT * FROM ({post_sql}) ORDER BY case_id").fetchall()
        assert pre_rows == post_rows
    finally:
        con.close()

    # Auto-compaction test: Q4 starts fresh delta count (1 < 3)
    m4 = state.update_with_period(p4, "2004Q4")
    assert len(m4.active_snapshot.active_delta_files) == 1


def test_idempotent_update_and_fingerprint_conflict(tmp_path: Path) -> None:
    bronze_dir = tmp_path / "bronze"
    index_root = tmp_path / "silver" / "index"
    state = ShardedStateIndex(
        index_root, tier="silver", source="faers", policy=ResolutionPolicy(shard_count=4)
    )

    p1 = _create_bronze_duckdb(
        bronze_dir / "faers_2004Q1.duckdb", [("101", "C1", 1, "20040101", None)]
    )
    m1 = state.update_with_period(p1, "2004Q1")

    # Re-running the EXACT same file is a 100% idempotent no-op (no generation bump!)
    m1_again = state.update_with_period(p1, "2004Q1")
    assert m1_again.active_snapshot_id == m1.active_snapshot_id
    assert m1_again.generation == m1.generation == 1

    # Different content for same period without replace_period=True MUST raise conflict error
    p1_modified = _create_bronze_duckdb(
        bronze_dir / "faers_2004Q1_v2.duckdb", [("199", "C1", 1, "20040101", None)]
    )
    with pytest.raises(ValueError, match="different source fingerprint"):
        state.update_with_period(p1_modified, "2004Q1", replace_period=False)


def test_resolution_tie_auditing(tmp_path: Path) -> None:
    bronze_dir = tmp_path / "bronze"
    index_root = tmp_path / "silver" / "index"
    state = ShardedStateIndex(
        index_root, tier="silver", source="faers", policy=ResolutionPolicy(shard_count=4)
    )

    # C_TIE: two reports with identical version=3, fda_date=20260501, mfr_date=20260425 -> tie!
    # C_CLEAR: version=2 clearly beats version=1 -> NOT a tie!
    pkg = _create_bronze_duckdb(
        bronze_dir / "faers_2026Q2.duckdb",
        [
            ("100001", "C_TIE", 3, "20260501", "20260425"),
            ("100002", "C_TIE", 3, "20260501", "20260425"),
            ("200001", "C_CLEAR", 1, "20260501", "20260425"),
            ("200002", "C_CLEAR", 2, "20260501", "20260425"),
        ],
    )
    state.update_with_period(pkg, "2026Q2")

    c_tie = state.get_case_timeline("C_TIE")
    assert c_tie is not None
    assert c_tie["latest_primary_id"] == "100002"
    assert c_tie["resolution_tie"] is True

    c_clear = state.get_case_timeline("C_CLEAR")
    assert c_clear is not None
    assert c_clear["latest_primary_id"] == "200002"
    assert c_clear["resolution_tie"] is False


def test_optimistic_concurrency_rejects_stale_parent(tmp_path: Path) -> None:
    from unittest.mock import patch

    from raxtik_etl.distribution.huggingface import upload_hf_index_folder

    bronze_dir = tmp_path / "bronze"
    index_root = tmp_path / "silver" / "index"
    state = ShardedStateIndex(
        index_root, tier="silver", source="faers", policy=ResolutionPolicy(shard_count=4)
    )

    p1 = _create_bronze_duckdb(
        bronze_dir / "faers_2004Q1.duckdb", [("101", "C1", 1, "20040101", None)]
    )
    p2 = _create_bronze_duckdb(
        bronze_dir / "faers_2004Q2.duckdb", [("201", "C1", 2, "20040501", None)]
    )
    state.update_with_period(p1, "2004Q1")
    state.update_with_period(p2, "2004Q2")  # parent_snapshot_id = "snap_2004Q1"

    # Simulate another process having already published "snap_2004Q2_other" on HF!
    with (
        patch(
            "raxtik_etl.distribution.huggingface.fetch_hf_json",
            return_value=("main", {"active_snapshot_id": "snap_2004Q2_other"}),
        ),
        pytest.raises(RuntimeError, match="Optimistic concurrency conflict"),
    ):
        upload_hf_index_folder(
            index_root=index_root,
            repo_id="raxtik-org/faers-safety-database",
            tier="silver",
            token="fake-token",
            enforce_optimistic_concurrency=True,
        )


def test_null_and_empty_case_id_fallback(tmp_path: Path) -> None:
    """NULL or blank CASEIDs must never be dropped or merged into a single fake case."""
    bronze_dir = tmp_path / "bronze"
    index_root = tmp_path / "silver" / "index"
    state = ShardedStateIndex(
        index_root, tier="silver", source="faers", policy=ResolutionPolicy(shard_count=4)
    )

    pkg = _create_bronze_duckdb(
        bronze_dir / "faers_2024Q1.duckdb",
        [
            ("1001", "C1", 1, "20240101", None),
            ("1002", None, 1, "20240102", None),  # type: ignore[list-item]
            ("1003", "", 1, "20240103", None),
            ("1004", "   ", 1, "20240104", None),
        ],
    )
    manifest = state.update_with_period(pkg, "2024Q1")

    # All 4 distinct reports must survive as 4 distinct entities (zero dropped, zero merged!)
    assert manifest.active_snapshot.total_entities == 4
    assert manifest.active_snapshot.total_submissions == 4

    for pid in ("1002", "1003", "1004"):
        rec = state.get_case_timeline(f"REPORT:{pid}")
        assert rec is not None
        assert rec["latest_primary_id"] == pid
        assert rec["submissions_count"] == 1


def test_build_periods_filter(tmp_path: Path) -> None:
    """Passing `periods=['2004Q1']` must NOT pull in extra ledger files like `2024Q1.parquet`."""
    bronze_dir = tmp_path / "bronze"
    index_root = tmp_path / "silver" / "index"
    state = ShardedStateIndex(
        index_root, tier="silver", source="faers", policy=ResolutionPolicy(shard_count=4)
    )

    p_2004 = _create_bronze_duckdb(
        bronze_dir / "faers_2004Q1.duckdb", [("101", "C1", 1, "20040101", None)]
    )
    p_2024 = _create_bronze_duckdb(
        bronze_dir / "faers_2024Q1.duckdb", [("901", "C2", 1, "20240101", None)]
    )
    state.ledger.extract_period_ledger(p_2004, "2004Q1")
    state.ledger.extract_period_ledger(p_2024, "2024Q1")

    manifest = state.build_from_ledgers(periods=["2004Q1"])
    assert manifest.active_snapshot.indexed_periods == ["2004Q1"]
    assert manifest.active_snapshot.total_entities == 1
    assert state.get_case_timeline("C1") is not None
    assert state.get_case_timeline("C2") is None


def test_replace_compacted_quarter(tmp_path: Path) -> None:
    """Replacing a quarter after YYYY.parquet compaction purges stale rows cleanly."""
    bronze = tmp_path / "bronze"
    policy = ResolutionPolicy(shard_count=4)
    state = ShardedStateIndex(tmp_path / "idx", tier="silver", source="faers", policy=policy)

    pkgs = {
        "2024Q1": _create_bronze_duckdb(bronze / "q1.duckdb", [("101", "C1", 1, "20240115", None)]),
        "2024Q2": _create_bronze_duckdb(
            bronze / "q2.duckdb",
            [("201", "C1", 2, "20240415", None), ("202", "C_STALE", 1, "20240415", None)],
        ),
        "2024Q3": _create_bronze_duckdb(bronze / "q3.duckdb", [("301", "C3", 1, "20240715", None)]),
        "2024Q4": _create_bronze_duckdb(bronze / "q4.duckdb", [("401", "C4", 1, "20241015", None)]),
    }
    for period, pkg in pkgs.items():
        state.update_with_period(pkg, period, compact_years=True)

    assert (state.ledger.ledger_dir / "2024.parquet").exists()
    assert not (state.ledger.ledger_dir / "2024Q2.parquet").exists()

    pkgs["2024Q2"] = _create_bronze_duckdb(
        bronze / "q2_new.duckdb", [("299", "C1", 2, "20240420", None)]
    )
    replaced = state.update_with_period(pkgs["2024Q2"], "2024Q2", replace_period=True)

    assert not (state.ledger.ledger_dir / "2024Q2.parquet").exists()
    assert state.get_case_timeline("C_STALE") is None
    c1 = state.get_case_timeline("C1")
    assert c1 is not None and [e["primary_id"] for e in c1["timeline"]] == ["299", "101"]

    clean = ShardedStateIndex(tmp_path / "clean", tier="silver", source="faers", policy=policy)
    for period, pkg in pkgs.items():
        clean.ledger.extract_period_ledger(pkg, period)
    m_clean = clean.build_from_ledgers()
    assert replaced.active_snapshot.total_entities == m_clean.active_snapshot.total_entities == 3
    assert c1 == clean.get_case_timeline("C1")


def test_republished_primary_id(tmp_path: Path) -> None:
    """Identical primary_id republished across quarters resolves by data_period DESC."""
    bronze = tmp_path / "bronze"
    state = ShardedStateIndex(
        tmp_path / "idx", tier="silver", source="faers", policy=ResolutionPolicy(shard_count=4)
    )
    for period in ("2006Q1", "2006Q2"):
        pkg = _create_bronze_duckdb(
            bronze / f"{period}.duckdb", [("555", "C_DUP", 1, "20060101", None)]
        )
        state.update_with_period(pkg, period)

    rec = state.get_case_timeline("C_DUP")
    assert rec is not None and rec["latest_quarter"] == "2006Q2" and rec["submissions_count"] == 2


def test_update_rejects_unverified_ledger(tmp_path: Path) -> None:
    """update_with_period must fail closed if a ledger exists on disk with no verified fingerprint."""
    bronze = tmp_path / "bronze"
    state = ShardedStateIndex(
        tmp_path / "idx", tier="silver", source="faers", policy=ResolutionPolicy(shard_count=4)
    )
    p1 = _create_bronze_duckdb(bronze / "q1.duckdb", [("101", "C1", 1, "20240115", None)])
    state.ledger.extract_period_ledger(p1, "2024Q1")

    p1_changed = _create_bronze_duckdb(
        bronze / "q1_v2.duckdb", [("999", "C1", 2, "20240120", None)]
    )
    with pytest.raises(ValueError, match="cannot be reused without a matching"):
        state.update_with_period(p1_changed, "2024Q1", replace_period=False)

    manifest = state.update_with_period(p1_changed, "2024Q1", replace_period=True)
    assert manifest.active_snapshot.indexed_periods == ["2024Q1"]
    rec = state.get_case_timeline("C1")
    assert rec is not None and rec["latest_primary_id"] == "999"


def test_subset_build_scopes_fingerprints(tmp_path: Path) -> None:
    """Rebuilding a subset of periods must drop fingerprints for omitted periods."""
    bronze = tmp_path / "bronze"
    state = ShardedStateIndex(
        tmp_path / "idx", tier="silver", source="faers", policy=ResolutionPolicy(shard_count=4)
    )
    p1 = _create_bronze_duckdb(bronze / "q1.duckdb", [("101", "C1", 1, "20040115", None)])
    p2 = _create_bronze_duckdb(bronze / "q2.duckdb", [("201", "C2", 1, "20040415", None)])
    state.update_with_period(p1, "2004Q1")
    state.update_with_period(p2, "2004Q2")

    sub = state.build_from_ledgers(periods=["2004Q2"])
    assert sub.active_snapshot.indexed_periods == ["2004Q2"]
    assert set(sub.active_snapshot.period_fingerprints.keys()) == {"2004Q2"}
