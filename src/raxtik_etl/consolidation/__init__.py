"""Multi-period consolidation packaging and cross-period case deduplication engine."""

from raxtik_etl.consolidation.merger import (
    build_consolidated_package,
    get_consolidation_summary_report,
    validate_and_normalize_data_periods,
)

__all__ = [
    "build_consolidated_package",
    "get_consolidation_summary_report",
    "validate_and_normalize_data_periods",
]
