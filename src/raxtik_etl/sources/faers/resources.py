"""dlt resource definitions for streaming FAERS tables with explicit schemas."""

from pathlib import Path
from typing import Generator, Iterable, Sequence

import dlt
from dlt.common.schema.typing import TAnySchemaColumns

from raxtik_etl.sources.faers.parser import parse_faers_ascii_file

DEMO_COLUMNS: TAnySchemaColumns = {
    "primaryid": {"data_type": "text"},
    "caseid": {"data_type": "text"},
    "caseversion": {"data_type": "text"},
    "i_f_cod": {"data_type": "text"},
    "event_dt": {"data_type": "text"},
    "mfr_dt": {"data_type": "text"},
    "init_fda_dt": {"data_type": "text"},
    "fda_dt": {"data_type": "text"},
    "mfr_num": {"data_type": "text"},
    "mfr_sndr": {"data_type": "text"},
    "age": {"data_type": "text"},
    "age_cod": {"data_type": "text"},
    "age_grp": {"data_type": "text"},
    "sex": {"data_type": "text"},
    "e_sub": {"data_type": "text"},
    "wt": {"data_type": "text"},
    "wt_cod": {"data_type": "text"},
    "rept_dt": {"data_type": "text"},
    "occp_cod": {"data_type": "text"},
    "reporter_country": {"data_type": "text"},
    "occr_country": {"data_type": "text"},
}

DRUG_COLUMNS: TAnySchemaColumns = {
    "primaryid": {"data_type": "text"},
    "caseid": {"data_type": "text"},
    "drug_seq": {"data_type": "text"},
    "role_cod": {"data_type": "text"},
    "drugname": {"data_type": "text"},
    "prod_ai": {"data_type": "text"},
    "val_vbm": {"data_type": "text"},
    "route": {"data_type": "text"},
    "dose_vbm": {"data_type": "text"},
    "cum_dose_chr": {"data_type": "text"},
    "cum_dose_unit": {"data_type": "text"},
    "dechal": {"data_type": "text"},
    "rechal": {"data_type": "text"},
    "lot_num": {"data_type": "text"},
    "exp_dt": {"data_type": "text"},
    "nda_num": {"data_type": "text"},
    "dose_amt": {"data_type": "text"},
    "dose_unit": {"data_type": "text"},
    "dose_form": {"data_type": "text"},
    "dose_freq": {"data_type": "text"},
}

REAC_COLUMNS: TAnySchemaColumns = {
    "primaryid": {"data_type": "text"},
    "caseid": {"data_type": "text"},
    "pt": {"data_type": "text"},
    "drug_rec_act": {"data_type": "text"},
}

OUTC_COLUMNS: TAnySchemaColumns = {
    "primaryid": {"data_type": "text"},
    "caseid": {"data_type": "text"},
    "outc_cod": {"data_type": "text"},
}

INDI_COLUMNS: TAnySchemaColumns = {
    "primaryid": {"data_type": "text"},
    "caseid": {"data_type": "text"},
    "indi_drug_seq": {"data_type": "text"},
    "indi_pt": {"data_type": "text"},
}


def _stream_files(files: Iterable[Path | str], table_type: str) -> Generator[dict, None, None]:
    """Iterate through all matching files and stream records."""
    for f in files:
        yield from parse_faers_ascii_file(f, table_type=table_type)


@dlt.resource(
    name="demo", write_disposition="append", primary_key="primaryid", columns=DEMO_COLUMNS
)
def demo_resource(files: Sequence[Path | str]):
    """Stream DEMO (Demographics) table."""
    yield from _stream_files(files, "demo")


@dlt.resource(name="drug", write_disposition="append", columns=DRUG_COLUMNS)
def drug_resource(files: Sequence[Path | str]):
    """Stream DRUG table."""
    yield from _stream_files(files, "drug")


@dlt.resource(name="reac", write_disposition="append", columns=REAC_COLUMNS)
def reac_resource(files: Sequence[Path | str]):
    """Stream REAC (Adverse Reactions) table."""
    yield from _stream_files(files, "reac")


@dlt.resource(name="outc", write_disposition="append", columns=OUTC_COLUMNS)
def outc_resource(files: Sequence[Path | str]):
    """Stream OUTC (Patient Outcomes) table."""
    yield from _stream_files(files, "outc")


@dlt.resource(name="indi", write_disposition="append", columns=INDI_COLUMNS)
def indi_resource(files: Sequence[Path | str]):
    """Stream INDI (Indications) table."""
    yield from _stream_files(files, "indi")
