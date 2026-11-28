"""Cover files (blueprint M9).

- front and back cover pages at the journal's page size (used in the
  electronic issue and in offprints)
- staple mode: one landscape sheet, back cover left, front cover right,
  fold mark in the middle, no spine
- glue mode: flat wrap back | spine | front with bleed, trim and fold marks,
  placed on an A3 sheet; for A4 journals (too wide for A3) separate pages
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.colors import Color, HexColor, black, white
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from docx.shared import RGBColor

from ..builder import front_matter as fm
from ..pdfops import compose, merge
from ..pdfops.compose import Layer
from ..pdfops.inspect import PT_PER_MM
from ..pdfops.stamp import SANS, SANS_BOLD, SERIF, printable, register_fonts
from ..settings.defaults import PAPER_SIZES_MM, PhysicalSettings
from ..settings.load_save import IssueFolder, JournalFolder
from ..settings.models import IssueSettings, JournalSettings
from .spine import WrapSize, fits_on_sheet, wrap_size


def _mm(v: float) -> float:
    return v * PT_PER_MM


@dataclass
class CoverPages:
    front: Path
    back: Path
    front_image: Path | None = None   # the uploaded pictures, used to fill the bleed exactly
    back_image: Path | None = None


def image_page(image: Path, target: Path, width_mm: float, height_mm: float) -> Path:
    """One page filled edge to edge with a picture (centred, cropped if the shape differs)."""
    c = canvas.Canvas(str(target), pagesize=(_mm(width_mm), _mm(height_mm)))
    reader = ImageReader(str(image))
    iw, ih = reader.getSize()
    w, h = _mm(width_mm), _mm(height_mm)
    scale = max(w / iw, h / ih)
    dw, dh = iw * scale, ih * scale
    c.drawImage(reader, (w - dw) / 2, (h - dh) / 2, dw, dh)
    c.showPage()
    c.save()
    return target


def _design_background(target: Path, width_mm: float, height_mm: float, color: str, pattern: str) -> Path:
    """Draw a selectable generated cover background."""
    w, h = _mm(width_mm), _mm(height_mm)
    c = canvas.Canvas(str(target), pagesize=(w, h))
    base = HexColor(color if color.startswith("#") else "#17324d")
    c.setFillColor(base)
    c.rect(0, 0, w, h, stroke=0, fill=1)
    # A quiet tint keeps patterns visible without competing with the cover text.
    tint = Color(min(1, base.red + .16), min(1, base.green + .16), min(1, base.blue + .16), alpha=.45)
    c.setStrokeColor(tint)
    c.setFillColor(tint)
    spacing = _mm(9)
    if pattern == "diagonal":
        c.setLineWidth(_mm(1.2))
        x = -h
        while x < w + h:
            c.line(x, 0, x + h, h)
            x += spacing * 2
    elif pattern == "dots":
        radius = _mm(1.2)
        x = spacing / 2
        while x < w:
            y = spacing / 2
            while y < h:
                c.circle(x, y, radius, stroke=0, fill=1)
                y += spacing
            x += spacing
    elif pattern == "grid":
        c.setLineWidth(_mm(.35))
        x = 0
        while x < w:
            c.line(x, 0, x, h)
            x += spacing
        y = 0
        while y < h:
            c.line(0, y, w, y)
            y += spacing
    c.showPage()
    c.save()
    return target


def _cover_band(width_mm: float, height_mm: float) -> bytes:
    """Add a translucent reading panel so white cover details stay legible over photos."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(_mm(width_mm), _mm(height_mm)))
    c.setFillColor(Color(0, 0, 0, alpha=.52))
    c.rect(0, _mm(height_mm * .14), _mm(width_mm), _mm(height_mm * .76), stroke=0, fill=1)
    c.showPage()
    c.save()
    return buffer.getvalue()


def _cover_text(journal: JournalSettings, issue: IssueSettings, layout, side: str):
    """Create a transparent, Unicode-capable text page using the existing Word renderer."""
    page = fm.Page(layout)
    _, height = PAPER_SIZES_MM[layout.page_size]
    white_text = RGBColor(255, 255, 255)
    page.para(journal.title, size=layout.title_pt + 7, bold=True,
              before=height * .29 * 2.83, after=9, colour=white_text)
    if issue.title:
        page.para(issue.title, size=layout.subtitle_pt + 2, italic=True, after=8, colour=white_text)
    page.para(f"Volume {issue.volume}  •  Issue {issue.number}  •  {issue.month} {issue.year}",
              size=layout.body_pt + 1, after=5, colour=white_text)
    if side == "front":
        for line in (journal.publisher, journal.website, journal.email):
            if line:
                page.para(line, size=layout.abstract_pt, after=2, colour=white_text)
        issn = "   ".join(x for x in (f"Print ISSN {journal.print_issn}" if journal.print_issn else "",
                                       f"Online ISSN {journal.e_issn}" if journal.e_issn else "") if x)
        if issn:
            page.para(issn, size=layout.abstract_pt, before=6, colour=white_text)
    else:
        if journal.aims_scope:
            page.para("Aims and Scope", size=layout.abstract_pt, bold=True,
                      before=5, after=2, colour=white_text)
            page.para(journal.aims_scope, size=layout.abstract_pt - 1, after=5, colour=white_text)
        issn = "   ".join(x for x in (f"Print ISSN {journal.print_issn}" if journal.print_issn else "",
                                       f"Online ISSN {journal.e_issn}" if journal.e_issn else "") if x)
        if issn:
            page.para(issn, size=layout.abstract_pt, before=4, colour=white_text)
        page.para(journal.publisher, size=layout.abstract_pt, before=8, colour=white_text)
        if journal.website:
            page.para(journal.website, size=layout.abstract_pt, colour=white_text)
        if journal.address:
            page.para(journal.address, size=layout.abstract_pt, colour=white_text)
        if journal.email:
            page.para(journal.email, size=layout.abstract_pt, colour=white_text)
    return page


def cover_pages(journal_folder: JournalFolder, issue_folder: IssueFolder, journal: JournalSettings,
                issue: IssueSettings) -> CoverPages:
    """Build image or designed covers, with issue details overlaid on both sides."""
    layout = issue.layout
    width, height = PAPER_SIZES_MM[layout.page_size]
    folder = issue_folder.work / "_cover"
    folder.mkdir(parents=True, exist_ok=True)
    text_pages = fm.render({"front_text": _cover_text(journal, issue, layout, "front"),
                            "back_text": _cover_text(journal, issue, layout, "back")}, folder)

    def build(side: str) -> Path:
        image_name = getattr(issue.cover, f"{side}_image")
        picture = issue_folder.assets / image_name if image_name else None
        if picture is not None and picture.is_file():
            background = image_page(picture, folder / f".{side}_background.pdf", width, height)
        else:
            background = _design_background(folder / f".{side}_background.pdf", width, height,
                                            getattr(issue.cover, f"{side}_background"),
                                            getattr(issue.cover, f"{side}_pattern"))
        target = folder / f"{side}.pdf"
        compose.overlay_page(background, [Layer(_cover_band(width, height)),
                                           Layer(text_pages[f"{side}_text"])], target)
        return target

    return CoverPages(build("front"), build("back"))


def physical(issue: IssueSettings) -> PhysicalSettings:
    p = issue.printing
    return PhysicalSettings(paper_thickness_mm=p.paper_thickness_mm, glue_allowance_mm=p.glue_allowance_mm,
                            bleed_mm=p.bleed_mm, unprintable_edge_mm=p.unprintable_edge_mm,
                            min_spine_for_text_mm=p.min_spine_for_text_mm)


def spine_text(journal: JournalSettings, issue: IssueSettings) -> str:
    if issue.cover.spine_text.strip():
        return issue.cover.spine_text.strip()
    return f"{journal.short_title or journal.title}   •   Vol. {issue.volume}, No. {issue.number}   •   {issue.year}"


def _marks_overlay(width: float, height: float, draw) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))
    register_fonts()
    draw(c)
    c.showPage()
    c.save()
    return buffer.getvalue()


def staple_cover(covers: CoverPages, issue: IssueSettings, target: Path) -> list[str]:
    """Back cover left, front cover right, on one landscape sheet (A4 for A5, A3 for A4)."""
    width, height = PAPER_SIZES_MM[issue.layout.page_size]
    sheet_w, sheet_h = 2 * width, height
    layers = [Layer(covers.back, rect=(0, 0, _mm(width), _mm(height))),
              Layer(covers.front, rect=(_mm(width), 0, _mm(2 * width), _mm(height)))]
    edge = issue.printing.unprintable_edge_mm

    def marks(c):
        if not issue.printing.crop_marks:
            return
        # Short fold ticks at top and bottom, inside the printable area.
        c.setStrokeColor(Color(0.5, 0.5, 0.5))
        c.setLineWidth(0.4)
        x = _mm(width)
        c.line(x, _mm(sheet_h - edge), x, _mm(sheet_h - edge - 4))
        c.line(x, _mm(edge), x, _mm(edge + 4))

    layers.append(Layer(_marks_overlay(_mm(sheet_w), _mm(sheet_h), marks)))
    compose.compose_sheet(_mm(sheet_w), _mm(sheet_h), layers, target)
    return ["Print the cover sheet at 100% (no 'fit to page'). The picture edges fall in the printer's "
            f"unprintable border ({edge:g} mm); trim or accept a thin white edge."]


def glue_cover(covers: CoverPages, journal: JournalSettings, issue: IssueSettings, interior_pages: int,
               folder: Path, name: str) -> tuple[list[Path], list[str], WrapSize]:
    """Flat wrap with spine for professional binding."""
    settings = physical(issue)
    measured = issue.printing.measured_stack_mm or None
    wrap = wrap_size(issue.layout.page_size, interior_pages, settings, trimmed=True, measured_stack_mm=measured)
    notes: list[str] = []
    page_w, page_h = wrap.page_width_mm, wrap.page_height_mm
    bleed, spine = wrap.bleed_mm, wrap.spine_mm
    text = spine_text(journal, issue)
    if not wrap.spine_text_allowed:
        notes.append(f"Spine is {spine:g} mm, below {settings.min_spine_for_text_mm:g} mm: spine left blank.")
    elif not printable(text):
        notes.append("Spine text uses letters the cover fonts cannot draw; type an English spine text in Cover settings.")

    files: list[Path] = []
    if fits_on_sheet(wrap, "A3"):
        sheet_w, sheet_h = PAPER_SIZES_MM["A3"][1], PAPER_SIZES_MM["A3"][0]  # landscape
        ox, oy = (sheet_w - wrap.width_mm) / 2, (sheet_h - wrap.height_mm) / 2  # wrap's lower-left corner
        # Covers are stretched over the bleed so colour reaches beyond the trim line.
        back_rect = (_mm(ox), _mm(oy), _mm(ox + bleed + page_w), _mm(oy + wrap.height_mm))
        front_x = ox + bleed + page_w + spine
        front_rect = (_mm(front_x), _mm(oy), _mm(front_x + page_w + bleed), _mm(oy + wrap.height_mm))
        bleed_w, bleed_h = page_w + bleed, wrap.height_mm
        layers = []
        for picture, page, rect, label in ((covers.back_image, covers.back, back_rect, "back"),
                                           (covers.front_image, covers.front, front_rect, "front")):
            if picture is not None:
                # A picture is drawn again at the bleed size, so the colour runs past the trim.
                page = image_page(picture, folder / f".{label}_bleed.pdf", bleed_w, bleed_h)
            layers.append(Layer(page, rect=rect, shrink=True, expand=True))

        def marks(c):
            c.setStrokeColor(black)
            c.setLineWidth(0.3)
            trim_l, trim_r = ox + bleed, ox + wrap.width_mm - bleed
            trim_b, trim_t = oy + bleed, oy + wrap.height_mm - bleed
            spine_l, spine_r = ox + bleed + page_w, ox + bleed + page_w + spine
            # Spine background and text
            c.setFillColor(Color(0.15, 0.2, 0.35))
            c.rect(_mm(spine_l), _mm(oy), _mm(spine), _mm(wrap.height_mm), stroke=0, fill=1)
            if wrap.spine_text_allowed and printable(text):
                size = min(10, spine * 2.83 * 0.55)
                c.saveState()
                c.setFillColor(white)
                c.setFont(SANS_BOLD, size)
                c.translate(_mm((spine_l + spine_r) / 2) + size * 0.35, _mm(oy + wrap.height_mm / 2))
                c.rotate(-90)  # reads top to bottom, as on English-language books
                c.drawCentredString(0, 0, text)
                c.restoreState()
            if issue.printing.crop_marks:
                # Crop marks at the four corners, outside the bleed.
                for x in (trim_l, trim_r):
                    for y in (trim_b, trim_t):
                        dy = -1 if y == trim_b else 1
                        dx = -1 if x == trim_l else 1
                        c.line(_mm(x), _mm(y + dy * (bleed + 1)), _mm(x), _mm(y + dy * (bleed + 6)))
                        c.line(_mm(x + dx * (bleed + 1)), _mm(y), _mm(x + dx * (bleed + 6)), _mm(y))
                # Fold marks for the spine, top and bottom.
                for x in (spine_l, spine_r):
                    c.line(_mm(x), _mm(oy - 1), _mm(x), _mm(oy - 6))
                    c.line(_mm(x), _mm(oy + wrap.height_mm + 1), _mm(x), _mm(oy + wrap.height_mm + 6))
            c.setFillColor(black)
            c.setFont(SANS, 7)
            c.drawString(_mm(8), _mm(6), f"{name}  |  wrap {wrap.width_mm:g} x {wrap.height_mm:g} mm incl. "
                                         f"{bleed:g} mm bleed  |  spine {spine:g} mm  |  {interior_pages} pages  |  print at 100%")

        layers.append(Layer(_marks_overlay(_mm(sheet_w), _mm(sheet_h), marks)))
        target = folder / f"{name}_cover_glue_{wrap.file_label()}.pdf"
        compose.compose_sheet(_mm(sheet_w), _mm(sheet_h), layers, target)
        for label in ("front", "back"):
            (folder / f".{label}_bleed.pdf").unlink(missing_ok=True)
        files.append(target)
    else:
        notes.append(f"The {issue.layout.page_size} wrap ({wrap.width_mm:g} mm wide) does not fit on A3: "
                     "front and back covers and a spine strip are given as separate pages.")
        # Spine strip on its own page
        strip = io.BytesIO()
        c = canvas.Canvas(strip, pagesize=(_mm(spine + 20), _mm(page_h + 20)))
        register_fonts()
        c.rect(_mm(10), _mm(10), _mm(spine), _mm(page_h))
        if wrap.spine_text_allowed and printable(text):
            c.saveState()
            c.setFont(SERIF, min(10, spine * 2.83 * 0.55))
            c.translate(_mm(10 + spine / 2) + 3, _mm(10 + page_h / 2))
            c.rotate(-90)
            c.drawCentredString(0, 0, text)
            c.restoreState()
        c.showPage()
        c.save()
        strip_path = folder / f".{name}_spine_strip.pdf"
        strip_path.write_bytes(strip.getvalue())
        target = folder / f"{name}_cover_glue_separate_spine{spine:g}mm.pdf"
        out, sources = merge.assemble([(covers.front, 0), (covers.back, 0), (strip_path, 0)], page_w, page_h)
        try:
            merge.save(out, target)
        finally:
            sources.close()
            strip_path.unlink(missing_ok=True)
        files.append(target)
    return files, notes, wrap
