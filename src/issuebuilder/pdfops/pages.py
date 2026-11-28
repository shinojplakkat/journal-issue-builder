"""Page-level PDF work: resizing, blank pages, shifting for the gutter."""

from __future__ import annotations

from pathlib import Path

import pikepdf
from pikepdf import Pdf, Rectangle

from .inspect import PT_PER_MM, page_size_mm


def mm(value: float) -> float:
    return value * PT_PER_MM


def fit_to_size(source: Path, target: Path, width_mm: float, height_mm: float) -> int:
    """Copy a PDF so every page has the given size (blueprint M4b).

    Pages that already have the size are copied unchanged. Others are scaled
    to fit and centred; the proportions are kept, the text is never stretched.
    Returns the page count.
    """
    with Pdf.open(source) as src:
        out = Pdf.new()
        for page in src.pages:
            w, h = page_size_mm(page)
            if abs(w - width_mm) < 1.5 and abs(h - height_mm) < 1.5:
                out.pages.append(page)
                continue
            out.add_blank_page(page_size=(mm(width_mm), mm(height_mm)))
            scale = min(width_mm / w, height_mm / h)
            box_w, box_h = mm(w * scale), mm(h * scale)
            x = (mm(width_mm) - box_w) / 2
            y = (mm(height_mm) - box_h) / 2
            out.pages[-1].add_overlay(page, Rectangle(x, y, x + box_w, y + box_h))
        target.parent.mkdir(parents=True, exist_ok=True)
        out.save(target)
        return len(out.pages)


def scale_factor(source: Path, width_mm: float) -> float:
    """How much the pages of a PDF shrink when fitted to the given width."""
    with Pdf.open(source) as src:
        w, h = page_size_mm(src.pages[0])
    return min(1.0, width_mm / w) if w else 1.0


def shift_page(page: pikepdf.Page, dx_pt: float) -> None:
    """Move everything on a page sideways by dx points (for the binding gutter)."""
    if "/Contents" not in page.obj:
        return  # a blank page has nothing to move
    page.contents_coalesce()
    stream = page.obj.Contents
    stream.write(b"q 1 0 0 1 %.3f 0 cm\n" % dx_pt + stream.read_bytes() + b"\nQ\n")


def shift_pdf_for_gutter(pdf: Pdf, gutter_mm: float) -> None:
    """Shift odd and even pages away from a shared binding gutter."""
    for number, page in enumerate(pdf.pages, 1):
        shift_page(page, mm(gutter_mm / 2) * (1 if number % 2 == 1 else -1))
