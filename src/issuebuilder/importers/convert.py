"""Adding submitted files to an issue (blueprint M2, M3).

A failing file never stops the others: it is added with an error status and
a clear message, so the editor sees it in the article list.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Callable

from ..analyzer.blocks import analyze_word, fill_details
from ..settings.defaults import PAPER_SIZES_MM
from ..settings.load_save import IssueFolder
from ..settings.models import MODE_JOURNAL, MODE_PDF, Article, Author, IssueSettings
from ..tools import libreoffice
from .docx_reader import clean_copy
from .pdf_reader import check_pdf

WORD_TYPES = {".doc", ".docx", ".odt", ".rtf"}
PDF_TYPES = {".pdf"}
SUPPORTED = WORD_TYPES | PDF_TYPES


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_word_path(issue: IssueFolder, article_id: str) -> Path:
    """The cleaned DOCX copy that everything else reads."""
    return issue.work / article_id / "clean.docx"


def import_files(issue: IssueFolder, settings: IssueSettings, paths: list[Path],
                 progress: Callable[[int, int, str], None] | None = None) -> list[Article]:
    """Copy files into the issue, convert and analyse them. Returns the new articles."""
    articles: list[Article] = []
    total = len(paths)
    for number, source in enumerate(paths, 1):
        source = Path(source)
        if progress:
            progress(number, total, source.name)
        article = Article(id=issue.new_article_id(settings), source_name=source.name)
        settings.article_order.append(article.id)
        try:
            _import_one(issue, settings, source, article)
        except Exception as error:  # keep going with the other files
            article.import_status = "error"
            article.import_message = f"{type(error).__name__}: {error}"
            if not article.title:
                article.title = source.stem
        issue.save_article(article)
        issue.save(settings)
        articles.append(article)
    return articles


def _import_one(issue: IssueFolder, settings: IssueSettings, source: Path, article: Article) -> None:
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError(f"{suffix or 'This'} files are not supported. Use DOC, DOCX, ODT or PDF.")
    if not source.is_file() or source.stat().st_size == 0:
        raise ValueError("The file is empty.")

    copied = issue.copy_original(source, article.id)
    article.source_file = str(copied.relative_to(issue.path)).replace("\\", "/")
    article.source_hash = file_hash(copied)
    work = issue.work / article.id
    work.mkdir(parents=True, exist_ok=True)

    if suffix in PDF_TYPES:
        _import_pdf(settings, copied, article)
    else:
        _import_word(issue, settings, copied, article, work)


def _import_word(issue: IssueFolder, settings: IssueSettings, copied: Path, article: Article, work: Path) -> None:
    article.source_kind = "word"
    article.mode = MODE_JOURNAL
    if copied.suffix.lower() == ".docx":
        docx_file = copied
    else:
        # DOC and ODT are converted to DOCX first; the copy in originals/ stays as sent.
        converted = libreoffice.convert_one(copied, "docx", work / "converted")
        docx_file = work / "converted.docx"
        shutil.move(str(converted), docx_file)
        shutil.rmtree(work / "converted", ignore_errors=True)

    clean = clean_word_path(issue, article.id)
    tracked, comments = clean_copy(docx_file, clean)
    if tracked:
        article.warnings.append("Tracked changes were accepted in the working copy.")
    if comments:
        article.warnings.append("Comments were removed from the working copy.")

    article.blocks, article.flags, _ = analyze_word(clean)
    fill_details(article, clean)
    if article.flags:
        article.warnings.append(
            "Contains " + ", ".join(article.flags) + ": check these pages carefully after building."
        )
    limit = settings.export.abstract_word_limit
    if article.abstract and len(article.abstract.split()) > limit:
        article.warnings.append(f"Abstract has {len(article.abstract.split())} words (limit {limit}).")
    if not any(b.label == "title" for b in article.blocks):
        article.warnings.append("No title found. Mark it on the Review screen.")


def _import_pdf(settings: IssueSettings, copied: Path, article: Article) -> None:
    article.source_kind = "pdf"
    article.mode = MODE_PDF
    report = check_pdf(copied)
    if not report.ok:
        raise ValueError(report.problem)
    article.page_count = report.pages
    suggestions = report.suggestions
    article.title = suggestions.get("title", "")
    article.short_title = article.title if len(article.title) <= 60 else ""
    article.authors = [Author(name=n) for n in suggestions.get("authors", []) if n]
    article.abstract = suggestions.get("abstract", "")
    article.warnings.extend(report.warnings)
    article.warnings.append("PDF article: title, authors and abstract are only suggestions. Please check them.")
    target_width, _ = PAPER_SIZES_MM[settings.layout.page_size]
    if report.width_mm and abs(report.width_mm - target_width) > 2:
        factor = min(target_width / report.width_mm, 1.0)
        effective = report.body_pt * factor
        if effective and effective < settings.export.min_scaled_body_pt:
            article.warnings.append(
                f"The PDF is {report.width_mm:.0f} mm wide; on {settings.layout.page_size} its body text "
                f"would print at about {effective:.1f} pt (below {settings.export.min_scaled_body_pt:g} pt). "
                "Ask for the Word file if possible."
            )


def reanalyse(issue: IssueFolder, article: Article) -> None:
    """Label the Word article again from scratch (after the rules change)."""
    clean = clean_word_path(issue, article.id)
    article.blocks, article.flags, _ = analyze_word(clean)
    fill_details(article, clean)
