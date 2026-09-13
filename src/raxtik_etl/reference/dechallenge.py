"""Official FDA Dechallenge Codes (DECHAL)."""

from __future__ import annotations

from typing import List

from raxtik_etl.reference.codes import ReferenceCodeEntry

FDA_DECHALLENGE_REFERENCE: List[ReferenceCodeEntry] = [
    ReferenceCodeEntry(
        "Y",
        "Positive",
        "Reaction abated upon drug discontinuation or reduction",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "N",
        "Negative",
        "Reaction did not abate upon drug discontinuation",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "U",
        "Unknown",
        "Dechallenge status unknown or unreported",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "D",
        "Does Not Apply",
        "Dose was not reduced or drug was continued",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
]
