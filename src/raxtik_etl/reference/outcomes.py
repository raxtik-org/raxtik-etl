"""Official FDA Patient Outcome Reference Codes and Raxtik Semantic Derivations."""

from __future__ import annotations

from typing import List

from raxtik_etl.reference.codes import OutcomeSemanticsEntry, ReferenceCodeEntry

FDA_OUTCOMES_REFERENCE: List[ReferenceCodeEntry] = [
    ReferenceCodeEntry(
        "DE",
        "Death",
        "Results in death",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "LT",
        "Life-Threatening",
        "Life-threatening adverse event",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "HO",
        "Hospitalization",
        "Initial or prolonged hospitalization",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "DS",
        "Disability",
        "Disability or permanent damage",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "CA",
        "Congenital Anomaly",
        "Congenital anomaly or birth defect",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "RI",
        "Required Intervention",
        "Required intervention to prevent permanent impairment",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
    ReferenceCodeEntry(
        "OT",
        "Other Serious",
        "Other serious or medically important event",
        "FDA_CDER",
        "FAERS_QDE_README",
        "1.0.0",
        "2004Q1",
        None,
        True,
    ),
]

RAXTIK_OUTCOME_SEMANTICS: List[OutcomeSemanticsEntry] = [
    OutcomeSemanticsEntry("DE", True, "Fatal", 1, "1.0.0", "ICH_E2B_R2_R3"),
    OutcomeSemanticsEntry("LT", True, "Life-Threatening", 2, "1.0.0", "ICH_E2B_R2_R3"),
    OutcomeSemanticsEntry(
        "HO", True, "Inpatient/Prolonged Hospitalization", 3, "1.0.0", "ICH_E2B_R2_R3"
    ),
    OutcomeSemanticsEntry("DS", True, "Disability / Incapacity", 4, "1.0.0", "ICH_E2B_R2_R3"),
    OutcomeSemanticsEntry(
        "CA", True, "Congenital Anomaly / Birth Defect", 5, "1.0.0", "ICH_E2B_R2_R3"
    ),
    OutcomeSemanticsEntry(
        "RI", True, "Required Intervention to Prevent Permanent Harm", 6, "1.0.0", "ICH_E2B_R2_R3"
    ),
    OutcomeSemanticsEntry(
        "OT", True, "Other Medically Important Event", 7, "1.0.0", "ICH_E2B_R2_R3"
    ),
]
