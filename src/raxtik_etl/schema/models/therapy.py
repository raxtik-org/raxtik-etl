"""Canonical Drug Therapy Duration (THER) schema model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Optional

from raxtik_etl.schema.base import (
    BaseCanonicalModel,
    Column,
    TransformationCategory,
    ValueOrigin,
)


@dataclass(slots=True)
class CanonicalTherapy(BaseCanonicalModel):
    """Canonical representation of Drug Therapy duration and dates (THER)."""

    __tablename__: ClassVar[str] = "ther"
    __table_description__: ClassVar[str] = (
        "Drug therapy start/stop administration dates and durations"
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
    therapy_drug_seq: int = Column(
        "INTEGER",
        is_primary_key=True,
        foreign_key="drug.drug_seq",
        nullable=False,
        category=TransformationCategory.H_RELATIONSHIP_KEY_CHANGE,
        description="Links to drug.drug_seq",
    )

    # Dates & Durations
    start_date: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Therapy start date (YYYYMMDD)",
    )
    end_date: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Therapy end date (YYYYMMDD)",
    )
    reported_duration: Optional[float] = Column(
        "DOUBLE",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Duration of therapy value",
    )
    reported_duration_code: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Unit of duration (YR, MON, WK, DY, HR)",
    )
    standard_duration_days: Optional[float] = Column(
        "DOUBLE",
        nullable=True,
        value_origin=ValueOrigin.NORMALIZED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Standardized therapy duration normalized to days",
    )


__all__ = ["CanonicalTherapy"]
