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

import pikepdf
from pikepdf import Pdf, Rectangle
from reportlab.lib.colors import Color, black, white
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from ..builder import front_matter as fm
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


def cover_pages(journal_folder: JournalFolder, issue_folder: IssueFolder, journal: JournalSettings,
                issue: IssueSettings) -> CoverPages:
    """Front and back cover pages at page size, from uploaded pictures or generated."""
    layout = issue.layout
    width, height = PAPER_SIZES_MM[layout.page_size]
    folder = issue_folder.work / "_cover"
    folder.mkdir(parents=True, exist_ok=True)
    generate: dict[str, fm.Page] = {}

    front_image = issue_folder.assets / issue.cover.front_image if issue.cover.front_image else None
    back_image = issue_folder.assets / issue.cover.back_image if issue.cover.back_image else None
    if front_image is not None and front_image.is_file():
        front = image_page(front_image, folder / "front.pdf", width, height)
    else:
        generate["front_generated"] = fm.generated_front_cover(journal, issue, layout,
                                                               journal_folder.logo_path(journal))
        front = folder / "front_generated.pdf"
    if back_image is not None and back_image.is_file():
        back = image_page(back_image, folder / "back.pdf", width, height)
    else:
        generate["back_generated"] = fm.generated_back_cover(journal, issue, layout)
        back = folder / "back_generated.pdf"
    if generate:
        fm.render(generate, folder)
        # A generated cover must be exactly one page.
        for path in (front, back):
            with Pdf.open(path, allow_overwriting_input=True) as pdf:
                if len(pdf.pages) > 1:
                    del pdf.pages[1:]
                    pdf.save(path)
    return CoverPages(front, back,
                      front_image if front_image is not None and front_image.is_file() else None,
                      back_image if back_image is not None and back_image.is_file() else None)


def physical(issue: IssueSettings) -> PhysicalSettings:
    p = issue.printing
    return PhysicalSettings(paper_thickness_mm=p.paper_thickness_mm, glue_allowance_mm=p.glue_allowance_mm,
                            bleed_mm=p.bleed_mm, unprintable_edge_mm=p.unprintable_edge_mm,
                            min_spine_for_text_mm=p.min_spine_for_text_mm)


def spine_text(journal: JournalSettings, issue: IssueSettings) -> str:
    if issue.cover.spine_text.strip():
        return issue.cover.spine_text.strip()
    return f"{journal.short_title or journal.title}   •   Vol. {issue.volume}, No. {issue.number}   •   {issue.year}"


# pikepdf copies page content lazily from the source file when the result is
# saved, so sources stay open in this list until then.
_open_sources: list[Pdf] = []


def _source(path: Path) -> Pdf:
    pdf = Pdf.open(path)
    _open_sources.append(pdf)
    return pdf


def _close_sources() -> None:
    while _open_sources:
        _open_sources.pop().close()


def _place(sheet: Pdf, page_index: int, source: Path, rect: Rectangle) -> None:
    sheet.pages[page_index].add_overlay(_source(source).pages[0], rect)


def _marks_overlay(width: float, height: float, draw) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))
    register_fonts()
    draw(c)
    c.showPage()
    c.save()
    return buffer.getvalue()


def _apply(sheet: Pdf, overlay: bytes) -> None:
    over = pikepdf.open(io.BytesIO(overlay))
    _open_sources.append(over)
    sheet.pages[0].add_overlay(over.pages[0])


def staple_cover(covers: CoverPages, issue: IssueSettings, target: Path) -> list[str]:
    """Back cover left, front cover right, on one landscape sheet (A4 for A5, A3 for A4)."""
    width, height = PAPER_SIZES_MM[issue.layout.page_size]
    sheet_w, sheet_h = 2 * width, height
    sheet = Pdf.new()
    sheet.add_blank_page(page_size=(_mm(sheet_w), _mm(sheet_h)))
    _place(sheet, 0, covers.back, Rectangle(0, 0, _mm(width), _mm(height)))
    _place(sheet, 0, covers.front, Rectangle(_mm(width), 0, _mm(2 * width), _mm(height)))
    edge = issue.printing.unprintable_edge_mm

    def marks(c):
        # Short fold ticks at top and bottom, inside the printable area.
        c.setStrokeColor(Color(0.5, 0.5, 0.5))
        c.setLineWidth(0.4)
        x = _mm(width)
        c.line(x, _mm(sheet_h - edge), x, _mm(sheet_h - edge - 4))
        c.line(x, _mm(edge), x, _mm(edge + 4))

    _apply(sheet, _marks_overlay(_mm(sheet_w), _mm(sheet_h), marks))
    sheet.save(target)
    _close_sources()
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
        sheet = Pdf.new()
        sheet.add_blank_page(page_size=(_mm(sheet_w), _mm(sheet_h)))
        # Covers are stretched over the bleed so colour reaches beyond the trim line.
        back_rect = Rectangle(_mm(ox), _mm(oy), _mm(ox + bleed + page_w), _mm(oy + wrap.height_mm))
        front_x = ox + bleed + page_w + spine
        front_rect = Rectangle(_mm(front_x), _mm(oy), _mm(front_x + page_w + bleed), _mm(oy + wrap.height_mm))
        bleed_w, bleed_h = page_w + bleed, wrap.height_mm
        for picture, page, rect, label in ((covers.back_image, covers.back, back_rect, "back"),
                                           (covers.front_image, covers.front, front_rect, "front")):
            if picture is not None:
                # A picture is drawn again at the bleed size, so the colour runs past the trim.
                page = image_page(picture, folder / f".{label}_bleed.pdf", bleed_w, bleed_h)
            _place_fill(sheet, page, rect)

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
            # Crop marks at the four corners, outside the bleed
            for x in (trim_l, trim_r):
                for y in (trim_b, trim_t):
                    dy = -1 if y == trim_b else 1
                    dx = -1 if x == trim_l else 1
                    c.line(_mm(x), _mm(y + dy * (bleed + 1)), _mm(x), _mm(y + dy * (bleed + 6)))
                    c.line(_mm(x + dx * (bleed + 1)), _mm(y), _mm(x + dx * (bleed + 6)), _mm(y))
            # Fold marks for the spine, top and bottom
            for x in (spine_l, spine_r):
                c.line(_mm(x), _mm(oy - 1), _mm(x), _mm(oy - 6))
                c.line(_mm(x), _mm(oy + wrap.height_mm + 1), _mm(x), _mm(oy + wrap.height_mm + 6))
            c.setFillColor(black)
            c.setFont(SANS, 7)
            c.drawString(_mm(8), _mm(6), f"{name}  |  wrap {wrap.width_mm:g} x {wrap.height_mm:g} mm incl. "
                                         f"{bleed:g} mm bleed  |  spine {spine:g} mm  |  {interior_pages} pages  |  print at 100%")

        _apply(sheet, _marks_overlay(_mm(sheet_w), _mm(sheet_h), marks))
        target = folder / f"{name}_cover_glue_{wrap.file_label()}.pdf"
        sheet.save(target)
        _close_sources()
        for label in ("front", "back"):
            (folder / f".{label}_bleed.pdf").unlink(missing_ok=True)
        files.append(target)
    else:
        notes.append(f"The {issue.layout.page_size} wrap ({wrap.width_mm:g} mm wide) does not fit on A3: "
                     "front and back covers and a spine strip are given as separate pages.")
        out = Pdf.new()
        for path in (covers.front, covers.back):
            out.pages.append(_source(path).pages[0])
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
        with pikepdf.open(io.BytesIO(strip.getvalue())) as s:
            out.pages.append(s.pages[0])
            target = folder / f"{name}_cover_glue_separate_spine{spine:g}mm.pdf"
            out.save(target)
        _close_sources()
        files.append(target)
    return files, notes, wrap


def _place_fill(sheet: Pdf, source: Path, rect: Rectangle) -> None:
    """Place a cover page in the rectangle (it includes the bleed)."""
    sheet.pages[0].add_overlay(_source(source).pages[0], rect, shrink=True, expand=True)
