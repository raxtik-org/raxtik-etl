"""Unit tests for the external exporter / connector base interface."""

from __future__ import annotations

from typing import Any, List, Optional

import duckdb

from raxtik_etl.exporters.base import BaseExporter, ExportResult


class DummyExporter(BaseExporter):
    target_type = "dummy"

    def export(
        self,
        con: duckdb.DuckDBPyConnection,
        destination: Any,
        tables: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> ExportResult:
        tbls = tables or ["demo"]
        return ExportResult(
            target_type=self.target_type,
            destination=str(destination),
            exported_tables=tbls,
            total_rows=10,
        )


def test_base_exporter_contract():
    exporter = DummyExporter()
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE demo (id INT);")

    res = exporter.export(con, destination="/tmp/dummy_sink")
    assert res.target_type == "dummy"
    assert res.exported_tables == ["demo"]
    assert res.total_rows == 10
    con.close()
