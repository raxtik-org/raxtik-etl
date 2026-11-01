"""Unit tests for Source Plugin Discovery and Registry in raxtik-etl."""

from unittest.mock import MagicMock, patch

import pytest

from raxtik_etl.sources import (
    SourceAdapter,
    SourcePluginNotFoundError,
    get_available_sources,
    get_source_adapter,
)


def test_plugin_discovery_with_mock_entrypoint():
    """Verify that get_available_sources discovers any entry-point registered under raxtik_etl.sources."""
    mock_ep = MagicMock()
    mock_ep.name = "mock_source"
    mock_adapter_cls = MagicMock(spec=SourceAdapter)
    mock_ep.load.return_value = mock_adapter_cls

    with patch("raxtik_etl.sources.registry.entry_points", return_value=[mock_ep]):
        sources = get_available_sources()
        assert "mock_source" in sources
        assert sources["mock_source"] == mock_adapter_cls


def test_plugin_discovery_finds_registered_sources():
    """Verify that get_available_sources discovers installed connectors via entry-points."""
    sources = get_available_sources()
    assert isinstance(sources, dict)
    if "faers" not in sources:
        pytest.skip("raxtik-source-faers connector is not installed in the environment.")
    adapter_cls = sources["faers"]
    instance = adapter_cls()
    assert isinstance(instance, SourceAdapter)


def test_get_source_adapter_instantiation():
    """Verify that get_source_adapter instantiates the requested connector."""
    sources = get_available_sources()
    if "faers" not in sources:
        pytest.skip("raxtik-source-faers connector is not installed in the environment.")
    adapter = get_source_adapter("faers")
    assert adapter.source_name == "faers"
    assert hasattr(adapter, "extract_and_load")


def test_plugin_not_found_raises_clean_error():
    """Verify that requesting an uninstalled connector raises SourcePluginNotFoundError."""
    with pytest.raises(
        SourcePluginNotFoundError, match="Source connector 'unknown_xyz' is not installed"
    ):
        get_source_adapter("unknown_xyz")


def test_get_dataset_client_fallback():
    """Verify get_dataset_client falls back to BaseDataset when no custom client registered."""
    from raxtik_etl.sdk import BaseDataset, get_dataset_client

    client_cls = get_dataset_client("unregistered_source")
    assert client_cls is BaseDataset


def test_get_source_adapter_cached_singleton():
    """Verify get_source_adapter returns cached singleton instance across repeated calls."""
    sources = get_available_sources()
    if "faers" not in sources:
        pytest.skip("raxtik-source-faers connector is not installed in the environment.")
    adapter1 = get_source_adapter("faers")
    adapter2 = get_source_adapter("faers")
    assert adapter1 is adapter2


def test_find_files_by_entity_case_insensitive_and_nested(tmp_path):
    """Verify find_files_by_entity matches uppercase .TXT files in subdirectories."""
    from raxtik_etl.sources.discovery import find_files_by_entity

    # Simulate FDA archive tree: root has README.doc, SIZE04Q1.TXT; ascii/ has DEMO04Q1.TXT
    (tmp_path / "README.doc").touch()
    (tmp_path / "SIZE04Q1.TXT").touch()
    sub_ascii = tmp_path / "ascii"
    sub_ascii.mkdir()
    (sub_ascii / "DEMO04Q1.TXT").touch()
    (sub_ascii / "DRUG04Q1.TXT").touch()

    mapping = {"DEMO": "demo", "DRUG": "drug"}
    found = find_files_by_entity(tmp_path, mapping, pattern="*.txt")

    assert "demo" in found
    assert len(found["demo"]) == 1
    assert found["demo"][0] == sub_ascii / "DEMO04Q1.TXT"

    assert "drug" in found
    assert len(found["drug"]) == 1
    assert found["drug"][0] == sub_ascii / "DRUG04Q1.TXT"
