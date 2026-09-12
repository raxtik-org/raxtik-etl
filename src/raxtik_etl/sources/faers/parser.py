"""Streaming parser for FDA FAERS $-delimited ASCII data files."""

import csv
import re
from pathlib import Path
from typing import Any, Dict, Generator, Optional


def detect_table_type(filename_or_path: str | Path) -> Optional[str]:
    """Detect FAERS table type (demo, drug, reac, outc, indi) from filename."""
    name = Path(filename_or_path).name.upper()
    if name.startswith("DEMO"):
        return "demo"
    elif name.startswith("DRUG"):
        return "drug"
    elif name.startswith("REAC"):
        return "reac"
    elif name.startswith("OUTC"):
        return "outc"
    elif name.startswith("INDI"):
        return "indi"
    elif name.startswith("THER"):
        return "ther"
    elif name.startswith("RPSR"):
        return "rpsr"
    return None


def _clean_field_name(name: str) -> str:
    """Normalize header field names to snake_case lowercase."""
    name = name.strip().lower()
    name = re.sub(r"[^\w]+", "_", name)
    name = re.sub(r"^_+|_+$", "", name)
    return name


def parse_faers_ascii_file(
    file_path: Path | str,
    table_type: Optional[str] = None,
    chunk_size: int = 10000,
) -> Generator[Dict[str, Any], None, None]:
    """
    Stream and parse a $-delimited FAERS ASCII file.

    Args:
        file_path: Path to the .txt ASCII file.
        table_type: Optional table type hint (demo, drug, reac, outc, indi).
        chunk_size: Batch yielding size if needed.

    Yields:
        Standardized dictionary for each record.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"FAERS ASCII file not found: {path}")

    # Fallback encoding list common for FDA FAERS dumps
    encodings = ["utf-8", "iso-8859-1", "latin-1", "cp1252"]

    file_obj = None
    for enc in encodings:
        try:
            file_obj = open(path, "r", encoding=enc, errors="replace")
            # Peek first line
            _ = file_obj.readline()
            file_obj.seek(0)
            break
        except Exception:
            if file_obj:
                file_obj.close()
                file_obj = None

    if file_obj is None:
        raise ValueError(f"Could not open {path} with supported encodings.")

    try:
        reader = csv.reader(file_obj, delimiter="$", quotechar=None)

        headers = None
        for row_idx, row in enumerate(reader):
            if not row or all(c.strip() == "" for c in row):
                continue

            # First non-empty row is header
            if headers is None:
                headers = [_clean_field_name(col) for col in row]
                continue

            # Check for repeated header rows within files
            if len(row) == len(headers) and row[0].strip().lower() == headers[0]:
                continue

            # Build record dict
            record: Dict[str, Any] = {}
            for idx, col_name in enumerate(headers):
                if idx < len(row):
                    val = row[idx].strip()
                    record[col_name] = val if val != "" else None
                else:
                    record[col_name] = None

            # Provide table_type tag if specified
            if table_type:
                record["_table_type"] = table_type

            yield record
    finally:
        file_obj.close()
