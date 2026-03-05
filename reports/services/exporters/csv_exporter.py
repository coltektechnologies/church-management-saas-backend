"""
CSV export using Python stdlib csv.
"""

import csv
from io import BytesIO, StringIO
from typing import Any, Dict, List

from .base import BaseExporter


class CSVExporter(BaseExporter):
    content_type = "text/csv"
    file_extension = "csv"

    def export(self, report_data: Dict[str, Any], title: str = "Report") -> BytesIO:
        out = StringIO()
        writer = csv.writer(out)

        meta = report_data.get("meta") or {}
        writer.writerow([title])
        writer.writerow(
            [f"Period: {meta.get('date_from', '')} to {meta.get('date_to', '')}"]
        )
        writer.writerow([])

        data = report_data.get("data")
        if data is None:
            writer.writerow(["No data available."])
            buffer = BytesIO(out.getvalue().encode("utf-8-sig"))  # BOM for Excel
            buffer.seek(0)
            return buffer

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    writer.writerow([str(key).replace("_", " ").title()])
                    self._write_rows(writer, value)
                    writer.writerow([])
                else:
                    writer.writerow([str(key).replace("_", " ").title(), value])
        elif isinstance(data, list) and data and isinstance(data[0], dict):
            self._write_rows(writer, data)

        buffer = BytesIO(out.getvalue().encode("utf-8-sig"))
        buffer.seek(0)
        return buffer

    def _write_rows(self, writer, rows: List[Dict]) -> None:
        if not rows:
            return
        headers = list(rows[0].keys())
        writer.writerow(headers)
        for row in rows:
            writer.writerow([str(row.get(h, "")) for h in headers])
