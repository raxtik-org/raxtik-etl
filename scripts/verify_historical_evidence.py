"""Phase 0 Historical Schema Evidence Verification Script.

Downloads official FDA FAERS/AEMS quarterly ASCII ZIP files, extracts and inspects
all 7 relational tables (DEMO, DRUG, REAC, OUTC, RPSR, THER, INDI), verifies delimiters,
encodings, headers, column counts, first data row field counts, and generates
cryptographic schema fingerprints (SHA-256) and comparison reports.

Outputs:
- docs/schema/evidence/{release}.json
- docs/schema/evidence/signatures/{signature_id}.json
- docs/schema/evidence/comparison.md
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests
from rich.console import Console
from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn, TimeRemainingColumn

console = Console()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = PROJECT_ROOT / "docs" / "schema" / "evidence"
SIGNATURES_DIR = EVIDENCE_DIR / "signatures"
CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "archives_cache"

EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
SIGNATURES_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Target sample releases for Phase 0 verification
TARGET_RELEASES = [
    {"release": "2004Q1", "url": "https://fis.fda.gov/content/Exports/aers_ascii_2004q1.zip"},
    {"release": "2012Q4", "url": "https://fis.fda.gov/content/Exports/faers_ascii_2012q4.zip"},
    {"release": "2014Q3", "url": "https://fis.fda.gov/content/Exports/faers_ascii_2014q3.zip"},
    {"release": "2024Q1", "url": "https://fis.fda.gov/content/Exports/faers_ascii_2024q1.zip"},
    {"release": "2026Q1", "url": "https://fis.fda.gov/content/Exports/faers_ascii_2026q1.zip"},
    {"release": "2026Q2", "url": "https://fis.fda.gov/content/Exports/faers_ascii_2026q2.zip"},
]

TABLE_PREFIXES = ["DEMO", "DRUG", "REAC", "OUTC", "RPSR", "THER", "INDI"]


@dataclass
class TableEvidence:
    table_type: str
    internal_filename: str
    byte_size: int
    delimiter: str
    encoding: str
    has_bom: bool
    header_raw: str
    columns: List[str]
    column_count: int
    first_data_row_raw: str
    first_data_row_field_count: int
    field_count_matches_header: bool
    table_signature_sha256: str


@dataclass
class ReleaseEvidence:
    release: str
    source_url: str
    download_timestamp: str
    archive_sha256: str
    zip_filename: str
    zip_byte_size: int
    tables: Dict[str, TableEvidence]
    release_signature_sha256: str


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def detect_delimiter(sample_bytes: bytes) -> str:
    header_line = sample_bytes.split(b"\n")[0].decode("utf-8", errors="ignore")
    if "$" in header_line:
        return "$"
    if "\t" in header_line:
        return "\t"
    if "," in header_line:
        return ","
    return "$"


def analyze_table_file(
    zf: zipfile.ZipFile, zip_info: zipfile.ZipInfo, table_type: str
) -> TableEvidence:
    with zf.open(zip_info) as f:
        # Read first 16KB to get header and first couple data rows
        sample_bytes = f.read(32768)

    has_bom = sample_bytes.startswith(b"\xef\xbb\xbf")
    encoding = "utf-8-sig" if has_bom else "utf-8"

    try:
        decoded_sample = sample_bytes.decode(encoding)
    except UnicodeDecodeError:
        encoding = "latin-1"
        decoded_sample = sample_bytes.decode(encoding, errors="replace")

    lines = [line.strip("\r") for line in decoded_sample.split("\n") if line.strip()]
    if not lines:
        raise ValueError(f"File {zip_info.filename} is completely empty.")

    header_raw = lines[0]
    delimiter = detect_delimiter(sample_bytes)

    # Parse columns
    columns = [col.strip() for col in header_raw.split(delimiter) if col.strip()]
    column_count = len(columns)

    first_data_row_raw = lines[1] if len(lines) > 1 else ""
    first_data_row_fields = (
        [f.strip() for f in first_data_row_raw.split(delimiter)] if first_data_row_raw else []
    )
    first_data_row_field_count = len(first_data_row_fields)

    # Check match (handle trailing delimiter quirks)
    field_count_matches = (first_data_row_field_count == column_count) or (
        first_data_row_field_count == column_count + 1 and first_data_row_fields[-1] == ""
    )

    # Compute deterministic Table Signature Hash
    canonical_sig_string = f"{table_type}|{delimiter}|" + "|".join(columns)
    table_sig_sha256 = hashlib.sha256(canonical_sig_string.encode("utf-8")).hexdigest()

    return TableEvidence(
        table_type=table_type,
        internal_filename=zip_info.filename,
        byte_size=zip_info.file_size,
        delimiter=delimiter,
        encoding=encoding,
        has_bom=has_bom,
        header_raw=header_raw,
        columns=columns,
        column_count=column_count,
        first_data_row_raw=first_data_row_raw[:200]
        + ("..." if len(first_data_row_raw) > 200 else ""),
        first_data_row_field_count=first_data_row_field_count,
        field_count_matches_header=field_count_matches,
        table_signature_sha256=table_sig_sha256,
    )


def download_archive(url: str, dest_path: Path) -> bool:
    if dest_path.exists() and dest_path.stat().st_size > 0:
        console.print(f"[green]Cached archive found:[/green] {dest_path.name}")
        return True

    console.print(f"[bold cyan]Downloading from FDA:[/bold cyan] {url}")
    headers = {"User-Agent": "Mozilla/5.0 (VigilForms Raxtik-ETL Evidence Verifier)"}
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=60)
        if response.status_code != 200:
            console.print(f"[red]HTTP Error {response.status_code} for {url}[/red]")
            return False

        total_size = int(response.headers.get("content-length", 0))
        with Progress(
            TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.1f}%",
            "•",
            DownloadColumn(),
            "•",
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("download", filename=dest_path.name, total=total_size)
            with open(dest_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        progress.update(task, advance=len(chunk))
        return True
    except Exception as e:
        console.print(f"[red]Failed to download {url}: {e}[/red]")
        if dest_path.exists():
            dest_path.unlink()
        return False


def process_release(release_info: Dict[str, str]) -> Optional[ReleaseEvidence]:
    release = release_info["release"]
    url = release_info["url"]
    dest_path = CACHE_DIR / f"{release.lower()}_ascii.zip"

    success = download_archive(url, dest_path)
    if not success:
        return None

    archive_sha256 = compute_sha256(dest_path)
    zip_size = dest_path.stat().st_size

    tables_evidence: Dict[str, TableEvidence] = {}

    with zipfile.ZipFile(dest_path, "r") as zf:
        file_list = zf.infolist()
        for prefix in TABLE_PREFIXES:
            # Find matching text file (e.g. DEMO04Q1.txt or ascii/DEMO24Q1.txt)
            matching_files = [
                f
                for f in file_list
                if re.search(rf"(?:^|[/\\]){prefix}[^/\\]*\.txt$", f.filename, re.IGNORECASE)
            ]
            if not matching_files:
                console.print(f"[yellow]Warning: No {prefix} file found in {release}[/yellow]")
                continue

            target_zipinfo = matching_files[0]
            evidence = analyze_table_file(zf, target_zipinfo, prefix)
            tables_evidence[prefix] = evidence

    # Calculate overall Release Signature Hash
    combined_sigs = "".join(
        tables_evidence[p].table_signature_sha256 for p in TABLE_PREFIXES if p in tables_evidence
    )
    release_sig_sha256 = hashlib.sha256(combined_sigs.encode("utf-8")).hexdigest()

    release_evidence = ReleaseEvidence(
        release=release,
        source_url=url,
        download_timestamp=datetime.now(timezone.utc).isoformat(),
        archive_sha256=archive_sha256,
        zip_filename=dest_path.name,
        zip_byte_size=zip_size,
        tables=tables_evidence,
        release_signature_sha256=release_sig_sha256,
    )

    # Save release JSON
    out_json = EVIDENCE_DIR / f"{release}.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(asdict(release_evidence), f, indent=2)

    console.print(
        f"[green]Saved evidence record:[/green] {out_json.name} (Release Sig: [bold]{release_sig_sha256[:12]}[/bold])"
    )
    return release_evidence


def generate_comparison_and_signatures(all_evidence: List[ReleaseEvidence]):
    # Group releases by signature hash
    signatures_map: Dict[str, List[ReleaseEvidence]] = {}
    for ev in all_evidence:
        sig = ev.release_signature_sha256
        signatures_map.setdefault(sig, []).append(ev)

    # Assign Signature IDs (S1, S2, S3, S4...) in chronological order
    sig_id_map: Dict[str, str] = {}
    sig_counter = 1
    # Sort by the earliest release in each signature group
    sorted_sigs = sorted(signatures_map.items(), key=lambda item: min(e.release for e in item[1]))

    for sig_hash, ev_list in sorted_sigs:
        sig_id = f"S{sig_counter}"
        sig_id_map[sig_hash] = sig_id
        sig_counter += 1

        # Save signature JSON
        sig_record = {
            "signature_id": sig_id,
            "signature_sha256": sig_hash,
            "representative_release": ev_list[0].release,
            "matching_releases": [e.release for e in ev_list],
            "tables": {
                p: {
                    "columns": ev_list[0].tables[p].columns if p in ev_list[0].tables else [],
                    "column_count": ev_list[0].tables[p].column_count
                    if p in ev_list[0].tables
                    else 0,
                    "delimiter": ev_list[0].tables[p].delimiter if p in ev_list[0].tables else "$",
                    "table_signature_sha256": ev_list[0].tables[p].table_signature_sha256
                    if p in ev_list[0].tables
                    else "",
                }
                for p in TABLE_PREFIXES
            },
        }
        with open(SIGNATURES_DIR / f"{sig_id}.json", "w", encoding="utf-8") as f:
            json.dump(sig_record, f, indent=2)

    # Generate docs/schema/evidence/comparison.md
    md = io.StringIO()
    md.write("# Phase 0 Empirical Schema Fingerprint Comparison Report\n\n")
    md.write(f"> **Generated at**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}\n\n")
    md.write("## 1. Verified Release Signatures & Fingerprints\n\n")
    md.write(
        "| Release | Signature ID | Release Signature Hash (SHA-256) | Archive Size (MB) | Verified Archive SHA-256 |\n"
    )
    md.write("| :--- | :--- | :--- | :--- | :--- |\n")
    for ev in all_evidence:
        sig_id = sig_id_map.get(ev.release_signature_sha256, "Unknown")
        size_mb = ev.zip_byte_size / (1024 * 1024)
        md.write(
            f"| **{ev.release}** | `{sig_id}` | `{ev.release_signature_sha256[:16]}...` | {size_mb:.2f} MB | `{ev.archive_sha256[:16]}...` |\n"
        )

    md.write("\n---\n\n")
    md.write("## 2. Table-by-Table Column Evolution\n\n")

    for prefix in TABLE_PREFIXES:
        md.write(f"### 📋 Table: `{prefix}`\n\n")
        # Build table comparison across distinct signatures
        sig_columns = {}
        for sig_hash, sig_id in sig_id_map.items():
            rep = signatures_map[sig_hash][0]
            if prefix in rep.tables:
                sig_columns[sig_id] = rep.tables[prefix].columns

        headers = ["#"] + [
            f"{sig_id} ({signatures_map[sig_hash][0].release})"
            for sig_hash, sig_id in sig_id_map.items()
        ]
        md.write("| " + " | ".join(headers) + " |\n")
        md.write("| " + " | ".join([":---"] + [":---" for _ in range(len(sig_id_map))]) + " |\n")

        max_cols = max(len(cols) for cols in sig_columns.values()) if sig_columns else 0
        for i in range(max_cols):
            row = [str(i + 1)]
            for sig_hash, sig_id in sig_id_map.items():
                cols = sig_columns.get(sig_id, [])
                col_name = cols[i] if i < len(cols) else "—"
                row.append(f"`{col_name}`" if col_name != "—" else "—")
            md.write("| " + " | ".join(row) + " |\n")
        md.write("\n")

    with open(EVIDENCE_DIR / "comparison.md", "w", encoding="utf-8") as f:
        f.write(md.getvalue())

    console.print(
        f"[bold green]Successfully generated comparison report:[/bold green] {EVIDENCE_DIR / 'comparison.md'}"
    )


def main():
    console.rule("[bold cyan]Phase 0 Historical Evidence Verification[/bold cyan]")
    all_evidence: List[ReleaseEvidence] = []

    for release_info in TARGET_RELEASES:
        ev = process_release(release_info)
        if ev:
            all_evidence.append(ev)

    if all_evidence:
        generate_comparison_and_signatures(all_evidence)
        console.rule("[bold green]Evidence Verification Complete[/bold green]")
    else:
        console.print("[red]No evidence records were processed successfully.[/red]")


if __name__ == "__main__":
    main()
