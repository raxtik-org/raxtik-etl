"""Unit tests for FAERS $-delimited ASCII parser."""

from pathlib import Path

from raxtik_etl.sources.faers.parser import detect_table_type, parse_faers_ascii_file


def test_detect_table_type():
    assert detect_table_type("DEMO24Q1.txt") == "demo"
    assert detect_table_type("drug24q1.txt") == "drug"
    assert detect_table_type("/path/to/REAC24Q1.TXT") == "reac"
    assert detect_table_type("OUTC24Q1.txt") == "outc"
    assert detect_table_type("INDI24Q1.txt") == "indi"
    assert detect_table_type("unknown_file.txt") is None


def test_parse_demo_file(fixtures_dir: Path):
    demo_file = fixtures_dir / "DEMO24Q1.txt"
    rows = list(parse_faers_ascii_file(demo_file, table_type="demo"))
    assert len(rows) == 5
    first = rows[0]
    assert first["primaryid"] == "10000001"
    assert first["caseid"] == "10000001"
    assert first["sex"] == "F"
    assert first["age"] == "45"
    assert first["age_cod"] == "YR"
    assert first["_table_type"] == "demo"


def test_parse_drug_file(fixtures_dir: Path):
    drug_file = fixtures_dir / "DRUG24Q1.txt"
    rows = list(parse_faers_ascii_file(drug_file, table_type="drug"))
    assert len(rows) == 5
    aspirin_row = rows[0]
    assert aspirin_row["drugname"] == "ASPIRIN"
    assert aspirin_row["role_cod"] == "PS"
    assert aspirin_row["route"] == "Oral"
