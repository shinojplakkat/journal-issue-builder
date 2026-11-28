"""Print files (blueprint M10): glue mode in page order, staple mode imposed.

Interior is shifted for the binding gutter and, when Ghostscript is present,
converted to grayscale.
"""

from __future__ import annotations

from pathlib import Path

from ..assembler.issue import Plan
from ..pdfops import grayscale, imposition, merge
from ..pdfops.pages import shift_pdf_for_gutter
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
        shift_pdf_for_gutter(pdf, gutter)

    folder.mkdir(parents=True, exist_ok=True)
    size = layout.page_size
    paper = size if mode == GLUE else SHEET_FOR_BOOKLET.get(size, "A4")
    profile = printing.paper_profiles.get(paper, {})
    duplex = profile.get("duplex", True)
    flip_edge = profile.get("flip_edge", "long" if paper == "A5" else "short")
    color_mode = profile.get("color_mode", "grayscale" if printing.grayscale else "color")
    if mode == GLUE:
        target = folder / f"{name}_print_interior_glue_{size}_{total}pages.pdf"
        merge.save(pdf, target)
        notes.append(f"Glue mode: {total} pages in reading order on {paper}, "
                     f"{'duplex' if duplex else 'single-sided'} ({flip_edge}-edge flip), 100% scale; "
                     f"{color_mode}, even count, {gutter:g} mm gutter.")
    else:
        sheet_name = SHEET_FOR_BOOKLET.get(size, "A4")
        target = folder / f"{name}_print_interior_staple_{size}-booklet-on-{sheet_name}_{total}pages.pdf"
        imposed = imposition.impose_pdf(pdf, size, PAPER_SIZES_MM)
        try:
            merge.save(imposed, target)
        finally:
            imposed.close()
        notes.append(f"Staple mode: {total} pages imposed on {total // 4} {paper} sheets "
                     f"({total // 2} sides). Print {'duplex' if duplex else 'single-sided'} "
                     f"({flip_edge}-edge flip), at 100% scale; {color_mode}. "
                     "Fold the stack in the middle and staple on the fold.")
        if total > printing.stapled_page_warning:
            notes.append(f"Warning: {total} pages may be too thick for an ordinary stapler "
                         f"(limit set to {printing.stapled_page_warning}).")
    interior.close()

    if color_mode == "grayscale":
        gray = target.with_name(target.stem + "_grayscale.pdf")
        ok, message = grayscale.convert(target, gray)
        if ok:
            target.unlink()
            gray.rename(target)
            notes.append("Interior converted to grayscale.")
        else:
            notes.append(message)
    return [target], notes
