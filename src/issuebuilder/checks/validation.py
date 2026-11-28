"""Checks before export (blueprint M13). Errors block export; warnings do not."""

from __future__ import annotations

import re
from dataclasses import dataclass

from PIL import Image

from ..settings.load_save import IssueFolder, JournalFolder
from ..settings.defaults import PAPER_SIZES_MM
from ..settings.models import Article, IssueSettings, JournalSettings
from ..settings.script_fonts import font_file_present, noto_family, scripts_in
from ..importers.pdf_reader import has_unmapped_glyph_placeholders
from ..pdfops import inspect

ISSN = re.compile(r"^\d{4}-\d{3}[\dXx]$")


@dataclass
class Finding:
    level: str      # "error" or "warning"
    where: str      # "Journal", "Issue" or the article
    message: str


def issn_valid(issn: str) -> bool:
    """ISSN check digit: weights 8..2, mod 11, 10 written as X."""
    if not ISSN.match(issn):
        return False
    digits = issn.replace("-", "")
    total = sum(int(d) * w for d, w in zip(digits[:7], range(8, 1, -1)))
    check = (11 - total % 11) % 11
    return digits[7].upper() == ("X" if check == 10 else str(check))


def check_issue(journal_folder: JournalFolder, issue_folder: IssueFolder) -> list[Finding]:
    journal = journal_folder.load_journal()
    settings = issue_folder.load()
    articles = issue_folder.load_articles(settings)
    found: list[Finding] = []
    found += _check_journal(journal)
    found += _check_issue(settings, articles, issue_folder)
    for article in articles:
        found += _check_article(article, settings, issue_folder)
    found += _check_duplicates(journal_folder, issue_folder, articles)
    return found


def _check_journal(j: JournalSettings) -> list[Finding]:
    out = []
    if not j.title.strip():
        out.append(Finding("error", "Journal", "The journal title is missing."))
    for label, issn in (("Print ISSN", j.print_issn), ("Online ISSN", j.e_issn)):
        if not issn.strip():
            out.append(Finding("error", "Journal", f"{label} is missing."))
        elif not issn_valid(issn.strip()):
            out.append(Finding("warning", "Journal", f"{label} '{issn}' does not have a valid check digit."))
    if not j.licence.strip():
        out.append(Finding("error", "Journal", "The licence text is missing."))
    if not j.publisher.strip():
        out.append(Finding("warning", "Journal", "The publisher name is missing."))
    return out


def _check_issue(s: IssueSettings, articles: list[Article], issue_folder: IssueFolder) -> list[Finding]:
    out = []
    if s.volume < 1 or s.number < 1:
        out.append(Finding("error", "Issue", "Volume and issue number must be 1 or more."))
    if not s.month or not s.year:
        out.append(Finding("error", "Issue", "The issue date (month and year) is missing."))
    if not articles:
        out.append(Finding("error", "Issue", "The issue has no articles."))
    width_mm, height_mm = PAPER_SIZES_MM[s.layout.page_size]
    for side in ("front", "back"):
        name = getattr(s.cover, f"{side}_image")
        if not name:
            continue
        image_path = issue_folder.assets / name
        if not image_path.is_file():
            out.append(Finding("warning", "Issue", f"The selected {side} cover image '{name}' is missing; "
                                                       "a generated background will be used instead."))
            continue
        try:
            with Image.open(image_path) as image:
                scale_mm_per_pixel = max(width_mm / image.width, height_mm / image.height)
                dpi = 25.4 / scale_mm_per_pixel if scale_mm_per_pixel else 0
            if dpi < s.export.min_image_dpi:
                out.append(Finding("warning", "Issue", f"The {side} cover image is about {dpi:.0f} dpi at "
                                                           f"{s.layout.page_size} size; print quality target "
                                                           f"is {s.export.min_image_dpi} dpi."))
        except Exception as exc:
            out.append(Finding("warning", "Issue", f"Could not check the {side} cover image: {exc}"))
    return out


def _check_article(a: Article, s: IssueSettings, issue_folder: IssueFolder | None = None) -> list[Finding]:
    where = f"{a.id}: {a.title[:50] or a.source_name}"
    out = []
    if a.import_status != "ok":
        out.append(Finding("warning", where, f"Could not be imported and will be left out: {a.import_message}"))
        return out
    if not a.title.strip():
        out.append(Finding("error", where, "The article has no title."))
    if not any(x.name.strip() for x in a.authors):
        out.append(Finding("error", where, "The article has no author."))
    if a.source_kind == "pdf" and has_unmapped_glyph_placeholders(
            " ".join([a.title, *(author.name for author in a.authors)])):
        out.append(Finding(
            "error", where,
            "The PDF text layer contains CID placeholders instead of readable characters. The article body is "
            "preserved, but its contents-page entry will be wrong. Use Edit details to enter the title and authors "
            "manually before export.",
        ))
    missing_dates = [name for name in ("received", "accepted", "published") if not a.dates.get(name, "").strip()]
    if missing_dates:
        out.append(Finding("warning", where, "Missing dates: " + ", ".join(missing_dates) + "."))
    if a.review_status == "needs_review":
        out.append(Finding("warning", where, "Not reviewed yet (Review screen)."))
    limit = s.export.abstract_word_limit
    if a.abstract and len(a.abstract.split()) > limit:
        out.append(Finding("warning", where, f"Abstract has {len(a.abstract.split())} words (limit {limit})."))
    if a.doi:
        suffix = a.doi.split("/", 1)[-1]
        if re.search(r"\d{4}-\d{3}[\dXx]", suffix) or re.search(r"(19|20)\d{2}", suffix) \
                or re.search(r"\b(vol|issue|pp?)\b", suffix, re.IGNORECASE) \
                or re.search(r"(?:^|[._/-])(?:[A-Za-z]\.){1,3}(?:$|[._/-])", suffix):
            out.append(Finding("warning", where, f"DOI suffix '{suffix}' contains a year, ISSN, issue or page "
                                                 "information or initials; DOIs should not carry meaning that may change."))
    for author in a.authors:
        if author.orcid:
            from ..analyzer.orcid import is_valid

            if not is_valid(author.orcid):
                out.append(Finding("warning", where, f"ORCID {author.orcid} of {author.name} is not valid."))
    for w in a.warnings:
        if "below" in w and "pt" in w:
            out.append(Finding("warning", where, w))
    if issue_folder is not None:
        built_pdf = issue_folder.work / a.id / "article.pdf"
        source_pdf = issue_folder.path / a.source_file if a.source_kind == "pdf" and a.source_file else None
        pdf = built_pdf if built_pdf.is_file() else source_pdf
        if pdf is not None and pdf.is_file():
            try:
                for page_number, dpi in inspect.image_resolutions(pdf):
                    if dpi < s.export.min_image_dpi:
                        out.append(Finding("warning", where, f"Image on page {page_number} is about {dpi} dpi; "
                                                               f"print quality target is {s.export.min_image_dpi} dpi."))
            except Exception as exc:
                out.append(Finding("warning", where, f"Could not check image resolution: {exc}"))
    article_text = " ".join(block.text for block in a.blocks)
    if not article_text and issue_folder is not None and a.source_kind == "pdf" and a.source_file:
        source = issue_folder.path / a.source_file
        if source.is_file():
            try:
                article_text = " ".join(line.text for line in inspect.text_lines(source))
            except Exception:
                pass
    for script in sorted(scripts_in(article_text)):
        if script == "Malayalam":
            selected_font = s.layout.script_fonts.get(script, "").strip() or s.layout.indic_font
            missing = [] if font_file_present(selected_font) else [selected_font]
            if missing:
                out.append(Finding("warning", where, f"Text contains Malayalam characters but the selected font "
                                                       f"'{missing[0]}' was not found. Install it or select an "
                                                       "installed Malayalam font in Layout."))
            continue
        mapped_font = s.layout.script_fonts.get(script, "").strip()
        if mapped_font:
            if not font_file_present(mapped_font):
                out.append(Finding("warning", where, f"Text contains {script} characters but the mapped font "
                                                       f"'{mapped_font}' was not found. Re-import it in Layout."))
            continue
        missing = [noto_family(script), noto_family(script, headings=True)]
        missing = [name for name in missing if not font_file_present(name)]
        if missing:
            out.append(Finding("warning", where, f"Text contains {script} characters but these fonts were not found: "
                                                   f"{', '.join(missing)}."))
    return out


def _check_duplicates(journal_folder: JournalFolder, current: IssueFolder, articles: list[Article]) -> list[Finding]:
    """An article may belong to only one issue (same file in two issues is an error)."""
    out = []
    mine = {a.source_hash: a for a in articles if a.source_hash}
    seen_here: dict[str, str] = {}
    for a in articles:
        if a.source_hash and a.source_hash in seen_here:
            out.append(Finding("error", f"{a.id}", f"Same file as {seen_here[a.source_hash]} in this issue."))
        seen_here.setdefault(a.source_hash, a.id)
    for other in journal_folder.list_issues():
        if other.path.resolve() == current.path.resolve():
            continue
        try:
            other_settings = other.load()
            for a in other.load_articles(other_settings):
                if a.source_hash in mine:
                    out.append(Finding("error", mine[a.source_hash].id,
                                       f"This article is also in {other_settings.label}."))
        except Exception:
            continue
    return out
