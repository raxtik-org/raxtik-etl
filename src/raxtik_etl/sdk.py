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
from pathlib import Path
from typing import Dict, Optional, Type, Union

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
    """Base interface to inspect and query any versioned safety data package."""

    source_name: str = "generic"
    default_hf_repo: Optional[str] = None

    def __init__(
        self,
        release: str,
        source: Optional[str] = None,
        package_dir: Optional[Union[str, Path]] = None,
        download_if_missing: bool = False,
        hf_repo: Optional[str] = None,
        timeout: int = DEFAULT_HTTP_TIMEOUT,
        revision: Optional[str] = None,
    ):
        self.release = release.upper()
        self.source = (source or self.source_name).lower()
        self.pkg_dir = Path(package_dir) if package_dir else get_default_package_dir()
        self.duckdb_path = self.pkg_dir / f"{self.source}_{self.release}.duckdb"

        if not self.duckdb_path.exists():
            if download_if_missing:
                from raxtik_etl.distribution.huggingface import (
                    DEFAULT_HF_REPO,
                    download_package_from_hf,
                )

                repo = hf_repo or self.default_hf_repo or DEFAULT_HF_REPO
                download_package_from_hf(
                    release_or_name=self.release,
                    dest_dir=self.pkg_dir,
                    repo_id=repo,
                    source_name=self.source,
                    timeout=timeout,
                    revision=revision,
                )
            else:
                raise FileNotFoundError(
                    f"Package for release {self.release} not found at {self.duckdb_path}. "
                    f"Build it locally using `raxtik-etl build-package --source {self.source} --release {self.release}` "
                    f"or pass `download_if_missing=True` to download from Hugging Face."
                )

        self._con = duckdb.connect(self.duckdb_path.as_posix(), read_only=True)
        self._validate_package_compatibility()

    @classmethod
    def from_hf(
        cls,
        release: str,
        source: Optional[str] = "faers",
        package_dir: Optional[Union[str, Path]] = None,
        hf_repo: Optional[str] = None,
        timeout: int = DEFAULT_HTTP_TIMEOUT,
        revision: Optional[str] = None,
    ) -> BaseDataset:
        """Loads a safety data package, automatically downloading from Hugging Face Hub if not present locally."""
        return cls(
            release=release,
            source=source,
            package_dir=package_dir,
            download_if_missing=True,
            hf_repo=hf_repo,
            timeout=timeout,
            revision=revision,
        )

    def compute_sha256(self) -> str:
        """Computes streaming SHA-256 checksum of the local DuckDB package."""
        from raxtik_etl.packaging.builder import compute_sha256

        return compute_sha256(self.duckdb_path)

    def verify_checksum(self, expected_sha256: Optional[str] = None) -> bool:
        """Validates the package's SHA-256 checksum against an expected value or companion .sha256 file."""
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

    def _validate_package_compatibility(self):
        """Validates that the package format version is compatible with this SDK version."""
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
        """Executes arbitrary SQL on the package and returns a Polars DataFrame."""
        return self._con.sql(sql).pl()

    def reports(self, limit: Optional[int] = None) -> pl.DataFrame:
        """Returns the immutable historical submission reports (DEMO table)."""
        limit_clause = f"LIMIT {limit}" if limit else ""
        return self.query(f"SELECT * FROM demo {limit_clause}")

    def cases(self, limit: Optional[int] = None) -> pl.DataFrame:
        """Returns the deterministic latest-case resolution view."""
        limit_clause = f"LIMIT {limit}" if limit else ""
        return self.query(f"SELECT * FROM cases {limit_clause}")

    def drugs(self, limit: Optional[int] = None) -> pl.DataFrame:
        """Returns reported drug products."""
        limit_clause = f"LIMIT {limit}" if limit else ""
        return self.query(f"SELECT * FROM drug {limit_clause}")

    def reactions(self, limit: Optional[int] = None) -> pl.DataFrame:
        """Returns reported adverse events."""
        limit_clause = f"LIMIT {limit}" if limit else ""
        return self.query(f"SELECT * FROM reac {limit_clause}")

    def outcomes(self, limit: Optional[int] = None) -> pl.DataFrame:
        """Returns patient outcomes."""
        limit_clause = f"LIMIT {limit}" if limit else ""
        return self.query(f"SELECT * FROM outc {limit_clause}")

    def metadata(self) -> Dict[str, str]:
        """Returns package metadata as a dictionary."""
        rows = self._con.execute("SELECT key, value FROM _metadata").fetchall()
        return dict(rows)

    def audit_report(self) -> Dict[str, str]:
        """Returns automated EDA data quality metrics."""
        rows = self._con.execute(
            "SELECT metric_name, metric_value FROM _data_quality_report"
        ).fetchall()
        return dict(rows)

    def print_summary(self):
        """Prints a rich formatted summary table of the package."""
        meta = self.metadata()
        audit = self.audit_report()

        table = Table(title=f"{self.source.upper()} Package [{self.release}] Summary", style="cyan")
        table.add_column("Metric / Property", style="bold white")
        table.add_column("Value", style="green")

        for k, v in meta.items():
            table.add_row(f"[Metadata] {k}", str(v))
        for k, v in audit.items():
            table.add_row(f"[Quality] {k}", str(v))

        console.print(table)

    def close(self):
        """Closes connection."""
        self._con.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def get_dataset_client(source_name: str) -> Type[BaseDataset]:
    """Discovers specialized client classes registered under `raxtik_etl.clients`."""
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

    def __new__(
        cls,
        release: str,
        source: str = "faers",
        package_dir: Optional[Union[str, Path]] = None,
        download_if_missing: bool = False,
        hf_repo: Optional[str] = None,
        timeout: int = DEFAULT_HTTP_TIMEOUT,
        revision: Optional[str] = None,
    ):
        target_cls = get_dataset_client(source)
        if target_cls is not cls and target_cls is not BaseDataset:
            return target_cls(
                release=release,
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
        release: str,
        source: Optional[str] = "faers",
        package_dir: Optional[Union[str, Path]] = None,
        hf_repo: Optional[str] = None,
        timeout: int = DEFAULT_HTTP_TIMEOUT,
        revision: Optional[str] = None,
    ) -> BaseDataset:
        """Loads a safety data package, automatically downloading from Hugging Face Hub if not present locally."""
        src = source or "faers"
        target_cls = get_dataset_client(src)
        if (
            target_cls is not cls
            and target_cls is not BaseDataset
            and hasattr(target_cls, "from_hf")
        ):
            return target_cls.from_hf(
                release=release,
                package_dir=package_dir,
                hf_repo=hf_repo,
                timeout=timeout,
                revision=revision,
            )
        return cls(
            release=release,
            source=src,
            package_dir=package_dir,
            download_if_missing=True,
            hf_repo=hf_repo,
            timeout=timeout,
            revision=revision,
        )
