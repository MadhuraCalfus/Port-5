"""Generates a single combined PDF report for one ticket: its details and
full chat transcript on the cover page(s), followed by every uploaded
attachment rendered as its own page — an image becomes a page, an existing
PDF attachment has its actual pages merged straight in, and text/Word
content gets extracted and rendered as a text page. Runs entirely in
memory: reportlab builds each piece as its own small PDF, pypdf stitches
them all into one.
"""
import io
from datetime import datetime, timezone

from docx import Document
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_styles = getSampleStyleSheet()
_cell_style = ParagraphStyle("cell", parent=_styles["Normal"], fontSize=9, leading=11)


def _cell(text: str):
    """Wrap a details-table value in a Paragraph so it wraps within the
    column instead of overflowing past it — plain strings in a reportlab
    Table never wrap on their own."""
    return Paragraph(text, _cell_style)


def _esc(value) -> str:
    """Escape for reportlab's Paragraph, which parses a small XML-like
    markup — anything user-typed (message text, names, filenames) has to go
    through this before being embedded in one."""
    if value is None:
        return "—"
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _cover_pdf_bytes(ticket: dict, comments: list[dict]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    story = [
        Paragraph(f"NykaaPulse — Ticket #{ticket['id']} Report", _styles["Title"]),
        Paragraph(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", _styles["Normal"]),
        Spacer(1, 16),
    ]

    # No single "assigned to" field exists on a ticket — it's assigned to a
    # team, not a specific person — so the team lead shown here is whoever
    # from that team actually replied in the chat, derived from the
    # transcript rather than a dedicated column.
    team_leads = sorted({c["author_name"] for c in comments if c.get("author_role") == "team"})
    team_lead_value = ", ".join(team_leads) if team_leads else "Not yet replied to"

    details = [
        ["Field", "Value"],
        ["Customer", _cell(f"{_esc(ticket.get('user_name'))} ({_esc(ticket.get('user_email'))})")],
        ["Status", _cell(_esc(ticket.get("status")))],
        ["Category", _cell(_esc(ticket.get("category")))],
        ["Priority", _cell(_esc(ticket.get("priority")) + (" (escalated)" if ticket.get("escalated") else ""))],
        ["Team", _cell(_esc(ticket.get("team")))],
        ["Team Lead", _cell(_esc(team_lead_value))],
        ["Tone", _cell(_esc(ticket.get("tone")))],
        ["Confidence", _cell(f"{ticket['confidence']:.0%}" if ticket.get("confidence") is not None else "—")],
        ["Submitted", _cell(_esc(ticket.get("created_at")))],
        ["AI reasoning", _cell(_esc(ticket.get("reasoning")))],
    ]
    table = Table(details, colWidths=[110, 380])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3d6b96")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f7f9")]),
            ]
        )
    )
    story += [table, Spacer(1, 14)]

    story += [
        Paragraph("Original message", _styles["Heading3"]),
        Paragraph(_esc(ticket.get("message")).replace("\n", "<br/>"), _styles["Normal"]),
        Spacer(1, 16),
        Paragraph("Conversation history", _styles["Heading3"]),
    ]
    if not comments:
        story.append(Paragraph("No messages on this ticket.", _styles["Normal"]))
    for c in comments:
        who = f"{_esc(c['author_name'])} ({_esc(c['author_role'])})"
        when = _esc(c.get("created_at"))
        if c.get("attachment_name"):
            text = f"<b>{who}</b> — {when}: [attached {_esc(c['attachment_name'])} — see page below]"
        else:
            text = f"<b>{who}</b> — {when}: {_esc(c['body']).replace(chr(10), '<br/>')}"
        story += [Paragraph(text, _styles["Normal"]), Spacer(1, 6)]

    doc.build(story)
    return buf.getvalue()


def _attachment_heading(name: str, uploaded_by: str, note: str | None = None) -> list:
    story = [Paragraph(f"Attachment: {_esc(name)} (from {_esc(uploaded_by)})", _styles["Heading3"]), Spacer(1, 10)]
    if note:
        story.append(Paragraph(_esc(note), _styles["Normal"]))
        story.append(Spacer(1, 10))
    return story


def _image_attachment_pdf_bytes(data: bytes, name: str, uploaded_by: str) -> bytes:
    img = Image.open(io.BytesIO(data))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    img_buf.seek(0)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.6 * inch)
    story = _attachment_heading(name, uploaded_by)

    max_w, max_h = 6.5 * inch, 8.5 * inch
    w, h = img.size
    scale = min(max_w / w, max_h / h, 1)
    story.append(RLImage(img_buf, width=w * scale, height=h * scale))
    doc.build(story)
    return buf.getvalue()


def _text_attachment_pdf_bytes(data: bytes, name: str, uploaded_by: str) -> bytes:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1", errors="replace")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.6 * inch)
    story = _attachment_heading(name, uploaded_by)
    for line in text.splitlines() or [""]:
        story.append(Paragraph(_esc(line) or "&nbsp;", _styles["Code"]))
    doc.build(story)
    return buf.getvalue()


def _docx_attachment_pdf_bytes(data: bytes, name: str, uploaded_by: str) -> bytes:
    extracted = Document(io.BytesIO(data))
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.6 * inch)
    story = _attachment_heading(name, uploaded_by, note="Text extracted from the Word document (formatting/images inside it aren't reproduced).")
    for para in extracted.paragraphs:
        story.append(Paragraph(_esc(para.text) or "&nbsp;", _styles["Normal"]))
        story.append(Spacer(1, 4))
    doc.build(story)
    return buf.getvalue()


def _placeholder_attachment_pdf_bytes(name: str, mime: str, uploaded_by: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.6 * inch)
    story = _attachment_heading(
        name, uploaded_by, note=f"This file type ({mime or 'unknown'}) can't be previewed here — download it separately from the ticket's chat."
    )
    doc.build(story)
    return buf.getvalue()


def generate_ticket_report(ticket: dict, comments: list[dict]) -> bytes:
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(_cover_pdf_bytes(ticket, comments))))

    for c in comments:
        data = c.get("attachment_data")
        if not data:
            continue
        name = c.get("attachment_name") or "attachment"
        mime = c.get("attachment_mime") or ""
        uploaded_by = f"{c['author_name']} ({c['author_role']})"

        try:
            if mime == "application/pdf":
                writer.append(PdfReader(io.BytesIO(data)))
                continue
            elif mime.startswith("image/"):
                page_bytes = _image_attachment_pdf_bytes(data, name, uploaded_by)
            elif mime in ("text/plain", "text/csv"):
                page_bytes = _text_attachment_pdf_bytes(data, name, uploaded_by)
            elif mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                page_bytes = _docx_attachment_pdf_bytes(data, name, uploaded_by)
            else:
                page_bytes = _placeholder_attachment_pdf_bytes(name, mime, uploaded_by)
        except Exception:
            # A malformed/unreadable attachment shouldn't break the whole
            # report — fall back to a placeholder page for that one file.
            page_bytes = _placeholder_attachment_pdf_bytes(name, mime, uploaded_by)

        writer.append(PdfReader(io.BytesIO(page_bytes)))

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
