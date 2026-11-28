"""Electronic issue and per-article PDFs (blueprint M11)."""

from __future__ import annotations

import re
from pathlib import Path

from ..assembler.issue import FRONT_PARTS, BACK_PARTS, Plan
from ..cover.wrap import CoverPages
from ..pdfops import bookmarks, inspect, merge
from ..settings.load_save import safe_name, unique_name
from ..settings.models import IssueSettings, JournalSettings
from .interior import build_interior

PART_TITLES = dict(FRONT_PARTS + BACK_PARTS)


def _label(spec) -> tuple[str, int | None, str]:
    if spec.number is None:
        return ("", None, "")
    return ("r" if spec.roman else "D", spec.number, "")


def contents_link_areas(contents_pdf: Path, entry_count: int) -> list[tuple[int, tuple]]:
    """Find each contents entry's area by its right-aligned page number.

    Returns [(page index inside the contents PDF, rect in PDF points)], one per
    entry, in order. If the numbers cannot all be found, returns [].
    """
    areas = []
    page_total = inspect.page_count(contents_pdf)
    for page_index in range(page_total):
        words, height = inspect.find_words(contents_pdf, page_index)
        # The page number may be joined to the dot leader ("Practice.....19").
        numbers = [w for w in words if re.search(r"\d+$", w["text"])]
        if not numbers:
            continue
        right = max(w["x1"] for w in numbers)
        numbers = [w for w in numbers if right - w["x1"] < 2]
        lefts = [w["x0"] for w in words]
        left = min(lefts) if lefts else 0
        previous_bottom = None
        for w in sorted(numbers, key=lambda w: w["top"]):
            top = previous_bottom if previous_bottom is not None else w["top"] - 2
            # Entry area: from just below the previous number to this number's line.
            top = max(top, w["top"] - 40)
            areas.append((page_index, (left, height - w["bottom"] - 1, right + 1, height - top)))
            previous_bottom = w["bottom"] + 1
    return areas if len(areas) == entry_count else []


def electronic_issue(plan: Plan, journal: JournalSettings, issue: IssueSettings, covers: CoverPages | None,
                     target: Path, *, keep_blanks: bool, proof: bool) -> list[str]:
    notes: list[str] = []
    specs = [s for s in plan.pages if keep_blanks or s.kind != "blank"]
    interior = build_interior(plan, journal, issue, specs, proof=proof)
    pdf = interior.pdf
    # Remember where each page ended up, before covers are added.
    position_of = {id(spec): n for n, spec in enumerate(specs)}
    offset = 0
    labels = [_label(s) for s in specs]
    if covers is not None:
        merge.add_cover_pages(pdf, interior.sources, covers.front, covers.back)
        offset = 1
        labels.insert(0, ("", None, "Cover"))
        labels.append(("", None, "Back cover"))
    bookmarks.set_page_labels(pdf, labels)

    def page_of(predicate) -> int | None:
        for spec in specs:
            if predicate(spec):
                return position_of[id(spec)] + offset
        return None

    marks = []
    if covers is not None:
        marks.append(("Cover", 0, []))
    for name, title in FRONT_PARTS:
        index = page_of(lambda s, n=name: s.element == n and s.kind == "content")
        if index is not None:
            marks.append((title, index, []))
    article_marks = []
    for placement in plan.placements:
        index = page_of(lambda s, a=placement.article.id: s.element == a and s.first_of_article)
        if index is not None:
            title = placement.article.title or placement.article.id
            if placement.article.author_names:
                title += f" — {placement.article.author_names}"
            article_marks.append((title, index))
    if article_marks:
        marks.append(("Articles", article_marks[0][1], article_marks))
    for name, title in BACK_PARTS:
        index = page_of(lambda s, n=name: s.element == n and s.kind == "content")
        if index is not None:
            marks.append((title, index, []))
    bookmarks.add_bookmarks(pdf, marks)

    # Clickable contents entries
    if plan.contents_pdf is not None and plan.placements:
        areas = contents_link_areas(plan.contents_pdf, len(plan.placements))
        if areas:
            for (page_in_contents, rect), placement in zip(areas, plan.placements):
                contents_page = page_of(lambda s, k=page_in_contents: s.element == "contents" and s.index == k)
                target_page = page_of(lambda s, a=placement.article.id: s.element == a and s.first_of_article)
                if contents_page is not None and target_page is not None:
                    bookmarks.add_link(pdf, contents_page, rect, target_page=target_page)
        else:
            notes.append("Contents links could not be placed; the contents page is still correct.")

    # Clickable DOI links on article first pages
    for position, rect in interior.doi_links:
        spec = specs[position]
        placement = next((p for p in plan.placements if p.article.id == spec.element), None)
        if placement and placement.article.doi:
            bookmarks.add_link(pdf, position + offset, rect, uri=f"https://doi.org/{placement.article.doi}")

    # Journal website text appears in the title and imprint pages. Make those
    # printed occurrences clickable in the electronic issue as well.
    website = journal.website.strip()
    if website:
        host = website.removeprefix("https://").removeprefix("http://").split("/", 1)[0].casefold()
        uri = website if website.startswith(("https://", "http://")) else "https://" + website
        for position, spec in enumerate(specs):
            if spec.kind != "content" or spec.element not in {"title_page", "imprint", "masthead"} \
                    or spec.source is None:
                continue
            try:
                words, height = inspect.find_words(spec.source, spec.index)
            except Exception:
                continue
            for word in words:
                if host and host in word["text"].casefold():
                    rect = (word["x0"], height - word["bottom"], word["x1"], height - word["top"])
                    bookmarks.add_link(pdf, position + offset, rect, uri=uri)
    email = journal.email.strip()
    if email and "@" in email:
        for position, spec in enumerate(specs):
            if spec.kind != "content" or spec.element not in {"imprint", "masthead"} or spec.source is None:
                continue
            try:
                words, height = inspect.find_words(spec.source, spec.index)
            except Exception:
                continue
            for word in words:
                if email.casefold() in word["text"].casefold():
                    rect = (word["x0"], height - word["bottom"], word["x1"], height - word["top"])
                    bookmarks.add_link(pdf, position + offset, rect, uri=f"mailto:{email}")

    authors = "; ".join(a.name for p in plan.placements for a in p.article.authors if a.name)
    issns = ", ".join(x for x in (f"ISSN {journal.print_issn} (Print)" if journal.print_issn else "",
                                  f"ISSN {journal.e_issn} (Online)" if journal.e_issn else "") if x)
    bookmarks.set_metadata(
        pdf,
        title=f"{journal.title}, {issue.label}",
        author=authors,
        subject=f"{journal.title}, Volume {issue.volume}, Issue {issue.number}. {issns}",
        keywords=f"{journal.title}; Volume {issue.volume}; Issue {issue.number}; {issns}",
    )
    merge.save(pdf, target)
    interior.close()
    return notes


def electronic_articles(plan: Plan, journal: JournalSettings, issue: IssueSettings, folder: Path,
                        *, proof: bool) -> list[Path]:
    """One PDF per article, cut from the issue so the page numbers match."""
    files = []
    used: set[str] = set()
    for placement in plan.placements:
        article = placement.article
        specs = [s for s in plan.pages if s.element == article.id and s.kind == "content"]
        if not specs:
            continue
        interior = build_interior(plan, journal, issue, specs, proof=proof, physical_start=placement.first_physical)
        pdf = interior.pdf
        bookmarks.set_page_labels(pdf, [_label(s) for s in specs])
        for position, rect in interior.doi_links:
            if article.doi:
                bookmarks.add_link(pdf, position, rect, uri=f"https://doi.org/{article.doi}")
        bookmarks.set_metadata(
            pdf,
            title=article.title,
            author="; ".join(a.name for a in article.authors if a.name),
            subject=f"{journal.title}, Vol. {issue.volume}, No. {issue.number}, {issue.year}, pp. {placement.pages_label}",
            keywords="; ".join(article.keywords),
        )
        name = unique_name(f"{issue.slug}_{safe_name(article.first_author_surname, 20)}_"
                           f"{safe_name(article.short_title or article.title, 30)}", used, ".pdf")
        target = folder / name
        merge.save(pdf, target)
        interior.close()
        files.append(target)
    return files
