"""End-to-end test: sample articles in, every output out. Needs LibreOffice."""

import hashlib
import lzma
import sys
import json
import re
from pathlib import Path

import pikepdf
import pdfplumber
import pytest

from issuebuilder.analyzer.orcid import is_valid
from issuebuilder.importers.convert import import_files
from issuebuilder.outputs.export import run_export
from issuebuilder.outputs.offprint import make_offprints
from issuebuilder.settings.load_save import JournalFolder
from issuebuilder.tools.libreoffice import LIBREOFFICE

GOLDEN = Path(__file__).parent / "golden"
GOLDEN_INFO = json.loads((GOLDEN / "sample_issue_v1.json").read_text(encoding="utf-8"))

pytestmark = pytest.mark.skipif(LIBREOFFICE.find() is None, reason="LibreOffice is not installed")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "samples"))
import make_samples  # noqa: E402


@pytest.fixture(scope="module")
def issue(tmp_path_factory):
    root = tmp_path_factory.mktemp("journal")
    samples = make_samples.main(root / "samples")
    journal = JournalFolder.create(root / "Journal")
    issue = journal.create_issue(1, 2, "July", 2027)
    settings = issue.load()
    # Keep this controlled fixture stable across developers and CI workers.
    settings.layout.indic_font = "Noto Serif Malayalam"
    issue.save(settings)
    import_files(issue, settings, samples)
    return journal, issue


@pytest.fixture(scope="module")
def golden_pdf(tmp_path_factory):
    """Expand the losslessly compressed binary baseline into pytest's temp folder."""
    data = lzma.decompress((GOLDEN / "sample_issue_v1.pdf.xz").read_bytes())
    assert hashlib.sha256(data).hexdigest() == GOLDEN_INFO["pdf_sha256"]
    path = tmp_path_factory.mktemp("golden") / "sample_issue_v1.pdf"
    path.write_bytes(data)
    return path


def test_import(issue):
    _, folder = issue
    articles = folder.load_articles()
    assert len(articles) == 5
    assert all(a.import_status == "ok" for a in articles), [a.import_message for a in articles]
    rhythm = next(a for a in articles if a.source_name == "article_rhythm.docx")
    assert rhythm.title == "Rhythm and Memory in Classical Performance Training"
    assert [a.name for a in rhythm.authors] == ["Priya Nair", "Rahul Menon"]
    assert rhythm.authors[0].corresponding
    assert is_valid(rhythm.authors[0].orcid)
    assert "Sample University 2" in rhythm.authors[1].affiliation
    assert len(rhythm.keywords) == 5
    assert {"tables", "images"} <= set(rhythm.flags)
    labels = [b.label for b in rhythm.blocks]
    assert labels.count("references") == 8
    assert "heading2" in labels


@pytest.mark.parametrize("mode, multiple", [("staple", 4), ("glue", 2)])
def test_export(issue, golden_pdf, mode, multiple):
    journal, folder = issue
    settings = folder.load()
    settings.printing.binding_mode = mode
    folder.save(settings)
    result = run_export(journal, folder, force=True, offprints=True, offprint_print=True)
    assert result.ok, result.notes
    names = [f.name for f in result.files]
    assert f"{settings.slug}_electronic_issue.pdf" in names
    assert any("print_interior" in n for n in names)
    assert any("cover" in n for n in names)
    assert any(n.startswith("calibration") for n in names)
    assert result.log is not None and result.log.is_file()

    with pikepdf.open(folder.output / f"{settings.slug}_electronic_issue.pdf") as pdf:
        with pikepdf.open(golden_pdf) as reference:
            assert len(pdf.pages) == len(reference.pages) == GOLDEN_INFO["electronic_pages"]
        assert "/PageLabels" in pdf.Root
        with pdf.open_outline() as outline:
            assert [item.title for item in outline.root][:2] == ["Cover", "Title page"]
        links = sum(len(p.obj.get("/Annots", [])) for p in pdf.pages)
        assert links == GOLDEN_INFO["link_annotations"]

    with pdfplumber.open(folder.output / f"{settings.slug}_electronic_issue.pdf") as pdf:
        contents = pdf.pages[GOLDEN_INFO["contents_pdf_page"] - 1].extract_text() or ""
    entries = []
    for line in contents.splitlines():
        page_number = re.search(r"\.{2,}\s*(\d+)\s*$", line)
        if page_number:
            title = re.sub(r"\.{2,}\s*\d+\s*$", "", line).strip()
            entries.append((title, int(page_number.group(1))))
    assert entries == [tuple(row) for row in GOLDEN_INFO["contents_entries"]]

    interior = next(f for f in result.files if "print_interior" in f.name)
    with pikepdf.open(interior) as pdf:
        if mode == "staple":
            # Two pages per side: count of sides is half the page count, which is a multiple of 4.
            assert (len(pdf.pages) * 2) % 4 == 0
        else:
            assert len(pdf.pages) % multiple == 0

    # Every article starts on a right-hand (odd) page.
    for article in folder.load_articles():
        assert article.start_page % 2 == 1, (article.id, article.start_page)
    starts = {article.source_name: article.start_page for article in folder.load_articles()}
    assert {name: starts[name] for name in GOLDEN_INFO["article_start_pages"]} == \
        GOLDEN_INFO["article_start_pages"]


def test_offprint_keeps_pages(issue):
    journal_folder, folder = issue
    from issuebuilder.assembler.issue import make_plan
    from issuebuilder.cover.wrap import cover_pages

    plan = make_plan(journal_folder, folder)
    journal, settings = journal_folder.load_journal(), folder.load()
    covers = cover_pages(journal_folder, folder, journal, settings)
    placement = plan.placements[1]
    files, _ = make_offprints(plan, journal, settings, covers, folder.output / "test_offprints",
                              [placement.article.id], printed=True)
    electronic = next(f for f in files if not f.name.endswith("_print_booklet.pdf"))
    with pikepdf.open(electronic) as pdf:
        body_pages = placement.last_physical - placement.first_physical + 1
        assert len(pdf.pages) == body_pages + 3   # cover, details, article, back cover
    booklet = next(f for f in files if f.name.endswith("_print_booklet.pdf"))
    with pikepdf.open(booklet) as pdf:
        assert (len(pdf.pages) * 2) % 4 == 0
