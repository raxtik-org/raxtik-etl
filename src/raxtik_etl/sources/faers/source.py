"""dlt source definition for FDA FAERS datasets."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import dlt

from raxtik_etl.config import RAW_DATA_DIR
from raxtik_etl.sources.faers.fetcher import find_local_faers_files
from raxtik_etl.sources.faers.resources import (
    demo_resource,
    drug_resource,
    indi_resource,
    outc_resource,
    reac_resource,
)


@dlt.source(name="faers")
def faers_source(
    data_dir: Optional[Union[Path, str]] = None,
    files_map: Optional[Any] = None,
    tables: Optional[List[str]] = None,
):
    """
    DLT source for loading FAERS ASCII data.

    Args:
        data_dir: Directory containing FAERS raw .txt files.
        files_map: Optional direct mapping of table_type -> list of file Paths.
        tables: List of tables to include (e.g. ['demo', 'drug', 'reac', 'outc', 'indi']).

    Yields:
        Configured dlt resources.
    """
    active_files: Dict[str, Any]
    if files_map is None:
        source_dir = Path(data_dir) if data_dir else RAW_DATA_DIR
        active_files = find_local_faers_files(source_dir)
    else:
        active_files = files_map

    requested_tables = set(tables) if tables else {"demo", "drug", "reac", "outc", "indi"}

    resource_factories = {
        "demo": demo_resource,
        "drug": drug_resource,
        "reac": reac_resource,
        "outc": outc_resource,
        "indi": indi_resource,
    }

    found_any = False
    for tbl_name, factory in resource_factories.items():
        if tbl_name in requested_tables and tbl_name in active_files and active_files[tbl_name]:
            found_any = True
            yield factory(files=active_files[tbl_name])

    if not found_any:
        # If no files found, still yield an empty resource to allow dlt introspection
        pass
