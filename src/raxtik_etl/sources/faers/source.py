"""dlt source definition for FDA FAERS datasets."""

from pathlib import Path
from typing import Dict, List, Optional, Union

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
    files_map: Optional[Dict[str, List[Path]]] = None,
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
    if files_map is None:
        source_dir = Path(data_dir) if data_dir else RAW_DATA_DIR
        files_map = find_local_faers_files(source_dir)

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
        if tbl_name in requested_tables and tbl_name in files_map and files_map[tbl_name]:
            found_any = True
            yield factory(files=files_map[tbl_name])

    if not found_any:
        # If no files found, still yield an empty resource to allow dlt introspection
        pass
