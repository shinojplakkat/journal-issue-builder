"""ORCID iD checking (blueprint section 6.4).

An ORCID iD has 16 characters in four groups of four, e.g. 0000-0002-1825-0097.
The last character is a check digit (0-9 or X), calculated with ISO 7064 MOD 11-2.
"""

import re

# Accepts plain iDs and ones written as links (https://orcid.org/...).
# Groups may be separated by hyphens or spaces, as authors type them both ways.
ORCID_PATTERN = re.compile(r"\b(\d{4})[- ]?(\d{4})[- ]?(\d{4})[- ]?(\d{3}[\dXx])\b")


def check_character(first_15_digits: str) -> str:
    """Calculate the 16th character from the first 15 digits."""
    total = 0
    for digit in first_15_digits:
        total = (total + int(digit)) * 2
    result = (12 - (total % 11)) % 11
    return "X" if result == 10 else str(result)


def normalise(orcid: str) -> str | None:
    """Return the iD in the standard form 0000-0000-0000-000X, or None if the shape is wrong."""
    text = orcid.strip()
    for prefix in ("https://orcid.org/", "http://orcid.org/", "orcid.org/"):
        if text.lower().startswith(prefix):
            text = text[len(prefix):]
    match = ORCID_PATTERN.fullmatch(text)
    if not match:
        return None
    return "-".join(match.groups()).upper()


def is_valid(orcid: str) -> bool:
    """True if the iD has the right shape AND the right check character."""
    standard = normalise(orcid)
    if standard is None:
        return False
    characters = standard.replace("-", "")
    return check_character(characters[:15]) == characters[15]


def find_orcids(text: str) -> list[tuple[str, bool]]:
    """Find every ORCID-like iD in a piece of text.

    Returns (standard form, valid) pairs, so an iD with a typing mistake
    can still be shown to the editor and flagged instead of silently dropped.
    """
    found = []
    for match in ORCID_PATTERN.finditer(text):
        standard = "-".join(match.groups()).upper()
        found.append((standard, is_valid(standard)))
    return found
