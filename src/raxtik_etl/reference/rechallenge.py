"""Official FDA Rechallenge Codes (RECHAL)."""

from __future__ import annotations

from typing import List

from raxtik_etl.reference.codes import ReferenceCodeEntry

FDA_RECHALLENGE_REFERENCE: List[ReferenceCodeEntry] = [
    ReferenceCodeEntry(
        "Y",
        "Positive",
        "Reaction recurred upon reintroduction of the drug",
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
        "Reaction did not recur upon reintroduction of the drug",
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
        "Rechallenge status unknown or not attempted",
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
        "Drug was not reintroduced",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
]
