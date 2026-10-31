"""Canonical Patient Outcome / Seriousness criteria (OUTC) schema model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from raxtik_etl.schema.base import (
    BaseCanonicalModel,
    Column,
    TransformationCategory,
    ValueOrigin,
)


@dataclass(slots=True)
class CanonicalOutcome(BaseCanonicalModel):
    """Canonical representation of Patient Outcome / Seriousness criteria (OUTC)."""

    __tablename__: ClassVar[str] = "outc"
    __table_description__: ClassVar[str] = "Patient outcomes and seriousness criteria"

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
    outcome_code: str = Column(
        "VARCHAR",
        is_primary_key=True,
        nullable=False,
        category=TransformationCategory.A_IDENTICAL,
        description="Outcome code (DE, LT, HO, DS, CA, RI, OT)",
    )

    # Derived Labels & Seriousness Flag
    outcome_label: str = Column(
        "VARCHAR",
        nullable=False,
        default="",
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Human-readable outcome label",
    )
    is_serious: bool = Column(
        "BOOLEAN",
        nullable=False,
        default=True,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Clinical flag indicating seriousness criteria",
    )


__all__ = ["CanonicalOutcome"]
