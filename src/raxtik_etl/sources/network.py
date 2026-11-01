"""Streaming HTTP network utilities with tqdm progress indicators.

Provides generic streaming download and remote file retrieval routines
shared across data source fetchers and distribution clients.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union

import requests
from tqdm import tqdm

DEFAULT_HTTP_TIMEOUT: int = int(os.getenv("RAXTIK_HTTP_TIMEOUT", "120"))


def stream_download(
    response: requests.Response,
    target_path: Path,
    chunk_size: int = 1024 * 1024,
    desc: Optional[str] = None,
) -> None:
    """Stream an open HTTP response directly to disk with a tqdm progress bar.

    Downloads to an ephemeral staging file (.tmp_<name>) and atomically replaces
    target_path upon full completion to prevent leaving corrupted files if interrupted.

    Args:
        response: Open streaming requests.Response object.
        target_path: Destination file Path.
        chunk_size: Chunk size in bytes for stream iteration.
        desc: Progress bar description (defaults to 'Downloading <filename>').
    """
    total_size = int(response.headers.get("content-length", 0))
    bar_desc = desc or f"Downloading {target_path.name}"
    tmp_path = target_path.with_name(f".tmp_{target_path.name}")
    try:
        with (
            open(tmp_path, "wb") as f,
            tqdm(
                desc=bar_desc,
                total=total_size if total_size > 0 else None,
                unit="iB",
                unit_scale=True,
                unit_divisor=1024,
            ) as bar,
        ):
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    size = f.write(chunk)
                    bar.update(size)
        tmp_path.replace(target_path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def download_file(
    url: str,
    target_path: Union[Path, str],
    *,
    timeout: int = DEFAULT_HTTP_TIMEOUT,
    chunk_size: int = 1024 * 1024,
    overwrite: bool = False,
    session: Optional[requests.Session] = None,
) -> Path:
    """Download a remote URL to disk with progress bar streaming.

    Args:
        url: Remote file URL to download.
        target_path: Destination file Path.
        timeout: HTTP request timeout in seconds.
        chunk_size: Streaming chunk size in bytes.
        overwrite: If False, skips download if destination file already exists.
        session: Optional requests.Session instance to reuse.

    Returns:
        Path to the downloaded file.

    Raises:
        requests.RequestException: If download fails or server returns non-200.
    """
    dest = Path(target_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not overwrite:
        return dest

    http = session or requests.Session()
    resp = http.get(url, stream=True, timeout=timeout)
    resp.raise_for_status()

    stream_download(resp, dest, chunk_size=chunk_size)
    return dest
