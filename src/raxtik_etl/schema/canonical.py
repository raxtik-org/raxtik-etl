"""Canonical Schema Models for FAERS Adverse Event Data Platform.

This module defines the 7 canonical entities (Case/Report, Drug, Reaction, Outcome,
Indication, Therapy, ReportSource), explicit value origin/presence enumerations,
and Provenance metadata.

Design Principles:
1. Pure contract: Contains only typed dataclasses and contracts; zero parsing or ETL logic.
2. Exact reported value preservation: Original values are stored verbatim as parsed.
3. Separation of Reported vs Derived: Raw fields vs standard derivations exist in non-overlapping attributes.
4. Independent Source Presence and Derivation Status: Tracks whether a field existed upstream and whether derivation succeeded.
5. First-class Provenance: Every record tracks source system, release, file, record locator, and timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


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

    FDA_REPORTED = "FDA_REPORTED"
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
    """Immutable audit and data lineage metadata for a record."""

    source_system: str  # e.g., 'FDA_FAERS_ASCII', 'OPENFDA_JSON'
    source_release: str  # e.g., '2004Q1', '2024Q1'
    source_file: str  # e.g., 'DEMO04Q1.txt', 'DRUG04Q1.txt'
    source_record_locator: Optional[str] = None  # e.g., 'row:18392' or 'json_path:results[42]'
    source_signature_id: Optional[str] = None  # e.g., 'S1', 'S2', 'S3'
    etl_version: str = "0.1.0"
    canonical_schema_version: str = "1.0.0"
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class CanonicalCase:
    """Canonical representation of an adverse event Case / Submission Report (DEMO)."""

    # Identifiers
    primary_id: str  # Submission report identifier (ISR in S1, PRIMARYID in S2/S3)
    case_id: str  # Case identifier (CASE in S1, CASEID in S2/S3)
    fda_case_version: Optional[int] = None  # CASEVERSION provided directly by FDA (NULL in S1)
    canonical_case_version: int = 1  # Raxtik analytical case version ordinal
    case_version_source: str = "FDA_REPORTED"  # 'FDA_REPORTED', 'DERIVED_FROM_FOLL_SEQ', etc.
    foll_seq: Optional[str] = None  # FOLL_SEQ (Raw follow-up sequence string in S1/S2)

    # Submission Flags & Dates
    initial_or_followup_code: Optional[str] = None  # I_F_COD ('I', 'F')
    initial_or_followup_label: Optional[str] = None  # 'Initial', 'Follow-up'
    event_date: Optional[str] = None  # EVENT_DT (YYYYMMDD)
    manufacturer_date: Optional[str] = None  # MFR_DT (YYYYMMDD)
    initial_fda_date: Optional[str] = None  # INIT_FDA_DT (YYYYMMDD, NULL in S1)
    fda_date: Optional[str] = None  # FDA_DT (YYYYMMDD)
    report_date: Optional[str] = None  # REPT_DT (YYYYMMDD)
    report_code: Optional[str] = None  # REPT_COD
    electronic_submission_flag: Optional[str] = None  # E_SUB ('Y', 'N')

    # Manufacturer & Administrative
    manufacturer_num: Optional[str] = None  # MFR_NUM
    manufacturer_sender: Optional[str] = None  # MFR_SNDR
    auth_num: Optional[str] = None  # AUTH_NUM (Introduced in S3)
    lit_ref: Optional[str] = None  # LIT_REF (Introduced in S3)
    to_mfr: Optional[str] = None  # TO_MFR

    # Patient Demographics - Reported Verbatim
    reported_age: Optional[float] = None  # AGE
    reported_age_code: Optional[str] = None  # AGE_COD ('YR', 'MON', 'WK', 'DY', 'HR', 'DEC')
    reported_age_group_code: Optional[str] = (
        None  # AGE_GRP ('N', 'I', 'C', 'T', 'A', 'E', NULL in S1/S2)
    )
    reported_sex_code: Optional[str] = None  # GNDR_COD in S1/S2, SEX in S3 ('M', 'F', 'UNK')
    reported_weight: Optional[float] = None  # WT
    reported_weight_code: Optional[str] = None  # WT_COD ('KG', 'LBS', 'GMS')

    # Patient Demographics - Standardized Derivations
    standard_age_years: Optional[float] = None  # Age converted to decimal years
    standard_sex_label: Optional[str] = None  # 'Male', 'Female', 'Unknown'
    standard_weight_kg: Optional[float] = None  # Weight converted to kilograms

    # Reporter & Geography
    reporter_occupation_code: Optional[str] = None  # OCCP_COD ('MD', 'PH', 'OT', 'LW', 'CN')
    reporter_occupation_label: Optional[str] = None  # 'Physician', 'Pharmacist', 'Consumer', etc.
    reporter_country: Optional[str] = None  # REPORTER_COUNTRY (ISO 2-letter)
    occurrence_country: Optional[str] = None  # OCCR_COUNTRY (ISO 2-letter)

    # Lineage
    provenance: Optional[Provenance] = None


@dataclass(slots=True)
class CanonicalDrug:
    """Canonical representation of a reported Drug Product (DRUG)."""

    # Identifiers
    primary_id: str
    case_id: str
    drug_seq: int  # DRUG_SEQ (1, 2, 3...)

    # Reported Drug Info (Immutable Verbatim)
    reported_drug_name: str  # DRUGNAME (exact parsed string)
    reported_active_ingredient: Optional[str] = None  # PROD_AI (NULL in S1/S2)
    reported_validation_code: Optional[str] = None  # VAL_VBM ('1'=Validated, '2'=Non-validated)

    # Suspect Role in Adverse Event
    role_code: Optional[str] = None  # ROLE_COD ('PS', 'SS', 'C', 'I')
    role_label: Optional[str] = None  # 'Primary Suspect', 'Secondary Suspect', etc.

    # Administration, Dosage & Route
    route: Optional[str] = None  # ROUTE (e.g. 'Oral', 'Intravenous')
    reported_dose_verbatim: Optional[str] = None  # DOSE_VBM
    dose_amount: Optional[float] = None  # DOSE_AMT (NULL in S1)
    dose_unit: Optional[str] = None  # DOSE_UNIT (NULL in S1)
    dose_form: Optional[str] = None  # DOSE_FORM (NULL in S1)
    dose_frequency: Optional[str] = None  # DOSE_FREQ (NULL in S1)
    cumulative_dose_amount: Optional[float] = None  # CUM_DOSE_CHR
    cumulative_dose_unit: Optional[str] = None  # CUM_DOSE_UNIT

    # Dechallenge / Rechallenge
    dechallenge_code: Optional[str] = None  # DECHAL ('Y', 'N', 'U', 'D')
    dechallenge_label: Optional[str] = None
    rechallenge_code: Optional[str] = None  # RECHAL ('Y', 'N', 'U', 'D')
    rechallenge_label: Optional[str] = None

    # Regulatory & Manufacturing
    lot_number: Optional[str] = None  # LOT_NUM (or lot_nbr in S2)
    expiration_date: Optional[str] = None  # EXP_DT (YYYYMMDD)
    nda_num: Optional[str] = None  # NDA_NUM / ANDA / BLA

    # Derived Standard Concepts (Non-Destructive Derivation)
    structural_clean_drug_name: Optional[str] = None  # Trimmed string without extraneous whitespace
    standard_concept_name: Optional[str] = None  # Resolved generic/INN substance name
    standard_concept_source: Optional[str] = None  # 'FDA_PROD_AI', 'RAXTIK_DRUG_DICTIONARY', etc.
    rxcui: Optional[str] = None  # RxNorm Concept Identifier (if matched)
    derivation_status: DerivationStatus = DerivationStatus.NOT_ATTEMPTED

    # Lineage
    provenance: Optional[Provenance] = None


@dataclass(slots=True)
class CanonicalReaction:
    """Canonical representation of an Adverse Reaction / Event (REAC)."""

    # Identifiers
    primary_id: str
    case_id: str
    reported_reaction_term: str  # PT (MedDRA Preferred Term string)
    reaction_seq: Optional[int] = None
    drug_reaction_action: Optional[str] = None  # DRUG_REC_ACT (NULL in S1/S2)

    # Lineage
    provenance: Optional[Provenance] = None


@dataclass(slots=True)
class CanonicalOutcome:
    """Canonical representation of Patient Outcome / Seriousness criteria (OUTC)."""

    # Identifiers
    primary_id: str
    case_id: str

    # Outcome Codes & Labels
    outcome_code: str  # OUTC_COD (DE, LT, HO, DS, CA, RI, OT)
    outcome_label: str  # 'Death', 'Life-Threatening', 'Hospitalization', etc.
    is_serious: bool = True

    # Lineage
    provenance: Optional[Provenance] = None


@dataclass(slots=True)
class CanonicalIndication:
    """Canonical representation of Medical Indications for drug use (INDI)."""

    # Identifiers
    primary_id: str
    case_id: str
    indication_drug_seq: int  # Links to DRUG.drug_seq (DRUG_SEQ in S1, INDI_DRUG_SEQ in S2/S3)

    # Indication Term (Immutable Verbatim)
    reported_indication_term: str  # INDI_PT (MedDRA Preferred Term)

    # Lineage
    provenance: Optional[Provenance] = None


@dataclass(slots=True)
class CanonicalTherapy:
    """Canonical representation of Drug Therapy duration and dates (THER)."""

    # Identifiers
    primary_id: str
    case_id: str
    therapy_drug_seq: int  # Links to DRUG.drug_seq (DRUG_SEQ in S1, DSG_DRUG_SEQ in S2/S3)

    # Therapy Dates
    start_date: Optional[str] = None  # START_DT (YYYYMMDD)
    end_date: Optional[str] = None  # END_DT (YYYYMMDD)

    # Duration
    reported_duration: Optional[float] = None  # DUR
    reported_duration_code: Optional[str] = None  # DUR_COD ('YR', 'MON', 'WK', 'DY', 'HR')
    standard_duration_days: Optional[float] = None  # Duration normalized to days

    # Lineage
    provenance: Optional[Provenance] = None


@dataclass(slots=True)
class CanonicalReportSource:
    """Canonical representation of Report Source classifications (RPSR)."""

    # Identifiers
    primary_id: str
    case_id: str

    # Source Codes & Labels
    report_source_code: str  # RPSR_COD (FGN, SDY, LIT, HP, CSM, CR, UF)
    report_source_label: str  # 'Foreign', 'Clinical Study', 'Literature', etc.

    # Lineage
    provenance: Optional[Provenance] = None
