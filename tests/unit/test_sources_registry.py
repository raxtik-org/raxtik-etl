"""Unit tests for Source Plugin Discovery and Registry in raxtik-etl."""

import pytest

from raxtik_etl.sources import (
    SourceAdapter,
    SourcePluginNotFoundError,
    get_available_sources,
    get_source_adapter,
)


def test_plugin_discovery_finds_registered_sources():
    """Verify that get_available_sources discovers installed connectors via entry-points."""
    sources = get_available_sources()
    assert isinstance(sources, dict)
    # The faers connector is installed as an entry point
    assert "faers" in sources
    adapter_cls = sources["faers"]
    instance = adapter_cls()
    assert isinstance(instance, SourceAdapter)


def test_get_source_adapter_instantiation():
    """Verify that get_source_adapter instantiates the requested connector."""
    adapter = get_source_adapter("faers")
    assert adapter.source_name == "faers"
    assert hasattr(adapter, "extract_and_load")


def test_plugin_not_found_raises_clean_error():
    """Verify that requesting an uninstalled connector raises SourcePluginNotFoundError."""
    with pytest.raises(
        SourcePluginNotFoundError, match="Source connector 'unknown_xyz' is not installed"
    ):
        get_source_adapter("unknown_xyz")
