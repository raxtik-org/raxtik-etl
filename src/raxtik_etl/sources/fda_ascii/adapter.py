"""FDA ASCII Source Adapter.

Extracts FDA quarterly ASCII archives into ephemeral staging files and loads them
into DuckDB through signature-specific mappings (S1, S2, S3).
"""

from __future__ import annotations

import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict

import duckdb
from rich.console import Console

from raxtik_etl.sources.fda_ascii.mappings.s1_legacy import (
    load_s1_demo,
    load_s1_drug,
    load_s1_indi,
    load_s1_outc,
    load_s1_reac,
    load_s1_rpsr,
    load_s1_ther,
)
from raxtik_etl.sources.fda_ascii.mappings.s2_migration import (
    load_s2_demo,
    load_s2_drug,
    load_s2_indi,
    load_s2_outc,
    load_s2_reac,
    load_s2_rpsr,
    load_s2_ther,
)
from raxtik_etl.sources.fda_ascii.mappings.s3_modern import (
    load_s3_demo,
    load_s3_drug,
    load_s3_indi,
    load_s3_outc,
    load_s3_reac,
    load_s3_rpsr,
    load_s3_ther,
)
from raxtik_etl.sources.fda_ascii.signatures.resolver import detect_archive_signature

console = Console()

TABLE_PREFIXES = ["DEMO", "DRUG", "REAC", "OUTC", "RPSR", "THER", "INDI"]


class FDAAsciiAdapter:
    """Extracts, detects signatures, and stages raw ASCII tables into canonical DuckDB relations."""

    def __init__(self, zip_path: Path, release: str):
        self.zip_path = zip_path
        self.release = release.upper()
        self.signature_id: str = "S1"

    def detect_signature(self, zf: zipfile.ZipFile) -> str:
        """Detect whether this archive matches Signature S1, S2, or S3 fail-closed."""
        return detect_archive_signature(zf, self.release)

    def extract_and_load(self, con: duckdb.DuckDBPyConnection) -> Dict[str, Any]:
        """Extracts text files from ZIP into DuckDB staging tables and normalizes to canonical schemas."""
        with zipfile.ZipFile(self.zip_path, "r") as zf:
            self.signature_id = self.detect_signature(zf)
            console.print(
                f"[cyan]Detected Schema Signature for {self.release}:[/cyan] [bold]{self.signature_id}[/bold]"
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                zf.extractall(tmp_path)

                # Locate the 7 extract files case-insensitively
                extracted_files = [
                    f for f in tmp_path.rglob("*") if f.is_file() and f.suffix.lower() == ".txt"
                ]
                table_files: Dict[str, Path] = {}
                for prefix in TABLE_PREFIXES:
                    matches = [
                        f
                        for f in extracted_files
                        if re.search(rf"(?:^|[/\\]){prefix}[^/\\]*\.txt$", f.name, re.IGNORECASE)
                    ]
                    if matches:
                        table_files[prefix.lower()] = matches[0]

                # Dispatch loading to signature-specific mappings
                if self.signature_id == "S1":
                    if "demo" in table_files:
                        load_s1_demo(con, table_files["demo"], self.release)
                    if "drug" in table_files:
                        load_s1_drug(con, table_files["drug"], self.release)
                    if "reac" in table_files:
                        load_s1_reac(con, table_files["reac"], self.release)
                    if "outc" in table_files:
                        load_s1_outc(con, table_files["outc"], self.release)
                    if "indi" in table_files:
                        load_s1_indi(con, table_files["indi"], self.release)
                    if "ther" in table_files:
                        load_s1_ther(con, table_files["ther"], self.release)
                    if "rpsr" in table_files:
                        load_s1_rpsr(con, table_files["rpsr"], self.release)

                elif self.signature_id == "S2":
                    if "demo" in table_files:
                        load_s2_demo(con, table_files["demo"], self.release)
                    if "drug" in table_files:
                        load_s2_drug(con, table_files["drug"], self.release)
                    if "reac" in table_files:
                        load_s2_reac(con, table_files["reac"], self.release)
                    if "outc" in table_files:
                        load_s2_outc(con, table_files["outc"], self.release)
                    if "indi" in table_files:
                        load_s2_indi(con, table_files["indi"], self.release)
                    if "ther" in table_files:
                        load_s2_ther(con, table_files["ther"], self.release)
                    if "rpsr" in table_files:
                        load_s2_rpsr(con, table_files["rpsr"], self.release)

                elif self.signature_id == "S3":
                    if "demo" in table_files:
                        load_s3_demo(con, table_files["demo"], self.release)
                    if "drug" in table_files:
                        load_s3_drug(con, table_files["drug"], self.release)
                    if "reac" in table_files:
                        load_s3_reac(con, table_files["reac"], self.release)
                    if "outc" in table_files:
                        load_s3_outc(con, table_files["outc"], self.release)
                    if "indi" in table_files:
                        load_s3_indi(con, table_files["indi"], self.release)
                    if "ther" in table_files:
                        load_s3_ther(con, table_files["ther"], self.release)
                    if "rpsr" in table_files:
                        load_s3_rpsr(con, table_files["rpsr"], self.release)

                else:
                    raise ValueError(f"Unsupported signature: {self.signature_id}")

        return {
            "release": self.release,
            "signature_id": self.signature_id,
            "archive_size_bytes": self.zip_path.stat().st_size,
        }
