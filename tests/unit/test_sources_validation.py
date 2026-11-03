"""Unit tests for extract file and header validation helpers."""

from pathlib import Path

import pytest

from raxtik_etl.sources import (
    BaseSourceAdapter,
    check_file_exists_and_non_empty,
    check_required_columns,
    find_cached_archive,
    parse_delimited_header,
    read_first_line,
    validate_extract_file,
)


@pytest.mark.parametrize(
    ("file_state", "expected_exception", "match_regex"),
    [
        ("missing", FileNotFoundError, "does not exist"),
        ("empty", ValueError, r"empty \(0 bytes\)"),
    ],
)
def test_check_file_exists_and_non_empty_failures(
    tmp_path: Path, file_state: str, expected_exception: type[Exception], match_regex: str
):
    target = tmp_path / f"{file_state}.txt"
    if file_state == "empty":
        target.touch()

    with pytest.raises(expected_exception, match=match_regex):
        check_file_exists_and_non_empty(target)


def test_check_file_exists_and_non_empty_valid(tmp_path: Path):
    valid = tmp_path / "valid.txt"
    valid.write_text("ISR$CASE\n1$2\n")
    assert check_file_exists_and_non_empty(valid) == valid


def test_read_first_line(tmp_path: Path):
    f = tmp_path / "test.txt"
    f.write_text("HEADER1$HEADER2\nROW1$ROW2\n")
    assert read_first_line(f) == "HEADER1$HEADER2"

    whitespace_f = tmp_path / "ws.txt"
    whitespace_f.write_text("   \n\n")
    with pytest.raises(ValueError, match="has no header line"):
        read_first_line(whitespace_f)


@pytest.mark.parametrize(
    ("header_text", "delimiter", "expected"),
    [
        ("ISR$CASE$DRUGNAME", "$", {"isr", "case", "drugname"}),
        (" ISR $ CASE $ FOLL_SEQ $ ", "$", {"isr", "case", "foll_seq"}),
        ("primaryid,caseid,drug_seq", ",", {"primaryid", "caseid", "drug_seq"}),
        ("col1\tcol2\tcol3", "\t", {"col1", "col2", "col3"}),
    ],
)
def test_parse_delimited_header(header_text: str, delimiter: str, expected: set[str]):
    assert parse_delimited_header(header_text, delimiter=delimiter) == expected


@pytest.mark.parametrize(
    ("header_text", "delimiter"),
    [
        ("ISR$CASE", ","),
        ("HEADER1,HEADER2", "$"),
    ],
)
def test_parse_delimited_header_missing_delimiter(header_text: str, delimiter: str):
    with pytest.raises(ValueError, match="Delimiter .* not found"):
        parse_delimited_header(header_text, delimiter=delimiter)


def test_check_required_columns():
    available = {"isr", "case", "foll_seq", "age"}
    # Pass check
    check_required_columns(available, {"isr", "case"}, source_name="DEMO.TXT")

    # Fail check
    with pytest.raises(ValueError, match="Missing required columns.*primaryid"):
        check_required_columns(available, {"isr", "primaryid"}, source_name="DEMO.TXT")


def test_validate_extract_file_composition(tmp_path: Path):
    valid_file = tmp_path / "DEMO04Q1.TXT"
    valid_file.write_text("ISR$CASE$I_F_COD\n101$C1$I\n")

    cols = validate_extract_file(valid_file, required_columns={"isr", "case"}, delimiter="$")
    assert cols == {"isr", "case", "i_f_cod"}


def test_base_source_adapter_validate_extract_file(tmp_path: Path):
    class CustomAdapter(BaseSourceAdapter):
        source_name = "test_custom"

    adapter = CustomAdapter()
    valid_file = tmp_path / "EXTRACT.TXT"
    valid_file.write_text("ID$NAME$VAL\n1$A$10\n")

    cols = adapter.validate_extract_file(valid_file, required_columns={"id", "name"}, delimiter="$")
    assert cols == {"id", "name", "val"}


@pytest.mark.parametrize(
    ("filename", "file_size", "query_period", "expect_match"),
    [
        # Matching variations for 2004Q1
        ("aers_ascii_2004q1.zip", 100, "2004Q1", True),
        ("faers_ascii_2004q1.zip", 100, "2004q1", True),
        ("2004q1_ascii.zip", 100, "2004-Q1", True),
        ("FAERS_ASCII_2004Q1.ZIP", 100, "2004_q1", True),
        # Modern naming variations for 2024Q3
        ("faers_ascii_2024q3.zip", 100, "2024Q3", True),
        # Mismatched quarter
        ("aers_ascii_2004q1.zip", 100, "2004Q2", False),
        ("aers_ascii_2004q1.zip", 100, "2005Q1", False),
        # 0 byte empty files ignored
        ("aers_ascii_2004q1.zip", 0, "2004Q1", False),
        # Non-zip files ignored
        ("aers_ascii_2004q1.txt", 100, "2004Q1", False),
    ],
)
def test_find_cached_archive(
    tmp_path: Path, filename: str, file_size: int, query_period: str, expect_match: bool
):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    f = cache_dir / filename
    if file_size > 0:
        f.write_bytes(b"x" * file_size)
    else:
        f.touch()

    result = find_cached_archive(cache_dir, query_period)
    if expect_match:
        assert result == f
    else:
        assert result is None


def test_find_cached_archive_non_existent_directory(tmp_path: Path):
    assert find_cached_archive(tmp_path / "does_not_exist", "2004Q1") is None
