"""Data sources framework, protocols, base adapters, and generic connectors for raxtik-etl."""

from raxtik_etl.sources.base import BaseSourceAdapter
from raxtik_etl.sources.discovery import find_files_by_entity
from raxtik_etl.sources.network import download_file, stream_download
from raxtik_etl.sources.parser import clean_field_name, detect_file_entity, parse_delimited_file
from raxtik_etl.sources.protocol import SourceAdapter, SourceArtifact, SourceLoadResult
from raxtik_etl.sources.registry import (
    SourcePluginNotFoundError,
    get_available_sources,
    get_source_adapter,
)
from raxtik_etl.sources.temporal import (
    format_quarter,
    is_valid_quarter,
    normalize_quarter,
    parse_quarter,
    parse_quarter_range,
    validate_and_normalize_data_periods,
)
from raxtik_etl.sources.validation import (
    check_file_exists_and_non_empty,
    check_required_columns,
    parse_delimited_header,
    read_first_line,
    validate_extract_file,
)

__all__ = [
    "BaseSourceAdapter",
    "SourceAdapter",
    "SourceArtifact",
    "SourceLoadResult",
    "SourcePluginNotFoundError",
    "get_available_sources",
    "get_source_adapter",
    "format_quarter",
    "is_valid_quarter",
    "normalize_quarter",
    "parse_quarter",
    "parse_quarter_range",
    "validate_and_normalize_data_periods",
    "download_file",
    "stream_download",
    "find_files_by_entity",
    "clean_field_name",
    "detect_file_entity",
    "parse_delimited_file",
    "check_file_exists_and_non_empty",
    "read_first_line",
    "parse_delimited_header",
    "check_required_columns",
    "validate_extract_file",
]
