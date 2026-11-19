"""Streaming HTTP network utilities with tqdm progress indicators.

Provides generic streaming download and remote file retrieval routines
shared across data source fetchers and distribution clients.
"""

from __future__ import annotations

import concurrent.futures
import os
import threading
import time
import zipfile
from pathlib import Path
from typing import Optional, Union

import requests
from tqdm import tqdm

DEFAULT_HTTP_TIMEOUT: int = int(os.getenv("RAXTIK_HTTP_TIMEOUT", "120"))
DEFAULT_PARALLEL_WORKERS: int = int(os.getenv("RAXTIK_DOWNLOAD_WORKERS", "8"))


def _parallel_range_download(
    url: str,
    target_path: Path,
    total_size: int,
    *,
    num_workers: int = DEFAULT_PARALLEL_WORKERS,
    timeout: int = DEFAULT_HTTP_TIMEOUT,
    desc: Optional[str] = None,
    session: Optional[requests.Session] = None,
    max_retries: int = 5,
) -> None:
    """Downloads a file using concurrent HTTP Range requests across multiple worker threads."""
    tmp_path = target_path.with_name(f".tmp_{target_path.name}")
    num_workers = max(1, min(num_workers, 16))
    chunk_len = (total_size + num_workers - 1) // num_workers

    ranges: list[tuple[int, int, int]] = []
    for i in range(num_workers):
        start = i * chunk_len
        end = min((i + 1) * chunk_len - 1, total_size - 1)
        if start <= end:
            ranges.append((i, start, end))

    bar_desc = desc or f"Downloading {target_path.name}"
    lock = threading.Lock()

    # Clean up any leftover part files from prior interrupted attempts
    for p in tmp_path.parent.glob(f"{tmp_path.name}.part*"):
        p.unlink(missing_ok=True)

    with tqdm(
        desc=bar_desc,
        total=total_size,
        unit="iB",
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:

        def fetch_range_part(part_idx: int, start: int, end: int) -> None:
            part_path = tmp_path.with_name(f"{tmp_path.name}.part{part_idx}")
            expected_bytes = end - start + 1

            # Dedicated thread session prevents server cookie-based connection throttling
            worker_session = requests.Session()
            worker_session.headers.update({"Accept-Encoding": "identity"})

            retries = 0
            try:
                while retries <= max_retries:
                    try:
                        headers = {
                            "Accept-Encoding": "identity",
                            "Range": f"bytes={start}-{end}",
                        }
                        read_timeout = (min(15, timeout), min(25, timeout))
                        resp = worker_session.get(
                            url, headers=headers, stream=True, timeout=read_timeout
                        )
                        resp.raise_for_status()

                        # Verify server returned 206 Partial Content
                        if resp.status_code != 206:
                            raise requests.RequestException(
                                f"Expected 206 Partial Content but got {resp.status_code}"
                            )

                        received = 0
                        with open(part_path, "wb") as f:
                            for chunk in resp.iter_content(chunk_size=128 * 1024):
                                if chunk:
                                    f.write(chunk)
                                    chunk_size = len(chunk)
                                    received += chunk_size
                                    with lock:
                                        bar.update(chunk_size)

                        if received == expected_bytes:
                            return

                        # Chunk incomplete, rollback progress and retry
                        with lock:
                            bar.update(-received)
                        part_path.unlink(missing_ok=True)
                        raise requests.RequestException(
                            f"Part {part_idx} incomplete: {received}/{expected_bytes} bytes"
                        )

                    except (
                        requests.RequestException,
                        ConnectionResetError,
                        TimeoutError,
                        BrokenPipeError,
                    ):
                        retries += 1
                        if retries > max_retries:
                            raise
                        time.sleep(min(2**retries, 8))
            finally:
                worker_session.close()

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(ranges))
        try:
            futures = [
                executor.submit(fetch_range_part, idx, start, end) for idx, start, end in ranges
            ]
            concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_EXCEPTION)
            for f in futures:
                f.result()
        finally:
            executor.shutdown(wait=True)

    # Reassemble parts sequentially into tmp_path
    with open(tmp_path, "wb") as outfile:
        for idx, start, end in ranges:
            part_path = tmp_path.with_name(f"{tmp_path.name}.part{idx}")
            expected = end - start + 1
            if not part_path.exists() or part_path.stat().st_size != expected:
                raise IOError(f"Part {idx} missing or corrupted during assembly")
            with open(part_path, "rb") as infile:
                while True:
                    buf = infile.read(1024 * 1024)
                    if not buf:
                        break
                    outfile.write(buf)
            part_path.unlink(missing_ok=True)

    if target_path.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(tmp_path, "r") as zf:
                bad_entry = zf.testzip()
                if bad_entry is not None:
                    raise zipfile.BadZipFile(f"CRC/deflate verification failed on '{bad_entry}'")
        except Exception as exc:
            tmp_path.unlink(missing_ok=True)
            raise ValueError(
                f"Downloaded archive '{tmp_path.name}' failed full zip integrity verification: {exc}"
            )

    tmp_path.replace(target_path)


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
            if target_path.suffix.lower() == ".zip" and not zipfile.is_zipfile(tmp_path):
                tmp_path.unlink(missing_ok=True)
                downloaded = 0
            else:
                tmp_path.replace(target_path)
                return

    # If the remote server supports HTTP Range and file is >= 4 MB, execute fast parallel multipart download
    if request_url and total_size >= 4 * 1024 * 1024:
        # Clear any stale partial sequential temp file so workers can download parallel chunks cleanly
        if tmp_path.exists() and total_size > 0 and downloaded < total_size:
            tmp_path.unlink(missing_ok=True)
        try:
            if response:
                try:
                    response.close()
                except Exception:
                    pass
            _parallel_range_download(
                url=request_url,
                target_path=target_path,
                total_size=total_size,
                desc=bar_desc,
                timeout=timeout,
                session=http_session,
                max_retries=max_retries,
            )
            return
        except Exception as exc:
            tqdm.write(
                f"\n[raxtik-etl] Parallel download failed ({exc}). Falling back to sequential stream..."
            )
            curr_response = http_session.get(
                request_url,
                headers={"Accept-Encoding": "identity"},
                stream=True,
                timeout=timeout,
            )
    else:
        curr_response = response
    retries = 0

    try:
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
                            headers={
                                "Accept-Encoding": "identity",
                                "Range": f"bytes={downloaded}-",
                            },
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

                    # Guard against premature disconnection returning EOF without exception
                    if total_size > 0 and downloaded < total_size:
                        raise requests.exceptions.ChunkedEncodingError(
                            f"Stream ended prematurely: received {downloaded:,} of {total_size:,} bytes"
                        )

                    # Successful full stream completion
                    break

                except (
                    requests.RequestException,
                    ConnectionResetError,
                    TimeoutError,
                    BrokenPipeError,
                ) as exc:
                    if curr_response:
                        try:
                            curr_response.close()
                        except Exception:
                            pass
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
            try:
                curr_response.close()
            except Exception:
                pass

    if target_path.suffix.lower() == ".zip" and not zipfile.is_zipfile(tmp_path):
        tmp_path.unlink(missing_ok=True)
        raise ValueError(
            f"Downloaded archive '{tmp_path.name}' is corrupted or incomplete and not a valid zip file."
        )

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
