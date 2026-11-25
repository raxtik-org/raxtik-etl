"""Unit tests for the generic delimited source parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from raxtik_etl.sources.parser import clean_field_name, detect_file_entity, parse_delimited_file


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("  Primary ID  ", "primary_id"), ("Drug-Seq#1", "drug_seq_1"), ("___CASE_ID___", "case_id")],
)
def test_clean_field_name(raw: str, expected: str) -> None:
    assert clean_field_name(raw) == expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [("DEMO24Q1.txt", "demo"), (Path("/tmp/drug_2024q1.txt"), "drug"), ("UNKNOWN.txt", None)],
)
def test_detect_file_entity(path: str | Path, expected: str | None) -> None:
    assert detect_file_entity(path, {"DEMO": "demo", "DRUG": "drug"}) == expected


def test_parse_delimited_file(tmp_path: Path) -> None:
    sample = tmp_path / "DEMO24Q1.txt"
    sample.write_text("Primary ID$Case-ID$Age\n101$C1$45\n\n102$C2$   \n", encoding="utf-8")

    records = list(parse_delimited_file(sample, delimiter="$", prefix_mapping={"DEMO": "demo"}))
    assert records == [
        {"primary_id": "101", "case_id": "C1", "age": "45", "_table_type": "demo"},
        {"primary_id": "102", "case_id": "C2", "age": None, "_table_type": "demo"},
    ]


def test_parse_missing_and_empty_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        list(parse_delimited_file(tmp_path / "missing.txt"))

    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    assert list(parse_delimited_file(empty, delimiter=",")) == []


def test_parse_encoding_fallback(tmp_path: Path) -> None:
    latin_file = tmp_path / "REAC24Q1.txt"
    latin_file.write_bytes("primaryid$pt\n101$Calf\xe9\n".encode("latin-1"))

    rows = list(parse_delimited_file(latin_file, delimiter="$", table_type="reac"))
    assert len(rows) == 1 and rows[0]["_table_type"] == "reac"

    with pytest.raises(OSError, match="Unable to open"):
        list(parse_delimited_file(latin_file, encodings=["nonexistent-encoding-xyz"]))
