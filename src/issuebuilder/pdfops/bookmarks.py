"""Bookmarks, page labels, clickable links and document metadata (blueprint M11)."""

from __future__ import annotations

from datetime import datetime, timezone

import pikepdf
from pikepdf import Array, Dictionary, Name, OutlineItem, Pdf, String


def add_bookmarks(pdf: Pdf, items: list[tuple[str, int, list[tuple[str, int]]]]) -> None:
    """items: [(title, page index, [(child title, page index), ...]), ...]."""
    with pdf.open_outline() as outline:
        outline.root.clear()
        for title, page, children in items:
            node = OutlineItem(title, page)
            for child_title, child_page in children:
                node.children.append(OutlineItem(child_title, child_page))
            outline.root.append(node)


def set_page_labels(pdf: Pdf, labels: list[tuple[str, int | None, str]]) -> None:
    """Give each page the number a reader sees in the PDF viewer (blueprint M11).

    labels: one (style, number, prefix) per page; style "r" (roman), "D"
    (arabic) or "" (prefix only, e.g. "Cover"). A new label range starts
    whenever the sequence breaks, e.g. after a removed blank page.
    """
    nums = Array()
    previous = None
    for index, (style, number, prefix) in enumerate(labels):
        continues = (previous is not None and previous[0] == style and previous[2] == prefix
                     and style and number is not None and previous[1] is not None and number == previous[1] + 1)
        if not continues:
            entry = Dictionary()
            if style:
                entry.S = Name("/" + style)
                entry.St = int(number or 1)
            if prefix:
                entry.P = String(prefix)
            nums.append(index)
            nums.append(entry)
        previous = (style, number, prefix)
    pdf.Root.PageLabels = Dictionary(Nums=nums)


def add_link(pdf: Pdf, page_index: int, rect: tuple[float, float, float, float], *,
             target_page: int | None = None, uri: str | None = None) -> None:
    """Add an invisible clickable area to a page."""
    page = pdf.pages[page_index]
    annot = Dictionary(Type=Name.Annot, Subtype=Name.Link, Rect=Array([float(v) for v in rect]),
                       Border=Array([0, 0, 0]))
    if uri:
        annot.A = Dictionary(S=Name.URI, URI=String(uri))
    else:
        annot.Dest = Array([pdf.pages[target_page].obj, Name.Fit])
    if "/Annots" not in page.obj:
        page.obj.Annots = Array()
    page.obj.Annots.append(pdf.make_indirect(annot))


def set_metadata(pdf: Pdf, title: str, author: str, subject: str, keywords: str) -> None:
    pdf.docinfo[Name.Title] = String(title)
    pdf.docinfo[Name.Author] = String(author)
    pdf.docinfo[Name.Subject] = String(subject)
    pdf.docinfo[Name.Keywords] = String(keywords)
    pdf.docinfo[Name.Creator] = String("Journal Issue Builder")
    pdf.docinfo[Name.CreationDate] = String(datetime.now(timezone.utc).strftime("D:%Y%m%d%H%M%SZ"))
    with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
        meta["dc:title"] = title
        meta["dc:creator"] = [a.strip() for a in author.split(";") if a.strip()] or [author]
        meta["dc:description"] = subject
        meta["pdf:Keywords"] = keywords
    # Open with bookmarks visible and show page labels.
    pdf.Root.PageMode = Name.UseOutlines


def update_metadata_file(path, title: str, author: str, subject: str, keywords: str) -> None:
    """Update document metadata at the PDF boundary and save the file."""
    from pathlib import Path

    target = Path(path)
    with Pdf.open(target, allow_overwriting_input=True) as pdf:
        set_metadata(pdf, title, author, subject, keywords)
        pdf.save(target)


__all__ = ["add_bookmarks", "set_page_labels", "add_link", "set_metadata", "pikepdf"]
