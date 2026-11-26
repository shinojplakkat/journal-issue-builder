"""Turning labelled paragraphs into blocks and article details (blueprint M4)."""

from __future__ import annotations

import re
from pathlib import Path

from ..importers.docx_reader import read_paragraphs, superscript_markers
from ..settings.models import Article, Author, Block
from .orcid import find_orcids
from .rules import ABSTRACT_START, EMAIL, KEYWORDS_START, label_paragraphs

MARKER = re.compile(r"[\d*†‡§]+")


def analyze_word(path: Path) -> tuple[list[Block], list[str], float]:
    """Label every paragraph. Returns (blocks, flags, body font size)."""
    info = read_paragraphs(path)
    labels = label_paragraphs(info.paragraphs, info.body_size)
    blocks = [
        Block(i=p.i, text=p.text, label=label, confidence=round(conf, 2), confirmed=False)
        for p, (label, conf) in zip(info.paragraphs, labels)
    ]
    return blocks, info.flags, info.body_size


def split_names(text: str) -> list[tuple[str, str]]:
    """'A. Smith1, B. Rao2* and C. Nair' -> [(name, markers), ...]."""
    parts = re.split(r",|;|\band\b|&", text)
    names = []
    for part in parts:
        markers = "".join(MARKER.findall(part))
        name = MARKER.sub("", part).strip(" .\t")
        # Keep initials' full stops: put back a final '.' after a single letter.
        if re.search(r"\b[A-Z]$", name):
            name += "."
        if name:
            names.append((name, markers))
    return names


def fill_details(article: Article, word_path: Path | None = None) -> None:
    """Fill title, authors, abstract and keywords from the labelled blocks.

    Called after import and again when the editor presses "Apply labels".
    Existing values the editor typed are replaced, because the labels are
    the editor's own corrections.
    """
    def texts(label: str) -> list[Block]:
        return [b for b in article.blocks if b.label == label]

    titles = texts("title")
    article.title = " ".join(b.text for b in titles).strip()
    article.subtitle = " ".join(b.text for b in texts("subtitle")).strip().lstrip(":").strip()

    # Authors with their markers, in order of appearance (first, second, third author).
    authors: list[Author] = []
    author_markers: list[str] = []
    for b in texts("author"):
        for name, markers in split_names(b.text):
            authors.append(Author(name=name, corresponding="*" in markers))
            author_markers.append(markers.replace("*", ""))

    # ORCID iDs and e-mails are attached in order: the first iD to the first author.
    orcids = [oid for b in texts("orcid") + texts("author") for oid, ok in find_orcids(b.text)]
    for author, oid in zip(authors, orcids):
        author.orcid = oid
    emails = [m.group(0) for b in texts("email") + texts("author") for m in EMAIL.finditer(b.text)]
    for author, mail in zip([a for a in authors if a.corresponding] or authors, emails):
        author.email = mail

    # Affiliations: linked through markers ("1 Dept. of X") when present, else by order.
    institutions = [b.text for b in texts("institution")]
    by_marker: dict[str, str] = {}
    unmarked: list[str] = []
    for text in institutions:
        match = re.match(r"^\s*([\d*†‡§]+)\s*(.+)$", text)
        if match:
            by_marker[match.group(1)] = match.group(2).strip()
        else:
            unmarked.append(text.strip())
    for k, author in enumerate(authors):
        markers = author_markers[k] if k < len(author_markers) else ""
        linked = [by_marker[m] for m in markers if m in by_marker]
        if linked:
            author.affiliation = "; ".join(linked)
        elif unmarked:
            author.affiliation = unmarked[min(k, len(unmarked) - 1)]
    if authors and not any(a.corresponding for a in authors):
        authors[0].corresponding = True
    article.authors = authors

    abstract_parts = [ABSTRACT_START.sub("", b.text, count=1).strip() for b in texts("abstract")]
    article.abstract = "\n".join(p for p in abstract_parts if p)

    keyword_text = " ".join(KEYWORDS_START.sub("", b.text, count=1) for b in texts("keywords"))
    article.keywords = [k.strip(" .") for k in re.split(r"[;,]", keyword_text) if k.strip(" .")]

    if not article.short_title and article.title:
        article.short_title = article.title if len(article.title) <= 60 else ""

    # Superscript markers may be invisible in plain text; use them if the text had none.
    if word_path is not None and authors and not any(author_markers):
        first_author_block = next(iter(texts("author")), None)
        if first_author_block is not None:
            try:
                sup = superscript_markers(word_path, first_author_block.i)
            except IndexError:
                sup = []
            for author, marker in zip(authors, sup):
                linked = [by_marker[m] for m in marker if m in by_marker]
                if linked:
                    author.affiliation = "; ".join(linked)
