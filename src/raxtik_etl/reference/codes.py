"""Base Reference Code-List Models and Universal Contracts.

Defines the typed contract for all versioned reference dimensions:
- ReferenceCodeEntry: FDA-reported source code definitions
- DerivedSemanticsEntry: Raxtik analytical and clinical interpretations
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class ReferenceCodeEntry:
    """Universal contract for official FDA reference code entries."""

    code: str
    label: str
    definition: str
    source_system: str = "FDA_CDER"
    source_document: str = "FAERS_QDE_README"
    reference_version: str = "1.0.0"
    valid_from: str = "2004Q1"
    valid_to: Optional[str] = None  # None indicates currently active
    is_active: bool = True


@dataclass(slots=True)
class OutcomeSemanticsEntry:
    """Raxtik-derived clinical and regulatory semantics for patient outcomes."""

    outcome_code: str
    is_serious: bool
    ich_seriousness_category: str
    severity_rank: int
    raxtik_semantics_version: str = "1.0.0"
    semantic_source: str = "ICH_E2B_R2_R3_GUIDELINES"
