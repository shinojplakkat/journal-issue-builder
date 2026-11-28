"""Persistent data models for books. Backwards-compatible JSON defaults are intentional."""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any


class Record:
    _list_types: dict[str, type] = {}

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None):
        obj = cls()
        for item in dataclasses.fields(cls):
            if not data or item.name not in data:
                continue
            value = data[item.name]
            current = getattr(obj, item.name)
            if isinstance(current, Record) and isinstance(value, dict):
                value = type(current).from_dict(value)
            elif item.name in cls._list_types and isinstance(value, list):
                child = cls._list_types[item.name]
                value = [child.from_dict(v) if isinstance(v, dict) else v for v in value]
            setattr(obj, item.name, value)
        return obj


@dataclass
class Contributor(Record):
    name: str = ""
    role: str = "Author"  # Author, Editor, Translator, Foreword, etc.
    affiliation: str = ""
    email: str = ""
    orcid: str = ""
    biography: str = ""


@dataclass
class Chapter(Record):
    id: str = ""
    title: str = ""
    subtitle: str = ""
    authors: list[str] = field(default_factory=list)
    source_file: str = ""
    source_name: str = ""
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    doi: str = ""
    references_note: str = "Chapter references retained in source manuscript"
    part: str = ""
    include: bool = True


@dataclass
class Book(Record):
    _list_types = {"contributors": Contributor, "chapters": Chapter}

    version: int = 1
    id: str = ""
    title: str = ""
    subtitle: str = ""
    book_type: str = "edited"  # edited or monograph
    isbn_print: str = ""
    isbn_ebook: str = ""
    publisher: str = ""
    publisher_address: str = ""
    publication_place: str = ""
    publication_year: int = 2026
    edition: str = "First edition"
    language: str = "English"
    subject: str = ""
    series_title: str = ""
    series_number: str = ""
    price: str = ""
    copyright_holder: str = ""
    copyright_year: int = 2026
    copyright_statement: str = "All rights reserved."
    dedication: str = ""
    epigraph: str = ""
    foreword: str = ""
    preface: str = ""
    acknowledgements: str = ""
    introduction: str = ""
    appendices: str = ""
    glossary: str = ""
    bibliography: str = ""
    index_note: str = ""
    trim_size: str = "A5"
    body_font: str = "Liberation Serif"
    contributors: list[Contributor] = field(default_factory=list)
    chapters: list[Chapter] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


def isbn13_valid(value: str) -> bool:
    """Return True for a valid ISBN-13 (hyphens/spaces are ignored)."""
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) != 13:
        return False
    total = sum(int(ch) * (1 if i % 2 == 0 else 3) for i, ch in enumerate(digits[:12]))
    return (10 - total % 10) % 10 == int(digits[-1])


def normalise_isbn(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())
