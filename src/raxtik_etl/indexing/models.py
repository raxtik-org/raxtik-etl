"""Tier-agnostic data models for the RAXTIK Derived Deduplication Index.

Defines the manifest, immutable snapshot records, explicit cross-runtime
partitioning specification, and configurable resolution policies shared
across Silver, Gold, and any future tiers.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

INDEX_FORMAT_VERSION = "1.0.0"  # Schema version of manifest.json and index Parquet files
DEFAULT_SHARD_COUNT = 16  # Number of hash-partitioned base state files (shard_00..shard_15.parquet)
DEFAULT_DELTA_COMPACTION_THRESHOLD = (
    4  # Auto-merge deltas into a new base once 4 quarter deltas accumulate (1 year)
)


def utc_now_iso() -> str:
    """Returns the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PartitioningSpec:
    """Explicit cross-runtime deterministic partitioning contract."""

    algorithm: str = "md5_u32"
    version: int = 1
    encoding: str = "utf-8"
    shard_count: int = DEFAULT_SHARD_COUNT

    def __post_init__(self) -> None:
        if self.shard_count < 1:
            raise ValueError(f"shard_count must be >= 1, got {self.shard_count}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PartitioningSpec:
        return cls(**data)


@dataclass(frozen=True)
class ResolutionPolicy:
    """Configurable deterministic resolution policy for a source or tier.

    Defaults align with the canonical RAXTIK schema so any source connector
    works out of the box while allowing connectors (e.g. FAERS, VAERS, EV)
    or higher tiers (e.g. Gold) to customize ranking and scoping rules.
    """

    entity_key: str = "case_id"
    record_key: str = "primary_id"
    version_column: str = "canonical_case_version"
    regulatory_date_column: str = "latest_regulatory_date"
    manufacturer_date_column: str = "manufacturer_date"
    source_table: str = "demo"
    child_tables: Tuple[str, ...] = ("drug", "reac", "outc", "indi", "ther", "rpsr")
    shard_count: int = DEFAULT_SHARD_COUNT
    delta_compaction_threshold: int = DEFAULT_DELTA_COMPACTION_THRESHOLD
    numeric_record_key_tiebreaker: bool = True
    policy_version: str = "1.0.0"

    def __post_init__(self) -> None:
        if self.shard_count < 1:
            raise ValueError(f"shard_count must be >= 1, got {self.shard_count}")
        if self.delta_compaction_threshold < 1:
            raise ValueError(
                f"delta_compaction_threshold must be >= 1, got {self.delta_compaction_threshold}"
            )

    def partitioning_spec(self) -> PartitioningSpec:
        return PartitioningSpec(shard_count=self.shard_count)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["child_tables"] = list(self.child_tables)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ResolutionPolicy:
        parsed = dict(data)
        if "child_tables" in parsed:
            parsed["child_tables"] = tuple(parsed["child_tables"])
        return cls(**parsed)


@dataclass
class SnapshotRecord:
    """Immutable metadata record for a single index snapshot (base shards + ordered deltas)."""

    snapshot_id: str
    parent_snapshot_id: Optional[str]
    generation: int
    tier: str
    source: str
    created_at: str
    indexed_periods: List[str]
    state_dir: str
    shard_count: int
    shard_files: List[str]
    ledger_files: List[str]
    total_submissions: int
    total_entities: int
    cross_period_entities: int
    active_delta_files: List[str] = field(default_factory=list)
    period_fingerprints: Dict[str, str] = field(default_factory=dict)
    partitioning: PartitioningSpec = field(default_factory=PartitioningSpec)
    resolution_policy_version: str = "1.0.0"
    format_version: str = INDEX_FORMAT_VERSION

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["partitioning"] = self.partitioning.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SnapshotRecord:
        parsed = dict(data)
        parsed["partitioning"] = PartitioningSpec.from_dict(parsed["partitioning"])
        return cls(**parsed)

    def save(self, path: Path) -> None:
        """Atomically writes this snapshot record to JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(path)

    @classmethod
    def load(cls, path: Path) -> SnapshotRecord:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


@dataclass
class IndexManifest:
    """Top-level manifest.json pointing to the active immutable snapshot."""

    tier: str
    source: str
    active_snapshot_id: str
    generation: int
    updated_at: str
    policy: ResolutionPolicy
    active_snapshot: SnapshotRecord
    snapshot_history: List[str] = field(default_factory=list)
    format_version: str = INDEX_FORMAT_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format_version": self.format_version,
            "tier": self.tier,
            "source": self.source,
            "active_snapshot_id": self.active_snapshot_id,
            "generation": self.generation,
            "updated_at": self.updated_at,
            "partitioning": self.active_snapshot.partitioning.to_dict(),
            "policy": self.policy.to_dict(),
            "active_snapshot": self.active_snapshot.to_dict(),
            "snapshot_history": list(self.snapshot_history),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> IndexManifest:
        return cls(
            format_version=data["format_version"],
            tier=data["tier"],
            source=data["source"],
            active_snapshot_id=data["active_snapshot_id"],
            generation=int(data["generation"]),
            updated_at=data["updated_at"],
            policy=ResolutionPolicy.from_dict(data["policy"]),
            active_snapshot=SnapshotRecord.from_dict(data["active_snapshot"]),
            snapshot_history=list(data["snapshot_history"]),
        )

    def save(self, path: Path) -> None:
        """Atomically writes manifest.json via temp file rename."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(path)

    @classmethod
    def load(cls, path: Path) -> IndexManifest:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
