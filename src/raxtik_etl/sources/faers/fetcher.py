"""Fetcher and archive extractor for FDA FAERS quarterly data dumps."""

import zipfile
from pathlib import Path
from typing import Dict, List, Optional

import requests
from tqdm import tqdm

from raxtik_etl.config import FAERS_BASE_URL, RAW_DATA_DIR
from raxtik_etl.sources.faers.parser import detect_table_type


def find_local_faers_files(directory: Path | str) -> Dict[str, List[Path]]:
    """
    Search directory recursively for FAERS ASCII files (.txt).

    Returns:
        Dict mapping table_type ('demo', 'drug', 'reac', 'outc', 'indi', etc.) to list of Paths.
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        return {}

    categorized: Dict[str, List[Path]] = {
        "demo": [],
        "drug": [],
        "reac": [],
        "outc": [],
        "indi": [],
        "ther": [],
        "rpsr": [],
    }

    for file_path in dir_path.rglob("*.txt"):
        tbl_type = detect_table_type(file_path)
        if tbl_type and tbl_type in categorized:
            categorized[tbl_type].append(file_path)

    return {k: sorted(v) for k, v in categorized.items() if v}


def download_quarterly_data(
    year: int,
    quarter: int,
    dest_dir: Optional[Path] = None,
    overwrite: bool = False,
) -> Path:
    """
    Download and extract FDA FAERS ASCII zip archive for a given year & quarter.

    Example URL: https://fis.fda.gov/content/Exports/faers_ascii_2024q1.zip

    Args:
        year: e.g. 2024
        quarter: 1, 2, 3, or 4
        dest_dir: Target extraction folder (defaults to data/raw/faers/{year}q{quarter})
        overwrite: Whether to re-download if files already exist.

    Returns:
        Path to directory containing extracted ASCII .txt files.
    """
    if quarter not in (1, 2, 3, 4):
        raise ValueError(f"Invalid quarter: {quarter}. Must be 1, 2, 3, or 4.")

    if dest_dir is None:
        target_dir = RAW_DATA_DIR / f"faers_{year}q{quarter}"
    else:
        target_dir = Path(dest_dir)

    target_dir.mkdir(parents=True, exist_ok=True)

    # Check if files already extracted
    existing_files = list(target_dir.rglob("*.txt"))
    if existing_files and not overwrite:
        return target_dir

    filename = f"faers_ascii_{year}q{quarter}.zip"
    url = f"{FAERS_BASE_URL}/{filename}"
    zip_path = target_dir / filename

    response = requests.get(url, stream=True, timeout=60)
    if response.status_code == 404:
        # Try alternate casing or naming pattern (e.g. FAERS_ASCII_2024Q1.zip)
        alt_filename = f"FAERS_ASCII_{year}Q{quarter}.zip"
        alt_url = f"{FAERS_BASE_URL}/{alt_filename}"
        response = requests.get(alt_url, stream=True, timeout=60)
        if response.status_code != 200:
            raise RuntimeError(
                f"Could not download FAERS archive from {url} or {alt_url} (HTTP {response.status_code})."
            )

    total_size = int(response.headers.get("content-length", 0))
    with (
        open(zip_path, "wb") as f,
        tqdm(
            desc=f"Downloading FAERS {year} Q{quarter}",
            total=total_size,
            unit="iB",
            unit_scale=True,
            unit_divisor=1024,
        ) as bar,
    ):
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            size = f.write(chunk)
            bar.update(size)

    # Extract zip contents
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(target_dir)

    # Optionally clean up zip file
    if zip_path.exists():
        zip_path.unlink()

    return target_dir
