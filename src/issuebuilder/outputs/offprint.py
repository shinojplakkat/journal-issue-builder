"""Offprints: one article with the issue's cover and publication details (blueprint M12).

Built from the finished issue plan, not rebuilt, so the article keeps its
original page numbers (unless 'renumber from 1' is chosen) and its side.
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

from reportlab.lib.colors import Color, black
from reportlab.pdfgen import canvas

from ..assembler.blank_pages import required_total
from ..assembler.issue import ArticlePlacement, Plan
from ..builder import front_matter as fm
from ..cover.wrap import CoverPages
from ..pdfops import bookmarks, compose, imposition, inspect, merge
from ..pdfops.compose import Layer
from ..pdfops.inspect import PT_PER_MM
from ..pdfops.stamp import SANS, SANS_BOLD, printable, register_fonts
from ..settings.defaults import PAPER_SIZES_MM
from ..settings.load_save import safe_name, unique_name
from ..settings.models import IssueSettings, JournalSettings
from .interior import build_interior


def how_to_cite(journal: JournalSettings, issue: IssueSettings, placement: ArticlePlacement) -> str:
    a = placement.article
    names = []
    for author in a.authors:
        parts = author.name.replace(".", ". ").split()
        if not parts:
            continue
        initials = " ".join(p[0] + "." for p in parts[:-1] if p[0].isalpha())
        names.append(f"{parts[-1]}, {initials}".strip(", "))
    who = ", ".join(names[:-1]) + (", & " if len(names) > 1 else "") + names[-1] if names else "Author"
    text = (f"{who} ({issue.year}). {a.title}. {journal.title}, {issue.volume}({issue.number}), "
            f"{placement.pages_label}.")
    if a.doi:
        text += f" https://doi.org/{a.doi}"
    return text


def _offprint_cover(front: Path, target: Path, width_mm: float, height_mm: float, authors: str) -> Path:
    """The issue's front cover with an 'Offprint' band and the author names."""
    register_fonts()
    w, h = width_mm * PT_PER_MM, height_mm * PT_PER_MM
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(w, h))
    band = 16 * PT_PER_MM
    c.setFillColor(Color(1, 1, 1, alpha=0.88))
    c.rect(0, 14 * PT_PER_MM, w, band, stroke=0, fill=1)
    c.setFillColor(black)
    c.setFont(SANS_BOLD, 11)
    c.drawCentredString(w / 2, 14 * PT_PER_MM + band - 6 * PT_PER_MM, "OFFPRINT")
    if authors and printable(authors):
        c.setFont(SANS, 8)
        c.drawCentredString(w / 2, 14 * PT_PER_MM + 4 * PT_PER_MM, authors[:90])
    c.showPage()
    c.save()
    compose.overlay_page(front, [Layer(buffer.getvalue())], target)
    return target


def make_offprints(plan: Plan, journal: JournalSettings, issue: IssueSettings, covers: CoverPages,
                   folder: Path, article_ids: list[str] | None = None, *, electronic: bool = True,
                   printed: bool = False, renumber: bool = False, cite: bool = True,
                   cover_line: bool = True) -> tuple[list[Path], list[str]]:
    """Make offprints for the chosen articles (all when article_ids is None)."""
    layout = issue.layout
    width, height = PAPER_SIZES_MM[layout.page_size]
    chosen = [p for p in plan.placements if article_ids is None or p.article.id in article_ids]
    notes: list[str] = []
    files: list[Path] = []
    if not chosen:
        return files, ["No articles chosen for offprints."]
    folder.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="offprints-"))

    details = {
        p.article.id: fm.offprint_details_page(journal, issue, layout, p.article, p.pages_label,
                                               how_to_cite(journal, issue, p) if cite else "")
        for p in chosen
    }
    detail_pdfs = fm.render(details, work)
    detail_pages: dict[str, list[tuple[Path, int]]] = {}
    for article_id, path in detail_pdfs.items():
        detail_pages[article_id] = [(path, page) for page in range(inspect.page_count(path))]
    used: set[str] = set()

    for placement in chosen:
        article = placement.article
        specs = [s for s in plan.pages if s.element == article.id and s.kind == "content"]
        renumbering = {k: str(k + 1) for k in range(len(specs))} if renumber else None
        interior = build_interior(plan, journal, issue, specs, physical_start=placement.first_physical,
                                  renumber=renumbering)
        body = work / f"{article.id}_body.pdf"
        merge.save(interior.pdf, body)
        interior.close()
        front = covers.front
        if cover_line:
            front = _offprint_cover(covers.front, work / f"{article.id}_cover.pdf", width, height, article.author_names)
        base = unique_name(f"{issue.slug}_{safe_name(article.first_author_surname, 20)}_"
                           f"{safe_name(article.short_title or article.title, 30)}", used, "")
        body_items = [(body, k) for k in range(len(specs))]
        detail_items = detail_pages[article.id]

        if electronic:
            items = [(front, 0)] + detail_items + body_items + [(covers.back, 0)]
            pdf, sources = merge.assemble(items, width, height)
            numbers = [int(s.label) if s.label.isdigit() else None for s in specs]
            if renumber:
                numbers = list(range(1, len(specs) + 1))
            labels = [("", None, "Cover")] + [("", None, "Details")] * len(detail_items) + \
                     [("D", n, "") if n is not None else ("", None, "") for n in numbers] + [("", None, "Back cover")]
            bookmarks.set_page_labels(pdf, labels)
            article_page = 1 + len(detail_items)
            bookmarks.add_bookmarks(pdf, [("Cover", 0, []), ("Publication details", 1, []),
                                          (article.title or article.id, article_page, [])])
            bookmarks.set_metadata(pdf, article.title, "; ".join(a.name for a in article.authors if a.name),
                                   f"Offprint from {journal.title}, {issue.label}, pp. {placement.pages_label}",
                                   "; ".join(article.keywords))
            target = folder / f"{base}.pdf"
            merge.save(pdf, target)
            sources.close()
            files.append(target)

        if printed:
            # Booklet: cover, publication details, article on its original side,
            # blank pages, back cover last; total a multiple of 4.
            items = [(front, 0)] + detail_items
            original_right = placement.first_physical % 2 == 1
            if original_right != (len(items) % 2 == 0):  # next position len+1 is right when len is even
                items.append((None, 0))
            items += body_items
            total = required_total(len(items) + 1, "staple")
            items += [(None, 0)] * (total - len(items) - 1) + [(covers.back, 0)]
            pdf, sources = merge.assemble(items, width, height)
            target = folder / f"{base}_print_booklet.pdf"
            imposed = imposition.impose_pdf(pdf, layout.page_size, PAPER_SIZES_MM)
            try:
                merge.save(imposed, target)
            finally:
                imposed.close()
            sources.close()
            files.append(target)
    notes.append(f"{len(chosen)} offprint(s) made.")
    return files, notes
