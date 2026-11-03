"""Temporal identifier normalization, validation, and quarterly arithmetic.

Provides standardized quarterly parsing, formatting, and range generation
for all quarterly adverse event datasets (FAERS, VAERS quarterly, etc.).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Sequence, Tuple, Union


def parse_quarter(period_or_filename: Union[str, Path]) -> Tuple[int, int]:
    """Extracts (year, quarter) integers from a quarterly identifier string or filename.

    Supports inputs such as '2004Q1', '2004q1', or 'faers_ascii_2004q1.zip'.

    Args:
        period_or_filename: String or Path containing a 4-digit year and 1-digit quarter.

    Returns:
        Tuple of (year, quarter).

    Raises:
        ValueError: If input does not match expected quarterly format (YYYYqQ).
    """
    match = re.search(r"(\d{4})[-_]?[qQ]([1-4])", str(period_or_filename))
    if not match:
        raise ValueError(
            f"Invalid quarterly format: '{period_or_filename}'. Expected format like '2004Q1'."
        )
    return int(match.group(1)), int(match.group(2))


def format_quarter(year: int, quarter: int) -> str:
    """Formats year and quarter integers into standardized uppercase string (e.g. '2004Q1').

    Args:
        year: 4-digit calendar year.
        quarter: Quarter integer (1-4).

    Returns:
        Standardized quarter identifier.
    """
    return f"{year}Q{quarter}"


def normalize_quarter(period_or_filename: Union[str, Path]) -> str:
    """Parses and formats any quarterly identifier or filename into standard uppercase 'YYYYQQ' (e.g. '2004Q1').

    Args:
        period_or_filename: String or Path containing a 4-digit year and 1-digit quarter.

    Returns:
        Standardized uppercase quarter string (e.g. '2004Q1').

    Raises:
        ValueError: If input cannot be parsed as a valid quarter.
    """
    year, quarter = parse_quarter(period_or_filename)
    return format_quarter(year, quarter)


def is_valid_quarter(period_or_filename: Union[str, Path]) -> bool:
    """Checks whether a given identifier or filename represents a valid quarterly dataset period.

    Args:
        period_or_filename: String or Path to validate.

    Returns:
        True if period is valid, False otherwise.
    """
    try:
        parse_quarter(period_or_filename)
        return True
    except ValueError:
        return False


def parse_quarter_range(start_quarter: str, end_quarter: str) -> List[str]:
    """Generates an inclusive list of quarterly releases between start and end (e.g. '2004Q1' to '2006Q4').

    Args:
        start_quarter: Starting period identifier (e.g. '2004Q1').
        end_quarter: Ending period identifier (e.g. '2006Q4').

    Returns:
        List of period identifier strings from start to end inclusive.
    """
    start_y, start_q = parse_quarter(start_quarter)
    end_y, end_q = parse_quarter(end_quarter)

    quarters: List[str] = []
    y, q = start_y, start_q
    while (y < end_y) or (y == end_y and q <= end_q):
        quarters.append(format_quarter(y, q))
        q += 1
        if q > 4:
            q = 1
            y += 1
    return quarters


def validate_and_normalize_data_periods(data_periods: Sequence[str]) -> List[str]:
    """Validates period inputs, ensuring non-empty, valid format, deduplicated, and chronologically ordered.

    Args:
        data_periods: Sequence of temporal period identifiers (e.g., ['2004Q1', '2005Q2']).

    Returns:
        List of deduplicated, chronologically sorted period strings.

    Raises:
        ValueError: If data_periods is empty or contains malformed period formats.
    """
    if not data_periods:
        raise ValueError("Data periods list cannot be empty. Please provide at least one period.")

    normalized: List[str] = []
    seen = set()

    for p in data_periods:
        clean = normalize_quarter(p)
        if clean not in seen:
            seen.add(clean)
            normalized.append(clean)

    # Sort chronologically by year and quarter
    normalized.sort(key=lambda x: parse_quarter(x))
    return normalized
