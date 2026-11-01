"""Unit tests for extract file and header validation helpers."""

from pathlib import Path

import pytest

from raxtik_etl.sources import (
    BaseSourceAdapter,
    check_file_exists_and_non_empty,
    check_required_columns,
    parse_delimited_header,
    read_first_line,
    validate_extract_file,
)


def test_check_file_exists_and_non_empty(tmp_path: Path):
    missing = tmp_path / "missing.txt"
    with pytest.raises(FileNotFoundError, match="does not exist"):
        check_file_exists_and_non_empty(missing)

    empty = tmp_path / "empty.txt"
    empty.touch()
    with pytest.raises(ValueError, match="empty \\(0 bytes\\)"):
        check_file_exists_and_non_empty(empty)

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


def test_parse_delimited_header():
    cols = parse_delimited_header("ISR$CASE$DRUGNAME", delimiter="$")
    assert cols == {"isr", "case", "drugname"}

    cols_spaces = parse_delimited_header(" ISR $ CASE $ FOLL_SEQ $ ", delimiter="$")
    assert cols_spaces == {"isr", "case", "foll_seq"}

    with pytest.raises(ValueError, match="Delimiter ',' not found"):
        parse_delimited_header("ISR$CASE", delimiter=",")


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
