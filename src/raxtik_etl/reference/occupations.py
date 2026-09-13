"""Official FDA Reporter Occupation Codes (OCCP_COD)."""

from __future__ import annotations

from typing import List

from raxtik_etl.reference.codes import ReferenceCodeEntry

FDA_OCCUPATIONS_REFERENCE: List[ReferenceCodeEntry] = [
    ReferenceCodeEntry(
        "MD",
        "Physician",
        "Medical Doctor / Physician",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "PH",
        "Pharmacist",
        "Licensed Pharmacist",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "OT",
        "Other Health Professional",
        "Nurse, Dentist, or other allied health professional",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "LW",
        "Lawyer",
        "Attorney or legal representative",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "CN",
        "Consumer",
        "Consumer, patient, family member, or non-healthcare reporter",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
]
