"""Python Client SDK for Pharmacovigilance Safety Data Packages.

Provides simple, zero-copy querying of local or remote DuckDB/Parquet datasets
with Polars.

Example:
    from raxtik_etl import Dataset

    with Dataset.from_hf("2004Q1", source="faers") as ds:
        ds.print_summary()
        cases_df = ds.cases(limit=100)
        drugs_df = ds.query("SELECT * FROM drug WHERE standard_concept_name = 'ASPIRIN'")
"""

from __future__ import annotations

import logging
from functools import lru_cache
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, Dict, Optional, Type, Union

import duckdb
import polars as pl
from rich.console import Console
from rich.table import Table

from raxtik_etl.distribution.huggingface import (
    DEFAULT_HTTP_TIMEOUT,
    get_default_package_dir,
)

logger = logging.getLogger(__name__)
console = Console()
ENTRY_POINT_CLIENT_GROUP = "raxtik_etl.clients"


class BaseDataset:
    """Base interface to inspect and query any versioned safety data package.

    Provides high-level Polars dataframe access, SQL query execution, and
    integrity verification over compiled DuckDB packages.

    Attributes:
        source_name: Default identifier of the pharmacovigilance source (e.g. 'generic', 'faers').
        default_hf_repo: Default remote Hugging Face dataset repository.
    """

    source_name: str = "generic"
    default_hf_repo: Optional[str] = None

    def __init__(
        self,
        data_period: str,
        source: Optional[str] = None,
        package_dir: Optional[Union[str, Path]] = None,
        download_if_missing: bool = False,
        hf_repo: Optional[str] = None,
        timeout: int = DEFAULT_HTTP_TIMEOUT,
        revision: Optional[str] = None,
        tier: str = "bronze",
        remote: bool = False,
        index_dir: Optional[Union[str, Path]] = None,
        cache_index: bool = False,
        as_of_period: Optional[str] = None,
    ) -> None:
        """Initializes a dataset connection (local or remote streaming via HTTP).

        Args:
            data_period: Temporal coverage period identifier (e.g., '2004Q1').
            source: Source identifier (e.g. 'faers'). Defaults to source_name.
            package_dir: Local directory containing package files.
            download_if_missing: If True, fetches package from Hugging Face if missing.
            hf_repo: Optional Hugging Face dataset repository ID override.
            timeout: HTTP request timeout in seconds when downloading.
            revision: Hugging Face Git revision or tag (e.g., 'main' or 'v0.1.0').
            tier: Dataset release tier ('bronze', 'silver', or future 'gold'). Defaults to 'bronze'.
            remote: If True, streams directly from Hugging Face Hub over HTTPS with zero local disk footprint.
            index_dir: Optional local directory containing a pre-built tier index (`manifest.json`).
            cache_index: When `remote=True` and `tier != 'bronze'`, caches the lightweight index
                locally for 0ms index latency while keeping Bronze data remote. Defaults to False
                (100% zero-disk fully remote).
            as_of_period: Optional upper-bound period (e.g. '2005Q3') for time-bounded winner resolution.

        Raises:
            ValueError: If data_period is empty.
            FileNotFoundError: If package is not present locally and download_if_missing is False.
        """
        period_clean = (data_period or "").upper().strip()
        if not period_clean:
            raise ValueError("data_period (e.g. '2004Q1') must be specified.")
        self.data_period = period_clean
        self.source = (source or self.source_name).lower()
        self.hf_repo = (
            hf_repo or self.default_hf_repo or f"raxtik-org/{self.source}-safety-database"
        )
        self.pkg_dir = Path(package_dir) if package_dir else get_default_package_dir()
        self.duckdb_path = self.pkg_dir / f"{self.source}_{self.data_period}.duckdb"
        self.tier = (tier or "bronze").lower().strip()
        self.remote = remote
        self.index_dir = Path(index_dir) if index_dir else None
        self.cache_index = cache_index
        self.as_of_period = as_of_period
        self._remote_url: Optional[str] = None
        self._index_shard_uris: Optional[list[str]] = None
        self._index_delta_uris: list[str] = []
        self._index_policy: Any = None

        is_derived_tier = self.tier != "bronze"

        if self.remote:
            from raxtik_etl.distribution.huggingface import connect_remote_hf_duckdb

            self._remote_url, self._con = connect_remote_hf_duckdb(
                repo_id=self.hf_repo,
                source=self.source,
                data_period=self.data_period,
                revision=revision,
                tier="bronze" if is_derived_tier else self.tier,
            )
            if is_derived_tier:
                self._mount_tier_middleware(
                    bronze_catalog=self.source,
                    download_if_missing=True,
                    timeout=timeout,
                    revision=revision,
                )
            self._validate_package_compatibility()
            return

        if not self.duckdb_path.exists():
            if download_if_missing:
                from raxtik_etl.distribution.huggingface import (
                    download_package_from_hf,
                )

                download_package_from_hf(
                    data_period_or_name=self.data_period,
                    dest_dir=self.pkg_dir,
                    repo_id=self.hf_repo,
                    source_name=self.source,
                    timeout=timeout,
                    revision=revision,
                    tier="bronze" if is_derived_tier else self.tier,
                )
            else:
                raise FileNotFoundError(
                    f"Package for data period {self.data_period} not found at {self.duckdb_path}. "
                    f"Build it locally using `raxtik-etl build --data-period {self.data_period}` "
                    f"or pass `download_if_missing=True` to download from Hugging Face."
                )

        if is_derived_tier:
            self._con = duckdb.connect(":memory:")
            self._con.execute(f"ATTACH '{self.duckdb_path.as_posix()}' AS bronze_db (READ_ONLY);")
            self._mount_tier_middleware(
                bronze_catalog="bronze_db",
                download_if_missing=download_if_missing,
                timeout=timeout,
                revision=revision,
            )
        else:
            self._con = duckdb.connect(self.duckdb_path.as_posix(), read_only=True)

        self._validate_package_compatibility()

    def _mount_tier_middleware(
        self,
        bronze_catalog: str,
        download_if_missing: bool,
        timeout: int,
        revision: Optional[str],
    ) -> None:
        """Resolves index shards (local, cached, or 100% remote) and mounts tier views."""
        from raxtik_etl.indexing.distribution import (
            fetch_remote_index_manifest,
            get_default_index_dir,
            resolve_local_index_shards,
            sync_remote_index_to_local_cache,
        )
        from raxtik_etl.indexing.middleware import apply_tier_views

        if self.remote:
            if self.index_dir and (self.index_dir / "manifest.json").exists():
                manifest, shard_uris, delta_uris = resolve_local_index_shards(self.index_dir)
            elif self.cache_index:
                manifest, shard_uris, delta_uris = sync_remote_index_to_local_cache(
                    repo_id=self.hf_repo,
                    source=self.source,
                    tier=self.tier,
                    revision=revision,
                    index_dir=self.index_dir,
                    timeout=timeout,
                )
            else:
                # 100% zero-disk fully remote mode via DuckDB httpfs
                manifest, shard_uris, delta_uris = fetch_remote_index_manifest(
                    repo_id=self.hf_repo,
                    tier=self.tier,
                    revision=revision,
                    timeout=timeout,
                )
            # Switch to writable in-memory catalog to mount views over remote bronze catalog
            self._con.execute("USE memory;")
        else:
            local_root = self.index_dir or get_default_index_dir(source=self.source, tier=self.tier)
            if (local_root / "manifest.json").exists():
                manifest, shard_uris, delta_uris = resolve_local_index_shards(local_root)
            elif download_if_missing:
                manifest, shard_uris, delta_uris = sync_remote_index_to_local_cache(
                    repo_id=self.hf_repo,
                    source=self.source,
                    tier=self.tier,
                    revision=revision,
                    index_dir=local_root,
                    timeout=timeout,
                )
            else:
                raise FileNotFoundError(
                    f"Local {self.tier} index manifest not found at {local_root / 'manifest.json'}. "
                    f"Build it using `raxtik-etl index build --tier {self.tier}` or pass `download_if_missing=True`."
                )

        self._index_shard_uris = shard_uris
        self._index_delta_uris = delta_uris
        self._index_policy = manifest.policy
        apply_tier_views(
            con=self._con,
            bronze_catalog=bronze_catalog,
            data_period=self.data_period,
            state_shard_uris=shard_uris,
            policy=manifest.policy,
            as_of_period=self.as_of_period,
            delta_uris=delta_uris,
        )

    @classmethod
    def from_hf(
        cls,
        data_period: str,
        source: Optional[str] = "faers",
        package_dir: Optional[Union[str, Path]] = None,
        hf_repo: Optional[str] = None,
        timeout: int = DEFAULT_HTTP_TIMEOUT,
        revision: Optional[str] = None,
        tier: str = "bronze",
        remote: bool = False,
        index_dir: Optional[Union[str, Path]] = None,
        cache_index: bool = False,
        as_of_period: Optional[str] = None,
    ) -> BaseDataset:
        """Loads a safety data package, automatically downloading from Hugging Face Hub if not present locally.

        Args:
            data_period: Temporal coverage period identifier (e.g., '2004Q1').
            source: Source identifier (e.g. 'faers'). Defaults to 'faers'.
            package_dir: Local destination directory for cached packages.
            hf_repo: Optional Hugging Face dataset repository override.
            timeout: HTTP request timeout in seconds.
            revision: Hugging Face Git revision or tag (defaults to version tag or 'main').
            tier: Dataset release tier ('bronze', 'silver', or future 'gold'). Defaults to 'bronze'.
            remote: If True, streams directly from Hugging Face Hub over HTTPS with zero local disk footprint.
            index_dir: Optional local directory containing a pre-built tier index.
            cache_index: When `remote=True` and `tier != 'bronze'`, caches the index locally.
            as_of_period: Optional upper-bound period for time-bounded winner resolution.

        Returns:
            Instantiated BaseDataset connected to downloaded or remotely attached DuckDB package.
        """
        return cls(
            data_period=data_period,
            source=source,
            package_dir=package_dir,
            download_if_missing=not remote,
            hf_repo=hf_repo,
            timeout=timeout,
            revision=revision,
            tier=tier,
            remote=remote,
            index_dir=index_dir,
            cache_index=cache_index,
            as_of_period=as_of_period,
        )

    def compute_sha256(self) -> str:
        """Computes streaming SHA-256 checksum of the local DuckDB package.

        Returns:
            Hexadecimal SHA-256 digest string.
        """
        if self.remote:
            raise NotImplementedError(
                "SHA-256 checksum computation requires a local file. Pass `remote=False` to download."
            )
        from raxtik_etl.packaging.builder import compute_sha256

        return compute_sha256(self.duckdb_path)

    def verify_checksum(self, expected_sha256: Optional[str] = None) -> bool:
        """Validates the package's SHA-256 checksum against an expected value or companion .sha256 file.

        Args:
            expected_sha256: Expected 64-character hexadecimal SHA-256 hash. If omitted,
                reads the companion `.duckdb.sha256` file in the same directory.

        Returns:
            True if verification succeeds, False if no expected checksum is found.

        Raises:
            ValueError: If computed checksum does not match expected checksum.
        """
        if self.remote:
            return True
        sha_file = self.duckdb_path.with_suffix(".duckdb.sha256")
        target_sha = expected_sha256
        if target_sha is None and sha_file.exists():
            target_sha = sha_file.read_text().strip().split()[0]

        if target_sha:
            actual_sha = self.compute_sha256()
            if actual_sha.lower() != target_sha.lower():
                raise ValueError(
                    f"Checksum verification failed for {self.duckdb_path.name}!\n"
                    f"Expected SHA-256: {target_sha}\n"
                    f"Actual SHA-256:   {actual_sha}"
                )
            return True
        return False

    def _validate_package_compatibility(self) -> None:
        """Validates that the package format version is compatible with this SDK version.

        Returns:
            None
        """
        try:
            rows = self._con.execute(
                "SELECT value FROM _metadata WHERE key = 'package_format_version'"
            ).fetchall()
            if rows:
                self.package_format_version = rows[0][0]
            else:
                self.package_format_version = "1.0.0"
        except Exception:
            self.package_format_version = "1.0.0"

    def query(self, sql: str) -> pl.DataFrame:
        """Executes arbitrary SQL on the package and returns a Polars DataFrame.

        Args:
            sql: SQL query string to execute against DuckDB relations.

        Returns:
            polars.DataFrame containing query results.
        """
        return self._con.sql(sql).pl()

    def _table_query(self, table: str, limit: Optional[int] = None) -> pl.DataFrame:
        limit_clause = f" LIMIT {int(limit)}" if limit is not None else ""
        return self._con.sql(f"SELECT * FROM {table}{limit_clause}").pl()  # nosec B608

    def reports(self, limit: Optional[int] = None) -> pl.DataFrame:
        """Returns the immutable historical submission reports (DEMO table).

        Args:
            limit: Optional maximum number of rows to return.

        Returns:
            polars.DataFrame containing DEMO table records.
        """
        return self._table_query("demo", limit)

    def cases(self, limit: Optional[int] = None) -> pl.DataFrame:
        """Returns the deterministic latest-case resolution view.

        Args:
            limit: Optional maximum number of rows to return.

        Returns:
            polars.DataFrame containing latest deduplicated case records.
        """
        return self._table_query("cases", limit)

    def drugs(self, limit: Optional[int] = None) -> pl.DataFrame:
        """Returns reported drug products.

        Args:
            limit: Optional maximum number of rows to return.

        Returns:
            polars.DataFrame containing DRUG table records.
        """
        return self._table_query("drug", limit)

    def reactions(self, limit: Optional[int] = None) -> pl.DataFrame:
        """Returns reported adverse events.

        Args:
            limit: Optional maximum number of rows to return.

        Returns:
            polars.DataFrame containing REAC table records.
        """
        return self._table_query("reac", limit)

    def outcomes(self, limit: Optional[int] = None) -> pl.DataFrame:
        """Returns patient outcomes.

        Args:
            limit: Optional maximum number of rows to return.

        Returns:
            polars.DataFrame containing OUTC table records.
        """
        return self._table_query("outc", limit)

    def metadata(self) -> Dict[str, str]:
        """Returns package metadata as a dictionary.

        Returns:
            Mapping of metadata keys to string values.
        """
        rows = self._con.execute("SELECT key, value FROM _metadata").fetchall()
        return dict(rows)

    def audit_report(self) -> Dict[str, str]:
        """Returns automated EDA data quality metrics.

        Returns:
            Mapping of metric names to recorded values.
        """
        rows = self._con.execute(
            "SELECT metric_name, metric_value FROM _data_quality_report"
        ).fetchall()
        return dict(rows)

    def print_summary(self) -> None:
        """Prints a rich formatted summary table of the package.

        Returns:
            None
        """
        meta = self.metadata()
        audit = self.audit_report()

        table = Table(
            title=f"{self.source.upper()} Package [{self.data_period}] Summary", style="cyan"
        )
        table.add_column("Metric / Property", style="bold white")
        table.add_column("Value", style="green")

        for k, v in meta.items():
            table.add_row(f"[Metadata] {k}", str(v))
        for k, v in audit.items():
            table.add_row(f"[Quality] {k}", str(v))

        console.print(table)

    def case_timeline(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Returns the full submission timeline for a case from the mounted tier index.

        Requires `tier != 'bronze'` (e.g. `tier='silver'`).
        """
        if self.tier == "bronze":
            raise ValueError("case_timeline() requires a derived tier index (e.g. tier='silver').")
        rows = self._con.execute(
            """
            SELECT
                case_id,
                latest_primary_id,
                latest_quarter,
                first_quarter,
                submissions_count,
                is_cross_quarter,
                resolution_tie,
                timeline
            FROM _index_state
            WHERE case_id = ?
            """,
            [case_id],
        ).fetchall()
        if not rows:
            return None
        row = rows[0]
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

    def materialize_tier(self, dest_path: Union[str, Path]) -> Path:
        """Materializes this tier-filtered dataset into a standalone portable DuckDB file."""
        if self.tier == "bronze":
            raise ValueError("materialize_tier() requires a derived tier (e.g. tier='silver').")
        if self.remote:
            raise NotImplementedError(
                "materialize_tier() requires a local Bronze package. Open with remote=False first."
            )
        if not self._index_shard_uris:
            raise RuntimeError("Tier index shards are not mounted.")
        from raxtik_etl.indexing.middleware import materialize_filtered_package

        return materialize_filtered_package(
            bronze_db_path=self.duckdb_path,
            dest_db_path=dest_path,
            data_period=self.data_period,
            state_shard_uris=self._index_shard_uris,
            policy=self._index_policy,
            tier=self.tier,
            as_of_period=self.as_of_period,
            delta_uris=self._index_delta_uris,
        )

    def close(self) -> None:
        """Closes the underlying DuckDB database connection.

        Returns:
            None
        """
        self._con.close()

    def __enter__(self) -> BaseDataset:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


@lru_cache(maxsize=16)
def get_dataset_client(source_name: str) -> Type[BaseDataset]:
    """Discovers specialized client classes registered under `raxtik_etl.clients`.

    Args:
        source_name: Lowercase source name identifier (e.g. 'faers').

    Returns:
        Registered client subclass or default BaseDataset if none is registered.
    """
    eps = entry_points(group=ENTRY_POINT_CLIENT_GROUP)
    for ep in eps:
        if ep.name == source_name.lower():
            try:
                client_cls = ep.load()
                return client_cls
            except (ImportError, AttributeError, ValueError) as err:
                logger.warning(
                    "Could not load specialized client plugin for '%s': %s", source_name, err
                )
    return BaseDataset


class Dataset(BaseDataset):
    """Canonical client that dynamically instantiates the registered source client if available."""

    source_name: str = "faers"

    def __new__(  # type: ignore[misc]
        cls,
        data_period: str,
        source: str = "faers",
        package_dir: Optional[Union[str, Path]] = None,
        download_if_missing: bool = False,
        hf_repo: Optional[str] = None,
        timeout: int = DEFAULT_HTTP_TIMEOUT,
        revision: Optional[str] = None,
        tier: str = "bronze",
        remote: bool = False,
        index_dir: Optional[Union[str, Path]] = None,
        cache_index: bool = False,
        as_of_period: Optional[str] = None,
    ) -> BaseDataset:  # type: ignore[misc]
        """Instantiates either a specialized source client subclass or BaseDataset.

        Args:
            data_period: Temporal coverage period identifier (e.g., '2004Q1').
            source: Source identifier (e.g. 'faers'). Defaults to 'faers'.
            package_dir: Local directory containing package files.
            download_if_missing: If True, downloads from Hugging Face if missing locally.
            hf_repo: Optional Hugging Face dataset repository ID override.
            timeout: HTTP request timeout in seconds.
            revision: Hugging Face Git revision or tag.
            tier: Dataset release tier ('bronze', 'silver', or future 'gold'). Defaults to 'bronze'.
            remote: If True, streams directly from Hugging Face Hub over HTTPS with zero local disk footprint.
            index_dir: Optional local directory containing a pre-built tier index.
            cache_index: When `remote=True` and `tier != 'bronze'`, caches the index locally.
            as_of_period: Optional upper-bound period for time-bounded winner resolution.

        Returns:
            Configured dataset client instance.
        """
        target_cls = get_dataset_client(source)
        if target_cls is not cls and target_cls is not BaseDataset:
            return target_cls(
                data_period=data_period,
                source=source,
                package_dir=package_dir,
                download_if_missing=download_if_missing,
                hf_repo=hf_repo,
                timeout=timeout,
                revision=revision,
                tier=tier,
                remote=remote,
                index_dir=index_dir,
                cache_index=cache_index,
                as_of_period=as_of_period,
            )
        instance = super().__new__(cls)
        return instance

    @classmethod
    def from_hf(
        cls,
        data_period: str,
        source: Optional[str] = "faers",
        package_dir: Optional[Union[str, Path]] = None,
        hf_repo: Optional[str] = None,
        timeout: int = DEFAULT_HTTP_TIMEOUT,
        revision: Optional[str] = None,
        tier: str = "bronze",
        remote: bool = False,
        index_dir: Optional[Union[str, Path]] = None,
        cache_index: bool = False,
        as_of_period: Optional[str] = None,
    ) -> BaseDataset:
        """Loads a safety data package, automatically downloading from Hugging Face Hub if not present locally.

        Args:
            data_period: Temporal coverage period identifier (e.g., '2004Q1').
            source: Source identifier (e.g. 'faers'). Defaults to 'faers'.
            package_dir: Destination directory for cached packages.
            hf_repo: Optional Hugging Face dataset repository override.
            timeout: HTTP request timeout in seconds.
            revision: Hugging Face Git revision or tag (defaults to version tag or 'main').
            tier: Dataset release tier ('bronze', 'silver', or future 'gold'). Defaults to 'bronze'.
            remote: If True, streams directly from Hugging Face Hub over HTTPS with zero local disk footprint.
            index_dir: Optional local directory containing a pre-built tier index.
            cache_index: When `remote=True` and `tier != 'bronze'`, caches the index locally.
            as_of_period: Optional upper-bound period for time-bounded winner resolution.

        Returns:
            Instantiated Dataset connected to downloaded or remotely attached DuckDB package.
        """
        src = source or "faers"
        target_cls = get_dataset_client(src)
        if (
            target_cls is not cls
            and target_cls is not BaseDataset
            and hasattr(target_cls, "from_hf")
        ):
            return target_cls.from_hf(
                data_period=data_period,
                source=src,
                package_dir=package_dir,
                hf_repo=hf_repo,
                timeout=timeout,
                revision=revision,
                tier=tier,
                remote=remote,
                index_dir=index_dir,
                cache_index=cache_index,
                as_of_period=as_of_period,
            )
        return cls(
            data_period=data_period,
            source=src,
            package_dir=package_dir,
            download_if_missing=not remote,
            hf_repo=hf_repo,
            timeout=timeout,
            revision=revision,
            tier=tier,
            remote=remote,
            index_dir=index_dir,
            cache_index=cache_index,
            as_of_period=as_of_period,
        )
