"""Comprehensive unit tests for Canonical Schema, Registry, and Views."""

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
        drug_seq=1,
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


def test_schema_registry_entities():
    assert len(SCHEMA_REGISTRY) > 0
    demo_fields = get_entity_fields("demo")
    assert any(f.field_name == "primary_id" for f in demo_fields)
    assert any(f.field_name == "case_id" for f in demo_fields)
    assert any(f.field_name == "event_date" for f in demo_fields)

    drug_fields = get_entity_fields("drug")
    assert any(f.field_name == "reported_drug_name" for f in drug_fields)
    assert any(f.field_name == "role_code" for f in drug_fields)


def test_views_sql_generation():
    sql = get_latest_cases_view_sql()
    assert "CREATE OR REPLACE VIEW cases AS" in sql
    assert "canonical_case_version DESC" in sql


def test_declarative_canonical_models():
    pks = CanonicalCase.get_primary_keys()
    assert pks == ["primary_id"]

    drug_pks = CanonicalDrug.get_primary_keys()
    assert drug_pks == ["primary_id", "drug_seq"]

    ddl = CanonicalCase.get_create_table_ddl()
    assert "CREATE TABLE IF NOT EXISTS demo (" in ddl
    assert "primary_id VARCHAR NOT NULL" in ddl
    assert "PRIMARY KEY (primary_id)" in ddl
