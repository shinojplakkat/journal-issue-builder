"""Reading Word (DOCX) files: cleaning a copy, and collecting paragraph features.

Only python-docx and lxml are used here (both already needed by python-docx).
"""

from __future__ import annotations

import statistics
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


@dataclass
class Paragraph:
    """What the analyzer needs to know about one paragraph."""

    i: int                 # index in document.paragraphs
    text: str
    style: str = ""
    size: float = 0.0      # main font size in points (0 = unknown)
    bold: bool = False     # all visible text is bold
    italic: bool = False   # all visible text is italic
    centred: bool = False
    has_superscript: bool = False
    words: int = 0


@dataclass
class WordInfo:
    paragraphs: list[Paragraph] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)      # tables, images, footnotes, equations
    body_size: float = 0.0                             # most common font size
    tracked_changes: bool = False
    comments: bool = False


# --------------------------------------------------------------------------- cleaning

def _accept_changes(root) -> tuple[bool, bool]:
    """Accept tracked changes and drop comments, in one XML tree. Returns (had_changes, had_comments)."""
    changed = False
    # Deleted text and moved-away text disappear.
    for tag in ("del", "moveFrom"):
        for el in list(root.iter(f"{{{W}}}{tag}")):
            el.getparent().remove(el)
            changed = True
    # Inserted and moved-in text stays, without its change wrapper.
    for tag in ("ins", "moveTo"):
        for el in list(root.iter(f"{{{W}}}{tag}")):
            parent = el.getparent()
            if parent is None:
                continue
            # A w:ins inside run properties only marks a changed paragraph mark.
            if parent.tag in (f"{{{W}}}rPr", f"{{{W}}}pPr"):
                parent.remove(el)
            else:
                index = parent.index(el)
                for child in list(el):
                    parent.insert(index, child)
                    index += 1
                parent.remove(el)
            changed = True
    # Records of formatting changes.
    for tag in ("rPrChange", "pPrChange", "sectPrChange", "tblPrChange", "trPrChange",
                "tcPrChange", "numberingChange", "moveFromRangeStart", "moveFromRangeEnd",
                "moveToRangeStart", "moveToRangeEnd"):
        for el in list(root.iter(f"{{{W}}}{tag}")):
            el.getparent().remove(el)
            changed = True
    comments = False
    for tag in ("commentRangeStart", "commentRangeEnd", "commentReference"):
        for el in list(root.iter(f"{{{W}}}{tag}")):
            parent = el.getparent()
            # A comment reference sits alone in its own run; remove that run.
            if tag == "commentReference" and parent.tag == f"{{{W}}}r":
                grand = parent.getparent()
                if grand is not None:
                    grand.remove(parent)
                    comments = True
                    continue
            parent.remove(el)
            comments = True
    return changed, comments


def clean_copy(source: Path, target: Path) -> tuple[bool, bool]:
    """Save a copy with all tracked changes accepted and comments removed (M3).

    Returns (tracked_changes_found, comments_found) so the editor can be warned.
    """
    document = Document(str(source))
    changed, comments = _accept_changes(document.element)
    for part in document.part.package.iter_parts():
        name = str(part.partname)
        if name.endswith(("footnotes.xml", "endnotes.xml")) or "/header" in name or "/footer" in name:
            element = getattr(part, "element", None) or getattr(part, "_element", None)
            if element is not None:
                c, k = _accept_changes(element)
                changed, comments = changed or c, comments or k
    target.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(target))
    if comments:
        _remove_comments_part(target)
    return changed, comments


def _remove_comments_part(path: Path) -> None:
    """Comments are also stored in word/comments.xml; replace it with an empty list."""
    with zipfile.ZipFile(path) as zin:
        items = [(info, zin.read(info.filename)) for info in zin.infolist()]
    empty = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             b'<w:comments xmlns:w="' + W.encode() + b'"/>')
    tmp = path.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for info, data in items:
            if info.filename == "word/comments.xml":
                data = empty
            zout.writestr(info, data)
    tmp.replace(path)


# --------------------------------------------------------------------------- reading

def _run_size(run, paragraph) -> float:
    if run.font.size:
        return run.font.size.pt
    style = paragraph.style
    while style is not None:
        if style.font is not None and style.font.size:
            return style.font.size.pt
        style = style.base_style
    return 0.0


def read_paragraphs(path: Path) -> WordInfo:
    """Collect features of every non-empty paragraph, and flag risky content."""
    document = Document(str(path))
    info = WordInfo()
    sizes: list[float] = []
    default_size = 0.0
    try:
        normal = document.styles["Normal"]
        if normal.font.size:
            default_size = normal.font.size.pt
    except KeyError:
        pass

    for i, p in enumerate(document.paragraphs):
        text = p.text.strip()
        if not text:
            continue
        runs = [r for r in p.runs if r.text.strip()]
        run_sizes = [_run_size(r, p) or default_size for r in runs]
        size = max(run_sizes) if run_sizes else default_size
        para = Paragraph(
            i=i,
            text=text,
            style=p.style.name if p.style is not None else "",
            size=size,
            bold=bool(runs) and all(r.bold or (r.bold is None and p.style is not None and p.style.font.bold) for r in runs),
            italic=bool(runs) and all(r.italic or (r.italic is None and p.style is not None and p.style.font.italic) for r in runs),
            centred=_is_centred(p),
            has_superscript=any(r.font.superscript for r in p.runs),
            words=len(text.split()),
        )
        info.paragraphs.append(para)
        # Weight sizes by words so the body size wins over many short lines.
        for s in run_sizes:
            if s:
                sizes.extend([s] * max(1, para.words // max(1, len(run_sizes))))

    info.body_size = statistics.mode(sizes) if sizes else (default_size or 12.0)

    body = document.element.body
    if document.tables:
        info.flags.append("tables")
    if list(body.iter(qn("w:drawing"))) or list(body.iter(qn("w:pict"))):
        info.flags.append("images")
    if list(body.iter(qn("w:footnoteReference"))) or list(body.iter(qn("w:endnoteReference"))):
        info.flags.append("footnotes")
    if list(body.iter(f"{{{M}}}oMath")):
        info.flags.append("equations")
    return info


def _is_centred(p) -> bool:
    alignment = p.alignment
    if alignment is None and p.style is not None:
        alignment = p.style.paragraph_format.alignment
    return alignment is not None and int(alignment) == 1  # WD_ALIGN_PARAGRAPH.CENTER


def superscript_markers(path: Path, index: int) -> list[str]:
    """Superscript texts in one paragraph (author and affiliation markers such as 1, 2, *)."""
    document = Document(str(path))
    p = document.paragraphs[index]
    return [r.text.strip() for r in p.runs if r.font.superscript and r.text.strip()]

