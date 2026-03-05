"""
Base exporter interface. Report data is a dict with 'data' and 'meta'.
Exporters flatten/serialize this into PDF, Excel, or CSV.
"""

from abc import ABC, abstractmethod
from io import BytesIO
from typing import Any, Dict


class BaseExporter(ABC):
    """Base class for report exporters (PDF, Excel, CSV)."""

    content_type: str = "application/octet-stream"
    file_extension: str = "bin"

    @abstractmethod
    def export(self, report_data: Dict[str, Any], title: str = "Report") -> BytesIO:
        """
        Turn report_data (dict with 'data' and 'meta') into a binary buffer.
        Caller can then write to response or file.
        """
        pass

    def _flatten_rows(self, data: Any) -> list:
        """Helper: turn nested dict/list into list of flat rows for tables."""
        if data is None:
            return []
        if isinstance(data, list):
            if not data:
                return []
            if isinstance(data[0], dict):
                return data
            return [data]
        if isinstance(data, dict):
            # Single summary row
            return [data]
        return []
