"""Comprehensive unit tests for Canonical Schema, Registry, and Views."""

from __future__ import annotations

import pytest

from raxtik_etl.schema.canonical import (
    CanonicalCase,
    CanonicalDrug,
    DerivationStatus,
    Provenance,
)
from raxtik_etl.schema.registry import (
    CANONICAL_SCHEMA_VERSION,
    SCHEMA_REGISTRY,
    get_entity_fields,
)
from raxtik_etl.schema.views import get_latest_cases_view_sql


def test_provenance_and_versioning():
    prov = Provenance(
        source_system="FDA_FAERS_ASCII",
        data_period="2004Q1",
        source_file="DEMO04Q1.txt",
        source_record_locator="row:100",
        source_signature_id="S1",
        etl_version="0.1.0",
        canonical_schema_version=CANONICAL_SCHEMA_VERSION,
    )
    assert prov.source_signature_id == "S1"
    assert prov.data_period == "2004Q1"
    assert prov.canonical_schema_version == "1.0.0"
    assert prov.source_record_locator == "row:100"


def test_canonical_case_reported_vs_derived():
    case = CanonicalCase(
        primary_id="10001",
        case_id="1000",
        source_case_version=None,
        canonical_case_version=1,
        foll_seq="0",
        reported_age=45.0,
        reported_age_code="YR",
        standard_age_years=45.0,
        reported_sex_code="F",
        standard_sex_label="Female",
    )
    assert case.primary_id == "10001"
    assert case.source_case_version is None
    assert case.canonical_case_version == 1
    assert case.standard_age_years == 45.0
    assert case.standard_sex_label == "Female"


def test_canonical_drug_verbatim_preservation():
    drug = CanonicalDrug(
        primary_id="10001",
        case_id="1000",
        drug_seq="1",
        reported_drug_name="TYLENOL EXTRA STRENGTH ( )",
        reported_active_ingredient=None,
        structural_clean_drug_name="TYLENOL EXTRA STRENGTH",
        standard_concept_name="ACETAMINOPHEN",
        standard_concept_source="RAXTIK_DRUG_DICTIONARY",
        rxcui="1191",
        derivation_status=DerivationStatus.SUCCESS,
    )
    assert drug.reported_drug_name == "TYLENOL EXTRA STRENGTH ( )"
    assert drug.reported_active_ingredient is None
    assert drug.structural_clean_drug_name == "TYLENOL EXTRA STRENGTH"
    assert drug.standard_concept_name == "ACETAMINOPHEN"
    assert drug.derivation_status == DerivationStatus.SUCCESS


@pytest.mark.parametrize(
    ("entity", "expected_fields"),
    [
        ("demo", ["primary_id", "case_id", "event_date"]),
        ("drug", ["reported_drug_name", "role_code"]),
    ],
)
def test_schema_registry_entities(entity: str, expected_fields: list[str]) -> None:
    assert len(SCHEMA_REGISTRY) > 0
    fields = [f.field_name for f in get_entity_fields(entity)]
    for field in expected_fields:
        assert field in fields


def test_views_sql_generation():
    sql = get_latest_cases_view_sql()
    assert "CREATE OR REPLACE VIEW cases AS" in sql
    assert "canonical_case_version DESC" in sql


@pytest.mark.parametrize(
    ("model_cls", "expected_pks"),
    [
        (CanonicalCase, ["primary_id"]),
        (CanonicalDrug, ["primary_id", "drug_seq"]),
    ],
)
def test_canonical_models_primary_keys(model_cls, expected_pks: list[str]) -> None:
    assert model_cls.get_primary_keys() == expected_pks


def test_canonical_case_ddl():
    ddl = CanonicalCase.get_create_table_ddl()
    assert "CREATE TABLE IF NOT EXISTS demo (" in ddl
    assert "primary_id VARCHAR NOT NULL" in ddl
    assert "PRIMARY KEY (primary_id)" in ddl
