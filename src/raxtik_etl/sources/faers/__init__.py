"""FAERS ingestion modules for dlt."""

from raxtik_etl.sources.faers.fetcher import download_quarterly_data, find_local_faers_files
from raxtik_etl.sources.faers.parser import detect_table_type, parse_faers_ascii_file
from raxtik_etl.sources.faers.source import faers_source

__all__ = [
    "faers_source",
    "parse_faers_ascii_file",
    "detect_table_type",
    "download_quarterly_data",
    "find_local_faers_files",
]
