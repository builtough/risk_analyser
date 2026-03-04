"""
Reporter Module — PDF and Excel reports from analysis findings.
"""
import io
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                     TableStyle, HRFlowable, PageBreak)
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

RISK_COLORS_PDF = {
    "HIGH":   None,  # set after import
    "MEDIUM": None,
    "LOW":    None,
}


def _risk_colors():
    if REPORTLAB_AVAILABLE and RISK_COLORS_PDF["HIGH"] is None:
        RISK_COLORS_PDF["HIGH"]   = colors.HexColor("#EF4444")
        RISK_COLORS_PDF["MEDIUM"] = colors.HexColor("#F59E0B")
        RISK_COLORS_PDF["LOW"]    = colors.HexColor("#22C55E")


def generate_pdf_report(findings: List[Dict], score_summary: Dict,
                        company_name: str = "Confidential") -> bytes:
    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab not installed. Run: pip install reportlab")
    _risk_colors()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=50, leftMargin=50, topMargin=60, bottomMargin=50)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('T', parent=styles['Title'], fontSize=26,
                                 textColor=colors.HexColor("#0F172A"), spaceAfter=6,
                                 fontName='Helvetica-Bold')
    sub_style   = ParagraphStyle('S', parent=styles['Normal'], fontSize=12,
                                 textColor=colors.HexColor("#64748B"), spaceAfter=4)
    section_style = ParagraphStyle('Sec', parent=styles['Heading2'], fontSize=14,
                                   textColor=colors.HexColor("#1E3A5F"),
                                   spaceBefore=16, spaceAfter=8, fontName='Helvetica-Bold')
    body_style  = ParagraphStyle('B', parent=styles['Normal'], fontSize=10,
                                 textColor=colors.HexColor("#374151"), spaceAfter=6, leading=14)

    story = []
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph("CONTRACT RISK ANALYSIS REPORT", title_style))
    story.append(Paragraph(f"Prepared for: {company_name}", sub_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M UTC')}", sub_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1E3A5F")))
    story.append(Spacer(1, 0.3 * inch))

    # Executive Summary
    story.append(Paragraph("EXECUTIVE SUMMARY", section_style))
    summary_data = [
        ["Overall Risk Level", score_summary.get("overall_risk", "N/A")],
        ["Total Findings",     str(score_summary.get("total",  0))],
        ["High Risk",          str(score_summary.get("high",   0))],
        ["Medium Risk",        str(score_summary.get("medium", 0))],
        ["Low Risk",           str(score_summary.get("low",    0))],
    ]
    tbl = Table(summary_data, colWidths=[3 * inch, 3 * inch])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#F1F5F9")),
        ('FONTNAME',   (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,-1), 10),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('GRID',       (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('LEFTPADDING',(0,0), (-1,-1), 12),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING',(0,0),(-1,-1),8),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.3 * inch))

    # Findings Detail
    story.append(Paragraph("DETAILED FINDINGS", section_style))
    if not findings:
        story.append(Paragraph("No risk findings detected.", body_style))
    else:
        for i, f in enumerate(findings, 1):
            level      = f.get("risk_level", "LOW")
            risk_color = RISK_COLORS_PDF.get(level, colors.green)

            hdr = Table([[
                Paragraph(f"#{i} {f.get('category_label','Finding')}",
                          ParagraphStyle('FH', fontName='Helvetica-Bold', fontSize=11,
                                         textColor=colors.white)),
                Paragraph(f"{level} RISK | {f.get('filename','')}",
                          ParagraphStyle('FH2', fontName='Helvetica', fontSize=9,
                                         textColor=colors.white)),
            ]], colWidths=[3.5*inch, 3*inch])
            hdr.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), risk_color),
                ('LEFTPADDING',(0,0),(-1,-1), 10),
                ('TOPPADDING', (0,0),(-1,-1), 8),
                ('BOTTOMPADDING',(0,0),(-1,-1),8),
            ]))
            story.append(hdr)

            detail_data = []
            for label, key in [("Finding:", "finding"), ("Flagged Language:", "problematic_language"),
                                ("Interpretation:", "interpretation")]:
                val = f.get(key, "")
                if val and val.upper() not in ("N/A", ""):
                    detail_data.append([label, val])
            if f.get("follow_up_questions"):
                qs = "\n".join(f"• {q}" for q in f["follow_up_questions"])
                detail_data.append(["Legal Team Qs:", qs])

            if detail_data:
                dtbl = Table(detail_data, colWidths=[1.8*inch, 4.7*inch])
                dtbl.setStyle(TableStyle([
                    ('FONTNAME',    (0,0), (0,-1), 'Helvetica-Bold'),
                    ('FONTSIZE',    (0,0), (-1,-1), 9),
                    ('VALIGN',      (0,0), (-1,-1), 'TOP'),
                    ('BACKGROUND',  (0,0), (-1,-1), colors.HexColor("#FAFAFA")),
                    ('GRID',        (0,0), (-1,-1), 0.3, colors.HexColor("#E5E7EB")),
                    ('LEFTPADDING', (0,0), (-1,-1), 10),
                    ('TOPPADDING',  (0,0), (-1,-1), 6),
                    ('BOTTOMPADDING',(0,0),(-1,-1), 6),
                ]))
                story.append(dtbl)
            story.append(Spacer(1, 0.2*inch))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


def generate_excel_report(findings: List[Dict], score_summary: Dict) -> bytes:
    # Late import to avoid circular dependency
    from modules.analyzer import RISK_CATEGORIES

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        wb = writer.book
        hdr_fmt  = wb.add_format({'bold':True,'bg_color':'#1E3A5F','font_color':'white',
                                   'border':1,'align':'center','valign':'vcenter','text_wrap':True})
        high_fmt = wb.add_format({'bg_color':'#FEE2E2','font_color':'#991B1B','bold':True})
        med_fmt  = wb.add_format({'bg_color':'#FEF3C7','font_color':'#92400E','bold':True})
        low_fmt  = wb.add_format({'bg_color':'#DCFCE7','font_color':'#166534','bold':True})

        # Sheet 1 — Summary
        pd.DataFrame({
            "Metric": ["Overall Risk","Total Findings","High Risk","Medium Risk","Low Risk"],
            "Value":  [score_summary.get("overall_risk","N/A"),
                       score_summary.get("total",0), score_summary.get("high",0),
                       score_summary.get("medium",0), score_summary.get("low",0)],
        }).to_excel(writer, sheet_name="Summary", index=False)
        ws = writer.sheets["Summary"]
        ws.set_column('A:A', 20); ws.set_column('B:B', 20)

        # Sheet 2 — All Findings
        if findings:
            rows = []
            for f in findings:
                qs = f.get("follow_up_questions", [])
                rows.append({
                    "Risk Level":        f.get("risk_level", ""),
                    "Category":          f.get("category_label", ""),
                    "Document":          f.get("filename", ""),
                    "Lines":             f"{f.get('start_line','?')}–{f.get('end_line','?')}",
                    "Finding":           f.get("finding", ""),
                    "Flagged Language":  f.get("problematic_language", ""),
                    "Interpretation":    f.get("interpretation", ""),
                    "Follow-up Q1":      qs[0] if len(qs) > 0 else "",
                    "Follow-up Q2":      qs[1] if len(qs) > 1 else "",
                    "Source Text":       f.get("source_text", "")[:200],
                })
            df = pd.DataFrame(rows)
            df.to_excel(writer, sheet_name="Findings", index=False)
            ws2 = writer.sheets["Findings"]
            for col, width in [('A',12),('B',25),('C',25),('D',10),('E',40),('F',35),('G',40),('H',35),('I',35)]:
                ws2.set_column(f'{col}:{col}', width)
            for row_idx, f in enumerate(findings, 1):
                fmt = {"HIGH": high_fmt, "MEDIUM": med_fmt}.get(f.get("risk_level","LOW"), low_fmt)
                ws2.write(row_idx, 0, f.get("risk_level",""), fmt)

        # Sheet 3 — Category Breakdown
        cat_rows = []
        for cat, data in score_summary.get("by_category", {}).items():
            if data["total"] > 0:
                cat_rows.append({
                    "Category": RISK_CATEGORIES.get(cat, {}).get("label", cat),
                    "Total":    data["total"],
                    "High":     data["HIGH"],
                    "Medium":   data["MEDIUM"],
                    "Low":      data["LOW"],
                })
        if cat_rows:
            pd.DataFrame(cat_rows).to_excel(writer, sheet_name="By Category", index=False)

    buffer.seek(0)
    return buffer.read()
