"""Canonical Case / Submission Report (DEMO) schema model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Optional

from raxtik_etl.schema.base import (
    BaseCanonicalModel,
    Column,
    Provenance,
    TransformationCategory,
    ValueOrigin,
)


@dataclass(slots=True)
class CanonicalCase(BaseCanonicalModel):
    """Canonical representation of an adverse event Case / Submission Report (DEMO)."""

    __tablename__: ClassVar[str] = "demo"
    __table_description__: ClassVar[str] = "Adverse event Case / Submission Report"

    # Identifiers (Required)
    primary_id: str = Column(
        "VARCHAR",
        is_primary_key=True,
        nullable=False,
        category=TransformationCategory.H_RELATIONSHIP_KEY_CHANGE,
        description="Unique submission report identifier",
    )
    case_id: str = Column(
        "VARCHAR",
        is_primary_key=False,
        nullable=False,
        category=TransformationCategory.H_RELATIONSHIP_KEY_CHANGE,
        description="Stable case identifier across versions",
    )

    # Submission Flags & Dates (Nullable / Defaults)
    source_case_version: Optional[int] = Column(
        "INTEGER",
        nullable=True,
        category=TransformationCategory.H_RELATIONSHIP_KEY_CHANGE,
        description="Source-provided version number",
    )
    canonical_case_version: int = Column(
        "INTEGER",
        nullable=False,
        default=1,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Raxtik analytical case version ordinal",
    )
    case_version_source: str = Column(
        "VARCHAR",
        nullable=False,
        default="SOURCE_REPORTED",
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Version determination methodology",
    )
    foll_seq: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Legacy follow-up sequence number",
    )
    initial_or_followup_code: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Report type flag (I=Initial, F=Followup)",
    )
    initial_or_followup_label: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Human-readable label for report type",
    )
    event_date: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Date adverse event occurred (YYYYMMDD)",
    )
    manufacturer_date: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Date manufacturer received report (YYYYMMDD)",
    )
    initial_regulatory_date: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.C_ADDED_LATER,
        description="Date initial report received by regulatory agency (YYYYMMDD)",
    )
    latest_regulatory_date: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Date latest version received by regulatory agency (YYYYMMDD)",
    )

    # Report Source Flags & Classifications
    report_type_code: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Report type code (DIR, EXP, PER, etc.)",
    )
    report_type_label: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Human-readable label for report type",
    )
    expedited_flag: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="15-day alert expedited flag (Y/N)",
    )
    manufacturer_control_number: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Manufacturer internal control number",
    )
    manufacturer_name: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Manufacturer name",
    )
    sender_type_code: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.C_ADDED_LATER,
        description="Sender type code (PUB, IND, PHM)",
    )
    sender_type_label: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Human-readable sender type label",
    )

    # Patient Demographics - Reported Verbatim
    reported_age: Optional[float] = Column(
        "DOUBLE",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Reported patient age value",
    )
    reported_age_code: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Reported unit of age (YR, MON, WK, DY, HR, DEC)",
    )
    age_group_code: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Patient age group code (NEO, INF, CHLD, ADOL, ADULT, ELD)",
    )
    reported_sex_code: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Reported sex code (M, F, UNK)",
    )
    reported_weight: Optional[float] = Column(
        "DOUBLE",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Reported patient weight value",
    )
    reported_weight_code: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Unit of weight (KG, LBS, GMS)",
    )

    # Patient Demographics - Standardized Derivations
    standard_age_years: Optional[float] = Column(
        "DOUBLE",
        nullable=True,
        value_origin=ValueOrigin.NORMALIZED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Normalized patient age in decimal years (0.0 to 125.0)",
    )
    standard_sex_label: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        value_origin=ValueOrigin.NORMALIZED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Standardized human-readable sex label (Male, Female, Unknown)",
    )
    standard_weight_kg: Optional[float] = Column(
        "DOUBLE",
        nullable=True,
        value_origin=ValueOrigin.NORMALIZED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Normalized patient weight in kilograms",
    )

    # Reporter & Geography
    reporter_occupation_code: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Reporter occupation code (MD, PH, OT, LW, CN)",
    )
    reporter_occupation_label: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Human-readable reporter occupation label",
    )
    reporter_country: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.C_ADDED_LATER,
        description="Reporter ISO country code",
    )
    occurrence_country: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.C_ADDED_LATER,
        description="Event occurrence country code",
    )

    # Lineage Metadata Object (Not a database column)
    provenance: Optional[Provenance] = field(default=None)


__all__ = ["CanonicalCase"]
