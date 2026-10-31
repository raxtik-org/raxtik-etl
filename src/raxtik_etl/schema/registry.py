"""Canonical Schema Registry and Metadata Specifications.

Provides a machine-readable catalog of all canonical entities, field definitions,
supported data types, nullability rules, value origins, transformation categories,
and field descriptions dynamically derived from the declarative Canonical Models.
"""

from __future__ import annotations

from typing import List

from raxtik_etl.schema.canonical import (
    CANONICAL_MODELS,
    FieldRegistryEntry,
    TransformationCategory,
    ValueOrigin,
)

# CANONICAL_SCHEMA_VERSION represents the specification version of the Raxtik Canonical
# Pharmacovigilance Schema contract (the 7 unified entities: demo/cases, drug, reac, outc,
# indi, ther, rpsr).
#
# Semantic versioning rules:
# - MAJOR (e.g. 2.0.0): Breaking schema alterations, such as renaming or removing canonical
#   fields, modifying field physical data types, or changing entity primary/foreign key relationships.
# - MINOR (e.g. 1.1.0): Backward-compatible schema additions, such as appending new nullable
#   fields or new standard derived dimensions.
# - PATCH (e.g. 1.0.1): Documentation clarifications, metadata description updates, or
#   non-functional schema constraint refinements.
CANONICAL_SCHEMA_VERSION = "1.0.0"

SCHEMA_REGISTRY: List[FieldRegistryEntry] = [
    field for model in CANONICAL_MODELS for field in model.get_fields()
]

CANONICAL_ENTITIES: tuple[str, ...] = tuple(m.__tablename__ for m in CANONICAL_MODELS)
CANONICAL_TABLES: tuple[str, ...] = CANONICAL_ENTITIES


def get_entity_fields(entity: str) -> List[FieldRegistryEntry]:
    """Retrieve all fields registered for a specific canonical entity.

    Args:
        entity: Canonical table/entity name (e.g., 'demo', 'drug', 'reac').

    Returns:
        List of FieldRegistryEntry instances belonging to the requested entity.
    """
    return [e for e in SCHEMA_REGISTRY if e.entity == entity]


__all__ = [
    "CANONICAL_ENTITIES",
    "CANONICAL_SCHEMA_VERSION",
    "CANONICAL_TABLES",
    "FieldRegistryEntry",
    "SCHEMA_REGISTRY",
    "TransformationCategory",
    "ValueOrigin",
    "get_entity_fields",
]
