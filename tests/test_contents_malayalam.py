"""The generated contents page must keep Malayalam entries and font selection."""

from docx import Document
from docx.oxml.ns import qn

from issuebuilder.builder.front_matter import ContentsEntry, contents_page
from issuebuilder.settings.models import IssueSettings, JournalSettings, LayoutSettings


def test_contents_page_preserves_malayalam_title_and_page_number(tmp_path):
    journal = JournalSettings(title="മലയാളം ജേർണൽ")
    issue = IssueSettings(volume=2, number=4, month="May", year=2026)
    layout = LayoutSettings.for_page_size("A5")
    layout.script_fonts["Malayalam"] = "Manjari"
    entry = ContentsEntry(
        article_id="article-1",
        kind="Research article",
        title="കേരളത്തിലെ ഭാഷയും സംസ്കാരവും",
        authors="അനു നായർ",
        page="37",
    )

    page = contents_page(journal, issue, layout, [entry])
    contents_paragraph = next(p for p in page.doc.paragraphs if "കേരളത്തിലെ" in p.text)
    font_element = contents_paragraph.runs[0]._element.rPr.rFonts
    assert font_element.get(qn("w:cs")) == "Manjari"
    assert contents_paragraph.text.endswith("\t37")

    target = tmp_path / "contents.docx"
    page.save(target)
    reopened = Document(target)
    output = "\n".join(p.text for p in reopened.paragraphs)
    assert entry.title in output
    assert entry.authors in output
    assert "37" in output
