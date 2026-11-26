import pytest

from issuebuilder.pdfops.imposition import Sheet, SheetSide, booklet_sheets, print_sequence


def test_eight_pages_exact_result():
    # Section 6.3: sheet 0 front 8|1, back 2|7; sheet 1 front 6|3, back 4|5.
    assert booklet_sheets(8) == [
        Sheet(0, SheetSide(8, 1), SheetSide(2, 7)),
        Sheet(1, SheetSide(6, 3), SheetSide(4, 5)),
    ]
    assert print_sequence(8) == [8, 1, 2, 7, 6, 3, 4, 5]


def test_twelve_pages():
    assert print_sequence(12) == [12, 1, 2, 11, 10, 3, 4, 9, 8, 5, 6, 7]


@pytest.mark.parametrize("n", [4, 8, 12, 16, 40, 64])
def test_every_page_appears_once_and_facing_pages_add_up(n):
    assert sorted(print_sequence(n)) == list(range(1, n + 1))
    for sheet in booklet_sheets(n):
        # On every side the two pages add up to N + 1.
        assert sheet.front.left + sheet.front.right == n + 1
        assert sheet.back.left + sheet.back.right == n + 1


@pytest.mark.parametrize("n", [0, 2, 6, 10, -4])
def test_count_must_be_multiple_of_four(n):
    with pytest.raises(ValueError):
        booklet_sheets(n)
