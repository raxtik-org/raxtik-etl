"""Comprehensive unit tests for Canonical Schema, Registry, and Views."""

from raxtik_etl.schema.canonical import (
    CanonicalCase,
    CanonicalDrug,
    DerivationStatus,
    Provenance,
)
from raxtik_etl.schema.registry import (
    CANONICAL_SCHEMA_VERSION,
    CASE_RESOLUTION_VERSION,
    get_signature_mapping,
)
from raxtik_etl.schema.views import get_latest_cases_view_sql


def test_provenance_and_versioning():
    prov = Provenance(
        source_system="FDA_FAERS_ASCII",
        source_release="2004Q1",
        source_file="DEMO04Q1.txt",
        source_record_locator="row:100",
        source_signature_id="S1",
        etl_version="0.1.0",
        canonical_schema_version=CANONICAL_SCHEMA_VERSION,
    )
    assert prov.source_signature_id == "S1"
    assert prov.canonical_schema_version == "1.0.0"
    assert prov.source_record_locator == "row:100"


def test_canonical_case_reported_vs_derived():
    case = CanonicalCase(
        primary_id="10001",
        case_id="1000",
        fda_case_version=None,  # Legacy S1 has no fda_case_version
        canonical_case_version=1,
        foll_seq="0",
        reported_age=45.0,
        reported_age_code="YR",
        standard_age_years=45.0,
        reported_sex_code="F",
        standard_sex_label="Female",
    )
    assert case.primary_id == "10001"
    assert case.fda_case_version is None
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


def test_schema_registry_signature_mappings():
    # Verify S1 (Legacy AERS) maps ISR to primary_id and CASE to case_id
    demo_s1_map = get_signature_mapping("S1", "demo")
    assert demo_s1_map["isr"] == "primary_id"
    assert demo_s1_map["case"] == "case_id"
    assert demo_s1_map["gndr_cod"] == "reported_sex_code"
    assert "prod_ai" not in get_signature_mapping("S1", "drug")

    # Verify S3 (Modern FAERS) maps PRIMARYID and PROD_AI
    demo_s3_map = get_signature_mapping("S3", "demo")
    assert demo_s3_map["primaryid"] == "primary_id"
    assert demo_s3_map["sex"] == "reported_sex_code"

    drug_s3_map = get_signature_mapping("S3", "drug")
    assert drug_s3_map["prod_ai"] == "reported_active_ingredient"


def test_views_sql_generation():
    sql = get_latest_cases_view_sql()
    assert "CREATE OR REPLACE VIEW cases AS" in sql
    assert f"Version: {CASE_RESOLUTION_VERSION}" in sql
    assert "canonical_case_version DESC" in sql
