"""Joining pages from many PDFs into one, with blank pages where needed."""

from __future__ import annotations

from pathlib import Path

import pikepdf
from pikepdf import Pdf

from .pages import mm


class PageSource:
    """Keeps each source PDF open once while pages are copied from it."""

    def __init__(self):
        self._open: dict[Path, Pdf] = {}

    def page(self, path: Path, index: int) -> pikepdf.Page:
        if path not in self._open:
            self._open[path] = Pdf.open(path)
        return self._open[path].pages[index]

    def keep(self, pdf: Pdf) -> Pdf:
        """Keep another opened PDF alive until close()."""
        self._open[Path(f"<kept {len(self._open)}>")] = pdf
        return pdf

    def open(self, path: Path) -> Pdf:
        return self.keep(Pdf.open(path))

    def close(self) -> None:
        for pdf in self._open.values():
            pdf.close()
        self._open.clear()


def assemble(items: list[tuple[Path | None, int]], width_mm: float, height_mm: float) -> tuple[Pdf, PageSource]:
    """Make one PDF from (source, page index) pairs; a None source is a blank page.

    The caller must close the returned PageSource after saving the PDF,
    because pikepdf reads page content lazily from the open sources.
    """
    out = Pdf.new()
    sources = PageSource()
    for source, index in items:
        if source is None:
            out.add_blank_page(page_size=(mm(width_mm), mm(height_mm)))
        else:
            out.pages.append(sources.page(source, index))
    return out, sources


def concatenate(files: list[Path], target: Path) -> None:
    out = Pdf.new()
    opened = [Pdf.open(f) for f in files]
    try:
        for pdf in opened:
            out.pages.extend(pdf.pages)
        out.save(target)
    finally:
        for pdf in opened:
            pdf.close()
