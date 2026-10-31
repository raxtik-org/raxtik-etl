"""Declarative Base Models, Descriptors, and Enums for Raxtik Canonical Schema.

Provides the foundational descriptor machinery for declaring schema models with
zero runtime overhead, automatic DuckDB CREATE TABLE DDL generation, and
dynamic schema catalog generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from enum import Enum
from typing import Any, ClassVar, Dict, List, Optional


class SourcePresence(str, Enum):
    """Indicates whether a field existed and was populated in the source release extract."""

    PRESENT_AND_POPULATED = "PRESENT_AND_POPULATED"
    PRESENT_BUT_EMPTY = "PRESENT_BUT_EMPTY"
    NOT_PRESENT_IN_SOURCE = "NOT_PRESENT_IN_SOURCE"


class DerivationStatus(str, Enum):
    """Tracks whether a standardized derivation was performed on a field."""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class ValueOrigin(str, Enum):
    """Classifies how the value in a field was originated."""

    SOURCE_REPORTED = "SOURCE_REPORTED"
    DERIVED = "DERIVED"
    NORMALIZED = "NORMALIZED"
    PROVENANCE = "PROVENANCE"


class TransformationCategory(str, Enum):
    """Formal 8-category schema evolution taxonomy."""

    A_IDENTICAL = "A_IDENTICAL"
    B_RENAMED_ALIAS = "B_RENAMED_ALIAS"
    C_ADDED_LATER = "C_ADDED_LATER"
    D_DEPRECATED_UNMAPPED = "D_DEPRECATED_UNMAPPED"
    E_CODE_SET_EVOLUTION = "E_CODE_SET_EVOLUTION"
    F_SEMANTIC_SPLIT = "F_SEMANTIC_SPLIT"
    G_DERIVED_STANDARDIZED = "G_DERIVED_STANDARDIZED"
    H_RELATIONSHIP_KEY_CHANGE = "H_RELATIONSHIP_KEY_CHANGE"


@dataclass(slots=True)
class Provenance:
    """Immutable audit and data lineage metadata for a record.

    Attributes:
        source_system: Upstream data provider or format (e.g., 'FDA_FAERS_ASCII', 'VAERS').
        data_period: Source temporal extract or period identifier (e.g., '2004Q1').
        source_file: Raw archive file or partition name from which the record originated.
        source_record_locator: Specific locator within source file (e.g., 'row:18392').
        source_signature_id: Format signature identifier (e.g., 'S1', 'S2', 'S3').
        etl_version: Version of the mapping logic used to ingest the record.
        canonical_schema_version: Version of the canonical pharmacovigilance data model.
        ingested_at: UTC timestamp when the record was processed.
    """

    source_system: str
    data_period: str
    source_file: str
    source_record_locator: Optional[str] = None
    source_signature_id: Optional[str] = None
    etl_version: str = "0.1.0"
    canonical_schema_version: str = "1.0.0"
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class FieldRegistryEntry:
    """Catalog entry describing a canonical field in the Raxtik pharmacovigilance schema.

    Attributes:
        field_name: Machine-readable snake_case identifier of the canonical field.
        entity: Fact or dimension table entity name (e.g., 'demo', 'drug', 'reac').
        data_type: Physical SQL storage data type (e.g., 'VARCHAR', 'INTEGER', 'DOUBLE').
        is_nullable: Whether NULL values are permissible under the canonical contract.
        value_origin: Classification of origin (SOURCE_REPORTED, DERIVED, NORMALIZED, PROVENANCE).
        category: Schema evolution and harmonization classification category.
        description: Human-readable technical and clinical definition of the field.
        is_primary_key: Whether this field participates in the primary key of the entity.
        foreign_key: Reference target (e.g. 'demo.primary_id') if this field is a foreign key.
    """

    field_name: str
    entity: str
    data_type: str
    is_nullable: bool
    value_origin: ValueOrigin
    category: TransformationCategory
    description: str
    is_primary_key: bool = False
    foreign_key: Optional[str] = None


@dataclass(slots=True)
class ColumnInfo:
    """Declarative column descriptor holding SQL storage types and schema evolution metadata.

    Attributes:
        data_type: Physical SQL storage data type (e.g. 'VARCHAR', 'INTEGER', 'DOUBLE').
        is_primary_key: Whether column participates in the table primary key.
        foreign_key: Optional foreign table reference identifier (e.g. 'demo.primary_id').
        nullable: Whether column permits NULL values.
        value_origin: Origin taxonomy classification (SOURCE_REPORTED, DERIVED, etc.).
        category: Schema evolution category (A_IDENTICAL, C_ADDED_LATER, etc.).
        description: Clinical and engineering definition of the field.
    """

    data_type: str
    is_primary_key: bool = False
    foreign_key: Optional[str] = None
    nullable: bool = True
    value_origin: ValueOrigin = ValueOrigin.SOURCE_REPORTED
    category: TransformationCategory = TransformationCategory.A_IDENTICAL
    description: str = ""


_MISSING = object()


def Column(
    data_type: str,
    *,
    is_primary_key: bool = False,
    foreign_key: Optional[str] = None,
    nullable: bool = True,
    value_origin: ValueOrigin = ValueOrigin.SOURCE_REPORTED,
    category: TransformationCategory = TransformationCategory.A_IDENTICAL,
    description: str = "",
    default: Any = _MISSING,
    default_factory: Any = _MISSING,
) -> Any:
    """Declares a column with SQL physical type, constraints, and evolution metadata.

    Returns a standard dataclass field with attached ColumnInfo in field.metadata.

    Args:
        data_type: SQL storage data type (e.g., 'VARCHAR', 'INTEGER', 'DOUBLE').
        is_primary_key: Whether column participates in the primary key.
        foreign_key: Foreign table column reference string if applicable.
        nullable: Whether NULL values are permissible.
        value_origin: Origin classification of values in this column.
        category: Schema evolution taxonomy classification category.
        description: Technical and clinical definition of the field.
        default: Default value if column is omitted during instantiation.
        default_factory: 0-argument callable producing default value.

    Returns:
        dataclass Field configured with ColumnInfo metadata.
    """
    col_info = ColumnInfo(
        data_type=data_type,
        is_primary_key=is_primary_key,
        foreign_key=foreign_key,
        nullable=nullable,
        value_origin=value_origin,
        category=category,
        description=description,
    )
    kwargs: Dict[str, Any] = {"metadata": {"column": col_info}}
    if default_factory is not _MISSING:
        kwargs["default_factory"] = default_factory
    elif default is not _MISSING:
        kwargs["default"] = default
    elif nullable:
        kwargs["default"] = None
    return field(**kwargs)


class BaseCanonicalModel:
    """Base declarative schema model for canonical pharmacovigilance entities."""

    __tablename__: ClassVar[str]
    __table_description__: ClassVar[str]

    @classmethod
    def get_columns(cls) -> Dict[str, ColumnInfo]:
        """Returns dictionary of column_name -> ColumnInfo metadata.

        Returns:
            Mapping of field names to their ColumnInfo metadata descriptors.
        """
        cols: Dict[str, ColumnInfo] = {}
        for f in fields(cls):  # type: ignore
            if "column" in f.metadata:
                cols[f.name] = f.metadata["column"]
        return cols

    @classmethod
    def get_primary_keys(cls) -> List[str]:
        """Returns list of column names that compose the primary key.

        Returns:
            List of primary key column names.
        """
        return [name for name, col in cls.get_columns().items() if col.is_primary_key]

    @classmethod
    def get_fields(cls) -> List[FieldRegistryEntry]:
        """Generates FieldRegistryEntry instances for the schema registry.

        Returns:
            List of FieldRegistryEntry instances representing each column of this entity.
        """
        return [
            FieldRegistryEntry(
                field_name=name,
                entity=cls.__tablename__,
                data_type=col.data_type,
                is_nullable=col.nullable,
                value_origin=col.value_origin,
                category=col.category,
                description=col.description,
                is_primary_key=col.is_primary_key,
                foreign_key=col.foreign_key,
            )
            for name, col in cls.get_columns().items()
        ]

    @classmethod
    def get_create_table_ddl(cls, table_name: Optional[str] = None) -> str:
        """Generates DuckDB CREATE TABLE DDL statement.

        Args:
            table_name: Optional table name override. Defaults to cls.__tablename__.

        Returns:
            DuckDB SQL CREATE TABLE DDL string.
        """
        tbl = table_name or cls.__tablename__
        cols = cls.get_columns()
        col_defs: List[str] = []
        for name, col in cols.items():
            null_str = "" if col.nullable else " NOT NULL"
            col_defs.append(f"    {name} {col.data_type}{null_str}")

        pks = cls.get_primary_keys()
        if pks:
            col_defs.append(f"    PRIMARY KEY ({', '.join(pks)})")

        inner = ",\n".join(col_defs)
        return f"CREATE TABLE IF NOT EXISTS {tbl} (\n{inner}\n);"


__all__ = [
    "BaseCanonicalModel",
    "Column",
    "ColumnInfo",
    "DerivationStatus",
    "FieldRegistryEntry",
    "Provenance",
    "SourcePresence",
    "TransformationCategory",
    "ValueOrigin",
]
