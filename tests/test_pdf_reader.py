from issuebuilder.importers import pdf_reader
from issuebuilder.pdfops.inspect import Line


def test_unmapped_glyphs_only_suppress_affected_metadata(monkeypatch, tmp_path):
    monkeypatch.setattr(pdf_reader.pdf_inspect, "open_status", lambda _path: "ok")
    monkeypatch.setattr(pdf_reader.pdf_inspect, "page_count_and_size", lambda _path: (2, (148, 210)))
    monkeypatch.setattr(pdf_reader.pdf_inspect, "text_lines", lambda *_args, **_kwargs: [
        Line(page=0, text="A(cid:27) Malayalam title", size=22, top=20, x0=10, x1=200, bottom=30),
        Line(page=0, text="Author Name", size=12, top=40, x0=10, x1=200, bottom=50),
    ])

    report = pdf_reader.check_pdf(tmp_path / "encoding-problem.pdf")

    assert report.ok
    assert report.suggestions["title"] == ""
    assert report.suggestions["authors"] == ["Author Name"]
    assert report.warnings == [
        "Some PDF text has an unreadable character mapping. Check the suggested title, authors and abstract."
    ]


def test_unmapped_glyphs_in_body_keep_clean_metadata_suggestions(monkeypatch, tmp_path):
    monkeypatch.setattr(pdf_reader.pdf_inspect, "open_status", lambda _path: "ok")
    monkeypatch.setattr(pdf_reader.pdf_inspect, "page_count_and_size", lambda _path: (2, (148, 210)))
    monkeypatch.setattr(pdf_reader.pdf_inspect, "text_lines", lambda *_args, **_kwargs: [
        Line(page=0, text="A Clear Article Title", size=22, top=20, x0=10, x1=200, bottom=30),
        Line(page=0, text="Author Name", size=12, top=40, x0=10, x1=200, bottom=50),
        Line(page=1, text="Body with (cid:27) unreadable glyph", size=10, top=40,
             x0=10, x1=200, bottom=50),
    ])

    report = pdf_reader.check_pdf(tmp_path / "body-encoding-problem.pdf")

    assert report.suggestions["title"] == "A Clear Article Title"
    assert report.suggestions["authors"] == ["Author Name"]
    assert report.warnings
35bc45c8054ae4c0d5cb8c2d25fe7e3f7e25fce7
