"""File discovery and entity categorization utilities.

Scans local directories and groups source extract files into canonical entities
based on prefix mappings or pattern matchers.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Dict, List, Mapping, Union


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
