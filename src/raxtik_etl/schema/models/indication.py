"""Canonical Medical Indication (INDI) schema model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from raxtik_etl.schema.base import (
    BaseCanonicalModel,
    Column,
    TransformationCategory,
)


@dataclass(slots=True)
class CanonicalIndication(BaseCanonicalModel):
    """Canonical representation of Medical Indications for drug use (INDI)."""

    __tablename__: ClassVar[str] = "indi"
    __table_description__: ClassVar[str] = "Medical indications for drug usage"

    # Identifiers (Required)
    primary_id: str = Column(
        "VARCHAR",
        is_primary_key=True,
        foreign_key="demo.primary_id",
        nullable=False,
        category=TransformationCategory.H_RELATIONSHIP_KEY_CHANGE,
        description="Links to demo.primary_id",
    )
    case_id: str = Column(
        "VARCHAR",
        is_primary_key=False,
        foreign_key="demo.case_id",
        nullable=False,
        category=TransformationCategory.H_RELATIONSHIP_KEY_CHANGE,
        description="Links to demo.case_id",
    )
    indication_drug_seq: int = Column(
        "INTEGER",
        is_primary_key=True,
        foreign_key="drug.drug_seq",
        nullable=False,
        category=TransformationCategory.H_RELATIONSHIP_KEY_CHANGE,
        description="Links to drug.drug_seq",
    )
    reported_indication_term: str = Column(
        "VARCHAR",
        is_primary_key=True,
        nullable=False,
        category=TransformationCategory.A_IDENTICAL,
        description="MedDRA Preferred Term indication",
    )


__all__ = ["CanonicalIndication"]
