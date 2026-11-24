"""End-to-end tests for Tier Query Middleware, SDK `tier='silver'`, and Materialization."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple
from unittest.mock import patch

import duckdb
import pytest

from raxtik_etl.indexing import ResolutionPolicy, ShardedStateIndex
from raxtik_etl.schema.registry import CANONICAL_SCHEMA_VERSION
from raxtik_etl.sdk import BaseDataset


def _build_bronze_package(
    db_path: Path,
    demo_rows: List[Tuple[str, str, Optional[int], Optional[str], Optional[str]]],
    drug_rows: List[Tuple[str, int, str]],
    reac_rows: List[Tuple[str, str]],
) -> Path:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(db_path.as_posix())
    try:
        con.execute(
            """
            CREATE TABLE demo (
                primary_id VARCHAR PRIMARY KEY,
                case_id VARCHAR,
                canonical_case_version INTEGER,
                latest_regulatory_date VARCHAR,
                manufacturer_date VARCHAR
            );
            CREATE TABLE drug (
                primary_id VARCHAR,
                drug_seq INTEGER,
                reported_drug_name VARCHAR
            );
            CREATE TABLE reac (
                primary_id VARCHAR,
                reported_reaction_term VARCHAR
            );
            CREATE TABLE _metadata (key VARCHAR, value VARCHAR);
            CREATE TABLE _data_quality_report (metric_name VARCHAR, metric_value VARCHAR);
            """
        )
        con.executemany("INSERT INTO demo VALUES (?, ?, ?, ?, ?);", demo_rows)
        con.executemany("INSERT INTO drug VALUES (?, ?, ?);", drug_rows)
        con.executemany("INSERT INTO reac VALUES (?, ?);", reac_rows)
        con.execute(
            "INSERT INTO _metadata VALUES ('canonical_schema_version', ?), ('package_format_version', '1.0.0');",
            [CANONICAL_SCHEMA_VERSION],
        )
        con.execute(
            "INSERT INTO _data_quality_report VALUES ('raw_reports', ?);", [str(len(demo_rows))]
        )
        con.execute("CREATE OR REPLACE VIEW cases AS SELECT * FROM demo;")
    finally:
        con.close()
    return db_path


def test_sdk_silver_middleware_drops_superseded_cases_and_scopes_child_tables(
    tmp_path: Path,
) -> None:
    pkg_dir = tmp_path / "packages"
    index_root = tmp_path / "silver" / "index"

    # 2004Q1 has:
    # - Case C1 (pid=101, v1) -> will be SUPERSEDED in 2006Q2!
    # - Case C2 (pid=102, v1) -> NEVER updated, stays in 2004Q1!
    p_2004q1 = _build_bronze_package(
        pkg_dir / "faers_2004Q1.duckdb",
        demo_rows=[
            ("101", "C1", 1, "20040115", None),
            ("102", "C2", 1, "20040201", None),
        ],
        drug_rows=[
            ("101", 1, "OLD_DRUG_FOR_C1"),
            ("102", 1, "ASPIRIN"),
        ],
        reac_rows=[
            ("101", "NAUSEA"),
            ("102", "HEADACHE"),
        ],
    )

    # 2006Q2 has:
    # - Case C1 (pid=205, v2) -> supersedes 2004Q1 v1!
    p_2006q2 = _build_bronze_package(
        pkg_dir / "faers_2006Q2.duckdb",
        demo_rows=[
            ("205", "C1", 2, "20060510", None),
        ],
        drug_rows=[
            ("205", 1, "UPDATED_DRUG_FOR_C1"),
        ],
        reac_rows=[
            ("205", "HOSPITALIZATION"),
        ],
    )

    # Build Silver index across both quarters
    state = ShardedStateIndex(
        index_root, tier="silver", source="faers", policy=ResolutionPolicy(shard_count=4)
    )
    state.update_with_period(p_2004q1, "2004Q1")
    state.update_with_period(p_2006q2, "2006Q2")

    # 1. Bronze tier on 2004Q1 returns BOTH C1 and C2 (raw as-reported)
    with BaseDataset("2004Q1", source="faers", package_dir=pkg_dir, tier="bronze") as bronze:
        assert sorted(bronze.cases()["case_id"].to_list()) == ["C1", "C2"]
        assert sorted(bronze.drugs()["reported_drug_name"].to_list()) == [
            "ASPIRIN",
            "OLD_DRUG_FOR_C1",
        ]

    # 2. Silver tier on 2004Q1 transparently DROPS C1 (superseded in 2006Q2) and scopes child tables!
    with BaseDataset(
        "2004Q1", source="faers", package_dir=pkg_dir, tier="silver", index_dir=index_root
    ) as silver_04:
        assert silver_04.cases()["case_id"].to_list() == ["C2"]
        assert silver_04.drugs()["reported_drug_name"].to_list() == ["ASPIRIN"]
        assert silver_04.reactions()["reported_reaction_term"].to_list() == ["HEADACHE"]
        # Raw `demo` still preserves full physical audit history
        assert silver_04.query("SELECT COUNT(*) AS n FROM demo")["n"][0] == 2
        # Case timeline lookup works directly on the SDK
        tl = silver_04.case_timeline("C1")
        assert tl is not None
        assert tl["latest_primary_id"] == "205"
        assert tl["latest_quarter"] == "2006Q2"

    # 3. Time-bounded Silver on 2004Q1 `as_of_period="2005Q4"` KEEPS C1 (not yet superseded!)
    with BaseDataset(
        "2004Q1",
        source="faers",
        package_dir=pkg_dir,
        tier="silver",
        index_dir=index_root,
        as_of_period="2005Q4",
    ) as silver_04_asof:
        assert sorted(silver_04_asof.cases()["case_id"].to_list()) == ["C1", "C2"]

    # 4. Silver tier on 2006Q2 returns C1 v2 (pid=205)
    with BaseDataset(
        "2006Q2", source="faers", package_dir=pkg_dir, tier="silver", index_dir=index_root
    ) as silver_06:
        assert silver_06.cases()["primary_id"].to_list() == ["205"]
        assert silver_06.drugs()["reported_drug_name"].to_list() == ["UPDATED_DRUG_FOR_C1"]


def test_sdk_materialize_tier_writes_standalone_filtered_duckdb(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "packages"
    index_root = tmp_path / "silver" / "index"
    mat_path = tmp_path / "materialized" / "faers_2004Q1_silver.duckdb"

    p_2004q1 = _build_bronze_package(
        pkg_dir / "faers_2004Q1.duckdb",
        demo_rows=[("101", "C1", 1, "20040115", None), ("102", "C2", 1, "20040201", None)],
        drug_rows=[("101", 1, "OLD_DRUG"), ("102", 1, "ASPIRIN")],
        reac_rows=[("101", "NAUSEA"), ("102", "HEADACHE")],
    )
    p_2006q2 = _build_bronze_package(
        pkg_dir / "faers_2006Q2.duckdb",
        demo_rows=[("205", "C1", 2, "20060510", None)],
        drug_rows=[("205", 1, "NEW_DRUG")],
        reac_rows=[("205", "DEATH")],
    )

    state = ShardedStateIndex(
        index_root, tier="silver", source="faers", policy=ResolutionPolicy(shard_count=4)
    )
    state.update_with_period(p_2004q1, "2004Q1")
    state.update_with_period(p_2006q2, "2006Q2")

    with BaseDataset(
        "2004Q1", source="faers", package_dir=pkg_dir, tier="silver", index_dir=index_root
    ) as silver_ds:
        out = silver_ds.materialize_tier(mat_path)
        assert out == mat_path
        assert mat_path.exists()

    # Open standalone materialized file directly with DuckDB (zero index needed!)
    con = duckdb.connect(mat_path.as_posix(), read_only=True)
    try:
        assert con.execute("SELECT case_id FROM cases").fetchall() == [("C2",)]
        assert con.execute("SELECT reported_drug_name FROM drug").fetchall() == [("ASPIRIN",)]
        meta = dict(con.execute("SELECT key, value FROM _metadata").fetchall())
        assert meta["tier"] == "silver"
    finally:
        con.close()


def test_sdk_remote_silver_supports_fully_remote_and_cache_index(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "packages"
    index_root = tmp_path / "silver" / "index"

    p_2004q1 = _build_bronze_package(
        pkg_dir / "faers_2004Q1.duckdb",
        demo_rows=[("101", "C1", 1, "20040115", None), ("102", "C2", 1, "20040201", None)],
        drug_rows=[("101", 1, "OLD_DRUG"), ("102", 1, "ASPIRIN")],
        reac_rows=[("101", "NAUSEA"), ("102", "HEADACHE")],
    )
    p_2006q2 = _build_bronze_package(
        pkg_dir / "faers_2006Q2.duckdb",
        demo_rows=[("205", "C1", 2, "20060510", None)],
        drug_rows=[("205", 1, "NEW_DRUG")],
        reac_rows=[("205", "DEATH")],
    )

    state = ShardedStateIndex(
        index_root, tier="silver", source="faers", policy=ResolutionPolicy(shard_count=4)
    )
    manifest = state.update_with_period(p_2004q1, "2004Q1")
    manifest = state.update_with_period(p_2006q2, "2006Q2")
    local_shards = [(index_root / rel).as_posix() for rel in manifest.active_snapshot.shard_files]
    local_deltas = [
        (index_root / rel).as_posix() for rel in manifest.active_snapshot.active_delta_files
    ]

    def _fake_connect_remote(repo_id, source, data_period, revision=None, tier="bronze"):
        # Verify remote silver ALWAYS attaches immutable Bronze package!
        assert tier == "bronze"
        con = duckdb.connect(":memory:")
        con.execute(f"ATTACH '{p_2004q1.as_posix()}' AS {source} (READ_ONLY);")
        con.execute(f"USE {source};")
        return f"https://example.test/{tier}/{data_period}.duckdb", con

    # Test 100% fully remote path (`cache_index=False`)
    with (
        patch(
            "raxtik_etl.distribution.huggingface.connect_remote_hf_duckdb",
            side_effect=_fake_connect_remote,
        ),
        patch(
            "raxtik_etl.indexing.distribution.fetch_remote_index_manifest",
            return_value=(manifest, local_shards, local_deltas),
        ) as mock_fetch_remote,
    ):
        with BaseDataset("2004Q1", source="faers", tier="silver", remote=True) as ds:
            mock_fetch_remote.assert_called_once()
            assert ds.cases()["case_id"].to_list() == ["C2"]
            assert ds.drugs()["reported_drug_name"].to_list() == ["ASPIRIN"]

    # Test `cache_index=True` path
    with (
        patch(
            "raxtik_etl.distribution.huggingface.connect_remote_hf_duckdb",
            side_effect=_fake_connect_remote,
        ),
        patch(
            "raxtik_etl.indexing.distribution.sync_remote_index_to_local_cache",
            return_value=(manifest, local_shards, local_deltas),
        ) as mock_sync_cache,
    ):
        with BaseDataset(
            "2004Q1", source="faers", tier="silver", remote=True, cache_index=True
        ) as ds:
            mock_sync_cache.assert_called_once()
            assert ds.cases()["case_id"].to_list() == ["C2"]


def test_sdk_rejects_unsupported_package_format_version(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "packages"
    db_path = _build_bronze_package(
        pkg_dir / "faers_2024Q1.duckdb",
        demo_rows=[("101", "C1", 1, "20240101", None)],
        drug_rows=[("101", 1, "ASPIRIN")],
        reac_rows=[("101", "HEADACHE")],
    )
    con = duckdb.connect(db_path.as_posix())
    try:
        con.execute("UPDATE _metadata SET value = '2.0.0' WHERE key = 'package_format_version';")
    finally:
        con.close()

    with pytest.raises(ValueError, match="Unsupported package_format_version '2.0.0'"):
        BaseDataset("2024Q1", source="faers", package_dir=pkg_dir, tier="bronze")
