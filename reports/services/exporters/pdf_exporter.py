"""
PDF export using reportlab (already in project requirements).
"""

from io import BytesIO
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

from .base import BaseExporter


class PDFExporter(BaseExporter):
    content_type = "application/pdf"
    file_extension = "pdf"

    def export(self, report_data: Dict[str, Any], title: str = "Report") -> BytesIO:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )
        styles = getSampleStyleSheet()
        story = []

        # Title
        story.append(Paragraph(title, styles["Title"]))
        story.append(Spacer(1, 0.25 * inch))

        meta = report_data.get("meta") or {}
        if meta:
            meta_text = (
                f"Period: {meta.get('date_from', '')} to {meta.get('date_to', '')}"
            )
            story.append(Paragraph(meta_text, styles["Normal"]))
            story.append(Spacer(1, 0.2 * inch))

        data = report_data.get("data")
        if data is None:
            story.append(Paragraph("No data available.", styles["Normal"]))
            doc.build(story)
            buffer.seek(0)
            return buffer

        # Convert dict/list data into tables
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    # List of dicts -> table
                    table_data = self._dict_list_to_table(value)
                    if table_data:
                        t = Table(table_data, repeatRows=1)
                        t.setStyle(
                            TableStyle(
                                [
                                    (
                                        "BACKGROUND",
                                        (0, 0),
                                        (-1, 0),
                                        colors.HexColor("#4472C4"),
                                    ),
                                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                                ]
                            )
                        )
                        story.append(
                            Paragraph(
                                str(key).replace("_", " ").title(), styles["Heading2"]
                            )
                        )
                        story.append(Spacer(1, 0.1 * inch))
                        story.append(t)
                        story.append(Spacer(1, 0.3 * inch))
                elif key in (
                    "total",
                    "total_income",
                    "total_expenses",
                    "net_position",
                    "net_cash_flow",
                    "cash_inflow",
                    "cash_outflow",
                    "total_new_members",
                    "transaction_count",
                ):
                    story.append(
                        Paragraph(
                            f"<b>{key.replace('_', ' ').title()}</b>: {value}",
                            styles["Normal"],
                        )
                    )
                    story.append(Spacer(1, 0.1 * inch))
        elif isinstance(data, list) and data and isinstance(data[0], dict):
            table_data = self._dict_list_to_table(data)
            if table_data:
                t = Table(table_data, repeatRows=1)
                t.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 10),
                            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                            ("FONTSIZE", (0, 1), (-1, -1), 8),
                        ]
                    )
                )
                story.append(t)

        doc.build(story)
        buffer.seek(0)
        return buffer

    def _dict_list_to_table(self, rows: List[Dict]) -> List[List[str]]:
        if not rows:
            return []
        headers = list(rows[0].keys())
        data = [[str(rows[0].get(h, "")) for h in headers]]
        for row in rows[1:]:
            data.append([str(row.get(h, "")) for h in headers])
        return [headers] + data
