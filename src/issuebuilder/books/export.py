"""Build a single book PDF from imported chapter files and optional book matter."""
from __future__ import annotations

import re
from pathlib import Path
from xml.sax.saxutils import escape

import pikepdf
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A5, A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle)

from ..pdfops.merge import concatenate
from ..tools import libreoffice
from .models import Book
from .storage import BookFolder


def _safe(text: str) -> str:
    return escape(text or "").replace("\n", "<br/>")


def _styles(book: Book):
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("BookTitle", parent=base["Title"], fontName="Times-Bold", fontSize=22,
                                 leading=28, alignment=TA_CENTER, spaceAfter=12),
        "subtitle": ParagraphStyle("BookSubtitle", parent=base["Normal"], fontName="Times-Italic",
                                    fontSize=14, leading=19, alignment=TA_CENTER, spaceAfter=20),
        "heading": ParagraphStyle("BookHeading", parent=base["Heading1"], fontName="Times-Bold",
                                   fontSize=16, leading=20, alignment=TA_CENTER, spaceAfter=16),
        "body": ParagraphStyle("BookMatter", parent=base["BodyText"], fontName="Times-Roman",
                                fontSize=10.5, leading=15, alignment=TA_JUSTIFY, spaceAfter=8),
        "small": ParagraphStyle("BookSmall", parent=base["BodyText"], fontName="Times-Roman",
                                 fontSize=9, leading=12, alignment=TA_LEFT),
    }


def _matter_pdf(folder: BookFolder, book: Book) -> Path:
    size = A4 if book.trim_size.upper() == "A4" else A5
    path = folder.work / "book_front_back_matter.pdf"
    styles = _styles(book)
    story = [Spacer(1, 45 * mm), Paragraph(_safe(book.title), styles["title"])]
    if book.subtitle:
        story.append(Paragraph(_safe(book.subtitle), styles["subtitle"]))
    editors = [c.name for c in book.contributors if c.role.lower() == "editor"]
    authors = [c.name for c in book.contributors if c.role.lower() == "author"]
    names = editors or authors
    if names:
        story += [Spacer(1, 12 * mm), Paragraph(_safe(", ".join(names)), styles["subtitle"])]
    story += [Spacer(1, 30 * mm), Paragraph(_safe(book.publisher), styles["body"]),
              Paragraph(_safe(book.publication_place), styles["body"]),
              Paragraph(str(book.publication_year), styles["body"]), PageBreak()]

    copyright_lines = [f"ISBN (Print): {book.isbn_print}" if book.isbn_print else "",
                       f"ISBN (Digital): {book.isbn_ebook}" if book.isbn_ebook else "",
                       f"{book.edition}" if book.edition else "",
                       f"© {book.copyright_year} {book.copyright_holder}" if book.copyright_holder else "",
                       book.copyright_statement, book.publisher, book.publisher_address]
    story += [Paragraph("Publication Details", styles["heading"])]
    story += [Paragraph(_safe(line), styles["small"]) for line in copyright_lines if line]
    story.append(PageBreak())

    if book.dedication:
        story += [Spacer(1, 55 * mm), Paragraph(_safe(book.dedication), styles["body"]), PageBreak()]
    if book.epigraph:
        story += [Spacer(1, 45 * mm), Paragraph(_safe(book.epigraph), styles["body"]), PageBreak()]
    for heading, value in (("Foreword", book.foreword), ("Preface", book.preface),
                           ("Acknowledgements", book.acknowledgements), ("Introduction", book.introduction)):
        if value.strip():
            story.append(Paragraph(heading, styles["heading"]))
            story.append(Paragraph(_safe(value), styles["body"]))
            story.append(PageBreak())

    included = [ch for ch in book.chapters if ch.include]
    story.append(Paragraph("Contents", styles["heading"]))
    rows = [[Paragraph("<b>Chapter</b>", styles["small"]), Paragraph("<b>Title and contributors</b>", styles["small"])]]
    for index, ch in enumerate(included, 1):
        byline = ", ".join(ch.authors)
        rows.append([Paragraph(str(index), styles["small"]),
                     Paragraph(_safe(ch.title) + ("<br/>" + _safe(byline) if byline else ""), styles["small"])])
    table = Table(rows, colWidths=[18 * mm, size[0] - 55 * mm], repeatRows=1)
    table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), .6, colors.black),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                               ("TOPPADDING", (0, 0), (-1, -1), 7)]))
    story += [table, PageBreak()]

    people = [c for c in book.contributors if c.name]
    if people:
        story.append(Paragraph("Contributors", styles["heading"]))
        for person in people:
            line = f"<b>{_safe(person.name)}</b> — {_safe(person.role)}"
            if person.affiliation:
                line += "<br/>" + _safe(person.affiliation)
            if person.biography:
                line += "<br/>" + _safe(person.biography)
            story.append(Paragraph(line, styles["body"]))
        story.append(PageBreak())

    for heading, value in (("Appendices", book.appendices), ("Glossary", book.glossary),
                           ("Bibliography", book.bibliography), ("Index", book.index_note)):
        if value.strip():
            story.append(Paragraph(heading, styles["heading"]))
            story.append(Paragraph(_safe(value), styles["body"]))
            story.append(PageBreak())

    doc = BaseDocTemplate(str(path), pagesize=size, leftMargin=22*mm, rightMargin=18*mm,
                          topMargin=20*mm, bottomMargin=20*mm, title=book.title,
                          author=", ".join(names))
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="book", frames=[frame])])
    doc.build(story)
    return path


def _chapter_pdf(folder: BookFolder, chapter, index: int) -> Path:
    source = folder.path / chapter.source_file
    if not source.is_file():
        raise FileNotFoundError(f"Chapter source is missing: {chapter.source_file}")
    if source.suffix.lower() == ".pdf":
        return source
    out = folder.work / "chapters" / f"{chapter.id}.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    converted = libreoffice.convert_one(source, "pdf", out.parent)
    if converted != out:
        converted.replace(out)
    return out


def export_book(folder: BookFolder, progress=None) -> Path:
    """Export front matter and all selected chapters into one PDF."""
    say = progress or (lambda message: None)
    book = folder.load()
    if not book.title.strip():
        raise ValueError("Enter a book title before exporting.")
    selected = [ch for ch in book.chapters if ch.include]
    if not selected:
        raise ValueError("Add at least one chapter and mark it for inclusion.")
    say("Creating book front matter and contents")
    matter = _matter_pdf(folder, book)
    parts = [matter]
    for number, chapter in enumerate(selected, 1):
        say(f"Preparing chapter {number} of {len(selected)}: {chapter.title}")
        parts.append(_chapter_pdf(folder, chapter, number))
    safe_title = re.sub(r"[^\\w.-]+", "_", book.title).strip("_") or "book"
    target = folder.output / f"{safe_title}.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    say("Combining pages into the book PDF")
    concatenate(parts, target)
    with pikepdf.open(target, allow_overwriting_input=True) as pdf:
        with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
            meta["/Title"] = book.title
            meta["/Author"] = ", ".join(c.name for c in book.contributors if c.name)
            meta["/Subject"] = book.subject
            meta["/Keywords"] = ", ".join([book.language, book.subject, "ISBN " + book.isbn_print])
        pdf.save(target)
    return target
