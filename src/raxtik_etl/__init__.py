"""raxtik-etl: High-performance canonical pharmacovigilance data engine and packaging toolkit."""

from typing import Any

__version__ = "0.1.0"

from raxtik_etl.distribution import get_default_package_dir  # noqa: E402
from raxtik_etl.sdk import BaseDataset, Dataset, get_dataset_client  # noqa: E402

__all__ = [
    "BaseDataset",
    "Dataset",
    "FAERS",
    "get_dataset_client",
    "get_default_package_dir",
    "__version__",
]


def __getattr__(name: str) -> Any:
    if name == "FAERS":
        return get_dataset_client("faers")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
