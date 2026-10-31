"""Canonical Report Source (RPSR) schema model."""

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
class CanonicalReportSource(BaseCanonicalModel):
    """Canonical representation of Report Source classifications (RPSR)."""

    __tablename__: ClassVar[str] = "rpsr"
    __table_description__: ClassVar[str] = "Report source classifications and reporting channels"

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
    report_source_code: str = Column(
        "VARCHAR",
        is_primary_key=True,
        nullable=False,
        category=TransformationCategory.A_IDENTICAL,
        description="Report source category code (FGN, SDY, LIT, HP, CSM, CR, UF)",
    )
    report_source_label: str = Column(
        "VARCHAR",
        nullable=False,
        default="",
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Human-readable description of report origin channel",
    )


__all__ = ["CanonicalReportSource"]
