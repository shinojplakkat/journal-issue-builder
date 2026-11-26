"""Spine width and cover wrap size (blueprint section 6.1 and M9).

All values are in millimetres.
"""

import math
from dataclasses import dataclass

from ..settings.defaults import PAPER_SIZES_MM, PhysicalSettings


def sheet_count(interior_pages: int) -> int:
    """Physical sheets in the book block. One sheet carries two pages."""
    if interior_pages < 0:
        raise ValueError("Page count cannot be negative.")
    return math.ceil(interior_pages / 2)


def spine_width_mm(
    interior_pages: int,
    paper_thickness_mm: float = 0.1,
    glue_allowance_mm: float = 0.5,
    measured_stack_mm: float | None = None,
) -> float:
    """Spine width = sheets x paper thickness + glue allowance.

    If the editor has measured the real stack of printed pages, that
    measurement replaces the calculated paper thickness.
    """
    if measured_stack_mm is not None:
        block = measured_stack_mm
    else:
        block = sheet_count(interior_pages) * paper_thickness_mm
    # Rounded to 0.01 mm to hide floating-point noise such as 4.500000001.
    return round(block + glue_allowance_mm, 2)


@dataclass
class WrapSize:
    page_width_mm: float
    page_height_mm: float
    spine_mm: float
    bleed_mm: float
    width_mm: float
    height_mm: float
    spine_text_allowed: bool  # False means: leave the spine blank and warn

    def file_label(self) -> str:
        """Short text for the cover file name, e.g. 'wrap_302.5x216mm_spine4.5mm'."""
        return f"wrap_{self.width_mm:g}x{self.height_mm:g}mm_spine{self.spine_mm:g}mm"


def wrap_size(
    page_size: str,
    interior_pages: int,
    settings: PhysicalSettings | None = None,
    trimmed: bool = True,
    measured_stack_mm: float | None = None,
) -> WrapSize:
    """Flat glue-binding cover: back cover | spine | front cover.

    Bleed is added on all four sides only when the cover will be trimmed.
    """
    settings = settings or PhysicalSettings()
    page_w, page_h = PAPER_SIZES_MM[page_size]
    spine = spine_width_mm(
        interior_pages,
        settings.paper_thickness_mm,
        settings.glue_allowance_mm,
        measured_stack_mm,
    )
    bleed = settings.bleed_mm if trimmed else 0.0
    return WrapSize(
        page_width_mm=page_w,
        page_height_mm=page_h,
        spine_mm=spine,
        bleed_mm=bleed,
        width_mm=round(2 * page_w + spine + 2 * bleed, 2),
        height_mm=round(page_h + 2 * bleed, 2),
        spine_text_allowed=spine >= settings.min_spine_for_text_mm,
    )


def fits_on_sheet(wrap: WrapSize, sheet: str = "A3") -> bool:
    """True if the wrap fits on the sheet in landscape orientation.

    An A5 wrap fits on A3; an A4 wrap does not, so the software must offer
    separate front and back cover pages instead (blueprint M9).
    """
    short, long = PAPER_SIZES_MM[sheet]
    return wrap.width_mm <= long and wrap.height_mm <= short
