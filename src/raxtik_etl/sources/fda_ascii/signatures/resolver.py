"""Fail-Closed Signature Resolver for FDA Quarterly ASCII Archives.

Inspects archive member headers and resolves to a verified schema signature (S1, S2, S3)
or raises an explicit ValueError.
"""

from __future__ import annotations

import re
import zipfile


def detect_archive_signature(zf: zipfile.ZipFile, release: str) -> str:
    """Detects whether an archive matches Signature S1, S2, or S3 using strict header inspection.

    Raises:
        ValueError: If archive headers do not match any verified historical signature.
    """
    file_list = zf.namelist()
    demo_files = [
        f for f in file_list if re.search(r"(?:^|[/\\])DEMO[^/\\]*\.txt$", f, re.IGNORECASE)
    ]
    if not demo_files:
        raise ValueError(f"Invalid FAERS archive: No DEMO table found in {release}")

    with zf.open(demo_files[0]) as f:
        header_sample = f.read(4096).decode("utf-8", errors="ignore")
    header_line = header_sample.split("\n")[0].strip()
    columns = [c.strip().lower() for c in header_line.split("$") if c.strip()]

    # 1. Signature S1 (Legacy AERS: 2004Q1 - 2012Q3)
    # Characterized by ISR as primary key, CASE as case key, FOLL_SEQ, GNDR_COD
    if "isr" in columns and "case" in columns:
        return "S1"

    # 2. Signature S2 (FAERS Migration: 2012Q4 - 2014Q2)
    # Characterized by PRIMARYID, CASEID, CASEVERSION, and GNDR_COD (prior to SEX in 2014Q3)
    if "primaryid" in columns and "caseid" in columns and "gndr_cod" in columns:
        return "S2"

    # 3. Signature S3 (Modern FAERS & AEMS: 2014Q3 - 2026Q2+)
    # Characterized by PRIMARYID, CASEID, SEX, and AGE_GRP or AUTH_NUM
    if (
        "primaryid" in columns
        and "caseid" in columns
        and ("sex" in columns or "age_grp" in columns or "auth_num" in columns)
    ):
        return "S3"

    raise ValueError(
        f"Unrecognized FDA ASCII schema signature for release {release}. "
        f"Detected DEMO columns: {columns[:10]}... "
        f"Ensure archive matches S1 (ISR), S2 (PRIMARYID+GNDR_COD), or S3 (PRIMARYID+SEX)."
    )
