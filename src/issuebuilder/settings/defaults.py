"""Default settings (blueprint section 7).

Every number here is a starting value, not a constant. The editor can change
them later in the settings screen. All lengths are in millimetres.
"""

from dataclasses import dataclass


@dataclass
class PhysicalSettings:
    """Blueprint section 7.3. Measure the real paper and printer, then edit."""

    paper_thickness_mm: float = 0.1       # one sheet of 80 gsm paper
    glue_allowance_mm: float = 0.5
    bleed_mm: float = 3.0
    unprintable_edge_mm: float = 5.0
    gutter_staple_mm: float = 5.0
    gutter_glue_mm: float = 12.0
    min_spine_for_text_mm: float = 5.0
    abstract_word_limit: int = 250
    min_scaled_body_pt: float = 9.0
    min_image_dpi: int = 300
    stapled_page_warning: int = 60


# Page and sheet sizes as (width, height) in portrait orientation.
PAPER_SIZES_MM = {
    "A5": (148.0, 210.0),
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
}
