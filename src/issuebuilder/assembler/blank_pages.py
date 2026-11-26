"""Blank-page balancing (blueprint section 6.2 and M7).

Physical page 1 is the first page after the outside cover, and it is a
right-hand page (recto). Odd pages are right, even pages are left.

The same function is used for the electronic issue (when blank pages are
kept), the print files and the offprints.
"""

from dataclasses import dataclass

RIGHT = "right"
LEFT = "left"
ANY = "any"

GLUE = "glue"
STAPLE = "staple"
NONE = "none"  # electronic output: no end padding


@dataclass
class Element:
    """One part of the issue: title page, contents, an article, and so on."""

    name: str
    page_count: int
    starts_on: str = RIGHT  # "right", "left" or "any"


@dataclass
class Slot:
    """One run of pages in the finished layout."""

    kind: str        # "element" or "blank"
    name: str        # element name, or the reason for the blank page
    first_page: int
    last_page: int

    @property
    def page_count(self) -> int:
        return self.last_page - self.first_page + 1


def side_of(page_number: int) -> str:
    """Odd pages are on the right, even pages on the left."""
    return RIGHT if page_number % 2 == 1 else LEFT


def required_total(total_pages: int, binding_mode: str) -> int:
    """Page count after end padding: even for glue, a multiple of 4 for staples."""
    if binding_mode == GLUE:
        multiple = 2
    elif binding_mode == STAPLE:
        multiple = 4
    elif binding_mode == NONE:
        return total_pages
    else:
        raise ValueError(f"Unknown binding mode: {binding_mode!r}")
    return -(-total_pages // multiple) * multiple  # round up to the multiple


def balance(elements: list[Element], binding_mode: str = NONE, first_page: int = 1) -> list[Slot]:
    """Lay out the elements in order, inserting blank pages where needed.

    first_page is normally 1. For an offprint it can be the article's
    original start page, so the article keeps its side and page numbers.
    """
    slots: list[Slot] = []
    next_page = first_page

    for element in elements:
        if element.starts_on not in (RIGHT, LEFT, ANY):
            raise ValueError(f"{element.name}: starts_on must be right, left or any.")
        if element.page_count < 1:
            raise ValueError(f"{element.name}: an element needs at least one page.")

        if element.starts_on != ANY and side_of(next_page) != element.starts_on:
            slots.append(Slot("blank", f"before {element.name}", next_page, next_page))
            next_page += 1

        last = next_page + element.page_count - 1
        slots.append(Slot("element", element.name, next_page, last))
        next_page = last + 1

    # Padding is counted on the pages actually laid out, not on the page numbers,
    # because an offprint may start at page 45 but still has only its own sheets.
    used = next_page - first_page
    padding = required_total(used, binding_mode) - used
    if padding:
        slots.append(Slot("blank", "end padding", next_page, next_page + padding - 1))

    return slots


def total_pages(slots: list[Slot]) -> int:
    return sum(slot.page_count for slot in slots)


def start_pages(slots: list[Slot]) -> dict[str, int]:
    """Start page of each element, for the contents page."""
    return {slot.name: slot.first_page for slot in slots if slot.kind == "element"}
