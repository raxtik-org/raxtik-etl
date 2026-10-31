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
    """Universal contract for official pharmacovigilance reference code entries.

    Attributes:
        code: Normalized machine-readable reference code value.
        label: Standard human-readable category or term name.
        definition: Full clinical or regulatory definition text.
        source_system: Originating authority or regulatory agency (e.g., 'FDA_CDER').
        source_document: Official specification or README document citation.
        reference_version: Semantic version of the reference codelist.
        valid_from: Earliest extract period where this code is valid (e.g., '2004Q1').
        valid_to: Latest extract period where this code is valid (None if active).
        is_active: Whether this code is currently active and acceptable.
    """

    code: str
    label: str
    definition: str
    source_system: str = "GENERIC"
    source_document: Optional[str] = None
    reference_version: str = "1.0.0"
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    is_active: bool = True


@dataclass(slots=True)
class OutcomeSemanticsEntry:
    """Raxtik-derived clinical and regulatory semantics for patient outcomes.

    Attributes:
        outcome_code: Outcome category code matching reference dimensions (e.g. 'DE', 'LT').
        is_serious: Clinical flag indicating seriousness criteria under regulatory standards.
        ich_seriousness_category: ICH E2B seriousness classification name.
        severity_rank: Numeric hierarchy rank for comparing severity (1 = most severe, e.g. Death).
        raxtik_semantics_version: Version of the Raxtik clinical outcome semantics mapping.
        semantic_source: Authoritative medical guidelines source citation.
    """

    outcome_code: str
    is_serious: bool
    ich_seriousness_category: str
    severity_rank: int
    raxtik_semantics_version: str = "1.0.0"
    semantic_source: str = "ICH_E2B_R2_R3_GUIDELINES"
