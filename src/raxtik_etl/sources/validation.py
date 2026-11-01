"""Validation helpers for raw extract files and headers."""

from __future__ import annotations

from pathlib import Path
from typing import Collection, Optional, Set, Union


def check_file_exists_and_non_empty(file_path: Union[Path, str]) -> Path:
    """Verifies that the target file exists and is not zero-byte empty.

    Args:
        file_path: Filesystem path to the file.

    Returns:
        Resolved Path object.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is 0 bytes.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Source file does not exist: {path}")
    if path.is_file() and path.stat().st_size == 0:
        raise ValueError(f"Source extract file is empty (0 bytes): {path.name}")
    return path


def read_first_line(file_path: Union[Path, str], encoding: str = "utf-8") -> str:
    """Reads and returns the first non-empty line of a text file.

    Args:
        file_path: Filesystem path to the file.
        encoding: Text file encoding (default: utf-8).

    Returns:
        Stripped string containing the first line.

    Raises:
        ValueError: If file contains no lines.
    """
    path = Path(file_path)
    with open(path, "r", encoding=encoding, errors="ignore") as f:
        line = f.readline().strip()
    if not line:
        raise ValueError(f"Source extract file '{path.name}' has no header line.")
    return line


def parse_delimited_header(header_line: str, delimiter: str = "$") -> Set[str]:
    """Splits a header line by delimiter into a set of trimmed, lowercase column names.

    Args:
        header_line: Raw header text line.
        delimiter: Separator character (default: '$').

    Returns:
        Set of lowercase column names.

    Raises:
        ValueError: If delimiter is not found in header_line or no columns parsed.
    """
    if delimiter not in header_line:
        raise ValueError(
            f"Delimiter '{delimiter}' not found in header line: '{header_line[:60]}...'"
        )
    columns = {col.strip().lower() for col in header_line.split(delimiter) if col.strip()}
    if not columns:
        raise ValueError(
            f"No valid column names parsed from header line with delimiter '{delimiter}'."
        )
    return columns


def check_required_columns(
    available_columns: Collection[str],
    required_columns: Collection[str],
    source_name: str = "file",
) -> None:
    """Asserts that all required columns are present in available columns.

    Args:
        available_columns: Collection of detected columns.
        required_columns: Collection of required columns.
        source_name: Identifier or filename for error reporting.

    Raises:
        ValueError: If one or more required columns are missing.
    """
    available_lower = {c.lower() for c in available_columns}
    missing = {c.lower() for c in required_columns} - available_lower
    if missing:
        raise ValueError(
            f"Corrupted or unexpected schema in '{source_name}': "
            f"Missing required columns {sorted(missing)}. "
            f"Detected: {sorted(list(available_lower))[:8]}..."
        )


def validate_extract_file(
    file_path: Union[Path, str],
    required_columns: Optional[Collection[str]] = None,
    delimiter: str = "$",
) -> Set[str]:
    """Validates that extract file exists, is non-empty, and contains expected headers.

    Composes check_file_exists_and_non_empty, read_first_line, parse_delimited_header,
    and check_required_columns into a single streamlined validation step.

    Args:
        file_path: Filesystem path to the text extract file.
        required_columns: Optional collection of lowercase column names that must exist.
        delimiter: Column delimiter (default '$').

    Returns:
        Set of detected lowercase column names.

    Raises:
        FileNotFoundError: If file is missing.
        ValueError: If file is empty, missing delimiter, or missing required columns.
    """
    path = check_file_exists_and_non_empty(file_path)
    header_line = read_first_line(path)
    columns = parse_delimited_header(header_line, delimiter=delimiter)
    if required_columns:
        check_required_columns(columns, required_columns, source_name=path.name)
    return columns
