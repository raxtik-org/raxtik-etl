"""Plugin Registry and Discovery for Source Connectors.

Discovers and instantiates source connectors registered via standard Python entry points
under the group `raxtik_etl.sources`.
"""

from __future__ import annotations

import sys
from typing import Dict, Type

from raxtik_etl.sources.protocol import SourceAdapter

if sys.version_info >= (3, 10):
    from importlib.metadata import entry_points
else:
    from importlib_metadata import entry_points

ENTRY_POINT_GROUP = "raxtik_etl.sources"


class SourcePluginNotFoundError(Exception):
    """Raised when a requested source connector is not installed in the environment."""

    pass


def get_available_sources() -> Dict[str, Type[SourceAdapter]]:
    """Discovers all source connectors registered under `raxtik_etl.sources`."""
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


def get_source_adapter(source_name: str) -> SourceAdapter:
    """Returns an instance of the requested source adapter.

    Args:
        source_name: The registered name of the connector (e.g. 'faers').

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
    return adapter_cls()
