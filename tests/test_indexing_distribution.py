"""Tests for index distribution, remote manifest sync, and HF index upload."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, List

import pytest

from raxtik_etl.distribution.huggingface import (
    build_hf_resolve_url,
    download_hf_file,
    fetch_hf_json,
    upload_hf_index_folder,
)
from raxtik_etl.indexing.distribution import (
    fetch_remote_index_manifest,
    get_default_index_dir,
    resolve_local_index_shards,
    sync_remote_index_to_local_cache,
    upload_index_to_hf,
)
from raxtik_etl.indexing.models import (
    INDEX_FORMAT_VERSION,
    IndexManifest,
    PartitioningSpec,
    ResolutionPolicy,
    SnapshotRecord,
)


def _sample_manifest(
    snapshot_id: str = "snap_2004Q2",
    parent_snapshot_id: str | None = "snap_2004Q1",
) -> IndexManifest:
    snap = SnapshotRecord(
        snapshot_id=snapshot_id,
        generation=2,
        tier="silver",
        source="faers",
        parent_snapshot_id=parent_snapshot_id,
        created_at="2026-01-01T00:00:00Z",
        shard_count=2,
        indexed_periods=["2004Q1", "2004Q2"],
        ledger_files=["ledger/2004Q1.parquet", "ledger/2004Q2.parquet"],
        total_submissions=10,
        total_entities=8,
        cross_period_entities=2,
        state_dir="state/base/snap_2004Q1",
        shard_files=[
            "state/base/snap_2004Q1/shard_00.parquet",
            "state/base/snap_2004Q1/shard_01.parquet",
        ],
        active_delta_files=["state/deltas/delta_snap_2004Q2.parquet"],
        partitioning=PartitioningSpec(shard_count=2),
    )
    return IndexManifest(
        format_version=INDEX_FORMAT_VERSION,
        tier="silver",
        source="faers",
        active_snapshot_id=snapshot_id,
        generation=2,
        updated_at="2026-01-01T00:00:00Z",
        policy=ResolutionPolicy(shard_count=2),
        active_snapshot=snap,
        snapshot_history=[snapshot_id],
    )


def test_get_default_index_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RAXTIK_CACHE_DIR", str(tmp_path))
    assert get_default_index_dir("FAERS", "Silver") == tmp_path / "indexes" / "faers" / "silver"
    monkeypatch.delenv("RAXTIK_CACHE_DIR", raising=False)
    assert get_default_index_dir("faers", "silver").parts[-3:] == ("indexes", "faers", "silver")


def test_build_hf_resolve_url() -> None:
    url = build_hf_resolve_url("org/repo", "v1.0.0", "/silver/index/manifest.json")
    assert (
        url == "https://huggingface.co/datasets/org/repo/resolve/v1.0.0/silver/index/manifest.json"
    )


@pytest.mark.parametrize("status_code", [200, 404])
def test_fetch_hf_json(monkeypatch: pytest.MonkeyPatch, status_code: int) -> None:
    monkeypatch.setattr(
        "raxtik_etl.distribution.huggingface.resolve_hf_revision",
        lambda repo_id, revision=None, timeout=30: revision or "v1.0.0",
    )
    monkeypatch.setattr(
        "raxtik_etl.distribution.huggingface.requests.get",
        lambda url, timeout=30: SimpleNamespace(
            status_code=status_code, text=json.dumps({"ok": True})
        ),
    )
    if status_code == 200:
        rev, payload = fetch_hf_json("org/repo", "silver/index/manifest.json")
        assert rev == "v1.0.0" and payload == {"ok": True}
    else:
        with pytest.raises(FileNotFoundError, match="HTTP 404"):
            fetch_hf_json("org/repo", "silver/index/manifest.json")


@pytest.mark.parametrize("should_fail", [False, True])
def test_download_hf_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, should_fail: bool
) -> None:
    class _Resp:
        def __enter__(self) -> "_Resp":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def raise_for_status(self) -> None:
            if should_fail:
                raise RuntimeError("HTTP 500")

        def iter_content(self, chunk_size: int = 1024) -> Any:
            yield from (b"parquet", b"", b"-bytes")

    monkeypatch.setattr(
        "raxtik_etl.distribution.huggingface.requests.get",
        lambda url, stream=True, timeout=30: _Resp(),
    )
    dest = tmp_path / "nested" / "shard.parquet"
    if should_fail:
        with pytest.raises(RuntimeError, match="HTTP 500"):
            download_hf_file("https://example.com/shard.parquet", dest)
        assert not dest.exists()
    else:
        assert download_hf_file("https://example.com/shard.parquet", dest) == dest
        assert dest.read_bytes() == b"parquet-bytes"
    assert not dest.with_suffix(".parquet.tmp").exists()


def test_sync_remote_index_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    manifest = _sample_manifest()
    monkeypatch.setattr(
        "raxtik_etl.indexing.distribution.fetch_hf_json",
        lambda repo_id, rel_path, revision=None, timeout=30: ("v0.1.0", manifest.to_dict()),
    )

    fetched, base_urls, delta_urls = fetch_remote_index_manifest("org/repo", tier="silver")
    assert fetched.active_snapshot_id == "snap_2004Q2"
    assert len(base_urls) == 2 and len(delta_urls) == 1

    pre_cached = tmp_path / manifest.active_snapshot.shard_files[0]
    pre_cached.parent.mkdir(parents=True, exist_ok=True)
    pre_cached.write_bytes(b"cached")

    downloaded: List[str] = []

    def _fake_download(url: str, dest_path: Path, timeout: int = 30) -> Path:
        downloaded.append(dest_path.name)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(b"downloaded")
        return dest_path

    monkeypatch.setattr("raxtik_etl.indexing.distribution.download_hf_file", _fake_download)

    synced, local_bases, local_deltas = sync_remote_index_to_local_cache(
        repo_id="org/repo", source="faers", tier="silver", index_dir=tmp_path
    )
    assert synced.active_snapshot_id == "snap_2004Q2"
    assert len(local_bases) == 2 and len(local_deltas) == 1
    assert downloaded == ["shard_01.parquet", "delta_snap_2004Q2.parquet"]


def test_resolve_local_index_shards(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Local index manifest not found"):
        resolve_local_index_shards(tmp_path)

    manifest = _sample_manifest()
    manifest.save(tmp_path / "manifest.json")

    with pytest.raises(FileNotFoundError, match="Missing local base index shard"):
        resolve_local_index_shards(tmp_path)

    for rel in manifest.active_snapshot.shard_files:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"shard")

    with pytest.raises(FileNotFoundError, match="Missing local index delta file"):
        resolve_local_index_shards(tmp_path)

    for rel in manifest.active_snapshot.active_delta_files:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"delta")

    loaded, bases, deltas = resolve_local_index_shards(tmp_path)
    assert loaded.active_snapshot_id == "snap_2004Q2" and len(bases) == 2 and len(deltas) == 1


def test_upload_hf_index_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Index manifest not found"):
        upload_hf_index_folder(tmp_path, repo_id="org/repo", token="tok")

    _sample_manifest().save(tmp_path / "manifest.json")

    monkeypatch.delenv("HF_TOKEN", raising=False)
    with pytest.raises(ValueError, match="Hugging Face write token required"):
        upload_hf_index_folder(tmp_path, repo_id="org/repo", token=None)

    monkeypatch.setattr(
        "raxtik_etl.distribution.huggingface.fetch_hf_json",
        lambda **kwargs: ("main", {"active_snapshot_id": "snap_2004Q9_other"}),
    )
    with pytest.raises(RuntimeError, match="Optimistic concurrency conflict"):
        upload_hf_index_folder(tmp_path, repo_id="org/repo", token="tok")

    monkeypatch.setattr(
        "raxtik_etl.distribution.huggingface.fetch_hf_json",
        lambda **kwargs: (_ for _ in ()).throw(FileNotFoundError("no remote manifest")),
    )

    uploads: List[dict[str, Any]] = []
    tags: List[dict[str, Any]] = []

    class _FakeHfApi:
        def __init__(self, token: str) -> None:
            self.token = token

        def upload_folder(self, **kwargs: Any) -> None:
            uploads.append(kwargs)

    monkeypatch.setattr("huggingface_hub.HfApi", _FakeHfApi)
    monkeypatch.setattr(
        "raxtik_etl.distribution.huggingface.tag_hf_dataset", lambda **kwargs: tags.append(kwargs)
    )

    url = upload_index_to_hf(
        index_root=tmp_path,
        repo_id="org/repo",
        tier="silver",
        token="tok",
        tag="v0.1.0",
        force=True,
    )
    assert url.endswith("/resolve/v0.1.0/silver/index/manifest.json")
    assert uploads[0]["path_in_repo"] == "silver/index"
    assert tags == [{"repo_id": "org/repo", "tag": "v0.1.0", "token": "tok", "force": True}]
