"""Canonical Schema Package for FAERS Adverse Event Data Platform."""

from raxtik_etl.schema.canonical import (
    CanonicalCase,
    CanonicalDrug,
    CanonicalIndication,
    CanonicalOutcome,
    CanonicalReaction,
    CanonicalReportSource,
    CanonicalTherapy,
    DerivationStatus,
    Provenance,
    SourcePresence,
    TransformationCategory,
    ValueOrigin,
)
from raxtik_etl.schema.registry import (
    CANONICAL_SCHEMA_VERSION,
    CASE_RESOLUTION_VERSION,
    SCHEMA_REGISTRY,
    FieldRegistryEntry,
    get_entity_fields,
    get_signature_mapping,
)
from raxtik_etl.schema.views import (
    get_active_substances_summary_view_sql,
    get_latest_cases_view_sql,
)

__all__ = [
    "CANONICAL_SCHEMA_VERSION",
    "CASE_RESOLUTION_VERSION",
    "CanonicalCase",
    "CanonicalDrug",
    "CanonicalIndication",
    "CanonicalOutcome",
    "CanonicalReaction",
    "CanonicalReportSource",
    "CanonicalTherapy",
    "DerivationStatus",
    "FieldRegistryEntry",
    "Provenance",
    "SCHEMA_REGISTRY",
    "SourcePresence",
    "TransformationCategory",
    "ValueOrigin",
    "get_active_substances_summary_view_sql",
    "get_entity_fields",
    "get_latest_cases_view_sql",
    "get_signature_mapping",
]
