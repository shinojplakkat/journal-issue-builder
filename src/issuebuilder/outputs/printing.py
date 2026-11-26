"""Print files (blueprint M10): glue mode in page order, staple mode imposed.

Interior is shifted for the binding gutter and, when Ghostscript is present,
converted to grayscale.
"""

from __future__ import annotations

from pathlib import Path

from pikepdf import Pdf, Rectangle

from ..assembler.issue import Plan
from ..pdfops import grayscale
from ..pdfops.imposition import booklet_sheets
from ..pdfops.pages import mm, shift_page
from ..settings.defaults import PAPER_SIZES_MM
from ..settings.models import GLUE, IssueSettings, JournalSettings
from .interior import build_interior

SHEET_FOR_BOOKLET = {"A5": "A4", "A4": "A3"}


def print_interior(plan: Plan, journal: JournalSettings, issue: IssueSettings, folder: Path,
                   name: str, *, proof: bool) -> tuple[list[Path], list[str]]:
    """Make the interior print file for the issue's binding mode. Returns (files, notes)."""
    notes: list[str] = []
    printing, layout = issue.printing, issue.layout
    mode = printing.binding_mode
    interior = build_interior(plan, journal, issue, plan.pages, proof=proof)
    pdf = interior.pdf
    total = len(pdf.pages)

    gutter = printing.gutter_glue_mm if mode == GLUE else printing.gutter_staple_mm
    if gutter:
        # Extra space on the binding side: recto content moves right, verso left.
        for number, page in enumerate(pdf.pages, 1):
            shift_page(page, mm(gutter / 2) * (1 if number % 2 == 1 else -1))

    folder.mkdir(parents=True, exist_ok=True)
    size = layout.page_size
    if mode == GLUE:
        target = folder / f"{name}_print_interior_glue_{size}_{total}pages.pdf"
        pdf.save(target)
        notes.append(f"Glue mode: {total} pages in reading order on {size}, printed double-sided "
                     f"(even count, gutter {gutter:g} mm).")
    else:
        sheet_name = SHEET_FOR_BOOKLET.get(size, "A4")
        target = folder / f"{name}_print_interior_staple_{size}-booklet-on-{sheet_name}_{total}pages.pdf"
        _impose(pdf, size).save(target)
        notes.append(f"Staple mode: {total} pages imposed on {total // 4} {sheet_name} sheets "
                     f"({total // 2} sides). Print double-sided, flip on the SHORT edge, at 100%; "
                     "fold the stack in the middle and staple on the fold.")
        if total > printing.stapled_page_warning:
            notes.append(f"Warning: {total} pages may be too thick for an ordinary stapler "
                         f"(limit set to {printing.stapled_page_warning}).")
    interior.close()

    if printing.grayscale:
        gray = target.with_name(target.stem + "_grayscale.pdf")
        ok, message = grayscale.convert(target, gray)
        if ok:
            target.unlink()
            gray.rename(target)
            notes.append("Interior converted to grayscale.")
        else:
            notes.append(message)
    return [target], notes


def _impose(interior: Pdf, size: str) -> Pdf:
    width, height = PAPER_SIZES_MM[size]
    sheet_w, sheet_h = 2 * width, height
    left = Rectangle(0, 0, mm(width), mm(height))
    right = Rectangle(mm(width), 0, mm(2 * width), mm(height))
    out = Pdf.new()
    for sheet in booklet_sheets(len(interior.pages)):
        for side in (sheet.front, sheet.back):
            out.add_blank_page(page_size=(mm(sheet_w), mm(sheet_h)))
            page = out.pages[-1]
            page.add_overlay(interior.pages[side.left - 1], left)
            page.add_overlay(interior.pages[side.right - 1], right)
    return out
