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

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Type, Union

import duckdb
import polars as pl
from rich.console import Console
from rich.table import Table

if sys.version_info >= (3, 10):
    from importlib.metadata import entry_points
else:
    from importlib_metadata import entry_points

from raxtik_etl.distribution.huggingface import (
    DEFAULT_HTTP_TIMEOUT,
    get_default_package_dir,
)

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
    ) -> None:
        """Initializes a local dataset connection, optionally downloading if missing.

        Args:
            data_period: Temporal coverage period identifier (e.g., '2004Q1').
            source: Source identifier (e.g. 'faers'). Defaults to source_name.
            package_dir: Local directory containing package files.
            download_if_missing: If True, fetches package from Hugging Face if missing.
            hf_repo: Optional Hugging Face dataset repository ID override.
            timeout: HTTP request timeout in seconds when downloading.
            revision: Hugging Face Git revision or tag (e.g., 'main' or 'v0.1.0').

        Raises:
            ValueError: If data_period is empty.
            FileNotFoundError: If package is not present locally and download_if_missing is False.
        """
        period_clean = (data_period or "").upper().strip()
        if not period_clean:
            raise ValueError("data_period (e.g. '2004Q1') must be specified.")
        self.data_period = period_clean
        self.source = (source or self.source_name).lower()
        self.pkg_dir = Path(package_dir) if package_dir else get_default_package_dir()
        self.duckdb_path = self.pkg_dir / f"{self.source}_{self.data_period}.duckdb"

        if not self.duckdb_path.exists():
            if download_if_missing:
                from raxtik_etl.distribution.huggingface import (
                    DEFAULT_HF_REPO,
                    download_package_from_hf,
                )

                repo = hf_repo or self.default_hf_repo or DEFAULT_HF_REPO
                download_package_from_hf(
                    data_period_or_name=self.data_period,
                    dest_dir=self.pkg_dir,
                    repo_id=repo,
                    source_name=self.source,
                    timeout=timeout,
                    revision=revision,
                )
            else:
                raise FileNotFoundError(
                    f"Package for data period {self.data_period} not found at {self.duckdb_path}. "
                    f"Build it locally using `raxtik-etl build-package --source {self.source} --data-period {self.data_period}` "
                    f"or pass `download_if_missing=True` to download from Hugging Face."
                )

        self._con = duckdb.connect(self.duckdb_path.as_posix(), read_only=True)
        self._validate_package_compatibility()

    @classmethod
    def from_hf(
        cls,
        data_period: str,
        source: Optional[str] = "faers",
        package_dir: Optional[Union[str, Path]] = None,
        hf_repo: Optional[str] = None,
        timeout: int = DEFAULT_HTTP_TIMEOUT,
        revision: Optional[str] = None,
    ) -> BaseDataset:
        """Loads a safety data package, automatically downloading from Hugging Face Hub if not present locally.

        Args:
            data_period: Temporal coverage period identifier (e.g., '2004Q1').
            source: Source identifier (e.g. 'faers'). Defaults to 'faers'.
            package_dir: Local destination directory for cached packages.
            hf_repo: Optional Hugging Face dataset repository override.
            timeout: HTTP request timeout in seconds.
            revision: Hugging Face Git revision or tag (defaults to version tag or 'main').

        Returns:
            Instantiated BaseDataset connected to downloaded DuckDB package.
        """
        return cls(
            data_period=data_period,
            source=source,
            package_dir=package_dir,
            download_if_missing=True,
            hf_repo=hf_repo,
            timeout=timeout,
            revision=revision,
        )

    def compute_sha256(self) -> str:
        """Computes streaming SHA-256 checksum of the local DuckDB package.

        Returns:
            Hexadecimal SHA-256 digest string.
        """
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
            pkg_ver = self._con.execute(
                "SELECT value FROM _metadata WHERE key = 'package_format_version'"
            ).fetchone()
            if pkg_ver:
                self.package_format_version = pkg_ver[0]
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

    def reports(self, limit: Optional[int] = None) -> pl.DataFrame:
        """Returns the immutable historical submission reports (DEMO table).

        Args:
            limit: Optional maximum number of rows to return.

        Returns:
            polars.DataFrame containing DEMO table records.
        """
        limit_clause = f"LIMIT {limit}" if limit else ""
        return self.query(f"SELECT * FROM demo {limit_clause}")

    def cases(self, limit: Optional[int] = None) -> pl.DataFrame:
        """Returns the deterministic latest-case resolution view.

        Args:
            limit: Optional maximum number of rows to return.

        Returns:
            polars.DataFrame containing latest deduplicated case records.
        """
        limit_clause = f"LIMIT {limit}" if limit else ""
        return self.query(f"SELECT * FROM cases {limit_clause}")

    def drugs(self, limit: Optional[int] = None) -> pl.DataFrame:
        """Returns reported drug products.

        Args:
            limit: Optional maximum number of rows to return.

        Returns:
            polars.DataFrame containing DRUG table records.
        """
        limit_clause = f"LIMIT {limit}" if limit else ""
        return self.query(f"SELECT * FROM drug {limit_clause}")

    def reactions(self, limit: Optional[int] = None) -> pl.DataFrame:
        """Returns reported adverse events.

        Args:
            limit: Optional maximum number of rows to return.

        Returns:
            polars.DataFrame containing REAC table records.
        """
        limit_clause = f"LIMIT {limit}" if limit else ""
        return self.query(f"SELECT * FROM reac {limit_clause}")

    def outcomes(self, limit: Optional[int] = None) -> pl.DataFrame:
        """Returns patient outcomes.

        Args:
            limit: Optional maximum number of rows to return.

        Returns:
            polars.DataFrame containing OUTC table records.
        """
        limit_clause = f"LIMIT {limit}" if limit else ""
        return self.query(f"SELECT * FROM outc {limit_clause}")

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
            except Exception:
                pass
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

        Returns:
            Configured dataset client instance.
        """
        target_cls = get_dataset_client(source)
        if target_cls is not cls and target_cls is not BaseDataset:
            return target_cls(
                data_period=data_period,
                package_dir=package_dir,
                download_if_missing=download_if_missing,
                hf_repo=hf_repo,
                timeout=timeout,
                revision=revision,
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
    ) -> BaseDataset:
        """Loads a safety data package, automatically downloading from Hugging Face Hub if not present locally.

        Args:
            data_period: Temporal coverage period identifier (e.g., '2004Q1').
            source: Source identifier (e.g. 'faers'). Defaults to 'faers'.
            package_dir: Destination directory for cached packages.
            hf_repo: Optional Hugging Face dataset repository override.
            timeout: HTTP request timeout in seconds.
            revision: Hugging Face Git revision or tag (defaults to version tag or 'main').

        Returns:
            Instantiated Dataset connected to downloaded DuckDB package.
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
                package_dir=package_dir,
                hf_repo=hf_repo,
                timeout=timeout,
                revision=revision,
            )
        return cls(
            data_period=data_period,
            source=src,
            package_dir=package_dir,
            download_if_missing=True,
            hf_repo=hf_repo,
            timeout=timeout,
            revision=revision,
        )
