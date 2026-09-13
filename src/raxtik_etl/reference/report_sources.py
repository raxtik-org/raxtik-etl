"""Official FDA Report Source Classifications (RPSR_COD)."""

from __future__ import annotations

from typing import List

from raxtik_etl.reference.codes import ReferenceCodeEntry

FDA_REPORT_SOURCES_REFERENCE: List[ReferenceCodeEntry] = [
    ReferenceCodeEntry(
        "FGN",
        "Foreign",
        "Foreign regulatory agency or international report",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "SDY",
        "Clinical Study",
        "Clinical trial or post-marketing surveillance study",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "LIT",
        "Literature",
        "Published scientific journal or literature report",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "HP",
        "Health Professional",
        "Voluntary report from physician, pharmacist, or healthcare worker",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "CSM",
        "Consumer",
        "Voluntary report from consumer, patient, or family member",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "CR",
        "Company Representative",
        "Report submitted via manufacturer field representative",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "UF",
        "User Facility",
        "Hospital, clinic, or healthcare facility report",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
]
