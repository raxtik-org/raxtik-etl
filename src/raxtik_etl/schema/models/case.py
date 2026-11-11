"""Canonical Case / Submission Report (DEMO) schema model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
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
        default=ValueOrigin.SOURCE_REPORTED.value,
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
    # Key Dates - Reported Verbatim, Standardized Imputed Dates, and Precision Flags
    event_date: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Date adverse event occurred (YYYYMMDD)",
    )
    standard_event_date: Optional[date] = Column(
        "DATE",
        nullable=True,
        value_origin=ValueOrigin.NORMALIZED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Imputed/parsed date adverse event occurred",
    )
    event_date_precision: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Event date precision audit classification (EXACT, YEAR_MONTH, YEAR_ONLY, INVALID)",
    )
    manufacturer_date: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Date manufacturer received report (YYYYMMDD)",
    )
    standard_manufacturer_date: Optional[date] = Column(
        "DATE",
        nullable=True,
        value_origin=ValueOrigin.NORMALIZED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Imputed/parsed date manufacturer received report",
    )
    manufacturer_date_precision: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Manufacturer date precision classification",
    )
    initial_regulatory_date: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.C_ADDED_LATER,
        description="Date initial report received by regulatory agency (YYYYMMDD)",
    )
    standard_initial_regulatory_date: Optional[date] = Column(
        "DATE",
        nullable=True,
        value_origin=ValueOrigin.NORMALIZED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Imputed/parsed date initial report received by regulatory agency",
    )
    initial_regulatory_date_precision: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Initial regulatory date precision classification",
    )
    latest_regulatory_date: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Date latest version received by regulatory agency (YYYYMMDD)",
    )
    standard_latest_regulatory_date: Optional[date] = Column(
        "DATE",
        nullable=True,
        value_origin=ValueOrigin.NORMALIZED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Imputed/parsed date latest version received by regulatory agency",
    )
    latest_regulatory_date_precision: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Latest regulatory date precision classification",
    )
    report_date: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Date report was sent by reporter (YYYYMMDD)",
    )
    standard_report_date: Optional[date] = Column(
        "DATE",
        nullable=True,
        value_origin=ValueOrigin.NORMALIZED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Imputed/parsed date report was sent by reporter",
    )
    report_date_precision: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Report date precision classification",
    )
    death_date: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.D_DEPRECATED_UNMAPPED,
        description="Date patient died (YYYYMMDD)",
    )
    standard_death_date: Optional[date] = Column(
        "DATE",
        nullable=True,
        value_origin=ValueOrigin.NORMALIZED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Imputed/parsed date patient died",
    )
    death_date_precision: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Death date precision classification",
    )
    confidentiality_flag: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.D_DEPRECATED_UNMAPPED,
        description="Voluntary reporter confidentiality request flag (Y/N)",
    )

    # Report Source Flags & Classifications
    report_type_code: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.B_RENAMED_ALIAS,
        description="Report type code (renamed from raw FDA rept_cod: DIR, EXP, PER, 5DAY, 30DAY)",
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
    electronic_submission_flag: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Electronic submission flag (Y/N)",
    )
    manufacturer_control_number: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.B_RENAMED_ALIAS,
        description="Manufacturer internal control number (renamed from raw FDA mfr_num)",
    )
    manufacturer_name: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.B_RENAMED_ALIAS,
        description="Manufacturer name (renamed from raw FDA mfr_sndr)",
    )
    auth_num: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.C_ADDED_LATER,
        description="Regulatory authorization number (Introduced 2014Q3)",
    )
    lit_ref: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.C_ADDED_LATER,
        description="Literature reference text (Introduced 2014Q3)",
    )
    to_mfr: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Distributor made report available to manufacturer flag (Y/N)",
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
    reported_age_unit_label: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Human-readable patient age measurement unit label",
    )
    age_group_code: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.C_ADDED_LATER,
        description="Patient age group code (from raw FDA age_grp: N=Neonate, I=Infant, C=Child, T=Adolescent, A=Adult, E=Elderly)",
    )
    age_group_label: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Human-readable patient age group classification label",
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
    reported_weight_unit_label: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Human-readable patient weight measurement unit label",
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
