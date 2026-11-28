"""Low-level PDF page composition used by covers and print outputs."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import pikepdf
from pikepdf import Pdf, Rectangle


@dataclass
class Layer:
    source: Path | bytes
    page: int = 0
    rect: tuple[float, float, float, float] | None = None
    shrink: bool = False
    expand: bool = False


def _open(source: Path | bytes) -> Pdf:
    return Pdf.open(io.BytesIO(source)) if isinstance(source, bytes) else Pdf.open(source)


def overlay_page(source: Path, layers: list[Layer], target: Path) -> None:
    """Overlay one or more PDF layers onto the first page of a source PDF."""
    opened: list[Pdf] = []
    try:
        base = Pdf.open(source)
        opened.append(base)
        page = base.pages[0]
        for layer in layers:
            document = _open(layer.source)
            opened.append(document)
            if layer.rect is None:
                page.add_overlay(document.pages[layer.page])
            else:
                page.add_overlay(document.pages[layer.page], Rectangle(*layer.rect),
                                 shrink=layer.shrink, expand=layer.expand)
        target.parent.mkdir(parents=True, exist_ok=True)
        base.save(target)
    finally:
        for pdf in opened:
            pdf.close()


def compose_sheet(width_pt: float, height_pt: float, layers: list[Layer], target: Path) -> None:
    """Place cover or booklet layers onto a single blank PDF sheet."""
    opened: list[Pdf] = []
    try:
        sheet = Pdf.new()
        sheet.add_blank_page(page_size=(width_pt, height_pt))
        for layer in layers:
            source = _open(layer.source)
            opened.append(source)
            page = sheet.pages[0]
            if layer.rect is None:
                page.add_overlay(source.pages[layer.page])
            else:
                page.add_overlay(source.pages[layer.page], Rectangle(*layer.rect),
                                 shrink=layer.shrink, expand=layer.expand)
        target.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(target)
    finally:
        for pdf in opened:
            pdf.close()
