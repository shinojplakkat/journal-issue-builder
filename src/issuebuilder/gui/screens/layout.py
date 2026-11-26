"""Layout screen (blueprint M8, M14): page size, fonts, sizes, margins, headers, numbering, parts."""

from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QFontComboBox, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from ...settings.models import ANY, LEFT, RIGHT, LayoutSettings
from ..common import AppState, ask, combo, info, int_spin, note, set_combo, spin

SIZES = [("body_pt", "Body text"), ("line_pt", "Body line spacing"), ("title_pt", "Article title"),
         ("subtitle_pt", "Subtitle"), ("h1_pt", "Heading 1"), ("h2_pt", "Heading 2"),
         ("abstract_pt", "Abstract and keywords"), ("ref_pt", "References"), ("footnote_pt", "Footnotes"),
         ("header_pt", "Header text"), ("number_pt", "Page number")]
MARGINS = [("margin_top", "Top"), ("margin_bottom", "Bottom"), ("margin_inside", "Inside (binding side)"),
           ("margin_outside", "Outside")]
PARTS = [("title_page", "Title page"), ("imprint", "Copyright and imprint"), ("masthead", "Editorial board"),
         ("contents", "Contents"), ("article", "Each article"), ("author_index", "Author index (end)"),
         ("aims_scope", "Aims and scope (end)"), ("notes_for_authors", "Notes for authors (end)")]
SIDES = [(RIGHT, "Right page"), (LEFT, "Left page"), (ANY, "Any page")]
HEADER_CHOICES = [("journal", "Journal short title"), ("article", "Article short title"), ("none", "Nothing")]


def font_box(name: str) -> QFontComboBox:
    box = QFontComboBox()
    box.setEditable(True)
    box.setCurrentText(name)
    return box


class LayoutScreen(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.page_size = combo([("A5", "A5 (148 × 210 mm)"), ("A4", "A4 (210 × 297 mm)")])
        self.body_font = font_box("Liberation Serif")
        self.heading_font = font_box("Liberation Sans")
        self.indic_font = font_box("Noto Serif Malayalam")
        page = QGroupBox("Page and fonts")
        page_form = QFormLayout(page)
        reset = QPushButton("Reset sizes and margins for this page size")
        reset.clicked.connect(self.reset_profile)
        size_row = QHBoxLayout()
        size_row.addWidget(self.page_size)
        size_row.addWidget(reset)
        size_row.addStretch()
        page_form.addRow("Page size", size_row)
        page_form.addRow("Body font", self.body_font)
        page_form.addRow("Headings font", self.heading_font)
        page_form.addRow("Font for Indian scripts", self.indic_font)
        page_form.addRow(note("Fonts must be installed on this computer. Liberation fonts come with "
                              "LibreOffice; for Malayalam, install Noto Serif Malayalam (free)."))

        self.sizes = {key: spin(8, 5, 40, 0.5, 1, " pt") for key, _ in SIZES}
        sizes = QGroupBox("Type sizes")
        grid = QGridLayout(sizes)
        for n, (key, label) in enumerate(SIZES):
            grid.addWidget(QLabel(label), n // 2, (n % 2) * 2)
            grid.addWidget(self.sizes[key], n // 2, (n % 2) * 2 + 1)

        self.margins = {key: spin(15, 0, 80, 0.5, 1, " mm") for key, _ in MARGINS}
        margins = QGroupBox("Margins (mirrored: the inside margin is on the binding side)")
        margin_row = QHBoxLayout(margins)
        for key, label in MARGINS:
            margin_row.addWidget(QLabel(label))
            margin_row.addWidget(self.margins[key])

        headers = QGroupBox("Headers and page numbers")
        header_form = QFormLayout(headers)
        self.header_on = QCheckBox("Print running headers")
        self.header_left = combo(HEADER_CHOICES)
        self.header_right = combo(HEADER_CHOICES)
        self.header_first = QCheckBox("Header also on the first page of each article")
        self.citation = QCheckBox("Citation line (journal, volume, pages, DOI) on each article's first page")
        self.number_position = combo([("outside", "Outside corner"), ("centre", "Centre")])
        self.roman = QCheckBox("Front matter in roman numerals (i, ii, iii)")
        self.first_arabic = int_spin(1, 1, 9999)
        self.blank_text = QCheckBox("Print 'This page intentionally left blank' on blank pages")
        header_form.addRow(self.header_on)
        header_form.addRow("Left pages show", self.header_left)
        header_form.addRow("Right pages show", self.header_right)
        header_form.addRow(self.header_first)
        header_form.addRow(self.citation)
        header_form.addRow("Page number position", self.number_position)
        header_form.addRow(self.roman)
        header_form.addRow("First article starts at page", self.first_arabic)
        header_form.addRow(self.blank_text)

        parts = QGroupBox("Parts of the issue and the side each starts on")
        parts_grid = QGridLayout(parts)
        self.part_on: dict[str, QCheckBox] = {}
        self.part_side = {}
        for n, (key, label) in enumerate(PARTS):
            if key == "article":
                parts_grid.addWidget(QLabel(label), n, 0)
            else:
                self.part_on[key] = QCheckBox(label)
                parts_grid.addWidget(self.part_on[key], n, 0)
            self.part_side[key] = combo(SIDES)
            parts_grid.addWidget(self.part_side[key], n, 1)
        parts_grid.addWidget(note("A blank page is added whenever a part would start on the wrong side. "
                                  "Each article's own setting (Edit details) can override 'Each article'."),
                             len(PARTS), 0, 1, 2)

        save = QPushButton("Save layout")
        save.setDefault(True)
        save.clicked.connect(self.save)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        for box in (page, sizes, margins, headers, parts):
            inner_layout.addWidget(box)
        inner_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        bottom = QHBoxLayout()
        bottom.addWidget(note("Layout settings belong to the open issue. Articles are laid out again on the next "
                              "preview or export."), 1)
        bottom.addWidget(save)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll)
        layout.addLayout(bottom)

        state.issue_changed.connect(self.load)

    def show_settings(self, l: LayoutSettings) -> None:
        set_combo(self.page_size, l.page_size)
        self.body_font.setCurrentText(l.body_font)
        self.heading_font.setCurrentText(l.heading_font)
        self.indic_font.setCurrentText(l.indic_font)
        for key, box in self.sizes.items():
            box.setValue(getattr(l, key))
        for key, box in self.margins.items():
            box.setValue(getattr(l, key))
        self.header_on.setChecked(l.header_on)
        set_combo(self.header_left, l.header_left)
        set_combo(self.header_right, l.header_right)
        self.header_first.setChecked(l.header_first_page)
        self.citation.setChecked(l.citation_line)
        set_combo(self.number_position, l.number_position)
        self.roman.setChecked(l.roman_front_matter)
        self.first_arabic.setValue(l.first_arabic_page)
        self.blank_text.setChecked(l.blank_page_text)
        for key, box in self.part_on.items():
            box.setChecked(bool(l.parts_on.get(key, False)))
        for key, box in self.part_side.items():
            set_combo(box, l.starts_on.get(key, RIGHT))

    def load(self) -> None:
        self.setEnabled(self.state.issue is not None)
        if self.state.issue is not None:
            self.show_settings(self.state.issue.load().layout)

    def collect(self) -> LayoutSettings:
        l = self.state.issue.load().layout
        l.page_size = self.page_size.currentData()
        l.body_font = self.body_font.currentText().strip() or l.body_font
        l.heading_font = self.heading_font.currentText().strip() or l.heading_font
        l.indic_font = self.indic_font.currentText().strip() or l.indic_font
        for key, box in self.sizes.items():
            setattr(l, key, box.value())
        for key, box in self.margins.items():
            setattr(l, key, box.value())
        l.header_on = self.header_on.isChecked()
        l.header_left = self.header_left.currentData()
        l.header_right = self.header_right.currentData()
        l.header_first_page = self.header_first.isChecked()
        l.citation_line = self.citation.isChecked()
        l.number_position = self.number_position.currentData()
        l.roman_front_matter = self.roman.isChecked()
        l.first_arabic_page = self.first_arabic.value()
        l.blank_page_text = self.blank_text.isChecked()
        l.parts_on = {key: box.isChecked() for key, box in self.part_on.items()}
        l.starts_on = {key: box.currentData() for key, box in self.part_side.items()}
        return l

    def save(self) -> None:
        if self.state.issue is None:
            return
        s = self.state.issue.load()
        new = self.collect()
        if new.first_arabic_page % 2 == 0 and new.starts_on.get("article") == RIGHT:
            info(self, "Page numbers", "Articles start on right-hand pages, which carry odd numbers. "
                                       "An even first page number will put odd numbers on left pages.")
        s.layout = new
        self.state.issue.save(s)
        self.state.data_changed.emit()
        info(self, "Saved", "Layout saved.")

    def reset_profile(self) -> None:
        if self.state.issue is None:
            return
        size = self.page_size.currentData()
        if ask(self, "Reset layout", f"Replace sizes and margins with the {size} defaults?"):
            current = self.collect()
            fresh = LayoutSettings.for_page_size(size)
            # Keep fonts, headers and parts; only sizes and margins come from the profile.
            for key, _ in SIZES + MARGINS:
                setattr(current, key, getattr(fresh, key))
            current.page_size = size
            self.show_settings(current)
