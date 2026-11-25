"""Index cache path resolution and delegation to `raxtik_etl.distribution.huggingface`.

All Hugging Face HTTP transport, streaming downloads, and single-commit uploads
live in `raxtik_etl.distribution.huggingface`. This module resolves local vs.
remote index shard + delta URIs for any tier (`silver`, `gold`, etc.).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Tuple

from raxtik_etl.distribution.huggingface import (
    DEFAULT_HTTP_TIMEOUT,
    build_hf_resolve_url,
    download_hf_file,
    fetch_hf_json,
    upload_hf_index_folder,
)
from raxtik_etl.indexing.models import IndexManifest


def get_default_index_dir(source: str, tier: str = "silver") -> Path:
    """Returns the default local cache directory for a source + tier index."""
    base_cache = os.getenv("RAXTIK_CACHE_DIR")
    root = Path(base_cache) if base_cache else (Path.home() / ".cache" / "raxtik")
    return root / "indexes" / source.lower().strip() / tier.lower().strip()


def fetch_remote_index_manifest(
    repo_id: str,
    tier: str = "silver",
    revision: Optional[str] = None,
    timeout: int = DEFAULT_HTTP_TIMEOUT,
) -> Tuple[IndexManifest, List[str], List[str]]:
    """Fetches `{tier}/index/manifest.json` and returns `(manifest, base_shard_urls, delta_urls)`."""
    tier_clean = tier.lower().strip()
    rev, raw = fetch_hf_json(
        repo_id=repo_id,
        rel_path=f"{tier_clean}/index/manifest.json",
        revision=revision,
        timeout=timeout,
    )
    manifest = IndexManifest.from_dict(raw)
    snap = manifest.active_snapshot
    base_urls = [
        build_hf_resolve_url(repo_id, rev, f"{tier_clean}/index/{rel}") for rel in snap.shard_files
    ]
    delta_urls = [
        build_hf_resolve_url(repo_id, rev, f"{tier_clean}/index/{rel}")
        for rel in snap.active_delta_files
    ]
    return manifest, base_urls, delta_urls


def sync_remote_index_to_local_cache(
    repo_id: str,
    source: str,
    tier: str = "silver",
    revision: Optional[str] = None,
    index_dir: Optional[Path] = None,
    timeout: int = DEFAULT_HTTP_TIMEOUT,
) -> Tuple[IndexManifest, List[str], List[str]]:
    """Downloads the active snapshot's manifest, base shards, and active deltas into local cache.

    Already-cached immutable files are skipped automatically.
    """
    dest_root = index_dir or get_default_index_dir(source=source, tier=tier)
    manifest, base_urls, delta_urls = fetch_remote_index_manifest(
        repo_id=repo_id, tier=tier, revision=revision, timeout=timeout
    )
    manifest.save(dest_root / "manifest.json")

    local_base_uris: List[str] = []
    for rel_path, url in zip(manifest.active_snapshot.shard_files, base_urls, strict=True):
        local_file = dest_root / rel_path
        if not local_file.exists():
            download_hf_file(url=url, dest_path=local_file, timeout=timeout)
        local_base_uris.append(local_file.as_posix())

    local_delta_uris: List[str] = []
    for rel_path, url in zip(manifest.active_snapshot.active_delta_files, delta_urls, strict=True):
        local_file = dest_root / rel_path
        if not local_file.exists():
            download_hf_file(url=url, dest_path=local_file, timeout=timeout)
        local_delta_uris.append(local_file.as_posix())

    return manifest, local_base_uris, local_delta_uris


def resolve_local_index_shards(
    index_root: Path | str,
) -> Tuple[IndexManifest, List[str], List[str]]:
    """Loads a local index manifest and returns `(manifest, base_shard_paths, active_delta_paths)`."""
    root = Path(index_root)
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Local index manifest not found at {manifest_path}")
    manifest = IndexManifest.load(manifest_path)

    base_shards: List[str] = []
    for rel in manifest.active_snapshot.shard_files:
        p = root / rel
        if not p.exists():
            raise FileNotFoundError(f"Missing local base index shard: {p}")
        base_shards.append(p.as_posix())

    delta_files: List[str] = []
    for rel in manifest.active_snapshot.active_delta_files:
        p = root / rel
        if not p.exists():
            raise FileNotFoundError(f"Missing local index delta file: {p}")
        delta_files.append(p.as_posix())

    return manifest, base_shards, delta_files


def upload_index_to_hf(
    index_root: Path | str,
    repo_id: str,
    tier: str = "silver",
    token: Optional[str] = None,
    enforce_optimistic_concurrency: bool = True,
    tag: Optional[str] = None,
    force: bool = False,
) -> str:
    """Delegates index publication to `raxtik_etl.distribution.huggingface.upload_hf_index_folder`."""
    return upload_hf_index_folder(
        index_root=Path(index_root),
        repo_id=repo_id,
        tier=tier,
        token=token,
        enforce_optimistic_concurrency=enforce_optimistic_concurrency,
        tag=tag,
        force=force,
    )
