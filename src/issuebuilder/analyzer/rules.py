"""Labelling rules for the parts of a Word article (blueprint M4).

All rules are in this one file so they can be improved from real samples.
Each paragraph gets a label and a confidence between 0 and 1. Anything
below LOW_CONFIDENCE is highlighted on the review screen.
"""

from __future__ import annotations

import re

from ..importers.docx_reader import Paragraph
from .orcid import ORCID_PATTERN

LABELS = [
    "title", "subtitle", "author", "orcid", "email", "institution",
    "abstract", "keywords", "heading1", "heading2", "body", "references",
    "other", "ignore",
]
LOW_CONFIDENCE = 0.6

# Parts of the article before the abstract / first heading.
FRONT_LABELS = {"title", "subtitle", "author", "orcid", "email", "institution"}

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
INSTITUTION_WORDS = re.compile(
    r"\b(university|universiti|department|dept\.?|institute|college|school|faculty|centre|center|"
    r"academy|kalamandalam|research|laboratory|hospital|vidyalaya|vidyapeeth|mahavidyalaya)\b",
    re.IGNORECASE,
)
ABSTRACT_START = re.compile(r"^\s*(abstract|summary)\b\s*[:.\-–—]?\s*", re.IGNORECASE)
KEYWORDS_START = re.compile(r"^\s*(key\s*-?\s*words?|index terms)\b\s*[:.\-–—]?\s*", re.IGNORECASE)
REFERENCES_HEADING = re.compile(
    r"^\s*(\d+\.?\s*)?(references|bibliography|works cited|works consulted|literature cited|sources)\s*:?\s*$",
    re.IGNORECASE,
)
OTHER_HEADING = re.compile(
    r"^\s*(\d+\.?\s*)?(acknowledge?ments?|funding|conflicts? of interest|declarations?|"
    r"competing interests?|author contributions?|data availability|notes on contributors?)\b",
    re.IGNORECASE,
)
NUMBERED_SUBHEADING = re.compile(r"^\s*\d+\.\d+(\.\d+)*\.?\s+\S")
NUMBERED_HEADING = re.compile(r"^\s*(\d+|[IVX]+)\.?\s+[A-Z]")


def is_heading_style(style: str) -> int:
    """1 or 2 for Word heading styles ('Heading 1', 'Heading 2', ...), else 0."""
    match = re.match(r"heading\s*(\d)", style.strip(), re.IGNORECASE)
    if match:
        return 1 if match.group(1) == "1" else 2
    return 0


def looks_like_heading(p: Paragraph, body_size: float) -> float:
    """Confidence that a paragraph is a heading even without a heading style."""
    if p.words > 14 or p.text.rstrip().endswith((".", ",", ";")) and not NUMBERED_HEADING.match(p.text):
        return 0.0
    score = 0.0
    if p.bold:
        score += 0.5
    if p.size and body_size and p.size > body_size + 0.5:
        score += 0.2
    if NUMBERED_HEADING.match(p.text) or NUMBERED_SUBHEADING.match(p.text):
        score += 0.2
    if p.text.isupper() and p.words <= 10:
        score += 0.2
    return min(score, 0.85)


def looks_like_name(text: str) -> bool:
    """A short line of capitalised words: 'A. Smith', 'Priya Nair¹, Rahul K.*'."""
    if EMAIL.search(text) or INSTITUTION_WORDS.search(text):
        return False
    cleaned = re.sub(r"[\d*†‡§,;&()]|\band\b", " ", text)
    words = [w for w in cleaned.split() if w]
    if not words or len(words) > 16:
        return False
    # A name line does not end like a sentence ("A. K. Rao" ends in a letter).
    if text.rstrip().endswith((".", ":")) and len(words) > 4:
        return False
    capitalised = sum(1 for w in words if w[0].isupper() or not w[0].isalpha())
    return capitalised / len(words) >= 0.75


def label_paragraphs(paragraphs: list[Paragraph], body_size: float) -> list[tuple[str, float]]:
    """Return (label, confidence) for each paragraph, in order."""
    n = len(paragraphs)
    result: list[tuple[str, float]] = [("body", 0.7)] * n
    if not n:
        return result

    # 1. Title: the Word "Title" style, else the largest or bold text near the top.
    title_index = None
    for k, p in enumerate(paragraphs[:8]):
        if p.style.lower() in ("title", "titel", "titre"):
            title_index, title_conf = k, 0.97
            break
    if title_index is None:
        top = paragraphs[:5]
        biggest = max(top, key=lambda p: p.size)
        if biggest.size > body_size + 1:
            title_index, title_conf = paragraphs.index(biggest), 0.85
        elif top[0].bold or top[0].centred:
            title_index, title_conf = 0, 0.75
        else:
            title_index, title_conf = 0, 0.5
    # Anything before the title (journal name, "Research article" ...) is ignored.
    for k in range(title_index):
        result[k] = ("ignore", 0.5)
    result[title_index] = ("title", title_conf)

    # 2. Find the abstract, keywords and references markers.
    abstract_at = next((k for k, p in enumerate(paragraphs) if k > title_index and ABSTRACT_START.match(p.text)), None)
    keywords_at = next((k for k, p in enumerate(paragraphs) if k > title_index and KEYWORDS_START.match(p.text)), None)
    references_at = next((k for k, p in enumerate(paragraphs) if k > title_index and REFERENCES_HEADING.match(p.text)), None)

    # The front block runs from after the title to the abstract (or first heading).
    first_heading = next(
        (k for k, p in enumerate(paragraphs) if k > title_index
         and (is_heading_style(p.style) or looks_like_heading(p, body_size) >= 0.6)
         and not looks_like_name(p.text)),
        None,
    )
    front_end = min(x for x in (abstract_at, keywords_at, first_heading, n) if x is not None)
    # Without an abstract, do not let a long front block swallow body text.
    front_end = min(front_end, title_index + 12)

    for k in range(title_index + 1, front_end):
        p = paragraphs[k]
        text = p.text
        if k == title_index + 1 and (p.italic or (p.size and p.size < paragraphs[title_index].size and p.size > body_size)) \
                and not looks_like_name(text) and not INSTITUTION_WORDS.search(text):
            result[k] = ("subtitle", 0.65)
        elif ORCID_PATTERN.search(text) and len(text) < 80:
            result[k] = ("orcid", 0.95)
        elif EMAIL.search(text) and p.words <= 8:
            result[k] = ("email", 0.9)
        elif INSTITUTION_WORDS.search(text) and p.words <= 30:
            result[k] = ("institution", 0.8)
        elif looks_like_name(text):
            result[k] = ("author", 0.75 if p.words <= 12 else 0.55)
        elif p.words > 40:
            # A long paragraph here is probably the start of the text.
            result[k] = ("body", 0.5)
        else:
            result[k] = ("author", 0.45)

    # 3. Abstract: the "Abstract" paragraph itself, and following paragraphs
    # until keywords or a heading.
    if abstract_at is not None:
        result[abstract_at] = ("abstract", 0.95)
        bare_heading = paragraphs[abstract_at].words <= 2   # just "Abstract"
        # Following paragraphs belong to the abstract up to the keywords or a
        # heading. If the text came on the same line ("Abstract: ...") and there
        # is no keywords line to stop at, take only that one paragraph.
        if bare_heading or keywords_at is not None:
            k = abstract_at + 1
            limit = keywords_at if keywords_at is not None else abstract_at + 6
            while k < min(n, limit):
                p = paragraphs[k]
                if is_heading_style(p.style) or looks_like_heading(p, body_size) >= 0.6:
                    break
                result[k] = ("abstract", 0.75)
                k += 1
    if keywords_at is not None:
        result[keywords_at] = ("keywords", 0.95)

    # 4. Body: headings, other sections, references.
    start = max(x for x in (front_end, (abstract_at or 0) + 1, (keywords_at or 0) + 1) if x is not None)
    in_other = False
    for k in range(start, n):
        if result[k][0] in ("abstract", "keywords"):
            continue
        p = paragraphs[k]
        if references_at is not None and k > references_at:
            result[k] = ("references", 0.9)
            continue
        if k == references_at:
            result[k] = ("heading1", 0.95)
            continue
        level = is_heading_style(p.style)
        if OTHER_HEADING.match(p.text) and (level or looks_like_heading(p, body_size) >= 0.5 or p.words <= 6):
            result[k] = ("other", 0.8)
            in_other = True
            continue
        if level:
            result[k] = (f"heading{level}", 0.95)
            in_other = False
            continue
        score = looks_like_heading(p, body_size)
        if score >= 0.5:
            level = 2 if NUMBERED_SUBHEADING.match(p.text) or (p.italic and not p.bold) else 1
            result[k] = (f"heading{level}", score)
            in_other = False
            continue
        result[k] = ("other", 0.7) if in_other else ("body", 0.8 if p.words > 12 else 0.65)
    return result
