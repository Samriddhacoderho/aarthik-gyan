import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

from schemas.audit import ApprovalRecord

REPORTS_DIR = "reports/output"


def build_risk_report_pdf(company_name: str, company_id: str, report_text: str,final_score: dict, approval_record: ApprovalRecord) -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    safe_name = company_id.replace("/", "_")
    file_path = os.path.join(REPORTS_DIR, f"risk_report_{safe_name}.pdf")

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleCustom", parent=styles["Title"], fontSize=18)
    heading_style = ParagraphStyle("HeadingCustom", parent=styles["Heading2"], spaceBefore=14, spaceAfter=6)
    body_style = ParagraphStyle("BodyCustom", parent=styles["BodyText"], leading=16)

    doc = SimpleDocTemplate(file_path, pagesize=letter,topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    elements = []

    elements.append(Paragraph(f"Risk Assessment Report — {company_name}", title_style))
    elements.append(Spacer(1, 12))

    # Report body — split on blank lines, treat lines ending ':' or short all-caps-ish lines as headings
    for block in report_text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        lines = block.split("\n")
        first_line = lines[0].strip()
        if len(first_line) < 60 and not first_line.endswith("."):
            elements.append(Paragraph(first_line, heading_style))
            remainder = "\n".join(lines[1:]).strip()
            if remainder:
                elements.append(Paragraph(remainder.replace("\n", "<br/>"), body_style))
        else:
            elements.append(Paragraph(block.replace("\n", "<br/>"), body_style))

    elements.append(Spacer(1, 16))
    elements.append(Paragraph("Approval & Audit Trail", heading_style))

    audit_data = [
        ["Field", "Value"],
        ["Decision", approval_record.decision],
        ["Approved by", approval_record.approved_by],
        ["Approved at", approval_record.approved_at],
        ["Final risk level", str(final_score.get("risk_level"))],
        ["Final debt-to-equity", str(final_score.get("debt_to_equity"))],
        ["Final current ratio", str(final_score.get("current_ratio"))],
        ["Final net margin", str(final_score.get("net_margin"))],
        ["Review iterations", str(approval_record.iteration_count)],
        ["Analyst notes", approval_record.edit_notes or "None"],
    ]
    table = Table(audit_data, colWidths=[2.2 * inch, 4 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d2d2d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
    ]))
    elements.append(table)

    doc.build(elements)
    return file_path