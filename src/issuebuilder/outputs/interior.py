"""Turning a Plan into PDF pages with numbers and headers (shared by all outputs)."""

from __future__ import annotations

from dataclasses import dataclass

from ..assembler.issue import PageSpec, Plan
from ..pdfops import merge
from ..pdfops.stamp import Stamp, StampStyle, apply_overlay, overlay_pdf
from ..settings.defaults import PAPER_SIZES_MM
from ..settings.models import IssueSettings, JournalSettings

BLANK_TEXT = "This page intentionally left blank"


@dataclass
class Interior:
    pdf: object                  # pikepdf.Pdf
    sources: merge.PageSource
    specs: list[PageSpec]        # the pages actually included, in order
    doi_links: list[tuple[int, tuple]]

    def close(self) -> None:
        self.sources.close()


def citation_line(journal: JournalSettings, issue: IssueSettings, pages_label: str) -> str:
    name = journal.short_title or journal.title
    return f"{name}, Vol. {issue.volume}, No. {issue.number}, {issue.month} {issue.year}, pp. {pages_label}"


def style_for(issue: IssueSettings) -> StampStyle:
    layout = issue.layout
    return StampStyle(header_pt=layout.header_pt, number_pt=layout.number_pt,
                      number_position=layout.number_position,
                      margin_inside_mm=layout.margin_inside, margin_outside_mm=layout.margin_outside,
                      margin_top_mm=layout.margin_top, margin_bottom_mm=layout.margin_bottom)


def build_interior(plan: Plan, journal: JournalSettings, issue: IssueSettings, specs: list[PageSpec],
                   *, proof: bool = False, physical_start: int = 1, renumber: dict[int, str] | None = None) -> Interior:
    """Assemble the given pages and stamp numbers and headers on them.

    physical_start: the physical page number of specs[0], used only to decide
    left or right (offprints keep the article's original side).
    renumber: optional {position: printed number} that replaces the plan's numbers.
    """
    layout = issue.layout
    width, height = PAPER_SIZES_MM[layout.page_size]
    pdf, sources = merge.assemble([(s.source if s.kind == "content" else None, s.index) for s in specs], width, height)

    placements = {p.article.id: p for p in plan.placements}
    stamps = []
    for position, spec in enumerate(specs):
        physical = physical_start + position
        stamp = Stamp(width_mm=width, height_mm=height, recto=physical % 2 == 1, proof=proof)
        number = renumber.get(position, spec.label) if renumber else spec.label
        if spec.kind == "blank":
            stamp.blank_text = BLANK_TEXT if layout.blank_page_text else ""
        else:
            if spec.print_number:
                stamp.number = number
            if spec.first_of_article:
                placement = placements.get(spec.element)
                if placement and layout.citation_line:
                    stamp.citation = citation_line(journal, issue, placement.pages_label)
                    if placement.article.doi:
                        stamp.doi_url = f"https://doi.org/{placement.article.doi}"
                if not layout.header_first_page:
                    stamp.header = ""
                else:
                    stamp.header = spec.header
            else:
                stamp.header = spec.header
        stamps.append(stamp)
    overlay, doi_links = overlay_pdf(stamps, style_for(issue))
    sources.keep(apply_overlay(pdf, overlay))
    return Interior(pdf, sources, list(specs), doi_links)
