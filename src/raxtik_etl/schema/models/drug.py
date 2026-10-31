"""Canonical Drug Product (DRUG) schema model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Optional

from raxtik_etl.schema.base import (
    BaseCanonicalModel,
    Column,
    DerivationStatus,
    TransformationCategory,
    ValueOrigin,
)


@dataclass(slots=True)
class CanonicalDrug(BaseCanonicalModel):
    """Canonical representation of a reported Drug Product (DRUG)."""

    __tablename__: ClassVar[str] = "drug"
    __table_description__: ClassVar[str] = "Reported drug products, indications, and therapy roles"

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
    drug_seq: int = Column(
        "INTEGER",
        is_primary_key=True,
        nullable=False,
        category=TransformationCategory.A_IDENTICAL,
        description="Sequence number of drug in report",
    )
    reported_drug_name: str = Column(
        "VARCHAR",
        is_primary_key=False,
        nullable=False,
        category=TransformationCategory.A_IDENTICAL,
        description="Immutable reported verbatim drug name",
    )

    # Suspect Role & Details (Nullable / Defaults)
    role_code: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.E_CODE_SET_EVOLUTION,
        description="Suspect role of drug (PS, SS, C, I)",
    )
    role_label: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Human-readable suspect role classification label",
    )
    reported_active_ingredient: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.C_ADDED_LATER,
        description="Active ingredient text (Added 2014Q3)",
    )
    reported_validation_code: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Validation flag (1=validated, 2=non-validated)",
    )
    route: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Administration route",
    )
    reported_dose_verbatim: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Verbatim dosage text",
    )
    dose_amount: Optional[float] = Column(
        "DOUBLE",
        nullable=True,
        category=TransformationCategory.F_SEMANTIC_SPLIT,
        description="Numerical dose amount",
    )
    dose_unit: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.F_SEMANTIC_SPLIT,
        description="Dose unit (MG, G, etc.)",
    )
    dose_form: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.F_SEMANTIC_SPLIT,
        description="Physical form (TABLET, CAPSULE, etc.)",
    )
    dose_frequency: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.F_SEMANTIC_SPLIT,
        description="Dosing frequency (QD, BID, etc.)",
    )
    cumulative_dose_amount: Optional[float] = Column(
        "DOUBLE",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Cumulative dose taken before event",
    )
    cumulative_dose_unit: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Cumulative dose unit",
    )
    dechallenge_code: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Dechallenge flag (Y, N, U, D)",
    )
    dechallenge_label: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Human-readable dechallenge outcome label",
    )
    rechallenge_code: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Rechallenge flag (Y, N, U, D)",
    )
    rechallenge_label: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Human-readable rechallenge outcome label",
    )
    lot_number: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Manufacturer lot number",
    )
    expiration_date: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Product expiration date (YYYYMMDD)",
    )
    regulatory_auth_num: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        category=TransformationCategory.A_IDENTICAL,
        description="Regulatory authorization or application number (NDA, ANDA, BLA, MAA, DIN)",
    )

    # Derived Standard Concepts (Non-Destructive Derivation)
    structural_clean_drug_name: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        value_origin=ValueOrigin.NORMALIZED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Standardized drug name string with noise removed",
    )
    standard_concept_name: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Normalized generic/INN substance concept name",
    )
    standard_concept_source: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Terminology system used for concept mapping (e.g. RxNorm)",
    )
    rxcui: Optional[str] = Column(
        "VARCHAR",
        nullable=True,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="RxNorm Concept Unique Identifier if resolved",
    )
    derivation_status: DerivationStatus = Column(
        "VARCHAR",
        nullable=False,
        default=DerivationStatus.NOT_ATTEMPTED,
        value_origin=ValueOrigin.DERIVED,
        category=TransformationCategory.G_DERIVED_STANDARDIZED,
        description="Status of automated standardization and vocabulary mapping",
    )


__all__ = ["CanonicalDrug"]
