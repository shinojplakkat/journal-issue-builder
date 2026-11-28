"""Calibration sheet (blueprint M10): checks printer scale, margins and duplex flip.

Two pages. Print double-sided at 100%, then:
- the ruler must measure exactly 100 mm (if not, the printer is scaling);
- the frame shows the unprintable edge set in the settings;
- the arrow on the back must point the same way as on the front when the
  sheet is held to the light; if it is upside down, change the flip edge.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import Color, black
from reportlab.pdfgen import canvas

from ..pdfops.inspect import PT_PER_MM
from ..pdfops.stamp import SANS, SANS_BOLD, register_fonts
from ..settings.defaults import PAPER_SIZES_MM


def _mm(v: float) -> float:
    return v * PT_PER_MM


def calibration_sheet(paper: str, target: Path, unprintable_edge_mm: float = 5, landscape: bool = False,
                      duplex: bool = True, flip_edge: str = "short") -> Path:
    register_fonts()
    w, h = PAPER_SIZES_MM[paper]
    if landscape:
        w, h = h, w
    c = canvas.Canvas(str(target), pagesize=(_mm(w), _mm(h)))
    for side in ("FRONT", "BACK"):
        edge = unprintable_edge_mm
        c.setStrokeColor(Color(0.6, 0.6, 0.6))
        c.setDash(3, 2)
        c.rect(_mm(edge), _mm(edge), _mm(w - 2 * edge), _mm(h - 2 * edge))
        c.setDash()
        c.setStrokeColor(black)
        c.setFillColor(black)
        c.setFont(SANS_BOLD, 14)
        c.drawCentredString(_mm(w / 2), _mm(h - edge - 12), f"Calibration sheet {paper}"
                            f"{' landscape' if landscape else ''} — {side}")
        c.setFont(SANS, 8)
        mode = f"duplex, flip {flip_edge} edge" if duplex else "single-sided; print each page separately"
        c.drawCentredString(_mm(w / 2), _mm(h - edge - 18),
                            f"Dashed frame = {edge:g} mm unprintable edge. Print at 100% (Actual size), {mode}.")
        # 100 mm rulers, horizontal and vertical
        x0, y0 = max((w - 100) / 2, edge + 32), h * 0.72
        _ruler(c, x0, y0, horizontal=True)
        _ruler(c, edge + 22, (h - 100) / 2 - 10, horizontal=False)
        c.setFont(SANS, 8)
        c.drawCentredString(_mm(w / 2), _mm(y0 + 5), "Both rulers must measure exactly 100 mm")
        # Arrow pointing to the top edge
        ax, ay = w / 2 + 10, h * 0.22
        c.setLineWidth(2)
        c.line(_mm(ax), _mm(ay), _mm(ax), _mm(ay + 30))
        path = c.beginPath()
        path.moveTo(_mm(ax - 5), _mm(ay + 24))
        path.lineTo(_mm(ax), _mm(ay + 32))
        path.lineTo(_mm(ax + 5), _mm(ay + 24))
        path.close()
        c.drawPath(path, fill=1)
        c.setLineWidth(1)
        c.setFont(SANS_BOLD, 10)
        c.drawCentredString(_mm(ax), _mm(ay - 6), "TOP")
        c.setFont(SANS, 8)
        if side == "BACK" and duplex:
            c.drawCentredString(_mm(w / 2), _mm(edge + 14),
                                "Hold the sheet to the light: this arrow must lie over the arrow on the front.")
            c.drawCentredString(_mm(w / 2), _mm(edge + 9),
                                f"If it points the other way, change the duplex flip edge ({flip_edge}) in the printer.")
        # Corner marks, 10 mm from each edge
        for cx in (10, w - 10):
            for cy in (10, h - 10):
                c.line(_mm(cx - 3), _mm(cy), _mm(cx + 3), _mm(cy))
                c.line(_mm(cx), _mm(cy - 3), _mm(cx), _mm(cy + 3))
        c.drawString(_mm(12), _mm(12), "10 mm from edges")
        c.showPage()
    c.save()
    return target


def _ruler(c: canvas.Canvas, x_mm: float, y_mm: float, horizontal: bool) -> None:
    c.setLineWidth(0.6)
    if horizontal:
        c.line(_mm(x_mm), _mm(y_mm), _mm(x_mm + 100), _mm(y_mm))
    else:
        c.line(_mm(x_mm), _mm(y_mm), _mm(x_mm), _mm(y_mm + 100))
    c.setLineWidth(0.3)
    c.setFont(SANS, 6)
    for k in range(101):
        length = 5 if k % 10 == 0 else (3 if k % 5 == 0 else 1.5)
        if horizontal:
            c.line(_mm(x_mm + k), _mm(y_mm), _mm(x_mm + k), _mm(y_mm - length))
            if k % 10 == 0:
                c.drawCentredString(_mm(x_mm + k), _mm(y_mm - 8), str(k))
        else:
            c.line(_mm(x_mm), _mm(y_mm + k), _mm(x_mm - length), _mm(y_mm + k))
            if k % 10 == 0:
                c.drawRightString(_mm(x_mm - 6), _mm(y_mm + k - 1), str(k))
