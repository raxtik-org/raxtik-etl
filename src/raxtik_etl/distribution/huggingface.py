"""Hugging Face Hub distribution module for downloading and uploading compiled packages.

Designed with zero-auth public downloads:
- Downloads can use direct streaming HTTP via requests (no Hugging Face login required).
- Uploads require `huggingface_hub` (in dev dependencies) and a valid write token.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import requests
from rich.console import Console
from tqdm import tqdm

console = Console()

DEFAULT_HF_REPO = os.getenv("RAXTIK_HF_REPO", "raxtik-org/faers-safety-database")


def download_package_from_hf(
    release_or_name: str,
    dest_dir: Path | str = "data/packages",
    repo_id: str = DEFAULT_HF_REPO,
    force: bool = False,
) -> Path:
    """
    Downloads a compiled .duckdb safety package from Hugging Face Hub.

    Publicly accessible without any authentication token or Hugging Face account.

    Args:
        release_or_name: e.g. '2004Q1' or 'faers_2004_2006_merged'
        dest_dir: Destination folder (defaults to data/packages)
        repo_id: Hugging Face dataset repository id
        force: Whether to overwrite existing local file

    Returns:
        Path to downloaded DuckDB package.
    """
    target_dir = Path(dest_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    rel_upper = release_or_name.strip()
    if not rel_upper.startswith("faers_"):
        filename = f"faers_{rel_upper.upper()}.duckdb"
    else:
        filename = f"{rel_upper}.duckdb"

    dest_file = target_dir / filename
    if dest_file.exists() and not force:
        console.print(f"[bold green]Package already present locally:[/bold green] {dest_file}")
        return dest_file

    # Try huggingface_hub if available
    try:
        from huggingface_hub import hf_hub_download  # type: ignore

        console.print(
            f"[bold cyan]Downloading {filename} from Hugging Face Hub ({repo_id})...[/bold cyan]"
        )
        downloaded_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            repo_type="dataset",
            local_dir=str(target_dir),
        )
        return Path(downloaded_path)
    except ImportError:
        # Fallback to direct HTTP download via requests (no huggingface_hub needed)
        url = f"https://huggingface.co/datasets/{repo_id}/resolve/main/{filename}"
        console.print(
            f"[bold cyan]Downloading {filename} via public direct stream from {url}...[/bold cyan]"
        )

        response = requests.get(url, stream=True, timeout=120)
        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to download package '{filename}' from Hugging Face Hub at {url} (HTTP {response.status_code})."
            )

        total_size = int(response.headers.get("content-length", 0))
        with (
            open(dest_file, "wb") as f,
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

        console.print(f"[bold green]✓ Download complete:[/bold green] {dest_file}")
        return dest_file


def upload_package_to_hf(
    release_or_name: str,
    package_dir: Path | str = "data/packages",
    repo_id: str = DEFAULT_HF_REPO,
    token: Optional[str] = None,
    include_parquet: bool = True,
) -> None:
    """
    Uploads a compiled .duckdb package and optional Parquet shards to Hugging Face Hub.

    Requires `huggingface_hub` (available via `pip install 'raxtik-etl[dev]'`) and
    a Hugging Face write token (via argument or HF_TOKEN env var).

    Args:
        release_or_name: e.g. '2004Q1' or 'faers_2004_2006_merged'
        package_dir: Directory containing compiled packages
        repo_id: Destination Hugging Face dataset repository id
        token: Hugging Face user write access token
        include_parquet: Whether to also upload the corresponding .parquet folder
    """
    try:
        from huggingface_hub import HfApi  # type: ignore
    except ImportError:
        raise ImportError(
            "Uploading requires 'huggingface_hub'. Please install it using: pip install 'raxtik-etl[dev]'"
        )

    auth_token = token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
    if not auth_token:
        raise ValueError(
            "Hugging Face write token is required to upload packages. "
            "Pass token=... or set the HF_TOKEN environment variable."
        )

    pkg_dir = Path(package_dir)
    rel_clean = release_or_name.strip()
    if not rel_clean.startswith("faers_"):
        duckdb_name = f"faers_{rel_clean.upper()}.duckdb"
        parquet_dir_name = f"faers_{rel_clean.upper()}.parquet"
    else:
        duckdb_name = f"{rel_clean}.duckdb"
        parquet_dir_name = f"{rel_clean}.parquet"

    duckdb_file = pkg_dir / duckdb_name
    parquet_dir = pkg_dir / parquet_dir_name

    if not duckdb_file.exists():
        raise FileNotFoundError(f"Package database not found at {duckdb_file}")

    api = HfApi(token=auth_token)

    # 1. Upload DuckDB file
    console.print(
        f"[bold cyan]Uploading {duckdb_name} ({duckdb_file.stat().st_size / (1024 * 1024):.2f} MB) to HF dataset {repo_id}...[/bold cyan]"
    )
    api.upload_file(
        path_or_fileobj=duckdb_file.as_posix(),
        path_in_repo=duckdb_name,
        repo_id=repo_id,
        repo_type="dataset",
    )
    console.print(f"[bold green]✓ Uploaded {duckdb_name} successfully.[/bold green]")

    # 2. Optionally upload Parquet shards
    if include_parquet and parquet_dir.exists():
        console.print(f"[bold cyan]Uploading Parquet shards from {parquet_dir_name}...[/bold cyan]")
        api.upload_folder(
            folder_path=parquet_dir.as_posix(),
            path_in_repo=parquet_dir_name,
            repo_id=repo_id,
            repo_type="dataset",
        )
        console.print(f"[bold green]✓ Uploaded {parquet_dir_name} successfully.[/bold green]")
