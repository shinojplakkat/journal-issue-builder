"""Data kept on disk as plain JSON: journal, issue and article (blueprint 3.4 and M1).

Each class can be turned into a dictionary (to_dict) and back (from_dict).
from_dict ignores unknown keys and fills missing ones with defaults, so files
written by an older or newer version still open.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any

FILE_VERSION = 1

RIGHT, LEFT, ANY = "right", "left", "any"
GLUE, STAPLE = "glue", "staple"

# How a Word article is turned into pages.
MODE_JOURNAL = "journal"    # restyled into the journal template
MODE_ORIGINAL = "original"  # author's own styles, only page size and margins changed
MODE_PDF = "pdf"            # submitted PDF, inserted unchanged (scaled if needed)

ARTICLE_TYPES = ["Research article", "Review article", "Book review", "Editorial", "Short communication"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


class Record:
    """Shared to_dict / from_dict for all the dataclasses below."""

    # field name -> class of the items, for lists of records
    _list_types: dict[str, type] = {}

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)  # type: ignore[arg-type]

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None):
        data = data or {}
        obj = cls()  # every field has a default
        for f in dataclasses.fields(cls):  # type: ignore[arg-type]
            if f.name not in data:
                continue
            value = data[f.name]
            current = getattr(obj, f.name)
            if isinstance(current, Record) and isinstance(value, dict):
                value = type(current).from_dict(value)
            elif f.name in cls._list_types and isinstance(value, list):
                item_cls = cls._list_types[f.name]
                value = [item_cls.from_dict(v) if isinstance(v, dict) else v for v in value]
            elif isinstance(current, dict) and isinstance(value, dict):
                merged = dict(current)
                merged.update(value)
                value = merged
            setattr(obj, f.name, value)
        return obj


# --------------------------------------------------------------------------- journal

@dataclass
class BoardMember(Record):
    name: str = ""
    role: str = ""
    institution: str = ""


@dataclass
class JournalSettings(Record):
    """Publication details (M1). Sample values; the editor replaces them."""

    _list_types = {"board": BoardMember}

    version: int = FILE_VERSION
    title: str = "Sample Journal of Arts and Humanities"
    short_title: str = "Sample Journal"
    abbreviation: str = "Sample J. Arts Hum."
    print_issn: str = "0000-0000"
    e_issn: str = "0000-0019"
    publisher: str = "Sample Publisher"
    address: str = "Street, City, State, PIN, Country"
    website: str = "https://www.example.org"
    email: str = "editor@example.org"
    editor_in_chief: str = "Dr. Editor Name"
    editors: list[str] = field(default_factory=lambda: ["Dr. Associate Editor One", "Dr. Associate Editor Two"])
    board: list[BoardMember] = field(default_factory=lambda: [
        BoardMember("Prof. Board Member One", "Member", "University One"),
        BoardMember("Prof. Board Member Two", "Member", "Institute Two"),
    ])
    frequency: str = "Biannual"
    aims_scope: str = ("The journal publishes peer-reviewed research articles, review articles "
                       "and book reviews in the arts and humanities.")
    peer_review: str = "All research articles in this journal undergo double-blind peer review."
    copyright_text: str = "© The authors. Published by Sample Publisher."
    licence: str = ("This work is licensed under a Creative Commons Attribution 4.0 "
                    "International Licence (CC BY 4.0).")
    logo: str = ""                 # file name inside the journal's assets folder
    doi_prefix: str = ""           # optional, e.g. 10.12345
    default_page_size: str = "A5"
    default_binding: str = STAPLE
    notes_for_authors: str = ("Manuscripts should be submitted in DOC, DOCX or ODT format with an "
                              "abstract of not more than 250 words and five keywords.")


# --------------------------------------------------------------------------- issue settings

@dataclass
class LayoutSettings(Record):
    """Typography and page profile (M8, section 7). All lengths in millimetres."""

    page_size: str = "A5"
    body_font: str = "Liberation Serif"      # Times-like, installed with LibreOffice
    heading_font: str = "Liberation Sans"    # Arial-like
    indic_font: str = "Manjari"
    script_fonts: dict[str, str] = field(default_factory=dict)
    body_pt: float = 11
    line_pt: float = 14
    title_pt: float = 15
    subtitle_pt: float = 12
    h1_pt: float = 12
    h2_pt: float = 11
    abstract_pt: float = 10
    ref_pt: float = 9
    footnote_pt: float = 9
    header_pt: float = 8
    number_pt: float = 9
    margin_top: float = 18
    margin_bottom: float = 20
    margin_inside: float = 20
    margin_outside: float = 15
    # Header and footer (M14)
    header_on: bool = True
    header_left: str = "journal"      # left pages: "journal" short title, "article", or "none"
    header_right: str = "article"     # right pages
    header_first_page: bool = False   # header on the first page of each article
    number_position: str = "outside"  # "centre" or "outside"
    citation_line: bool = True        # journal, volume, pages and DOI on each article's first page
    # Numbering (M7)
    roman_front_matter: bool = True
    first_arabic_page: int = 1
    blank_page_text: bool = False     # "This page intentionally left blank"
    # Which parts appear, and on which side they start (M7)
    parts_on: dict[str, bool] = field(default_factory=lambda: {
        "inside_front_cover": False, "title_page": True, "imprint": True, "masthead": True, "contents": True,
        "aims_scope": False, "notes_for_authors": False,
        "inside_back_cover": False,
    })
    starts_on: dict[str, str] = field(default_factory=lambda: {
        "inside_front_cover": LEFT, "title_page": RIGHT, "imprint": LEFT, "masthead": RIGHT, "contents": RIGHT,
        "article": RIGHT, "aims_scope": RIGHT, "notes_for_authors": RIGHT,
        "inside_back_cover": LEFT,
    })

    @classmethod
    def for_page_size(cls, size: str) -> "LayoutSettings":
        """Defaults from blueprint 7.1 (A5) and 7.2 (A4)."""
        if size == "A4":
            return cls(page_size="A4", body_pt=12, line_pt=15, title_pt=16, subtitle_pt=13,
                       h1_pt=13, h2_pt=12, abstract_pt=10, ref_pt=10, footnote_pt=10,
                       header_pt=9, number_pt=10, margin_top=25, margin_bottom=25,
                       margin_inside=28, margin_outside=22)
        return cls()


@dataclass
class PrintSettings(Record):
    """Print outputs (M10) and physical values (7.3)."""

    binding_mode: str = STAPLE
    gutter_staple_mm: float = 5
    gutter_glue_mm: float = 12
    grayscale: bool = True
    paper_thickness_mm: float = 0.1
    glue_allowance_mm: float = 0.5
    bleed_mm: float = 3
    unprintable_edge_mm: float = 5
    min_spine_for_text_mm: float = 5
    measured_stack_mm: float = 0       # 0 = not measured, use paper thickness
    stapled_page_warning: int = 60
    crop_marks: bool = True
    paper_profiles: dict = field(default_factory=dict)


@dataclass
class CoverSettings(Record):
    front_image: str = ""          # file inside the issue's assets folder
    back_image: str = ""           # empty = generated from journal details
    front_background: str = "#17324d"
    back_background: str = "#f2eee5"
    front_pattern: str = "solid"
    back_pattern: str = "solid"
    spine_text: str = ""           # empty = automatic (short title, volume, issue, year)
    offprint_line: bool = True


@dataclass
class ExportSettings(Record):
    electronic_issue: bool = True
    electronic_articles: bool = True
    pdfa_electronic: bool = False
    keep_blank_pages: bool = False
    include_covers_in_electronic: bool = True
    print_interior: bool = True
    print_cover: bool = True
    proof_watermark: bool = False
    abstract_word_limit: int = 250
    min_scaled_body_pt: float = 9
    min_image_dpi: int = 300


@dataclass
class IssueSettings(Record):
    version: int = FILE_VERSION
    volume: int = 1
    number: int = 1
    month: str = "January"
    year: int = 2027
    title: str = ""                # optional special-issue title
    inside_front_cover: str = ""   # optional notes or advertisement
    inside_back_cover: str = ""    # optional notes or advertisement
    article_order: list[str] = field(default_factory=list)
    layout: LayoutSettings = field(default_factory=LayoutSettings)
    printing: PrintSettings = field(default_factory=PrintSettings)
    cover: CoverSettings = field(default_factory=CoverSettings)
    export: ExportSettings = field(default_factory=ExportSettings)

    @property
    def slug(self) -> str:
        return f"vol{self.volume}-issue{self.number}"

    @property
    def label(self) -> str:
        return f"Volume {self.volume}, Issue {self.number}, {self.month} {self.year}"


# --------------------------------------------------------------------------- article

@dataclass
class Author(Record):
    name: str = ""
    orcid: str = ""
    affiliation: str = ""
    email: str = ""
    corresponding: bool = False


@dataclass
class Block(Record):
    """One labelled paragraph of a Word article (M4)."""

    i: int = 0                 # paragraph index in the Word file
    text: str = ""
    label: str = "body"
    confidence: float = 0.5
    confirmed: bool = False
    source_indices: list[int] = field(default_factory=list)


@dataclass
class Article(Record):
    _list_types = {"authors": Author, "blocks": Block}

    version: int = FILE_VERSION
    id: str = ""
    source_file: str = ""      # relative to the issue folder, inside originals/
    source_kind: str = ""      # "word" or "pdf"
    source_name: str = ""      # the file name the author sent
    source_hash: str = ""      # SHA-256, to catch the same article in two issues
    type: str = "Research article"
    title: str = ""
    subtitle: str = ""
    short_title: str = ""      # for running headers; Latin letters print best
    authors: list[Author] = field(default_factory=list)
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    dates: dict[str, str] = field(default_factory=lambda: {"received": "", "accepted": "", "published": ""})
    doi: str = ""
    blocks: list[Block] = field(default_factory=list)
    correction_log: list[dict[str, str]] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)       # tables, images, footnotes ...
    warnings: list[str] = field(default_factory=list)
    review_status: str = "needs_review"  # needs_review, reviewed, keep_original
    mode: str = MODE_JOURNAL
    starts_on: str = RIGHT
    stamp_numbers: bool = True           # add issue page numbers on this article's pages
    import_status: str = "ok"            # ok or error
    import_message: str = ""
    page_count: int = 0
    start_page: int | None = None
    end_page: int | None = None

    @property
    def author_names(self) -> str:
        names = [a.name for a in self.authors if a.name.strip()]
        if len(names) <= 2:
            return " and ".join(names)
        return ", ".join(names[:-1]) + " and " + names[-1]

    @property
    def first_author_surname(self) -> str:
        if not self.authors or not self.authors[0].name.strip():
            return "Author"
        return self.authors[0].name.strip().split()[-1]

    def header_title(self) -> str:
        text = self.short_title or self.title
        return text if len(text) <= 60 else text[:57].rstrip() + "..."
