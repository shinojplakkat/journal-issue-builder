"""Front and back matter pages (blueprint M7): title page, imprint, masthead,
contents, author index, aims and scope, notes for authors, offprint details,
and the generated covers used when no cover picture is uploaded.

Each page is written as a small Word document and turned into PDF by
LibreOffice, so any script the editor types (for example Malayalam) prints
correctly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.shared import Mm, Pt, RGBColor

from ..settings.defaults import PAPER_SIZES_MM
from ..settings.models import Article, IssueSettings, JournalSettings, LayoutSettings
from ..tools import libreoffice
from .word_layout import set_run_font, set_style_font, setup_pages, text_width_mm

CENTER, LEFT, JUSTIFY = WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.JUSTIFY


@dataclass
class ContentsEntry:
    article_id: str
    kind: str          # article type, e.g. "Research article"
    title: str
    authors: str
    page: str          # printed start page


class Page:
    """Small helper so the page builders below read like a description."""

    def __init__(self, layout: LayoutSettings):
        self.layout = layout
        self.doc = Document()
        setup_pages(self.doc, layout)
        set_style_font(self.doc.styles["Normal"], layout.body_font, layout.body_pt, layout.indic_font)
        fmt = self.doc.styles["Normal"].paragraph_format
        fmt.space_before = Pt(0)
        fmt.space_after = Pt(0)
        # The first paragraph exists already in a new document; reuse it.
        self._fresh = True

    def para(self, text: str = "", size: float | None = None, bold: bool = False, italic: bool = False,
             align=CENTER, before: float = 0, after: float = 0, font: str | None = None,
             colour: RGBColor | None = None):
        if self._fresh and self.doc.paragraphs:
            p = self.doc.paragraphs[0]
        else:
            p = self.doc.add_paragraph()
        self._fresh = False
        p.alignment = align
        p.paragraph_format.space_before = Pt(before)
        p.paragraph_format.space_after = Pt(after)
        if text:
            self.run(p, text, size, bold, italic, font, colour)
        return p

    def run(self, p, text: str, size: float | None = None, bold: bool = False, italic: bool = False,
            font: str | None = None, colour: RGBColor | None = None):
        r = p.add_run(text)
        set_run_font(r, font or self.layout.body_font, size or self.layout.body_pt, self.layout.indic_font)
        r.font.bold = bold
        r.font.italic = italic
        if colour is not None:
            r.font.color.rgb = colour
        return r

    def picture(self, path: Path, width_mm: float, before: float = 0, after: float = 6):
        p = self.para(align=CENTER, before=before, after=after)
        p.add_run().add_picture(str(path), width=Mm(width_mm))
        return p

    def page_break(self):
        p = self.para()
        p.add_run().add_break(WD_BREAK.PAGE)

    @property
    def text_width(self) -> float:
        return text_width_mm(self.layout)

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(str(path))
        return path


def _issue_line(issue: IssueSettings) -> str:
    return f"Volume {issue.volume}  •  Issue {issue.number}  •  {issue.month} {issue.year}"


def _issn_line(journal: JournalSettings) -> str:
    parts = []
    if journal.print_issn:
        parts.append(f"ISSN {journal.print_issn} (Print)")
    if journal.e_issn:
        parts.append(f"ISSN {journal.e_issn} (Online)")
    return "   ".join(parts)


# --------------------------------------------------------------------------- pages

def title_page(journal: JournalSettings, issue: IssueSettings, layout: LayoutSettings, logo: Path | None) -> Page:
    page = Page(layout)
    _, height = PAPER_SIZES_MM[layout.page_size]
    top = height * 0.12
    if logo:
        page.picture(logo, min(32, page.text_width / 3), before=top * 2.83 / 2)
        top = 0
    page.para(journal.title, size=layout.title_pt + 5, bold=True, before=top * 2.83, after=10)
    if issue.title:
        page.para(issue.title, size=layout.subtitle_pt + 1, italic=True, after=10)
    page.para(_issue_line(issue), size=layout.body_pt + 1, before=18, after=4)
    page.para(_issn_line(journal), size=layout.abstract_pt, after=4)
    page.para(journal.publisher, size=layout.body_pt, bold=True, before=height * 0.25 * 2.83)
    if journal.address:
        page.para(journal.address, size=layout.abstract_pt)
    if journal.website:
        page.para(journal.website, size=layout.abstract_pt)
    return page


def imprint_page(journal: JournalSettings, issue: IssueSettings, layout: LayoutSettings) -> Page:
    """Copyright and imprint (verso of the title page)."""
    page = Page(layout)
    small = layout.abstract_pt
    page.para(journal.title, size=layout.body_pt, bold=True, align=LEFT, after=2)
    page.para(f"{journal.frequency} journal  •  {_issue_line(issue)}", size=small, align=LEFT, after=2)
    page.para(_issn_line(journal), size=small, align=LEFT, after=10)
    for heading, text in (
        ("Publisher", "\n".join(x for x in (journal.publisher, journal.address) if x)),
        ("Contact", "\n".join(x for x in (journal.website, journal.email) if x)),
        ("Peer review", journal.peer_review),
        ("Copyright", journal.copyright_text),
        ("Licence", journal.licence),
    ):
        if not text:
            continue
        page.para(heading, size=small, bold=True, align=LEFT, before=6)
        for line in text.split("\n"):
            page.para(line, size=small, align=LEFT)
    if journal.doi_prefix:
        page.para("DOI prefix", size=small, bold=True, align=LEFT, before=6)
        page.para(journal.doi_prefix, size=small, align=LEFT)
    page.para("The views expressed in the articles are those of the authors.",
              size=small - 1, italic=True, align=LEFT, before=14)
    return page


def masthead_page(journal: JournalSettings, layout: LayoutSettings) -> Page:
    page = Page(layout)
    page.para("Editorial Board", size=layout.h1_pt + 1, bold=True, font=layout.heading_font, after=12)
    if journal.editor_in_chief:
        page.para("Editor-in-Chief", size=layout.abstract_pt, bold=True, before=4)
        page.para(journal.editor_in_chief, size=layout.body_pt)
    if journal.editors:
        page.para("Editors", size=layout.abstract_pt, bold=True, before=10)
        for name in journal.editors:
            page.para(name, size=layout.body_pt)
    if journal.board:
        page.para("Editorial Board", size=layout.abstract_pt, bold=True, before=10, after=4)
        for member in journal.board:
            p = page.para(align=CENTER, after=3)
            page.run(p, member.name, layout.body_pt)
            detail = ", ".join(x for x in (member.role, member.institution) if x)
            if detail:
                p.add_run().add_break()
                page.run(p, detail, layout.abstract_pt, italic=True)
    return page


def contents_page(journal: JournalSettings, issue: IssueSettings, layout: LayoutSettings,
                  entries: list[ContentsEntry]) -> Page:
    page = Page(layout)
    page.para("Contents", size=layout.h1_pt + 2, bold=True, font=layout.heading_font, after=4)
    page.para(_issue_line(issue), size=layout.abstract_pt, after=12)
    tab_at = Mm(page.text_width)
    kinds = {e.kind for e in entries}
    previous_kind = None
    for entry in entries:
        if len(kinds) > 1 and entry.kind != previous_kind:
            page.para(_plural(entry.kind).upper(), size=layout.abstract_pt - 0.5, bold=True,
                      font=layout.heading_font, align=LEFT, before=8, after=3)
            previous_kind = entry.kind
        p = page.para(align=LEFT, before=5)
        p.paragraph_format.tab_stops.add_tab_stop(tab_at, WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        p.paragraph_format.right_indent = Mm(0)
        p.paragraph_format.keep_with_next = True
        page.run(p, entry.title + "\t" + entry.page, layout.abstract_pt + 0.5)
        if entry.authors:
            page.para(entry.authors, size=layout.abstract_pt - 0.5, italic=True, align=LEFT)
    return page


def _plural(kind: str) -> str:
    if kind.endswith("y"):
        return kind[:-1] + "ies"
    return kind if kind.endswith("s") or kind == "Editorial" else kind + "s"


def author_index_page(layout: LayoutSettings, names: list[tuple[str, str]]) -> Page:
    page = Page(layout)
    page.para("Author Index", size=layout.h1_pt + 1, bold=True, font=layout.heading_font, after=10)
    tab_at = Mm(page.text_width)
    for name, pages in names:
        p = page.para(align=LEFT, after=1)
        p.paragraph_format.tab_stops.add_tab_stop(tab_at, WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        page.run(p, f"{name}\t{pages}", layout.abstract_pt)
    return page


def text_page(layout: LayoutSettings, heading: str, text: str) -> Page:
    page = Page(layout)
    page.para(heading, size=layout.h1_pt + 1, bold=True, font=layout.heading_font, after=10)
    for line in text.split("\n"):
        if line.strip():
            page.para(line.strip(), size=layout.body_pt, align=JUSTIFY, after=6)
    return page


def offprint_details_page(journal: JournalSettings, issue: IssueSettings, layout: LayoutSettings,
                          article: Article, pages: str, how_to_cite: str) -> Page:
    """Publication details for a single-article offprint (blueprint M12)."""
    page = Page(layout)
    small = layout.abstract_pt
    page.para("OFFPRINT", size=small, bold=True, font=layout.heading_font, after=8)
    page.para(journal.title, size=layout.body_pt + 1, bold=True, after=2)
    page.para(_issue_line(issue), size=small, after=2)
    page.para(_issn_line(journal), size=small, after=12)
    page.para(article.title, size=layout.body_pt, bold=True, after=2)
    if article.author_names:
        page.para(article.author_names, size=small, italic=True, after=2)
    page.para(f"Pages {pages}", size=small, after=2)
    if article.doi:
        page.para(f"https://doi.org/{article.doi}", size=small, after=2)
    if how_to_cite:
        page.para("How to cite", size=small, bold=True, align=LEFT, before=10)
        page.para(how_to_cite, size=small, align=LEFT)
    page.para("Publisher", size=small, bold=True, align=LEFT, before=10)
    page.para(", ".join(x for x in (journal.publisher, journal.address) if x), size=small, align=LEFT)
    page.para(", ".join(x for x in (journal.website, journal.email) if x), size=small, align=LEFT)
    page.para("Copyright and licence", size=small, bold=True, align=LEFT, before=10)
    page.para(journal.copyright_text, size=small, align=LEFT)
    page.para(journal.licence, size=small, align=LEFT)
    return page


def generated_front_cover(journal: JournalSettings, issue: IssueSettings, layout: LayoutSettings,
                          logo: Path | None) -> Page:
    """Plain front cover used when no cover picture has been uploaded."""
    page = Page(layout)
    _, height = PAPER_SIZES_MM[layout.page_size]
    page.para(_issn_line(journal), size=layout.abstract_pt - 1, after=0)
    page.para(journal.title, size=layout.title_pt + 9, bold=True, before=height * 0.18 * 2.83, after=10)
    if issue.title:
        page.para(issue.title, size=layout.subtitle_pt + 2, italic=True, after=6)
    page.para(_issue_line(issue), size=layout.body_pt + 1, before=10)
    if logo:
        page.picture(logo, 28, before=height * 0.12 * 2.83)
    page.para(journal.publisher, size=layout.body_pt, bold=True, before=20)
    return page


def generated_back_cover(journal: JournalSettings, issue: IssueSettings, layout: LayoutSettings) -> Page:
    page = Page(layout)
    page.para(journal.title, size=layout.h1_pt + 1, bold=True, after=10, before=20)
    if journal.aims_scope:
        page.para("Aims and Scope", size=layout.abstract_pt, bold=True, before=6, after=2)
        page.para(journal.aims_scope, size=layout.abstract_pt, align=JUSTIFY)
    page.para(_issn_line(journal), size=layout.abstract_pt, before=20)
    for line in (journal.publisher, journal.address, journal.website, journal.email):
        if line:
            page.para(line, size=layout.abstract_pt)
    return page


# --------------------------------------------------------------------------- rendering

def render(pages: dict[str, Page], folder: Path) -> dict[str, Path]:
    """Turn the pages into PDFs with one LibreOffice call. Returns {name: pdf}."""
    folder.mkdir(parents=True, exist_ok=True)
    sources = {name: page.save(folder / f"{name}.docx") for name, page in pages.items()}
    done = libreoffice.convert(list(sources.values()), "pdf", folder)
    missing = [name for name, src in sources.items() if src not in done]
    if missing:
        raise RuntimeError("LibreOffice could not make: " + ", ".join(missing))
    return {name: done[src] for name, src in sources.items()}


__all__ = ["ContentsEntry", "Page", "render", "title_page", "imprint_page", "masthead_page",
           "contents_page", "author_index_page", "text_page", "offprint_details_page",
           "generated_front_cover", "generated_back_cover", "WD_SECTION", "WD_TABLE_ALIGNMENT"]
