"""Regression coverage for accepting Word edits without touching submissions."""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from issuebuilder.importers.docx_reader import clean_copy


def test_clean_copy_accepts_edits_removes_comments_and_preserves_source(tmp_path: Path):
    source = tmp_path / "submitted.docx"
    target = tmp_path / "working" / "clean.docx"
    document = Document()
    paragraph = document.add_paragraph()
    paragraph.add_run("Keep ")

    deleted = OxmlElement("w:del")
    deleted_run = OxmlElement("w:r")
    deleted_text = OxmlElement("w:delText")
    deleted_text.text = "rejected "
    deleted_run.append(deleted_text)
    deleted.append(deleted_run)
    paragraph._p.append(deleted)

    inserted = OxmlElement("w:ins")
    inserted_run = OxmlElement("w:r")
    inserted_text = OxmlElement("w:t")
    inserted_text.text = "accepted"
    inserted_run.append(inserted_text)
    inserted.append(inserted_run)
    paragraph._p.append(inserted)

    paragraph._p.append(OxmlElement("w:commentRangeStart"))
    comment_run = OxmlElement("w:r")
    comment_reference = OxmlElement("w:commentReference")
    comment_run.append(comment_reference)
    paragraph._p.append(comment_run)
    paragraph._p.append(OxmlElement("w:commentRangeEnd"))
    document.save(source)
    # Word stores comment bodies in a separate package part as well as range markers.
    with zipfile.ZipFile(source, "a") as package:
        package.writestr(
            "word/comments.xml",
            b'<?xml version="1.0"?><w:comments '
            b'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            b'<w:comment w:id="0"><w:p><w:r><w:t>Private comment</w:t></w:r></w:p>'
            b"</w:comment></w:comments>",
        )
    submitted_bytes = source.read_bytes()

    changed, comments = clean_copy(source, target)

    assert changed and comments
    assert source.read_bytes() == submitted_bytes
    assert Document(target).paragraphs[0].text == "Keep accepted"
    with zipfile.ZipFile(target) as package:
        if "word/comments.xml" in package.namelist():
            cleaned_comments = ET.fromstring(package.read("word/comments.xml"))
            assert list(cleaned_comments) == []
        cleaned_document = ET.fromstring(package.read("word/document.xml"))
    assert not any(node.tag.rsplit("}", 1)[-1] in {
        "del", "ins", "commentRangeStart", "commentRangeEnd", "commentReference"
    } for node in cleaned_document.iter())
