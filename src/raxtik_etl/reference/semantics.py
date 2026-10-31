"""Raxtik Universal Clinical and Regulatory Outcome Semantics.

Maps standard adverse event outcome codes to seriousness classifications,
ICH E2B categories, and clinical severity ranks.
"""

from __future__ import annotations

from typing import List

from raxtik_etl.reference.codes import OutcomeSemanticsEntry

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
