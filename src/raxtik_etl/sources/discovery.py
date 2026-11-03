"""File discovery and entity categorization utilities.

Scans local directories and groups source extract files into canonical entities
based on prefix mappings or pattern matchers.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Union

from raxtik_etl.sources.temporal import normalize_quarter


def find_files_by_entity(
    directory: Union[Path, str],
    prefix_to_entity: Mapping[str, str],
    pattern: str = "*.txt",
) -> Dict[str, List[Path]]:
    """Recursively search directory and categorize files matching prefix mapping.

    Searches subdirectories recursively and matches file patterns
    case-insensitively (e.g. matching both .txt and .TXT).

    Args:
        directory: Directory path to scan.
        prefix_to_entity: Mapping from uppercase filename prefix to canonical entity name.
        pattern: Glob pattern to filter candidates (default: '*.txt').

    Returns:
        Dict mapping canonical entity name to a sorted list of matching Path objects.
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        return {}

    categorized: Dict[str, List[Path]] = {entity: [] for entity in prefix_to_entity.values()}

    for file_path in dir_path.rglob("*"):
        if not file_path.is_file():
            continue
        if pattern and not fnmatch.fnmatch(file_path.name.lower(), pattern.lower()):
            continue
        name = file_path.name.upper()
        for prefix, entity in prefix_to_entity.items():
            if name.startswith(prefix.upper()):
                categorized[entity].append(file_path)
                break

    return {k: sorted(v) for k, v in categorized.items() if v}


def find_cached_archive(
    directory: Union[Path, str],
    data_period: str,
    source_name: Optional[str] = None,
) -> Optional[Path]:
    """Finds an existing cached zip archive for a quarterly data period.

    Supports source-partitioned cache directories (e.g. `raw_archives/faers/`)
    as well as flat archive directories.

    Args:
        directory: Directory containing raw archives.
        data_period: Quarterly period string (e.g. '2004Q1').
        source_name: Optional source connector name (e.g. 'faers').

    Returns:
        Path to matching archive file, or None if not found.
    """
    base_dir = Path(directory)
    if not base_dir.exists():
        return None

    search_dirs: list[Path] = []
    if source_name:
        source_dir = base_dir / source_name.lower().strip()
        if source_dir.is_dir():
            search_dirs.append(source_dir)
    search_dirs.append(base_dir)

    try:
        target_period = normalize_quarter(data_period)
    except ValueError:
        return None

    for s_dir in search_dirs:
        for f in s_dir.iterdir():
            if not f.is_file() or not f.name.lower().endswith(".zip") or f.stat().st_size == 0:
                continue
            try:
                if normalize_quarter(f.name) == target_period:
                    return f
            except ValueError:
                continue
    return None
