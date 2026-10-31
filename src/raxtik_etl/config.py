"""Global configuration and directory paths for raxtik-etl."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Base data directories
DATA_DIR = Path(os.getenv("RAXTIK_DATA_DIR", PROJECT_ROOT / "data"))
RAW_DATA_DIR = DATA_DIR / "raw"
INTERMEDIATE_DATA_DIR = DATA_DIR / "intermediate"
OUTPUT_DATA_DIR = DATA_DIR / "output"

# Exporter output paths
DEFAULT_DUCKDB_PATH = INTERMEDIATE_DATA_DIR / "raxtik.duckdb"
DEFAULT_SQLITE_PATH = OUTPUT_DATA_DIR / "raxtik_seed.sqlite"
DEFAULT_PARQUET_DIR = OUTPUT_DATA_DIR / "parquet"


def ensure_directories() -> None:
    """Ensure that standard data directories exist.

    Returns:
        None
    """
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    INTERMEDIATE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DATA_DIR.mkdir(parents=True, exist_ok=True)
