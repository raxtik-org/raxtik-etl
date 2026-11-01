"""Plugin Registry and Discovery for Source Connectors.

Discovers and instantiates source connectors registered via standard Python entry points
under the group `raxtik_etl.sources`.
"""

from __future__ import annotations

from functools import lru_cache
from importlib.metadata import entry_points, version
from typing import Dict, Type

from raxtik_etl.sources.protocol import SourceAdapter

ENTRY_POINT_GROUP = "raxtik_etl.sources"


class SourcePluginNotFoundError(Exception):
    """Raised when a requested source connector is not installed in the environment."""

    pass


def get_available_sources() -> Dict[str, Type[SourceAdapter]]:
    """Discovers all source connectors registered under `raxtik_etl.sources`.

    Returns:
        Mapping of connector name to connector class.
    """
    discovered = {}
    eps = entry_points(group=ENTRY_POINT_GROUP)
    for ep in eps:
        try:
            adapter_cls = ep.load()
            discovered[ep.name] = adapter_cls
        except Exception:
            # Skip invalid plugins but don't crash discovery
            continue
    return discovered


@lru_cache(maxsize=16)
def get_source_adapter(source_name: str) -> SourceAdapter:
    """Returns a cached singleton instance of the requested source adapter.

    Args:
        source_name: The registered name of the connector (e.g. 'faers').

    Returns:
        Instantiated SourceAdapter protocol implementation.

    Raises:
        SourcePluginNotFoundError: If connector is not registered in the environment.
    """
    sources = get_available_sources()
    if source_name not in sources:
        installed = list(sources.keys())
        raise SourcePluginNotFoundError(
            f"Source connector '{source_name}' is not installed. "
            f"Discovered connectors: {installed}. "
            f"Install the connector package (e.g., `pip install raxtik-source-{source_name}`)."
        )

    adapter_cls = sources[source_name]
    adapter = adapter_cls()

    # Automatically resolve source_version from package metadata if not explicitly set
    if getattr(adapter, "source_version", None) is None:
        try:
            mod_pkg = adapter_cls.__module__.split(".")[0]
            adapter.source_version = version(mod_pkg)
        except Exception:
            try:
                adapter.source_version = version(f"raxtik-source-{source_name}")
            except Exception:
                pass

    return adapter
