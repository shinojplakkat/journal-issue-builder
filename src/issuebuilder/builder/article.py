"""Making one PDF per article at the issue's page size (blueprint M6).

Results are cached: an article is laid out again only when its file, its
labels or the layout settings change. All Word articles that need building
go to LibreOffice in one call, which is much faster than one call each.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Callable

from ..importers.convert import clean_word_path
from ..pdfops import pages as pdfpages
from ..settings.defaults import PAPER_SIZES_MM
from ..settings.load_save import IssueFolder
from ..settings.models import MODE_PDF, Article, LayoutSettings
from ..tools import libreoffice
from .word_layout import prepare_word


def article_pdf_path(issue: IssueFolder, article_id: str) -> Path:
    return issue.work / article_id / "article.pdf"


def _cache_key(article: Article, layout: LayoutSettings) -> str:
    data = {
        "hash": article.source_hash,
        "mode": article.mode,
        "blocks": [(b.i, b.label) for b in article.blocks],
        "dates": article.dates,
        "doi": article.doi,
        "layout": layout.to_dict(),
        "builder": 4,  # raise when the layout code changes, to rebuild everything
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def build_articles(issue: IssueFolder, articles: list[Article], layout: LayoutSettings,
                   progress: Callable[[str], None] | None = None) -> list[str]:
    """Make article.pdf for every article that imported correctly.

    Returns a list of problems (one line per failed article); the article's
    page_count is updated and saved.
    """
    problems: list[str] = []
    width, height = PAPER_SIZES_MM[layout.page_size]
    to_convert: dict[str, Path] = {}
    staging = issue.work / "_layout"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)

    for article in articles:
        if article.import_status != "ok":
            continue
        target = article_pdf_path(issue, article.id)
        key_file = target.with_suffix(".key")
        key = _cache_key(article, layout)
        if target.is_file() and key_file.is_file() and key_file.read_text() == key:
            continue
        try:
            if article.mode == MODE_PDF:
                if progress:
                    progress(f"Fitting PDF article {article.id} to {layout.page_size}")
                source = issue.path / article.source_file
                article.page_count = pdfpages.fit_to_size(source, target, width, height)
                key_file.write_text(key)
            else:
                docx = staging / f"{article.id}.docx"
                prepare_word(clean_word_path(issue, article.id), docx, article, layout)
                to_convert[article.id] = docx
        except Exception as error:
            problems.append(f"{article.id} ({article.title[:40]}): {error}")

    if to_convert:
        if progress:
            progress(f"LibreOffice is laying out {len(to_convert)} Word article(s)")
        try:
            done = libreoffice.convert(list(to_convert.values()), "pdf", staging / "pdf")
        except Exception as error:
            done = {}
            problems.append(f"LibreOffice: {error}")
        for article in articles:
            if article.id not in to_convert:
                continue
            produced = done.get(to_convert[article.id])
            if produced is None:
                problems.append(f"{article.id} ({article.title[:40]}): LibreOffice did not produce a PDF.")
                continue
            target = article_pdf_path(issue, article.id)
            # LibreOffice keeps landscape sections; fit_to_size makes every page the issue size.
            article.page_count = pdfpages.fit_to_size(produced, target, width, height)
            target.with_suffix(".key").write_text(_cache_key(article, layout))

    for article in articles:
        if article.import_status == "ok" and article_pdf_path(issue, article.id).is_file():
            from ..pdfops.inspect import page_count

            article.page_count = page_count(article_pdf_path(issue, article.id))
            issue.save_article(article)
    shutil.rmtree(staging, ignore_errors=True)
    return problems
