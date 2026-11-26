"""Page numbers, running headers, citation lines and the PROOF watermark.

These are drawn with ReportLab on a transparent page and laid over the
article pages with pikepdf, so they look the same on Word-built articles
and on PDFs that were passed through.
"""

from __future__ import annotations

import io
import sys
from dataclasses import dataclass
from pathlib import Path

import pikepdf
from reportlab.lib.colors import Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .inspect import PT_PER_MM

SERIF, SERIF_ITALIC, SERIF_BOLD, SANS, SANS_BOLD = "JIB-Serif", "JIB-Serif-Italic", "JIB-Serif-Bold", "JIB-Sans", "JIB-Sans-Bold"
_FONT_FILES = {
    SERIF: "LiberationSerif-Regular.ttf",
    SERIF_ITALIC: "LiberationSerif-Italic.ttf",
    SERIF_BOLD: "LiberationSerif-Bold.ttf",
    SANS: "LiberationSans-Regular.ttf",
    SANS_BOLD: "LiberationSans-Bold.ttf",
}
_registered = False
_charset: set[int] = set()


def fonts_dir() -> Path:
    """The bundled fonts folder, in development and in the packaged program."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "fonts"
    return Path(__file__).resolve().parents[3] / "fonts"


def register_fonts() -> None:
    global _registered
    if _registered:
        return
    folder = fonts_dir()
    for name, file in _FONT_FILES.items():
        font = TTFont(name, str(folder / file))
        pdfmetrics.registerFont(font)
        if name == SERIF:
            _charset.update(font.face.charToGlyph.keys())
    _registered = True


def printable(text: str) -> bool:
    """True if the bundled fonts can draw every character (no shaping needed)."""
    register_fonts()
    return all(ord(c) in _charset or c.isspace() for c in text)


@dataclass
class Stamp:
    """What to draw on one page."""

    width_mm: float
    height_mm: float
    recto: bool                      # right-hand page
    number: str = ""
    header: str = ""
    citation: str = ""               # first page of an article
    doi_url: str = ""
    blank_text: str = ""             # "This page intentionally left blank"
    proof: bool = False


@dataclass
class StampStyle:
    header_pt: float = 8
    number_pt: float = 9
    number_position: str = "outside"  # "centre" or "outside"
    margin_inside_mm: float = 20
    margin_outside_mm: float = 15
    margin_top_mm: float = 18
    margin_bottom_mm: float = 20


def _fit(c: canvas.Canvas, text: str, font: str, size: float, max_width: float) -> str:
    if c.stringWidth(text, font, size) <= max_width:
        return text
    while text and c.stringWidth(text + "…", font, size) > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def overlay_pdf(stamps: list[Stamp], style: StampStyle) -> tuple[bytes, list[tuple[int, tuple]]]:
    """Draw all stamps, one overlay page per page.

    Returns the PDF bytes and the positions of DOI links: [(page, rect)],
    so the electronic version can make them clickable.
    """
    register_fonts()
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    links: list[tuple[int, tuple]] = []
    for n, s in enumerate(stamps):
        w, h = s.width_mm * PT_PER_MM, s.height_mm * PT_PER_MM
        c.setPageSize((w, h))
        inside = style.margin_inside_mm * PT_PER_MM
        outside = style.margin_outside_mm * PT_PER_MM
        left = inside if s.recto else outside
        right = w - (outside if s.recto else inside)
        text_width = right - left
        header_y = h - max(8, style.margin_top_mm - 8) * PT_PER_MM
        number_y = max(6, style.margin_bottom_mm - 11) * PT_PER_MM

        if s.proof:
            c.saveState()
            c.setFillColor(Color(0.6, 0.6, 0.6, alpha=0.25))
            c.setFont(SANS_BOLD, min(w, h) / 5)
            c.translate(w / 2, h / 2)
            c.rotate(45)
            c.drawCentredString(0, 0, "PROOF")
            c.restoreState()

        c.setFillColor(Color(0, 0, 0))
        if s.header and printable(s.header):
            text = _fit(c, s.header, SERIF_ITALIC, style.header_pt, text_width)
            if s.recto:
                c.setFont(SERIF_ITALIC, style.header_pt)
                c.drawRightString(right, header_y, text)
            else:
                c.setFont(SERIF_ITALIC, style.header_pt)
                c.drawString(left, header_y, text)
            c.setLineWidth(0.3)
            c.line(left, header_y - 2.5, right, header_y - 2.5)

        if s.citation and printable(s.citation):
            size = style.header_pt - 0.5
            c.setFont(SERIF, size)
            text = s.citation + (f"  {s.doi_url}" if s.doi_url else "")
            text = _fit(c, text, SERIF, size, text_width)
            c.drawString(left, header_y, text)
            if s.doi_url and s.doi_url in text:
                start = left + c.stringWidth(text[: text.index(s.doi_url)], SERIF, size)
                end = start + c.stringWidth(s.doi_url, SERIF, size)
                links.append((n, (start, header_y - 2, end, header_y + size)))

        if s.number:
            c.setFont(SERIF, style.number_pt)
            if style.number_position == "centre":
                c.drawCentredString((left + right) / 2, number_y, s.number)
            elif s.recto:
                c.drawRightString(right, number_y, s.number)
            else:
                c.drawString(left, number_y, s.number)

        if s.blank_text:
            c.setFont(SERIF_ITALIC, style.header_pt + 1)
            c.drawCentredString(w / 2, h / 2, s.blank_text)
        c.showPage()
    c.save()
    return buffer.getvalue(), links


def apply_overlay(pdf: pikepdf.Pdf, overlay: bytes) -> pikepdf.Pdf:
    """Lay overlay page n over page n of pdf.

    Returns the opened overlay; keep it open until pdf has been saved,
    because pikepdf copies the page content only when saving.
    """
    over = pikepdf.open(io.BytesIO(overlay))
    for page, stamp_page in zip(pdf.pages, over.pages):
        page.add_overlay(stamp_page)
    return over
