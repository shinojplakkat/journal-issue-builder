"""Cover exports keep identifying details visible over generated and image covers."""

from __future__ import annotations

from pathlib import Path

import pdfplumber
from PIL import Image
from reportlab.pdfgen import canvas

from issuebuilder.builder import front_matter
from issuebuilder.cover.wrap import cover_pages
from issuebuilder.settings.defaults import PAPER_SIZES_MM
from issuebuilder.settings.load_save import JournalFolder
from issuebuilder.pdfops.inspect import PT_PER_MM


def _configured_issue(tmp_path: Path):
    journal_folder = JournalFolder.create(tmp_path / "journal")
    journal = journal_folder.load_journal()
    journal.title = "Journal of Clear Testing"
    journal.short_title = "Clear Testing"
    journal.publisher = "Example Press"
    journal.website = "https://example.test/journal"
    journal.email = "editor@example.test"
    journal.print_issn = "1234-5678"
    journal_folder.save_journal(journal)
    issue_folder = journal_folder.create_issue(3, 2, "June", 2026, "The Test Issue")
    return journal_folder, issue_folder, journal, issue_folder.load()


def _assert_cover_details(pdf: Path):
    with pdfplumber.open(pdf) as document:
        assert len(document.pages) == 1
        text = document.pages[0].extract_text() or ""
    for required in ("Journal of Clear Testing", "The Test Issue", "Volume 3", "Issue 2", "June 2026"):
        assert required in text, (required, text)


def _render_cover_text(pages, folder: Path):
    """Render the already-built cover text pages without depending on LibreOffice."""
    output = {}
    for name, page in pages.items():
        width_mm, height_mm = PAPER_SIZES_MM[page.layout.page_size]
        path = folder / f"{name}.pdf"
        document = canvas.Canvas(str(path), pagesize=(width_mm * PT_PER_MM, height_mm * PT_PER_MM))
        document.setFont("Helvetica", 10)
        y = height_mm * PT_PER_MM * .72
        for paragraph in page.doc.paragraphs:
            if paragraph.text.strip():
                document.drawString(24, y, paragraph.text.replace("•", "-"))
                y -= 16
        document.showPage()
        document.save()
        output[name] = path
    return output


def test_generated_pattern_covers_include_issue_details(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(front_matter, "render", _render_cover_text)
    journal_folder, issue_folder, journal, issue = _configured_issue(tmp_path)
    issue.cover.front_pattern = "diagonal"
    issue.cover.front_background = "#102840"
    issue.cover.back_pattern = "dots"
    issue.cover.back_background = "#743620"
    issue_folder.save(issue)

    covers = cover_pages(journal_folder, issue_folder, journal, issue)

    _assert_cover_details(covers.front)
    _assert_cover_details(covers.back)


def test_uploaded_cover_photos_include_issue_details(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(front_matter, "render", _render_cover_text)
    journal_folder, issue_folder, journal, issue = _configured_issue(tmp_path)
    for side, color in (("front", (150, 40, 60)), ("back", (25, 80, 125))):
        name = f"{side}.png"
        Image.new("RGB", (700, 1000), color).save(issue_folder.assets / name)
        setattr(issue.cover, f"{side}_image", name)
    issue_folder.save(issue)

    covers = cover_pages(journal_folder, issue_folder, journal, issue)

    _assert_cover_details(covers.front)
    _assert_cover_details(covers.back)
