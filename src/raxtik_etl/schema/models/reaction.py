"""Canonical Adverse Reaction / Event (REAC) schema model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Optional

from raxtik_etl.schema.base import (
    BaseCanonicalModel,
    Column,
    TransformationCategory,
)


@dataclass(slots=True)
class CanonicalReaction(BaseCanonicalModel):
    """Canonical representation of an Adverse Reaction / Event (REAC)."""

    __tablename__: ClassVar[str] = "reac"
    __table_description__: ClassVar[str] = (
        "Reported adverse event reactions and MedDRA preferred terms"
    )

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
    reported_reaction_term: str = Column(
        "VARCHAR",
        is_primary_key=True,
        nullable=False,
        category=TransformationCategory.A_IDENTICAL,
        description="MedDRA Preferred Term adverse reaction",
    )

    # Optional reaction metadata
    reaction_seq: Optional[int] = Column(
        "INTEGER",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Sequence ordinal for the reaction entry within the report",
    )
    drug_reaction_action: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.C_ADDED_LATER,
        description="Action taken with drug (Added 2014Q3)",
    )


__all__ = ["CanonicalReaction"]
