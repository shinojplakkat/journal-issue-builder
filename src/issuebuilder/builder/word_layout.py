"""Laying out Word articles in the journal's page format (blueprint M6, M8).

Instead of rebuilding the text from scratch, a copy of the author's own Word
file is changed: page size, mirrored margins, journal fonts and sizes for
each labelled part. LibreOffice then makes the PDF. This keeps tables,
footnotes, images and Indian scripts that a rebuild would lose.

Two modes:
  journal   restyle every labelled paragraph in the journal template
  original  keep the author's styles; only page size and margins change
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor
from docx.text.paragraph import Paragraph

from ..settings.defaults import PAPER_SIZES_MM
from ..settings.models import Article, LayoutSettings, MODE_JOURNAL

BLACK = RGBColor(0, 0, 0)
FRONT_LABELS = ("title", "subtitle", "author", "orcid", "email", "institution", "abstract", "keywords")


# --------------------------------------------------------------------------- page setup

def setup_pages(document, layout: LayoutSettings) -> None:
    """A5/A4 pages with mirrored margins and no headers or footers.

    Headers and page numbers are added later on the finished issue, so the
    numbering runs continuously across all articles.
    """
    width, height = PAPER_SIZES_MM[layout.page_size]
    for section in document.sections:
        landscape = section.page_width is not None and section.page_height is not None \
            and section.page_width > section.page_height
        section.page_width, section.page_height = (Mm(height), Mm(width)) if landscape else (Mm(width), Mm(height))
        section.top_margin = Mm(layout.margin_top)
        section.bottom_margin = Mm(layout.margin_bottom)
        section.left_margin = Mm(layout.margin_inside)
        section.right_margin = Mm(layout.margin_outside)
        section.gutter = Mm(0)
        section.header_distance = Mm(8)
        section.footer_distance = Mm(8)
        sect = section._sectPr
        for tag in ("w:headerReference", "w:footerReference", "w:titlePg", "w:pgNumType", "w:cols"):
            for el in sect.findall(qn(tag)):
                sect.remove(el)
    _set_mirror_margins(document)


def _set_mirror_margins(document) -> None:
    settings = document.settings.element
    if settings.find(qn("w:mirrorMargins")) is None:
        settings.insert(0, OxmlElement("w:mirrorMargins"))
    # Odd/even headers are not used any more.
    for el in settings.findall(qn("w:evenAndOddHeaders")):
        settings.remove(el)


def text_width_mm(layout: LayoutSettings) -> float:
    width, _ = PAPER_SIZES_MM[layout.page_size]
    return width - layout.margin_inside - layout.margin_outside


def fit_images_and_tables(document, layout: LayoutSettings) -> None:
    """Shrink pictures wider than the text, and let tables fit the text width."""
    max_width = Mm(text_width_mm(layout))
    for shape in document.inline_shapes:
        try:
            if shape.width and shape.width > max_width:
                ratio = max_width / shape.width
                shape.height = int(shape.height * ratio)
                shape.width = max_width
        except (AttributeError, ZeroDivisionError, TypeError):
            continue
    for table in document.tables:
        tbl_pr = table._tbl.tblPr
        width = tbl_pr.find(qn("w:tblW"))
        if width is None:
            width = OxmlElement("w:tblW")
            tbl_pr.append(width)
        width.set(qn("w:type"), "pct")
        width.set(qn("w:w"), "5000")  # 100 percent
        for el in tbl_pr.findall(qn("w:tblLayout")):
            tbl_pr.remove(el)
        table.autofit = True
        # Fixed column widths from an A4 page would overflow an A5 page.
        grid = table._tbl.find(qn("w:tblGrid"))
        if grid is not None:
            for col in grid.findall(qn("w:gridCol")):
                col.getparent().remove(col)
        for cell in table._tbl.iter(qn("w:tcW")):
            cell.set(qn("w:type"), "auto")
            cell.set(qn("w:w"), "0")


# --------------------------------------------------------------------------- fonts

def set_run_font(run, name: str | None, size_pt: float | None, indic_font: str | None = None) -> None:
    """Set Latin and complex-script font and size for one run."""
    if size_pt:
        run.font.size = Pt(size_pt)
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    if name:
        for attr in ("w:ascii", "w:hAnsi", "w:eastAsia"):
            fonts.set(qn(attr), name)
        for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme"):
            fonts.attrib.pop(qn(attr), None)
    if indic_font:
        fonts.set(qn("w:cs"), indic_font)
        fonts.attrib.pop(qn("w:cstheme"), None)
    if size_pt:
        size_cs = rpr.find(qn("w:szCs"))
        if size_cs is None:
            size_cs = OxmlElement("w:szCs")
            rpr.append(size_cs)
        size_cs.set(qn("w:val"), str(int(round(size_pt * 2))))


def set_style_font(style, name: str, size_pt: float, indic_font: str) -> None:
    style.font.name = name
    style.font.size = Pt(size_pt)
    rpr = style.element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is not None:
        for attr in ("w:ascii", "w:hAnsi", "w:eastAsia"):
            fonts.set(qn(attr), name)
        fonts.set(qn("w:cs"), indic_font)
        for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            fonts.attrib.pop(qn(attr), None)
    size_cs = rpr.find(qn("w:szCs"))
    if size_cs is None:
        size_cs = OxmlElement("w:szCs")
        rpr.append(size_cs)
    size_cs.set(qn("w:val"), str(int(round(size_pt * 2))))


def _remove_page_breaks(paragraph) -> None:
    for br in paragraph._p.iter(qn("w:br")):
        if br.get(qn("w:type")) == "page":
            br.getparent().remove(br)
    ppr = paragraph._p.pPr
    if ppr is not None:
        for el in ppr.findall(qn("w:pageBreakBefore")):
            ppr.remove(el)


def _has_content_other_than_text(paragraph) -> bool:
    p = paragraph._p
    return any(True for _ in p.iter(qn("w:drawing"))) or any(True for _ in p.iter(qn("w:pict"))) \
        or any(True for _ in p.iter("{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath"))


# --------------------------------------------------------------------------- restyling

def restyle(document, article: Article, layout: LayoutSettings) -> None:
    """Apply the journal template to the labelled paragraphs (journal mode)."""
    body, heading, indic = layout.body_font, layout.heading_font, layout.indic_font
    normal = document.styles["Normal"]
    set_style_font(normal, body, layout.body_pt, indic)
    for name, size in (("Footnote Text", layout.footnote_pt), ("Endnote Text", layout.footnote_pt)):
        try:
            set_style_font(document.styles[name], body, size, indic)
        except KeyError:
            pass

    labels = {b.i: b.label for b in article.blocks}
    paragraphs = document.paragraphs

    # Remove ignored paragraphs and empty spacing paragraphs, from the end so
    # the indexes of the earlier ones stay valid.
    for index in range(len(paragraphs) - 1, -1, -1):
        p = paragraphs[index]
        if labels.get(index) == "ignore" or (not p.text.strip() and not _has_content_other_than_text(p)):
            p._p.getparent().remove(p._p)
            labels.pop(index, None)

    kept = [(i, p) for i, p in enumerate(paragraphs) if p._p.getparent() is not None]
    last_front = None
    for index, p in kept:
        label = labels.get(index, "body")
        _remove_page_breaks(p)
        fmt = p.paragraph_format
        fmt.first_line_indent = None
        fmt.left_indent = None
        fmt.right_indent = None
        fmt.space_before = Pt(0)
        fmt.space_after = Pt(0)
        fmt.line_spacing_rule = WD_LINE_SPACING.SINGLE
        size, font, bold, italic, align = layout.body_pt, body, None, None, WD_ALIGN_PARAGRAPH.JUSTIFY

        if label == "title":
            size, font, bold, align = layout.title_pt, body, True, WD_ALIGN_PARAGRAPH.CENTER
            fmt.space_after = Pt(4)
            fmt.keep_with_next = True
        elif label == "subtitle":
            size, italic, align = layout.subtitle_pt, True, WD_ALIGN_PARAGRAPH.CENTER
            fmt.space_after = Pt(4)
        elif label == "author":
            size, align = layout.body_pt, WD_ALIGN_PARAGRAPH.CENTER
            fmt.space_before = Pt(6)
        elif label in ("orcid", "email", "institution"):
            size, align = layout.abstract_pt, WD_ALIGN_PARAGRAPH.CENTER
            italic = label == "institution"
        elif label in ("abstract", "keywords"):
            size = layout.abstract_pt
            fmt.left_indent = Mm(5)
            fmt.right_indent = Mm(5)
            first_abstract = label == "abstract" and (last_front is None or labels.get(last_front) != "abstract")
            fmt.space_before = Pt(10 if first_abstract or label == "keywords" else 0)
            if label == "abstract" and p.text.strip().lower() in ("abstract", "summary"):
                bold, align = True, WD_ALIGN_PARAGRAPH.CENTER
        elif label == "heading1":
            size, font, bold, align = layout.h1_pt, heading, True, WD_ALIGN_PARAGRAPH.LEFT
            fmt.space_before, fmt.space_after, fmt.keep_with_next = Pt(12), Pt(4), True
        elif label == "heading2":
            size, font, bold, italic, align = layout.h2_pt, heading, True, True, WD_ALIGN_PARAGRAPH.LEFT
            fmt.space_before, fmt.space_after, fmt.keep_with_next = Pt(8), Pt(3), True
        elif label == "references":
            size = layout.ref_pt
            fmt.left_indent = Mm(5)
            fmt.first_line_indent = Mm(-5)  # hanging indent
            fmt.space_after = Pt(2)
            align = WD_ALIGN_PARAGRAPH.LEFT
        elif label == "other":
            size = layout.abstract_pt
        else:  # body
            fmt.first_line_indent = Mm(5)

        if _has_content_other_than_text(p):
            # Pictures and equations: exact line spacing would cut them off.
            fmt.first_line_indent = None
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            continue
        if label in ("body", "other"):
            # Body lines on a fixed grid (11 on 14 pt by default, section 7.1).
            fmt.line_spacing_rule = WD_LINE_SPACING.EXACTLY
            fmt.line_spacing = Pt(layout.line_pt * (size / layout.body_pt))
        p.alignment = align
        for run in p.runs:
            # Superscript markers and footnote numbers keep their own size.
            if run.font.superscript or run._element.find(qn("w:footnoteReference")) is not None:
                set_run_font(run, font, None, indic)
                continue
            set_run_font(run, font, size, indic)
            if bold is not None:
                run.font.bold = bold
            if italic is not None:
                run.font.italic = italic
            if label in ("title", "subtitle", "heading1", "heading2"):
                run.font.color.rgb = BLACK  # Word heading styles are often blue
        if label in FRONT_LABELS:
            last_front = index

    # Dates and DOI under the title block (blueprint M6).
    lines = []
    dates = [f"{k.capitalize()}: {v}" for k, v in article.dates.items() if v]
    if dates:
        lines.append("   ".join(dates))
    if article.doi:
        lines.append(f"DOI: https://doi.org/{article.doi}")
    if lines and last_front is not None:
        anchor = paragraphs[last_front]._p
        for text in reversed(lines):
            new = OxmlElement("w:p")
            anchor.addnext(new)
            para = Paragraph(new, paragraphs[last_front]._parent)
            run = para.add_run(text)
            set_run_font(run, body, layout.ref_pt, indic)
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            para.paragraph_format.space_before = Pt(4)


def prepare_word(source: Path, target: Path, article: Article, layout: LayoutSettings) -> Path:
    """Write the laid-out Word copy that LibreOffice turns into the article PDF."""
    document = Document(str(source))
    setup_pages(document, layout)
    fit_images_and_tables(document, layout)
    if article.mode == MODE_JOURNAL:
        restyle(document, article, layout)
    target.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(target))
    return target
