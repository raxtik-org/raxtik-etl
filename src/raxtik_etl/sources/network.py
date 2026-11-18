"""Streaming HTTP network utilities with tqdm progress indicators.

Provides generic streaming download and remote file retrieval routines
shared across data source fetchers and distribution clients.
"""

from __future__ import annotations

import os
import time
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
    url: Optional[str] = None,
    session: Optional[requests.Session] = None,
    max_retries: int = 5,
    timeout: int = DEFAULT_HTTP_TIMEOUT,
) -> None:
    """Stream an HTTP response directly to disk with resumable retries and a tqdm progress bar.

    Downloads to an ephemeral staging file (.tmp_<name>) and atomically replaces
    target_path upon full completion to prevent leaving corrupted files if interrupted.
    If the remote server terminates the connection prematurely, automatically resumes
    from the current byte offset using HTTP Range requests.

    Args:
        response: Open streaming requests.Response object.
        target_path: Destination file Path.
        chunk_size: Chunk size in bytes for stream iteration.
        desc: Progress bar description (defaults to 'Downloading <filename>').
        url: Remote file URL (used for reconnecting on broken pipes).
        session: Optional requests.Session for reconnecting.
        max_retries: Maximum reconnection attempts on dropped streams.
        timeout: HTTP request timeout in seconds for reconnection attempts.
    """
    request_url = url or getattr(response, "url", None)
    http_session = session or requests.Session()

    # Determine total file size from Content-Length or Content-Range
    total_size = 0
    if "content-length" in response.headers:
        try:
            total_size = int(response.headers["content-length"])
        except ValueError:
            pass
    if "content-range" in response.headers:
        try:
            total_size = int(response.headers["content-range"].split("/")[-1])
        except ValueError:
            pass

    # If chunked transfer without content-length, probe total size via range query
    if total_size <= 0 and request_url:
        try:
            probe = http_session.get(
                request_url,
                headers={"Accept-Encoding": "identity", "Range": "bytes=0-0"},
                timeout=min(timeout, 10),
            )
            if "content-range" in probe.headers:
                total_size = int(probe.headers["content-range"].split("/")[-1])
            probe.close()
        except Exception:
            pass

    bar_desc = desc or f"Downloading {target_path.name}"
    tmp_path = target_path.with_name(f".tmp_{target_path.name}")
    downloaded = 0

    if tmp_path.exists():
        downloaded = tmp_path.stat().st_size
        if total_size > 0 and downloaded >= total_size:
            tmp_path.replace(target_path)
            return

    curr_response = response
    retries = 0

    with tqdm(
        desc=bar_desc,
        total=total_size if total_size > 0 else None,
        initial=downloaded,
        unit="iB",
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        while True:
            try:
                # If resuming from an offset and current response is not already a 206 Partial Content
                if downloaded > 0 and curr_response.status_code != 206 and request_url:
                    curr_response.close()
                    curr_response = http_session.get(
                        request_url,
                        headers={"Accept-Encoding": "identity", "Range": f"bytes={downloaded}-"},
                        stream=True,
                        timeout=timeout,
                    )
                    if curr_response.status_code != 206:
                        # Server does not support Range; restart from beginning
                        downloaded = 0
                        bar.reset(total=total_size if total_size > 0 else None)

                file_mode = "ab" if downloaded > 0 else "wb"
                with open(tmp_path, file_mode) as f:
                    for chunk in curr_response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            size = len(chunk)
                            downloaded += size
                            bar.update(size)

                # Successful stream completion
                break

            except (
                requests.RequestException,
                ConnectionResetError,
                TimeoutError,
                BrokenPipeError,
            ) as exc:
                retries += 1
                if retries > max_retries or not request_url:
                    raise
                wait_sec = min(2**retries, 10)
                tqdm.write(
                    f"\n[raxtik-etl] Connection interrupted: {exc}. "
                    f"Resuming from {downloaded:,} bytes in {wait_sec}s (retry {retries}/{max_retries})..."
                )
                time.sleep(wait_sec)
                curr_response = http_session.get(
                    request_url,
                    headers={"Accept-Encoding": "identity", "Range": f"bytes={downloaded}-"},
                    stream=True,
                    timeout=timeout,
                )
            finally:
                if curr_response:
                    curr_response.close()

    tmp_path.replace(target_path)


def download_file(
    url: str,
    target_path: Union[Path, str],
    *,
    timeout: int = DEFAULT_HTTP_TIMEOUT,
    chunk_size: int = 1024 * 1024,
    overwrite: bool = False,
    session: Optional[requests.Session] = None,
) -> Path:
    """Download a remote URL to disk with progress bar streaming and automatic resume.

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
    headers = {"Accept-Encoding": "identity"}
    resp = http.get(url, headers=headers, stream=True, timeout=timeout)
    resp.raise_for_status()

    stream_download(resp, dest, chunk_size=chunk_size, url=url, session=http, timeout=timeout)
    return dest
