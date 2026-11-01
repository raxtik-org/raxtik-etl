"""Delimited file streaming parser with robust multi-encoding fallback.

Parses arbitrary delimited files (CSV, TSV, dollar-delimited, etc.) into clean
dictionary records with normalized snake_case column names.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict, Generator, List, Mapping, Optional, Union


def clean_field_name(name: str) -> str:
    """Normalize header field names to snake_case lowercase.

    Args:
        name: Raw header string from file.

    Returns:
        Cleaned lowercase snake_case column identifier.
    """
    name = name.strip().lower()
    name = re.sub(r"[^\w]+", "_", name)
    name = re.sub(r"^_+|_+$", "", name)
    return name


def detect_file_entity(
    filename_or_path: Union[str, Path],
    prefix_mapping: Mapping[str, str],
) -> Optional[str]:
    """Detect canonical entity from a filename using prefix mapping.

    Args:
        filename_or_path: Filename string or Path to inspect.
        prefix_mapping: Mapping from prefix to canonical entity name.

    Returns:
        Canonical entity name or None if unrecognized.
    """
    name = Path(filename_or_path).name.upper()
    for prefix, entity in prefix_mapping.items():
        if name.startswith(prefix.upper()):
            return entity
    return None


def parse_delimited_file(
    file_path: Union[Path, str],
    delimiter: str = "$",
    table_type: Optional[str] = None,
    encodings: Optional[List[str]] = None,
    prefix_mapping: Optional[Mapping[str, str]] = None,
) -> Generator[Dict[str, Any], None, None]:
    """Stream and parse any delimited text file into normalized dictionary records.

    Handles encoding fallbacks (utf-8, iso-8859-1, latin-1, cp1252) and standardizes
    field names to lowercase snake_case.

    Args:
        file_path: Path to the delimited text file.
        delimiter: Column delimiter character (e.g. '$', ',', '\t').
        table_type: Optional canonical table name hint.
        encodings: Optional list of encodings to attempt.
        prefix_mapping: Optional prefix mapping for table type detection.

    Yields:
        Standardized record dictionary.

    Raises:
        FileNotFoundError: If file_path does not exist.
        OSError: If file cannot be read using supported encodings.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Delimited file not found: {path}")

    resolved_table_type = table_type
    if not resolved_table_type and prefix_mapping:
        resolved_table_type = detect_file_entity(path, prefix_mapping)

    encoding_list = encodings or ["utf-8", "iso-8859-1", "latin-1", "cp1252"]
    file_obj = None

    for enc in encoding_list:
        try:
            file_obj = open(path, "r", encoding=enc, errors="replace")
            file_obj.readline()
            file_obj.seek(0)
            break
        except Exception:
            if file_obj:
                file_obj.close()
                file_obj = None

    if file_obj is None:
        raise OSError(f"Unable to open {path} with any supported encoding.")

    try:
        reader = csv.reader(file_obj, delimiter=delimiter, quoting=csv.QUOTE_NONE)
        raw_headers = next(reader, None)
        if not raw_headers:
            return

        headers = [clean_field_name(h) for h in raw_headers]

        for row in reader:
            if not row or not any(row):
                continue

            record: Dict[str, Any] = {}
            for i, val in enumerate(row):
                if i < len(headers):
                    v = val.strip() if val else None
                    record[headers[i]] = v if v != "" else None

            if resolved_table_type:
                record["_table_type"] = resolved_table_type

            yield record

    finally:
        file_obj.close()
