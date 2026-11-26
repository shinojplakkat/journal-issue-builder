"""Putting the issue together (blueprint M7 and 6.5).

The result is a Plan: one PageSpec per physical page, saying where the page
comes from, its printed number, and its header. Every output (electronic,
print, offprints) is made from the same plan, so page numbers always agree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..builder import front_matter as fm
from ..builder.article import article_pdf_path, build_articles
from ..pdfops.inspect import page_count
from ..settings.load_save import IssueFolder, JournalFolder
from ..settings.models import Article, IssueSettings, JournalSettings
from .blank_pages import NONE, Element, balance
from .numbering import to_roman

FRONT_PARTS = [("title_page", "Title page"), ("imprint", "Copyright and imprint"),
               ("masthead", "Editorial board"), ("contents", "Contents")]
BACK_PARTS = [("author_index", "Author index"), ("aims_scope", "Aims and scope"),
              ("notes_for_authors", "Notes for authors")]


@dataclass
class PageSpec:
    kind: str                      # "content" or "blank"
    source: Path | None = None     # PDF the page comes from
    index: int = 0                 # page index inside that PDF
    element: str = ""              # part name or article id
    role: str = ""                 # "front", "article", "back", "blank"
    number: int | None = None      # printed number (None = not printed)
    roman: bool = False
    header: str = ""
    first_of_article: bool = False
    print_number: bool = True      # False on blank pages and the title page

    @property
    def label(self) -> str:
        if self.number is None:
            return ""
        return to_roman(self.number) if self.roman else str(self.number)


@dataclass
class ArticlePlacement:
    article: Article
    first_physical: int
    last_physical: int
    first_number: int
    last_number: int

    @property
    def pages_label(self) -> str:
        return f"{self.first_number}–{self.last_number}" if self.last_number != self.first_number \
            else str(self.first_number)


@dataclass
class Plan:
    pages: list[PageSpec] = field(default_factory=list)
    placements: list[ArticlePlacement] = field(default_factory=list)
    parts: dict[str, tuple[int, int]] = field(default_factory=dict)   # part -> (first, last) physical
    contents_pdf: Path | None = None
    contents_entries: list[fm.ContentsEntry] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def _side(value: str) -> str:
    return value if value in ("right", "left", "any") else "right"


def make_plan(journal_folder: JournalFolder, issue_folder: IssueFolder,
              progress: Callable[[str], None] | None = None, binding_mode: str = NONE) -> Plan:
    """Build every article, the front and back matter, and lay out the issue."""
    say = progress or (lambda message: None)
    journal = journal_folder.load_journal()
    settings = issue_folder.load()
    layout = settings.layout
    articles = issue_folder.load_articles(settings)

    plan = Plan()
    say("Laying out articles")
    plan.problems += build_articles(issue_folder, articles, layout, say)
    ready = [a for a in articles if a.import_status == "ok" and article_pdf_path(issue_folder, a.id).is_file()]
    for a in articles:
        if a not in ready:
            plan.problems.append(f"{a.id} ({a.title[:40] or a.source_name}) is left out: "
                                 f"{a.import_message or 'no PDF could be made'}")

    say("Making front and back matter")
    work = issue_folder.work / "_matter"
    logo = journal_folder.logo_path(journal)
    fixed: dict[str, fm.Page] = {}
    on = layout.parts_on
    if on.get("title_page", True):
        fixed["title_page"] = fm.title_page(journal, settings, layout, logo)
    if on.get("imprint", True):
        fixed["imprint"] = fm.imprint_page(journal, settings, layout)
    if on.get("masthead", True):
        fixed["masthead"] = fm.masthead_page(journal, layout)
    if on.get("aims_scope") and journal.aims_scope:
        fixed["aims_scope"] = fm.text_page(layout, "Aims and Scope", journal.aims_scope)
    if on.get("notes_for_authors") and journal.notes_for_authors:
        fixed["notes_for_authors"] = fm.text_page(layout, "Notes for Authors", journal.notes_for_authors)
    pdfs = fm.render(fixed, work) if fixed else {}

    # Contents and author index depend on page numbers, which depend on the
    # contents' own length: repeat until stable (blueprint 6.5).
    contents_pages = 1
    index_pages = 1
    for _round in range(4):
        counts = {name: page_count(path) for name, path in pdfs.items()}
        if on.get("contents", True):
            counts["contents"] = contents_pages
        if on.get("author_index"):
            counts["author_index"] = index_pages
        pages, placements, parts = _lay_out(settings, ready, counts, pdfs, issue_folder, binding_mode)
        entries = [
            fm.ContentsEntry(p.article.id, p.article.type, p.article.title, p.article.author_names, str(p.first_number))
            for p in placements
        ]
        extra: dict[str, fm.Page] = {}
        if on.get("contents", True):
            extra["contents"] = fm.contents_page(journal, settings, layout, entries)
        if on.get("author_index"):
            extra["author_index"] = fm.author_index_page(layout, _author_index(placements))
        if not extra:
            break
        rendered = fm.render(extra, work)
        pdfs.update(rendered)
        new_contents = page_count(rendered["contents"]) if "contents" in rendered else contents_pages
        new_index = page_count(rendered["author_index"]) if "author_index" in rendered else index_pages
        if new_contents == contents_pages and new_index == index_pages:
            break
        contents_pages, index_pages = new_contents, new_index

    counts = {name: page_count(path) for name, path in pdfs.items()}
    plan.pages, plan.placements, plan.parts = _lay_out(settings, ready, counts, pdfs, issue_folder, binding_mode,
                                                       journal=journal)
    plan.contents_pdf = pdfs.get("contents")
    plan.contents_entries = entries
    for placement in plan.placements:
        a = placement.article
        a.start_page, a.end_page = placement.first_number, placement.last_number
        issue_folder.save_article(a)
    return plan


def _author_index(placements: list[ArticlePlacement]) -> list[tuple[str, str]]:
    index: dict[str, list[str]] = {}
    for p in placements:
        for author in p.article.authors:
            if author.name.strip():
                index.setdefault(author.name.strip(), []).append(str(p.first_number))
    def surname_key(name: str) -> str:
        return name.split()[-1].lower() + " " + name.lower()
    return [(name, ", ".join(pages)) for name, pages in sorted(index.items(), key=lambda kv: surname_key(kv[0]))]


def _lay_out(settings: IssueSettings, articles: list[Article], counts: dict[str, int], pdfs: dict[str, Path],
             issue_folder: IssueFolder, binding_mode: str, journal: JournalSettings | None = None):
    """Run the blank-page rules and number every page."""
    layout = settings.layout
    starts = layout.starts_on
    elements: list[Element] = []
    roles: dict[str, str] = {}
    for name, _title in FRONT_PARTS:
        if name in counts:
            elements.append(Element(name, counts[name], _side(starts.get(name, "right"))))
            roles[name] = "front"
    for a in articles:
        side = a.starts_on if a.starts_on in ("right", "left", "any") else _side(starts.get("article", "right"))
        elements.append(Element(a.id, max(1, a.page_count), side))
        roles[a.id] = "article"
    for name, _title in BACK_PARTS:
        if name in counts:
            elements.append(Element(name, counts[name], _side(starts.get(name, "right"))))
            roles[name] = "back"

    slots = balance(elements, binding_mode)

    # Arabic numbering starts on the first article (or the first back part).
    first_arabic_physical = next((s.first_page for s in slots if s.kind == "element" and roles[s.name] != "front"),
                                 None)
    offset = (first_arabic_physical - layout.first_arabic_page) if first_arabic_physical else 0

    by_id = {a.id: a for a in articles}
    short = (journal.short_title or journal.title) if journal else ""
    pages: list[PageSpec] = []
    placements: list[ArticlePlacement] = []
    parts: dict[str, tuple[int, int]] = {}
    for slot in slots:
        for k, physical in enumerate(range(slot.first_page, slot.last_page + 1)):
            front = first_arabic_physical is None or physical < first_arabic_physical
            if slot.kind == "blank":
                pages.append(PageSpec("blank", role="blank", element=slot.name,
                                      number=physical if front else physical - offset,
                                      roman=front and layout.roman_front_matter, print_number=False))
                continue
            role = roles[slot.name]
            spec = PageSpec("content", element=slot.name, role=role, index=k,
                            number=physical if front else physical - offset,
                            roman=front and layout.roman_front_matter)
            if role == "article":
                spec.source = article_pdf_path(issue_folder, slot.name)
                spec.first_of_article = k == 0
                article = by_id[slot.name]
                if layout.header_on:
                    rule = layout.header_right if physical % 2 == 1 else layout.header_left
                    spec.header = {"journal": short, "article": article.header_title()}.get(rule, "")
                if not article.stamp_numbers:
                    spec.print_number = False
                    spec.header = ""
            else:
                spec.source = pdfs.get(slot.name)  # contents: not made yet in the first rounds
                spec.print_number = slot.name != "title_page"
            pages.append(spec)
        if slot.kind == "element":
            parts[slot.name] = (slot.first_page, slot.last_page)
            if roles[slot.name] == "article":
                first, last = slot.first_page, slot.last_page
                placements.append(ArticlePlacement(by_id[slot.name], first, last, first - offset, last - offset))
    return pages, placements, parts
