from issuebuilder.importers import pdf_reader
from issuebuilder.pdfops.inspect import Line


def test_unmapped_glyphs_disable_unreliable_metadata_suggestions(monkeypatch, tmp_path):
    monkeypatch.setattr(pdf_reader.pdf_inspect, "open_status", lambda _path: "ok")
    monkeypatch.setattr(pdf_reader.pdf_inspect, "page_count_and_size", lambda _path: (2, (148, 210)))
    monkeypatch.setattr(pdf_reader.pdf_inspect, "text_lines", lambda *_args, **_kwargs: [
        Line(page=0, text="A(cid:27) Malayalam title", size=22, top=20, x0=10, x1=200, bottom=30),
        Line(page=0, text="Author Name", size=12, top=40, x0=10, x1=200, bottom=50),
    ])

    report = pdf_reader.check_pdf(tmp_path / "encoding-problem.pdf")

    assert report.ok
    assert report.suggestions == {"title": "", "authors": [], "abstract": ""}
    assert report.warnings == [
        "This PDF's text encoding cannot be read reliably. Fill in the title, authors and abstract manually."
    ]
