from pathlib import Path

import pikepdf
import pytest
from reportlab.pdfgen import canvas

from issuebuilder.pdfops import pdfa
from issuebuilder.pdfops.inspect import pdfa2b_structure, unembedded_fonts
from issuebuilder.tools.ghostscript import GHOSTSCRIPT, make_pdfa2b


def _one_page_pdf(path: Path) -> None:
    page = canvas.Canvas(str(path))
    page.setTitle("Journal output check")
    page.setFont("Helvetica", 12)
    page.drawString(72, 720, "Journal output check")
    page.bookmarkPage("issue-start")
    page.addOutlineEntry("Issue start", "issue-start")
    page.linkURL("https://example.org", (72, 700, 180, 720), relative=0)
    page.save()


def test_font_audit_flags_unembedded_nonstandard_font(tmp_path):
    path = tmp_path / "unembedded.pdf"
    _one_page_pdf(path)
    with pikepdf.open(path) as pdf:
        fonts = pdf.pages[0].obj["/Resources"]["/Font"]
        font = next(iter(fonts.values()))
        font["/BaseFont"] = pikepdf.Name("/JournalAuditFont")
        descriptor = font.get("/FontDescriptor")
        if descriptor is None:
            descriptor = pikepdf.Dictionary()
            font["/FontDescriptor"] = descriptor
        descriptor["/FontName"] = pikepdf.Name("/JournalAuditFont")
        for key in ("/FontFile", "/FontFile2", "/FontFile3"):
            if key in descriptor:
                del descriptor[key]
        pdf.save(path.with_name("missing-font.pdf"))

    assert unembedded_fonts(path.with_name("missing-font.pdf")) == ["page 1: JournalAuditFont"]


def test_pdfa2b_export_uses_strict_ghostscript_mode(tmp_path):
    if GHOSTSCRIPT.find() is None:
        pytest.skip("Ghostscript is not installed")
    source, target = tmp_path / "issue.pdf", tmp_path / "issue-pdfa2b.pdf"
    _one_page_pdf(source)
    linked_source = tmp_path / "issue-with-internal-link.pdf"
    with pikepdf.open(source) as pdf:
        pdf.Root["/PageLabels"] = pikepdf.Dictionary(
            Nums=pikepdf.Array([0, pikepdf.Dictionary(S=pikepdf.Name.D)]))
        page = pdf.pages[0].obj
        internal = pikepdf.Dictionary(
            Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Link,
            Rect=pikepdf.Array([190, 700, 260, 720]),
            Dest=pikepdf.Array([pdf.pages[0].obj, pikepdf.Name.Fit]),
        )
        page["/Annots"].append(pdf.make_indirect(internal))
        pdf.save(linked_source)
    title = "Journal Issue മലയാളം"
    ok, message = make_pdfa2b(linked_source, target, title)
    if not ok and "sRGB ICC profile" in message:
        pytest.skip(message)
    assert ok, message
    assert target.is_file() and target.stat().st_size > 0
    with pikepdf.open(target) as pdf:
        assert len(pdf.pages) == 1
        assert "/OutputIntents" in pdf.Root
        assert unembedded_fonts(target) == []
        assert pdf.Root.get("/Outlines")
        assert "/PageLabels" in pdf.Root
        assert str(pdf.docinfo.get("/Title", "")) == title
    assert pdfa.restore_links(linked_source, target) == 2
    with pikepdf.open(target) as pdf:
        annotations = pdf.pages[0].obj.get("/Annots", [])
        links = [annotation for annotation in annotations if annotation.get("/Subtype") == "/Link"]
        assert len(links) == 2
        assert all(int(link.get("/F", 0)) & 4 for link in links)
        assert any(annotation.get("/A", {}).get("/URI") == "https://example.org" for annotation in links)
        internal_link = next(annotation for annotation in links if "/Dest" in annotation)
        assert tuple(internal_link["/Dest"][0].objgen) == tuple(pdf.pages[0].obj.objgen)
    assert pdfa2b_structure(target)[0]
