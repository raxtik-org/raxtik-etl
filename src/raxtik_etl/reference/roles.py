"""Official FDA Drug Role Codes (ROLE_COD)."""

from __future__ import annotations

from typing import List

from raxtik_etl.reference.codes import ReferenceCodeEntry

FDA_ROLES_REFERENCE: List[ReferenceCodeEntry] = [
    ReferenceCodeEntry(
        "PS",
        "Primary Suspect",
        "Primary suspect drug identified as causing adverse event",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "SS",
        "Secondary Suspect",
        "Secondary suspect drug suspected of contributing",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "C",
        "Concomitant",
        "Concomitant drug taken concurrently by patient",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "I",
        "Interacting",
        "Drug suspected of causing a drug-drug interaction",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    # Historical AERS legacy numeric representations (S1 era)
    ReferenceCodeEntry(
        "1",
        "Primary Suspect (Legacy)",
        "Legacy numeric code for Primary Suspect",
        "FDA_CDER",
        "AERS_DOCUMENTATION",
        "1.0.0",
        "2004Q1",
        "2012Q3",
        False,
    ),
    ReferenceCodeEntry(
        "2",
        "Secondary Suspect (Legacy)",
        "Legacy numeric code for Secondary Suspect",
        "FDA_CDER",
        "AERS_DOCUMENTATION",
        "1.0.0",
        "2004Q1",
        "2012Q3",
        False,
    ),
    ReferenceCodeEntry(
        "3",
        "Concomitant (Legacy)",
        "Legacy numeric code for Concomitant",
        "FDA_CDER",
        "AERS_DOCUMENTATION",
        "1.0.0",
        "2004Q1",
        "2012Q3",
        False,
    ),
    ReferenceCodeEntry(
        "4",
        "Interacting (Legacy)",
        "Legacy numeric code for Interacting",
        "FDA_CDER",
        "AERS_DOCUMENTATION",
        "1.0.0",
        "2004Q1",
        "2012Q3",
        False,
    ),
]
