import itertools

import pytest

from issuebuilder.assembler.blank_pages import (
    ANY, GLUE, LEFT, NONE, RIGHT, STAPLE,
    Element, balance, side_of, start_pages, total_pages,
)


def default_front_matter():
    # The defaults from blueprint M7.
    return [
        Element("title page", 1, RIGHT),
        Element("copyright", 1, LEFT),
        Element("contents", 1, RIGHT),
        Element("masthead", 1, RIGHT),
    ]


def check_layout(slots, elements, first_page=1):
    """Every element starts on its required side, and pages run without gaps."""
    expected = first_page
    for slot in slots:
        assert slot.first_page == expected, "pages must be continuous"
        expected = slot.last_page + 1
    starts = start_pages(slots)
    for element in elements:
        if element.starts_on != ANY:
            assert side_of(starts[element.name]) == element.starts_on, element.name


def test_page_sides():
    assert side_of(1) == RIGHT
    assert side_of(2) == LEFT


def test_simple_example():
    elements = default_front_matter() + [Element("article 1", 3, RIGHT), Element("article 2", 2, RIGHT)]
    slots = balance(elements, NONE)
    # title 1, copyright 2, contents 3, blank 4, masthead 5, blank 6,
    # article 1 = 7-9, blank 10, article 2 = 11-12
    assert start_pages(slots) == {
        "title page": 1, "copyright": 2, "contents": 3, "masthead": 5,
        "article 1": 7, "article 2": 11,
    }
    assert total_pages(slots) == 12
    blanks = [s.first_page for s in slots if s.kind == "blank"]
    assert blanks == [4, 6, 10]


@pytest.mark.parametrize("mode, multiple", [(GLUE, 2), (STAPLE, 4)])
def test_all_combinations_of_article_lengths(mode, multiple):
    # Section 6.2: elements of 1 to 9 pages in many combinations.
    for lengths in itertools.product(range(1, 10), repeat=3):
        for article_side in (RIGHT, ANY):
            elements = default_front_matter() + [
                Element(f"article {i}", n, article_side) for i, n in enumerate(lengths)
            ]
            slots = balance(elements, mode)
            check_layout(slots, elements)
            assert total_pages(slots) % multiple == 0


def test_left_and_right_starts_mixed():
    for lengths in itertools.product(range(1, 10), repeat=4):
        sides = [RIGHT, LEFT, ANY, LEFT]
        elements = [Element(f"e{i}", n, s) for i, (n, s) in enumerate(zip(lengths, sides))]
        check_layout(balance(elements, NONE), elements)


def test_electronic_mode_adds_no_end_padding():
    slots = balance([Element("article", 3, RIGHT)], NONE)
    assert total_pages(slots) == 3


def test_offprint_keeps_original_pages_and_side():
    # An article on pages 45-62 (section M12 acceptance test).
    elements = [Element("article", 18, RIGHT)]
    slots = balance(elements, STAPLE, first_page=45)
    assert start_pages(slots)["article"] == 45
    assert slots[0].last_page == 62
    assert total_pages(slots) == 20  # padded to a multiple of 4


def test_offprint_on_even_start_page_gets_blank_before():
    slots = balance([Element("article", 5, RIGHT)], NONE, first_page=44)
    assert slots[0].kind == "blank" and slots[0].first_page == 44
    assert start_pages(slots)["article"] == 45


def test_bad_values_rejected():
    with pytest.raises(ValueError):
        balance([Element("x", 0)])
    with pytest.raises(ValueError):
        balance([Element("x", 1, "middle")])
    with pytest.raises(ValueError):
        balance([Element("x", 1)], "spiral")
