import pytest

from issuebuilder.cover.spine import fits_on_sheet, sheet_count, spine_width_mm, wrap_size
from issuebuilder.settings.defaults import PhysicalSettings


@pytest.mark.parametrize("pages, expected_mm", [(80, 4.5), (120, 6.5), (200, 10.5)])
def test_spine_matches_blueprint_examples(pages, expected_mm):
    # Section 6.1: 0.1 mm paper and 0.5 mm glue.
    assert spine_width_mm(pages, 0.1, 0.5) == pytest.approx(expected_mm, abs=0.1)
    assert spine_width_mm(pages, 0.1, 0.5) == expected_mm


def test_odd_page_count_rounds_up_to_whole_sheet():
    assert sheet_count(81) == 41
    assert spine_width_mm(81, 0.1, 0.5) == 4.6


def test_measured_stack_replaces_paper_thickness():
    assert spine_width_mm(80, 0.1, 0.5, measured_stack_mm=5.2) == 5.7


def test_negative_pages_rejected():
    with pytest.raises(ValueError):
        sheet_count(-2)


def test_a5_wrap_with_bleed_fits_a3():
    wrap = wrap_size("A5", 80)
    # 2 x 148 + 4.5 + 2 x 3 = 306.5 ; 210 + 2 x 3 = 216
    assert wrap.width_mm == 306.5
    assert wrap.height_mm == 216
    assert fits_on_sheet(wrap, "A3")
    assert wrap.file_label() == "wrap_306.5x216mm_spine4.5mm"


def test_wrap_without_trimming_has_no_bleed():
    wrap = wrap_size("A5", 80, trimmed=False)
    assert wrap.width_mm == 300.5
    assert wrap.height_mm == 210


def test_a4_wrap_does_not_fit_a3():
    assert not fits_on_sheet(wrap_size("A4", 80), "A3")


def test_spine_text_only_from_minimum_width():
    assert not wrap_size("A5", 80).spine_text_allowed   # 4.5 mm < 5 mm
    assert wrap_size("A5", 120).spine_text_allowed      # 6.5 mm
    relaxed = PhysicalSettings(min_spine_for_text_mm=4.0)
    assert wrap_size("A5", 80, settings=relaxed).spine_text_allowed
