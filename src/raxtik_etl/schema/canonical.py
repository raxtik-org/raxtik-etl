"""Canonical Schema Models for FAERS Adverse Event Data Platform.

This module re-exports all canonical entities, base descriptors, and enums from
`raxtik_etl.schema.base` and `raxtik_etl.schema.models` for centralized, backward-compatible access.
"""

from __future__ import annotations

from raxtik_etl.schema.base import (
    BaseCanonicalModel,
    Column,
    ColumnInfo,
    DerivationStatus,
    FieldRegistryEntry,
    Provenance,
    SourcePresence,
    TransformationCategory,
    ValueOrigin,
)
from raxtik_etl.schema.models import (
    CANONICAL_MODELS,
    CanonicalCase,
    CanonicalDrug,
    CanonicalIndication,
    CanonicalOutcome,
    CanonicalReaction,
    CanonicalReportSource,
    CanonicalTherapy,
)

__all__ = [
    "CANONICAL_MODELS",
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
    "SourcePresence",
    "TransformationCategory",
    "ValueOrigin",
]
