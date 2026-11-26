"""Looking inside PDFs: can it be opened, how many pages, what text and sizes.

All PDF work lives in pdfops (blueprint rule 8). pikepdf handles the file
structure and pdfplumber reads text with its size and position.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pikepdf

PT_PER_MM = 72 / 25.4


@dataclass
class Line:
    page: int
    text: str
    size: float
    top: float      # distance from the top of the page in points
    x0: float
    x1: float
    bottom: float


def open_status(path: Path) -> str:
    """'ok', 'encrypted', 'corrupt' or 'empty'."""
    try:
        with pikepdf.open(path) as pdf:
            return "ok" if len(pdf.pages) else "empty"
    except pikepdf.PasswordError:
        return "encrypted"
    except Exception:
        return "corrupt"


def page_size_mm(page: pikepdf.Page) -> tuple[float, float]:
    box = page.cropbox if "/CropBox" in page.obj else page.mediabox
    width = float(box[2]) - float(box[0])
    height = float(box[3]) - float(box[1])
    rotate = int(page.obj.get("/Rotate", 0)) % 180
    if rotate:
        width, height = height, width
    return round(width / PT_PER_MM, 1), round(height / PT_PER_MM, 1)


def page_count(path: Path) -> int:
    with pikepdf.open(path) as pdf:
        return len(pdf.pages)


def page_count_and_size(path: Path) -> tuple[int, tuple[float, float]]:
    with pikepdf.open(path) as pdf:
        return len(pdf.pages), page_size_mm(pdf.pages[0])


def text_lines(path: Path, max_pages: int | None = None, pages: list[int] | None = None) -> list[Line]:
    """Text lines in reading order, each with its main font size."""
    import pdfplumber  # imported here: it is slow to load and only needed for this

    lines: list[Line] = []
    with pdfplumber.open(path) as pdf:
        indexes = pages if pages is not None else range(min(len(pdf.pages), max_pages or len(pdf.pages)))
        for index in indexes:
            page = pdf.pages[index]
            words = page.extract_words(extra_attrs=["size"], keep_blank_chars=False, use_text_flow=True)
            current: list[dict] = []
            for word in words:
                if current and abs(word["top"] - current[-1]["top"]) > max(2.0, word["size"] * 0.4):
                    lines.append(_make_line(index, current))
                    current = []
                current.append(word)
            if current:
                lines.append(_make_line(index, current))
    return lines


def _make_line(page: int, words: list[dict]) -> Line:
    sizes = [w["size"] for w in words]
    return Line(
        page=page,
        text=" ".join(w["text"] for w in words),
        size=max(set(sizes), key=sizes.count),
        top=min(w["top"] for w in words),
        x0=min(w["x0"] for w in words),
        x1=max(w["x1"] for w in words),
        bottom=max(w["bottom"] for w in words),
    )


def find_words(path: Path, page_index: int) -> list[dict]:
    """Words on one page with positions (points, origin top-left)."""
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        page = pdf.pages[page_index]
        return page.extract_words(), float(page.height)


def image_resolutions(path: Path, max_pages: int | None = None) -> list[tuple[int, float]]:
    """(page number, lowest effective dpi) for pages carrying images.

    Effective dpi = image pixels / printed size in inches.
    """
    import pdfplumber

    found = []
    with pdfplumber.open(path) as pdf:
        for index, page in enumerate(pdf.pages[: max_pages or len(pdf.pages)]):
            lowest = None
            for image in page.images:
                width_in = (image["x1"] - image["x0"]) / 72
                pixels = image.get("srcsize", (0, 0))[0]
                if width_in > 0.3 and pixels:
                    dpi = pixels / width_in
                    lowest = dpi if lowest is None else min(lowest, dpi)
            if lowest is not None:
                found.append((index + 1, round(lowest)))
    return found
