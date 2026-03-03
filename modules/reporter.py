"""
Reporter Module
Generates PDF and Excel reports from analysis findings.
Designed for legal/compliance teams with professional formatting.
"""

import io
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                     TableStyle, HRFlowable, PageBreak)
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

RISK_COLORS_PDF = {
    "HIGH": colors.HexColor("#EF4444"),
    "MEDIUM": colors.HexColor("#F59E0B"),
    "LOW": colors.HexColor("#22C55E")
}


def generate_pdf_report(findings: List[Dict], score_summary: Dict, company_name: str = "Confidential") -> bytes:
    """
    Generate a professional PDF risk report from analysis findings.
    Returns PDF as bytes for download.
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab not installed. Run: pip install reportlab")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=60,
        bottomMargin=50
    )

    styles = getSampleStyleSheet()
    story = []

    # ── Title Page ──────────────────────────────
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=26,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=6,
        fontName='Helvetica-Bold'
    )
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor("#64748B"),
        spaceAfter=4
    )
    section_style = ParagraphStyle(
        'Section',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor("#1E3A5F"),
        spaceBefore=16,
        spaceAfter=8,
        fontName='Helvetica-Bold'
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor("#374151"),
        spaceAfter=6,
        leading=14
    )

    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph("CONTRACT RISK ANALYSIS REPORT", title_style))
    story.append(Paragraph(f"Prepared for: {company_name}", subtitle_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M UTC')}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1E3A5F")))
    story.append(Spacer(1, 0.3 * inch))

    # ── Executive Summary ───────────────────────
    overall_color = RISK_COLORS_PDF.get(score_summary.get("overall_risk", "LOW"), colors.green)
    story.append(Paragraph("EXECUTIVE SUMMARY", section_style))

    summary_data = [
        ["Overall Risk Level", score_summary.get("overall_risk", "N/A")],
        ["Total Findings", str(score_summary.get("total", 0))],
        ["High Risk Findings", str(score_summary.get("high", 0))],
        ["Medium Risk Findings", str(score_summary.get("medium", 0))],
        ["Low Risk Findings", str(score_summary.get("low", 0))]
    ]

    summary_table = Table(summary_data, colWidths=[3 * inch, 3 * inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor("#0F172A")),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 0.3 * inch))

    # ── Findings Detail ──────────────────────────
    story.append(Paragraph("DETAILED FINDINGS", section_style))

    if not findings:
        story.append(Paragraph("No risk findings detected in the analyzed documents.", body_style))
    else:
        for i, f in enumerate(findings, 1):
            risk_level = f.get("risk_level", "LOW")
            risk_color = RISK_COLORS_PDF.get(risk_level, colors.green)

            # Finding header row
            header_data = [[
                Paragraph(f"#{i} {f.get('category_label', 'Finding')}", 
                          ParagraphStyle('FH', fontName='Helvetica-Bold', fontSize=11, textColor=colors.white)),
                Paragraph(f"{risk_level} RISK | {f.get('filename', '')}",
                          ParagraphStyle('FH2', fontName='Helvetica', fontSize=9, textColor=colors.white))
            ]]
            header_table = Table(header_data, colWidths=[3.5 * inch, 3 * inch])
            header_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), risk_color),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(header_table)

            # Finding body
            detail_data = []
            if f.get("finding"):
                detail_data.append(["Finding:", f.get("finding", "")])
            if f.get("problematic_language") and f.get("problematic_language") != "N/A":
                detail_data.append(["Flagged Language:", f.get("problematic_language", "")])
            if f.get("interpretation"):
                detail_data.append(["Interpretation:", f.get("interpretation", "")])
            if f.get("follow_up_questions"):
                qs = "\n".join(f"• {q}" for q in f["follow_up_questions"])
                detail_data.append(["Legal Team Questions:", qs])

            if detail_data:
                detail_table = Table(detail_data, colWidths=[1.8 * inch, 4.7 * inch])
                detail_table.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor("#374151")),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#FAFAFA")),
                    ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB")),
                    ('LEFTPADDING', (0, 0), (-1, -1), 10),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ]))
                story.append(detail_table)

            story.append(Spacer(1, 0.2 * inch))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


def generate_excel_report(findings: List[Dict], score_summary: Dict) -> bytes:
    """
    Generate an Excel report with multiple sheets:
    - Summary: overall risk scores
    - Findings: detailed table of all findings
    - By Category: breakdown by risk category
    """
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        workbook = writer.book

        # ── Formats ─────────────────────────────
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#1E3A5F', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True
        })
        high_fmt = workbook.add_format({'bg_color': '#FEE2E2', 'font_color': '#991B1B', 'bold': True})
        medium_fmt = workbook.add_format({'bg_color': '#FEF3C7', 'font_color': '#92400E', 'bold': True})
        low_fmt = workbook.add_format({'bg_color': '#DCFCE7', 'font_color': '#166534', 'bold': True})
        wrap_fmt = workbook.add_format({'text_wrap': True, 'valign': 'top'})

        # ── Sheet 1: Summary ─────────────────────
        summary_data = {
            "Metric": ["Overall Risk", "Total Findings", "High Risk", "Medium Risk", "Low Risk"],
            "Value": [
                score_summary.get("overall_risk", "N/A"),
                score_summary.get("total", 0),
                score_summary.get("high", 0),
                score_summary.get("medium", 0),
                score_summary.get("low", 0)
            ]
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name="Summary", index=False)
        ws = writer.sheets["Summary"]
        ws.set_column('A:A', 20)
        ws.set_column('B:B', 20)

        # ── Sheet 2: All Findings ────────────────
        if findings:
            rows = []
            for f in findings:
                rows.append({
                    "Risk Level": f.get("risk_level", ""),
                    "Category": f.get("category_label", ""),
                    "Document": f.get("filename", ""),
                    "Finding": f.get("finding", ""),
                    "Flagged Language": f.get("problematic_language", ""),
                    "Interpretation": f.get("interpretation", ""),
                    "Follow-up Q1": f.get("follow_up_questions", [""])[0] if f.get("follow_up_questions") else "",
                    "Follow-up Q2": f.get("follow_up_questions", ["", ""])[1] if len(f.get("follow_up_questions", [])) > 1 else "",
                    "Source Text": f.get("source_text", "")[:200]
                })
            df = pd.DataFrame(rows)
            df.to_excel(writer, sheet_name="Findings", index=False)
            ws2 = writer.sheets["Findings"]
            ws2.set_column('A:A', 12)
            ws2.set_column('B:B', 25)
            ws2.set_column('C:C', 25)
            ws2.set_column('D:D', 40)
            ws2.set_column('E:H', 35)

            # Color code risk rows
            for row_idx, f in enumerate(findings, 1):
                level = f.get("risk_level", "LOW")
                fmt = {"HIGH": high_fmt, "MEDIUM": medium_fmt}.get(level, low_fmt)
                ws2.write(row_idx, 0, level, fmt)

        # ── Sheet 3: Category Breakdown ──────────
        cat_rows = []
        for cat, data in score_summary.get("by_category", {}).items():
            if data["total"] > 0:
                from modules.analyzer import RISK_CATEGORIES
                cat_rows.append({
                    "Category": RISK_CATEGORIES.get(cat, {}).get("label", cat),
                    "Total": data["total"],
                    "High": data["HIGH"],
                    "Medium": data["MEDIUM"],
                    "Low": data["LOW"]
                })
        if cat_rows:
            pd.DataFrame(cat_rows).to_excel(writer, sheet_name="By Category", index=False)

    buffer.seek(0)
    return buffer.read()