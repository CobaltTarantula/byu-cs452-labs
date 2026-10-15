"""Render the executed SQL questions and database result rows as a PDF."""

import os
from html import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from recommender.db_query import QUESTIONS, fetch_results, format_cell


def create_pdf(path: str | None = None) -> str:
    path = path or os.getenv("RESULTS_PDF", "results.pdf")
    page_size = landscape(letter)
    doc = SimpleDocTemplate(
        path,
        pagesize=page_size,
        rightMargin=0.42 * inch,
        leftMargin=0.42 * inch,
        topMargin=0.42 * inch,
        bottomMargin=0.42 * inch,
        title="Podcast Recommender: Queries and Results",
        author="CS452 project",
    )
    base = getSampleStyleSheet()
    subtitle = ParagraphStyle("Subtitle", parent=base["BodyText"], fontSize=9, leading=12)
    cell = ParagraphStyle("Cell", parent=base["BodyText"], fontSize=7.3, leading=9)
    header = ParagraphStyle("Header", parent=cell, textColor=colors.white, fontName="Helvetica-Bold")
    code = ParagraphStyle("SQL", fontName="Courier", fontSize=6.5, leading=8, alignment=TA_LEFT)

    result_rows = fetch_results()
    story = [
        Paragraph("Podcast Vector Recommender", base["Title"]),
        Paragraph("Executed PostgreSQL queries and results · pgvector L2 distance (&lt;-&gt;)", subtitle),
        Spacer(1, 10),
    ]

    for question, ((_, sql, _, _), (_, columns, rows)) in enumerate(zip(QUESTIONS, result_rows), 1):
        story.append(Paragraph(escape(result_rows[question - 1][0]), base["Heading2"]))
        story.append(Preformatted(sql.strip(), code, maxLineLength=140))
        story.append(Spacer(1, 5))

        data = [[Paragraph(escape(str(column)), header) for column in columns]]
        for row in rows:
            data.append([Paragraph(escape(format_cell(value)), cell) for value in row])

        if len(columns) == 6:
            widths = [1.85 * inch, 0.72 * inch, 5.15 * inch, 0.62 * inch, 0.62 * inch, 0.78 * inch]
        else:
            widths = [7.25 * inch, 1.05 * inch]
        table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#25476a")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c6cfda")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f5f8")]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.extend([table, Spacer(1, 13)])

    doc.build(story)
    return path


if __name__ == "__main__":
    print(f"Wrote {create_pdf()}")
