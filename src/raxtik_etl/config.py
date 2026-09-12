"""Global configuration and directory paths for raxtik-etl."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Base data directories
DATA_DIR = Path(os.getenv("RAXTIK_DATA_DIR", PROJECT_ROOT / "data"))
RAW_DATA_DIR = DATA_DIR / "raw"
INTERMEDIATE_DATA_DIR = DATA_DIR / "intermediate"
OUTPUT_DATA_DIR = DATA_DIR / "output"

# DuckDB intermediate database
DEFAULT_DUCKDB_PATH = INTERMEDIATE_DATA_DIR / "faers.duckdb"

# Exporter output paths
DEFAULT_SQLITE_PATH = OUTPUT_DATA_DIR / "faers_seed.sqlite"
DEFAULT_PARQUET_DIR = OUTPUT_DATA_DIR / "parquet"

# FAERS configuration
FAERS_TABLE_TYPES = ["demo", "drug", "reac", "outc", "indi"]
FAERS_BASE_URL = "https://fis.fda.gov/content/Exports"


def ensure_directories():
    """Ensure that standard data directories exist."""
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    INTERMEDIATE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DATA_DIR.mkdir(parents=True, exist_ok=True)
