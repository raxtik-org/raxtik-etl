"""Canonical Schema Package for FAERS Adverse Event Data Platform."""

from raxtik_etl.schema.canonical import (
    CANONICAL_MODELS,
    BaseCanonicalModel,
    CanonicalCase,
    CanonicalDrug,
    CanonicalIndication,
    CanonicalOutcome,
    CanonicalReaction,
    CanonicalReportSource,
    CanonicalTherapy,
    Column,
    ColumnInfo,
    DerivationStatus,
    FieldRegistryEntry,
    Provenance,
    SourcePresence,
    TransformationCategory,
    ValueOrigin,
)
from raxtik_etl.schema.registry import (
    CANONICAL_ENTITIES,
    CANONICAL_SCHEMA_VERSION,
    CANONICAL_TABLES,
    SCHEMA_REGISTRY,
    get_entity_fields,
)
from raxtik_etl.schema.views import (
    get_active_substances_summary_view_sql,
    get_latest_cases_view_sql,
)

__all__ = [
    "CANONICAL_ENTITIES",
    "CANONICAL_MODELS",
    "CANONICAL_SCHEMA_VERSION",
    "CANONICAL_TABLES",
    "BaseCanonicalModel",
    "CanonicalCase",
    "CanonicalDrug",
    "CanonicalIndication",
    "CanonicalOutcome",
    "CanonicalReaction",
    "CanonicalReportSource",
    "CanonicalTherapy",
    "Column",
    "ColumnInfo",
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
]
