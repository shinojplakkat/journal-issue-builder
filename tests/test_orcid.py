import pytest

from issuebuilder.analyzer.orcid import check_character, find_orcids, is_valid, normalise


def test_blueprint_example_is_valid():
    assert is_valid("0000-0002-1825-0097")


def test_check_character_x():
    # ORCID's own documentation example whose check character is X.
    assert check_character("000000021694233") == "X"
    assert is_valid("0000-0002-1694-233X")
    assert is_valid("0000-0002-1694-233x")


@pytest.mark.parametrize("bad", [
    "0000-0002-1825-0098",   # wrong check digit
    "0000-0002-1825-009",    # too short
    "0000-0002-1825-00977",  # too long
    "abcd-0002-1825-0097",
    "",
])
def test_invalid_ids(bad):
    assert not is_valid(bad)


@pytest.mark.parametrize("written", [
    "https://orcid.org/0000-0002-1825-0097",
    "orcid.org/0000-0002-1825-0097",
    "0000 0002 1825 0097",
    "0000000218250097",
])
def test_other_ways_of_writing(written):
    assert normalise(written) == "0000-0002-1825-0097"
    assert is_valid(written)


def test_find_in_author_line():
    text = "A. Smith (ORCID: https://orcid.org/0000-0002-1825-0097), B. Rao 0000-0002-1825-0098"
    assert find_orcids(text) == [
        ("0000-0002-1825-0097", True),
        ("0000-0002-1825-0098", False),
    ]
