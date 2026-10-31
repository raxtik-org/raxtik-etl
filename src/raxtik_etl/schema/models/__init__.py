"""Canonical Schema Entity Models for Pharmacovigilance."""

from typing import Type

from raxtik_etl.schema.base import BaseCanonicalModel
from raxtik_etl.schema.models.case import CanonicalCase
from raxtik_etl.schema.models.drug import CanonicalDrug
from raxtik_etl.schema.models.indication import CanonicalIndication
from raxtik_etl.schema.models.outcome import CanonicalOutcome
from raxtik_etl.schema.models.reaction import CanonicalReaction
from raxtik_etl.schema.models.report_source import CanonicalReportSource
from raxtik_etl.schema.models.therapy import CanonicalTherapy

CANONICAL_MODELS: tuple[Type[BaseCanonicalModel], ...] = (
    CanonicalCase,
    CanonicalDrug,
    CanonicalReaction,
    CanonicalOutcome,
    CanonicalIndication,
    CanonicalTherapy,
    CanonicalReportSource,
)

__all__ = [
    "CANONICAL_MODELS",
    "CanonicalCase",
    "CanonicalDrug",
    "CanonicalIndication",
    "CanonicalOutcome",
    "CanonicalReaction",
    "CanonicalReportSource",
    "CanonicalTherapy",
]
