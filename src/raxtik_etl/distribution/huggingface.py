"""Hugging Face Hub distribution module for downloading and uploading compiled packages.

Designed with zero-auth public downloads:
- Downloads can use direct streaming HTTP via requests (no Hugging Face login required).
- Uploads require `huggingface_hub` (in dev dependencies) and a valid write token.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Optional, Union

import requests
from rich.console import Console
from tqdm import tqdm

console = Console()

DEFAULT_HF_REPO = os.getenv("RAXTIK_HF_REPO", "raxtik-org/faers-safety-database")


def get_default_package_dir() -> Path:
    """Returns the default central cache directory for packages (~/.cache/raxtik/packages).

    Returns:
        Path to default package cache directory.
    """
    if env_dir := os.getenv("RAXTIK_CACHE_DIR"):
        return Path(env_dir)
    return Path.home() / ".cache" / "raxtik" / "packages"


DEFAULT_HTTP_TIMEOUT: int = int(os.getenv("RAXTIK_HTTP_TIMEOUT", "120"))


def resolve_hf_revision(
    repo_id: str,
    revision: Optional[str] = None,
    timeout: int = DEFAULT_HTTP_TIMEOUT,
) -> str:
    """Resolves the Hugging Face Git revision (tag, branch, or commit SHA).

    Resolution hierarchy:
    1. Explicit revision passed as parameter.
    2. RAXTIK_HF_REVISION environment variable.
    3. Derived tag candidate from package version ('0.1.0.dev', 'v0.1.0.dev0', 'v0.1.0', etc.).
    4. Fallback to 'main'.

    Args:
        repo_id: Hugging Face dataset repository ID (e.g. 'raxtik-org/faers-safety-database').
        revision: Optional explicit revision or branch name.
        timeout: HTTP timeout in seconds for repository checks.

    Returns:
        Resolved Git revision string.
    """
    if revision:
        return revision
    if env_rev := os.getenv("RAXTIK_HF_REVISION"):
        return env_rev

    # Try version tag candidates (e.g. '0.1.0.dev', 'v0.1.0.dev0', 'v0.1.0')
    from raxtik_etl import __version__

    candidates = [__version__, f"v{__version__}"]
    if ".dev" in __version__:
        clean_dev = __version__.split(".dev")[0] + ".dev"
        candidates.insert(0, clean_dev)
        candidates.insert(1, f"v{clean_dev}")

    for tag_candidate in candidates:
        try:
            check_url = (
                f"https://huggingface.co/datasets/{repo_id}/resolve/{tag_candidate}/.gitattributes"
            )
            resp = requests.head(check_url, timeout=min(timeout, 5), allow_redirects=True)
            if resp.status_code == 200:
                return tag_candidate
        except Exception:
            pass

    return "main"


def _fetch_remote_hf_sha256(
    repo_id: str,
    rel_path: str,
    filename: str,
    revision: str = "main",
    timeout: int = DEFAULT_HTTP_TIMEOUT,
) -> Optional[str]:
    """Attempts to fetch the expected SHA-256 hash for a file from Hugging Face Hub.

    Args:
        repo_id: Hugging Face dataset repository ID.
        rel_path: Subfolder relative path in the repository.
        filename: Base filename of the target artifact.
        revision: Target Git revision or tag.
        timeout: HTTP timeout in seconds.

    Returns:
        Lower-cased 64-character hexadecimal SHA-256 string if resolved, else None.
    """
    # 1. Try companion .sha256 file from HF
    for path_candidate in [f"{rel_path}.sha256", f"{filename}.sha256"]:
        url = f"https://huggingface.co/datasets/{repo_id}/resolve/{revision}/{path_candidate}"
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200 and resp.text:
                match = re.search(r"([a-f0-9]{64})", resp.text.strip(), re.IGNORECASE)
                if match:
                    return match.group(1).lower()
        except Exception:
            pass

    # 2. Try git LFS pointer header (X-Linked-ETag / ETag)
    for path_candidate in [rel_path, filename]:
        url = f"https://huggingface.co/datasets/{repo_id}/resolve/{revision}/{path_candidate}"
        try:
            head_resp = requests.head(url, timeout=timeout, allow_redirects=False)
            for hdr in ["X-Linked-ETag", "X-Linked-Sha256", "ETag"]:
                val = head_resp.headers.get(hdr, "")
                match = re.search(r"([a-f0-9]{64})", val, re.IGNORECASE)
                if match:
                    return match.group(1).lower()
        except Exception:
            pass

    return None


def download_package_from_hf(
    data_period_or_name: str,
    dest_dir: Optional[Path | str] = None,
    repo_id: str = DEFAULT_HF_REPO,
    source_name: str = "faers",
    force: bool = False,
    timeout: int = DEFAULT_HTTP_TIMEOUT,
    revision: Optional[str] = None,
) -> Path:
    """Downloads a compiled .duckdb safety package from Hugging Face Hub.

    Publicly accessible without any authentication token or Hugging Face account.
    Automatically fetches and verifies the SHA-256 integrity checksum from Hugging Face.

    Args:
        data_period_or_name: Period identifier (e.g. '2004Q1') or package name (e.g. 'faers_2004_2006_consolidated').
        dest_dir: Destination folder (defaults to ~/.cache/raxtik/packages).
        repo_id: Hugging Face dataset repository id.
        source_name: Source name prefix (defaults to 'faers').
        force: Whether to overwrite existing local file.
        timeout: HTTP timeout in seconds for requests (defaults to RAXTIK_HTTP_TIMEOUT or 120).
        revision: Specific Git revision or tag (defaults to version tag matching package, or 'main').

    Returns:
        Path to downloaded DuckDB package.
    """
    target_dir = Path(dest_dir) if dest_dir else get_default_package_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    rel_upper = data_period_or_name.strip()
    prefix = f"{source_name}_"
    if not rel_upper.lower().startswith(prefix.lower()):
        filename = f"{source_name}_{rel_upper.upper()}.duckdb"
    else:
        filename = f"{rel_upper}.duckdb"

    match = re.search(r"(\d{4})Q[1-4]", rel_upper)
    subfolder = match.group(1) if match else ("merged" if "merged" in rel_upper.lower() else "")
    rel_path = f"{subfolder}/{filename}" if subfolder else filename

    dest_file = target_dir / filename
    if dest_file.exists() and not force:
        console.print(f"[bold green]Package already present locally:[/bold green] {dest_file}")
        return dest_file

    resolved_revision = resolve_hf_revision(repo_id=repo_id, revision=revision, timeout=timeout)

    # Try huggingface_hub if available
    downloaded_file: Optional[Path] = None
    try:
        from huggingface_hub import hf_hub_download  # type: ignore
        from huggingface_hub.utils import EntryNotFoundError  # type: ignore

        console.print(
            f"[bold cyan]Downloading {filename} (revision: {resolved_revision}) from Hugging Face Hub ({repo_id})...[/bold cyan]"
        )
        try:
            downloaded_path = hf_hub_download(
                repo_id=repo_id,
                filename=rel_path,
                revision=resolved_revision,
                repo_type="dataset",
                local_dir=str(target_dir),
                force_download=force,
            )
        except (EntryNotFoundError, FileNotFoundError):
            # Fall back to root path if not in year subfolder
            downloaded_path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                revision=resolved_revision,
                repo_type="dataset",
                local_dir=str(target_dir),
                force_download=force,
            )
        downloaded_file = Path(downloaded_path)

        # Verify integrity
        if downloaded_file and downloaded_file.exists():
            from raxtik_etl.packaging.builder import compute_sha256

            actual_sha = compute_sha256(downloaded_file)
            remote_sha = _fetch_remote_hf_sha256(
                repo_id, rel_path, filename, revision=resolved_revision, timeout=timeout
            )
            if remote_sha:
                if actual_sha.lower() != remote_sha.lower():
                    downloaded_file.unlink(missing_ok=True)
                    raise ValueError(
                        f"Integrity check failed for {downloaded_file.name} downloaded from Hugging Face!\n"
                        f"Expected SHA-256 (HF): {remote_sha}\n"
                        f"Actual SHA-256:        {actual_sha}"
                    )
                console.print(
                    f"[bold green]✓ Verified SHA-256 integrity against Hugging Face:[/bold green] {actual_sha[:12]}"
                )
    except ImportError:
        # Fallback to direct HTTP download via requests with atomic .part staging
        url = f"https://huggingface.co/datasets/{repo_id}/resolve/{resolved_revision}/{rel_path}"
        console.print(
            f"[bold cyan]Downloading {filename} (revision: {resolved_revision}) via public direct stream from {url}...[/bold cyan]"
        )

        response = requests.get(url, stream=True, timeout=timeout)
        if response.status_code != 200:
            # Try root URL fallback
            fallback_url = (
                f"https://huggingface.co/datasets/{repo_id}/resolve/{resolved_revision}/{filename}"
            )
            response = requests.get(fallback_url, stream=True, timeout=timeout)
            if response.status_code != 200:
                if resolved_revision != "main":
                    console.print(
                        f"[yellow]Revision '{resolved_revision}' not found for {filename}. Retrying with 'main'...[/yellow]"
                    )
                    url_main = f"https://huggingface.co/datasets/{repo_id}/resolve/main/{rel_path}"
                    response = requests.get(url_main, stream=True, timeout=timeout)
                    if response.status_code != 200:
                        fallback_main = (
                            f"https://huggingface.co/datasets/{repo_id}/resolve/main/{filename}"
                        )
                        response = requests.get(fallback_main, stream=True, timeout=timeout)
                        if response.status_code != 200:
                            raise RuntimeError(
                                f"Failed to download package '{filename}' from Hugging Face Hub at {url} (HTTP {response.status_code})."
                            )
                    resolved_revision = "main"
                else:
                    raise RuntimeError(
                        f"Failed to download package '{filename}' from Hugging Face Hub at {url} (HTTP {response.status_code})."
                    )

        total_size = int(response.headers.get("content-length", 0))
        part_file = dest_file.with_suffix(".duckdb.part")
        if part_file.exists():
            part_file.unlink()

        try:
            with (
                open(part_file, "wb") as f,
                tqdm(
                    desc=filename,
                    total=total_size if total_size > 0 else None,
                    unit="iB",
                    unit_scale=True,
                    unit_divisor=1024,
                ) as bar,
            ):
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        size = f.write(chunk)
                        bar.update(size)

            # Automatic SHA-256 verification on .part staging file before promotion
            from raxtik_etl.packaging.builder import compute_sha256

            actual_sha = compute_sha256(part_file)
            remote_sha = _fetch_remote_hf_sha256(
                repo_id, rel_path, filename, revision=resolved_revision, timeout=timeout
            )
            if remote_sha:
                if actual_sha.lower() != remote_sha.lower():
                    part_file.unlink(missing_ok=True)
                    raise ValueError(
                        f"Integrity check failed for {part_file.name} downloaded from Hugging Face!\n"
                        f"Expected SHA-256 (HF): {remote_sha}\n"
                        f"Actual SHA-256:        {actual_sha}"
                    )
                console.print(
                    f"[bold green]✓ Verified SHA-256 integrity against Hugging Face:[/bold green] {actual_sha[:12]}"
                )

            # Atomically rename .part file to final destination
            part_file.replace(dest_file)
            console.print(f"[bold green]✓ Download complete:[/bold green] {dest_file}")
            downloaded_file = dest_file
        except Exception:
            if part_file.exists():
                part_file.unlink()
            raise

    return downloaded_file if downloaded_file else dest_file


def upload_package_to_hf(
    data_period_or_name: Union[str, List[str]],
    package_dir: Optional[Path | str] = None,
    repo_id: str = DEFAULT_HF_REPO,
    source_name: str = "faers",
    token: Optional[str] = None,
    include_parquet: bool = True,
    tag: Optional[str] = None,
    force: bool = False,
    commit_message: Optional[str] = None,
) -> None:
    """Uploads compiled .duckdb package(s) and Parquet shards to Hugging Face Hub in a single atomic Git commit.

    Organizes releases cleanly into year subfolders (e.g. 2004/faers_2004Q1.duckdb, merged/...).
    Supports a single period name or a batch list of periods for bulk 1-commit upload.

    Args:
        data_period_or_name: Period identifier (e.g. '2004Q1') or list of periods (e.g. ['2011Q1', '2011Q2']).
        package_dir: Directory containing compiled packages (defaults to ~/.cache/raxtik/packages).
        repo_id: Destination Hugging Face dataset repository id.
        source_name: Source name prefix (defaults to 'faers').
        token: Hugging Face user write access token.
        include_parquet: Whether to also upload corresponding .parquet folders.
        tag: Optional Git tag to attach to Hugging Face repository upon upload.
        force: Whether to force overwrite existing tags on Hugging Face.
        commit_message: Optional custom commit message.

    Returns:
        None

    Raises:
        ImportError: If huggingface_hub is not installed.
        ValueError: If HF write token is missing.
        FileNotFoundError: If no package files are found to upload.
    """
    try:
        from huggingface_hub import CommitOperationAdd, HfApi  # type: ignore
    except ImportError:
        raise ImportError(
            "Uploading requires 'huggingface_hub'. Please install it using: pip install 'raxtik-etl[dev]'"
        )

    auth_token = token or os.environ.get("HF_TOKEN")
    if not auth_token:
        raise ValueError(
            "Hugging Face write token is required to upload packages. "
            "Please pass token=... or set the HF_TOKEN environment variable."
        )

    pkg_dir = Path(package_dir) if package_dir else get_default_package_dir()
    api = HfApi(token=auth_token)

    periods = (
        [data_period_or_name] if isinstance(data_period_or_name, str) else list(data_period_or_name)
    )
    if not periods:
        return

    operations: List[CommitOperationAdd] = []
    total_bytes = 0

    for rel in periods:
        rel_clean = rel.strip()
        prefix = f"{source_name}_"
        if not rel_clean.lower().startswith(prefix.lower()):
            duckdb_name = f"{source_name}_{rel_clean.upper()}.duckdb"
            parquet_dir_name = f"{source_name}_{rel_clean.upper()}.parquet"
        else:
            duckdb_name = f"{rel_clean}.duckdb"
            parquet_dir_name = f"{rel_clean}.parquet"

        match = re.search(r"(\d{4})Q[1-4]", rel_clean.upper())
        subfolder = match.group(1) if match else ("merged" if "merged" in rel_clean.lower() else "")

        duckdb_file = pkg_dir / duckdb_name
        parquet_dir = pkg_dir / parquet_dir_name

        if duckdb_file.exists():
            path_in_repo = f"{subfolder}/{duckdb_name}" if subfolder else duckdb_name
            operations.append(
                CommitOperationAdd(
                    path_in_repo=path_in_repo,
                    path_or_fileobj=duckdb_file.as_posix(),
                )
            )
            total_bytes += duckdb_file.stat().st_size

        if include_parquet and parquet_dir.exists():
            for p_file in sorted(parquet_dir.glob("*.parquet")):
                rel_p = (
                    f"{subfolder}/{parquet_dir_name}/{p_file.name}"
                    if subfolder
                    else f"{parquet_dir_name}/{p_file.name}"
                )
                operations.append(
                    CommitOperationAdd(
                        path_in_repo=rel_p,
                        path_or_fileobj=p_file.as_posix(),
                    )
                )
                total_bytes += p_file.stat().st_size

    if not operations:
        raise FileNotFoundError(
            f"No package files found to upload for periods: {periods} at {pkg_dir}"
        )

    msg = commit_message or (
        f"Add {source_name.upper()} data for {periods[0]}..{periods[-1]} "
        f"({len(periods)} quarters, {total_bytes / (1024 * 1024):.1f} MB)"
        if len(periods) > 1
        else f"Add {source_name.upper()} data for {periods[0]} ({total_bytes / (1024 * 1024):.1f} MB)"
    )

    console.print(
        f"[bold cyan]Uploading {len(operations)} files ({total_bytes / (1024 * 1024):.1f} MB) in 1 commit to {repo_id}...[/bold cyan]"
    )
    api.create_commit(
        repo_id=repo_id,
        repo_type="dataset",
        operations=operations,
        commit_message=msg,
    )
    console.print(
        f"[bold green]✓ Uploaded {periods[0]}..{periods[-1]} ({total_bytes / (1024 * 1024):.1f} MB in 1 commit).[/bold green]"
    )

    # 3. Optionally attach/update Git tag on Hugging Face dataset
    if tag:
        try:
            if force:
                try:
                    api.delete_tag(repo_id=repo_id, tag=tag, repo_type="dataset")
                except Exception:
                    pass
            api.create_tag(
                repo_id=repo_id,
                tag=tag,
                repo_type="dataset",
                tag_message=f"Release {tag} for raxtik-etl",
                exist_ok=True,
            )
            console.print(
                f"[bold green]✓ Tagged Hugging Face repository {repo_id} at '{tag}'[/bold green]"
            )
        except Exception as tag_err:
            console.print(
                f"[bold yellow]Warning: could not create tag '{tag}' on Hugging Face: {tag_err}[/bold yellow]"
            )


def tag_hf_dataset(
    repo_id: str = DEFAULT_HF_REPO,
    tag: str = "0.1.0.dev",
    token: Optional[str] = None,
    force: bool = False,
) -> None:
    """Creates or overwrites a Git tag on the Hugging Face dataset repository.

    Args:
        repo_id: Target Hugging Face dataset repository ID.
        tag: Git tag string to create (e.g. '0.1.0.dev1' or 'v0.1.0').
        token: Optional Hugging Face write token. Defaults to HF_TOKEN environment variable.
        force: Whether to overwrite the tag if it already exists remotely.

    Returns:
        None

    Raises:
        ImportError: If huggingface_hub is not installed.
        ValueError: If HF write token is missing.
    """
    try:
        from huggingface_hub import HfApi  # type: ignore
    except ImportError:
        raise ImportError(
            "Tagging requires 'huggingface_hub'. Please install it using: pip install 'raxtik-etl[dev]'"
        )

    auth_token = token or os.environ.get("HF_TOKEN")
    if not auth_token:
        raise ValueError(
            "HF_TOKEN is required to tag the dataset. Please pass token=... or set the HF_TOKEN environment variable."
        )
    api = HfApi(token=auth_token)
    try:
        api.delete_tag(repo_id=repo_id, tag=tag, repo_type="dataset")
    except Exception:
        pass
    api.create_tag(
        repo_id=repo_id,
        tag=tag,
        repo_type="dataset",
        tag_message=f"Release {tag}",
    )
    console.print(f"[bold green]✓ Tagged Hugging Face repository {repo_id} at '{tag}'[/bold green]")
