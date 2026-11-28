"""Preserve supported interactive links after Ghostscript PDF/A conversion."""

from __future__ import annotations

from pathlib import Path

import pikepdf

from .inspect import page_size_mm


def _clone_direct_object(obj):
    if isinstance(obj, pikepdf.Dictionary):
        return pikepdf.Dictionary({key: _clone_direct_object(value) for key, value in obj.items()})
    if isinstance(obj, pikepdf.Array):
        return pikepdf.Array([_clone_direct_object(value) for value in obj])
    return obj


def restore_links(source: Path, target: Path) -> int:
    """Copy URI and explicit-page links into a converted PDF/A file.

    Ghostscript converts page appearance and fonts, but does not reliably keep
    Link annotations. Rectangles remain valid because the conversion keeps the
    page dimensions. Explicit destinations are remapped to the output pages.
    """
    temporary = target.with_name(target.stem + ".links.tmp.pdf")
    count = 0
    try:
        with pikepdf.open(source) as original, pikepdf.open(target) as converted:
            if len(original.pages) != len(converted.pages):
                raise ValueError("Ghostscript changed the number of pages; links cannot be remapped safely.")
            for source_page, output_page in zip(original.pages, converted.pages):
                source_size, output_size = page_size_mm(source_page), page_size_mm(output_page)
                if any(abs(a - b) > 0.1 for a, b in zip(source_size, output_size)):
                    raise ValueError("Ghostscript changed a page size; link positions cannot be preserved safely.")
            page_index = {tuple(page.obj.objgen): index for index, page in enumerate(original.pages)}
            for source_page, output_page in zip(original.pages, converted.pages):
                annotations = source_page.obj.get("/Annots", [])
                links = [item for item in annotations if item.get("/Subtype") == "/Link"]
                if not links:
                    continue
                existing = [item for item in output_page.obj.get("/Annots", [])
                            if item.get("/Subtype") != "/Link"]
                for link in links:
                    source_destination = link.get("/Dest")
                    source_action = link.get("/A")
                    if source_action and source_action.get("/S") == "/GoTo":
                        source_destination = source_action.get("/D")
                    destination_page = None
                    if source_destination and len(source_destination):
                        destination_page = page_index.get(tuple(source_destination[0].objgen))
                    copied = converted.copy_foreign(link)
                    # PDF/A requires every non-popup annotation to carry flags.
                    # Preserve source flags, or make restored links visible and printable.
                    if "/F" not in copied:
                        copied["/F"] = 4
                    destination = copied.get("/Dest")
                    if destination_page is not None and destination is not None:
                        destination[0] = converted.pages[destination_page].obj
                    action = copied.get("/A")
                    if destination_page is not None and action and action.get("/S") == "/GoTo":
                        action["/D"][0] = converted.pages[destination_page].obj
                    existing.append(copied)
                    count += 1
                output_page.obj["/Annots"] = pikepdf.Array(existing)
            if "/PageLabels" in original.Root:
                converted.Root["/PageLabels"] = _clone_direct_object(original.Root["/PageLabels"])
            converted.save(temporary)
        temporary.replace(target)
        return count
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
