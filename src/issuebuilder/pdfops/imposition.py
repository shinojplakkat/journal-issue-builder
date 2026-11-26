"""Booklet imposition for saddle stitching (blueprint section 6.3).

This module only works out the page ORDER. Placing the pages on the
paper with PyMuPDF comes in milestone 7.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SheetSide:
    left: int
    right: int


@dataclass(frozen=True)
class Sheet:
    """One folded sheet. Sheet 0 is the outermost one."""

    index: int
    front: SheetSide
    back: SheetSide


def booklet_sheets(page_count: int) -> list[Sheet]:
    """Return the sheets of a saddle-stitched booklet, outermost first.

    For N pages and sheet k:
        front: left = N - 2k      right = 1 + 2k
        back : left = 2 + 2k      right = N - 1 - 2k
    """
    if page_count <= 0 or page_count % 4 != 0:
        raise ValueError(
            f"A stapled booklet needs a page count that is a multiple of 4 (got {page_count}). "
            "Pad with blank pages first."
        )
    n = page_count
    return [
        Sheet(
            index=k,
            front=SheetSide(left=n - 2 * k, right=1 + 2 * k),
            back=SheetSide(left=2 + 2 * k, right=n - 1 - 2 * k),
        )
        for k in range(n // 4)
    ]


def print_sequence(page_count: int) -> list[int]:
    """Page numbers in the order they go onto the printed sides, two per side.

    For N = 8: [8, 1, 2, 7, 6, 3, 4, 5]
    """
    sequence = []
    for sheet in booklet_sheets(page_count):
        sequence += [sheet.front.left, sheet.front.right, sheet.back.left, sheet.back.right]
    return sequence
