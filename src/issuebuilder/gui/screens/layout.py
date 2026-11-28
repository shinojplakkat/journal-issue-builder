"""Layout screen (blueprint M8, M14): page size, fonts, sizes, margins, headers, numbering, parts."""

from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QFileDialog, QFontComboBox, QFormLayout, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from ...settings.models import ANY, LEFT, RIGHT, LayoutSettings
from ...settings.script_fonts import SUPPORTED_SCRIPTS, import_user_font
from ..common import AppState, combo, info, int_spin, note, set_combo, spin

SIZES = [("body_pt", "Body text"), ("line_pt", "Body line spacing"), ("title_pt", "Article title"),
         ("subtitle_pt", "Subtitle"), ("h1_pt", "Heading 1"), ("h2_pt", "Heading 2"),
         ("abstract_pt", "Abstract and keywords"), ("ref_pt", "References"), ("footnote_pt", "Footnotes"),
         ("header_pt", "Header text"), ("number_pt", "Page number")]
MARGINS = [("margin_top", "Top"), ("margin_bottom", "Bottom"), ("margin_inside", "Inside (binding side)"),
           ("margin_outside", "Outside")]
PARTS = [("inside_front_cover", "Inside front cover"), ("title_page", "Title page"),
         ("imprint", "Copyright and imprint"), ("masthead", "Editorial board"),
         ("contents", "Contents"), ("article", "Each article"), ("author_index", "Author index (end)"),
         ("aims_scope", "Aims and scope (end)"), ("notes_for_authors", "Notes for authors (end)"),
         ("inside_back_cover", "Inside back cover")]
SIDES = [(RIGHT, "Right page"), (LEFT, "Left page"), (ANY, "Any page")]
HEADER_CHOICES = [("journal", "Journal short title"), ("article", "Article short title"), ("none", "Nothing")]
FONT_PROFILES = {
    "liberation": ("Liberation Serif", "Liberation Sans", "Noto Serif Malayalam"),
    "tinos": ("Tinos", "Arimo", "Noto Serif Malayalam"),
    "book": ("TeX Gyre Pagella", "TeX Gyre Heros", "Noto Serif Malayalam"),
    "modern": ("Gelasio", "Arimo", "Noto Serif Malayalam"),
    "indian": ("Noto Serif Malayalam", "Noto Sans Malayalam", "Noto Serif Malayalam"),
    "manjari": ("Liberation Serif", "Liberation Sans", "Manjari"),
}
FONT_PROFILE_LABELS = {
    "liberation": "Classic (Liberation)", "tinos": "Classic (Tinos / Arimo)",
    "book": "Book style (TeX Gyre)", "modern": "Modern (Gelasio / Arimo)",
    "indian": "Indian scripts (Noto Malayalam)",
    "manjari": "Indian scripts (Manjari)",
}


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
        self.script_choice = combo([(script, script) for script in SUPPORTED_SCRIPTS])
        self.script_font_choice = font_box("Noto Serif Malayalam")
        self.script_choice.currentIndexChanged.connect(self.show_script_font)
        map_font = QPushButton("Map font to script")
        map_font.clicked.connect(self.map_script_font)
        add_font = QPushButton("Add font file…")
        add_font.clicked.connect(self.add_font_file)
        font_mapping = QGroupBox("Language fonts")
        mapping_row = QHBoxLayout(font_mapping)
        mapping_row.addWidget(QLabel("Script"))
        mapping_row.addWidget(self.script_choice)
        mapping_row.addWidget(QLabel("Font"))
        mapping_row.addWidget(self.script_font_choice, 1)
        mapping_row.addWidget(map_font)
        mapping_row.addWidget(add_font)
        self.font_profile = combo([("custom", "Custom fonts")] +
                                  [(key, label) for key, label in FONT_PROFILE_LABELS.items()])
        self.font_profile.currentIndexChanged.connect(self.apply_font_profile)
        page = QGroupBox("Page and fonts")
        page_form = QFormLayout(page)
        size_row = QHBoxLayout()
        size_row.addWidget(self.page_size)
        size_row.addStretch()
        page_form.addRow("Page size", size_row)
        page_form.addRow("Font profile", self.font_profile)
        page_form.addRow("Body font", self.body_font)
        page_form.addRow("Headings font", self.heading_font)
        page_form.addRow("Font for Indian scripts", self.indic_font)
        page_form.addRow(font_mapping)
        page_form.addRow(note("Fonts must be installed on this computer. Liberation fonts come with "
                              "LibreOffice. Add a local OTF/TTF font and map it to its script here. "
                              "Manjari is included with the Linux installer."))

        self.sizes = {key: spin(8, 5, 40, 0.5, 1, " pt", click_only=True) for key, _ in SIZES}
        sizes = QGroupBox("Type sizes")
        grid = QGridLayout(sizes)
        self.restore_defaults_button = QPushButton("Restore default sizes and margins")
        self.restore_defaults_button.setToolTip("Restore the standard values for the selected page size and save them.")
        self.restore_defaults_button.clicked.connect(self.reset_profile)
        grid.addWidget(note("Point sizes change by typing a value or clicking the arrows."), 0, 0, 1, 4)
        grid.addWidget(self.restore_defaults_button, 0, 4, 1, 2)
        for n, (key, label) in enumerate(SIZES):
            row = n // 2 + 1
            grid.addWidget(QLabel(label), row, (n % 2) * 2)
            grid.addWidget(self.sizes[key], row, (n % 2) * 2 + 1)

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
        self.show_script_font()
        profile = next((key for key, fonts in FONT_PROFILES.items()
                        if fonts == (l.body_font, l.heading_font, l.indic_font)), "custom")
        set_combo(self.font_profile, profile)
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

    def apply_font_profile(self) -> None:
        profile = FONT_PROFILES.get(self.font_profile.currentData())
        if profile:
            self.body_font.setCurrentText(profile[0])
            self.heading_font.setCurrentText(profile[1])
            self.indic_font.setCurrentText(profile[2])

    def show_script_font(self, *_args) -> None:
        if self.state.issue is None:
            return
        settings = self.state.issue.load().layout
        script = self.script_choice.currentData()
        font = settings.script_fonts.get(script, settings.indic_font if script == "Malayalam" else
                                         f"Noto Serif {script}")
        self.script_font_choice.setCurrentText(font)

    def map_script_font(self) -> None:
        if self.state.issue is None:
            return
        script = self.script_choice.currentData()
        font = self.script_font_choice.currentText().strip()
        if not font:
            info(self, "Choose a font", "Enter or select a font family before mapping it.")
            return
        settings = self.state.issue.load()
        settings.layout.script_fonts[script] = font
        if script == "Malayalam":
            settings.layout.indic_font = font
        self.state.issue.save(settings)
        self.state.data_changed.emit()
        info(self, "Font mapped", f"{font} will be used for {script} text in generated pages.")

    def add_font_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Add a font file", "",
                                              "Font files (*.otf *.ttf *.ttc)")
        if not path:
            return
        try:
            family, _installed_path = import_user_font(path)
        except (OSError, ValueError, RuntimeError) as exc:
            info(self, "Could not add font", str(exc))
            return
        self.script_font_choice.setCurrentText(family)
        self.map_script_font()

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
        settings = self.state.issue.load()
        fresh = LayoutSettings.for_page_size(size)
        # Preserve fonts, headers and page rules; restore only typography and margins.
        settings.layout.page_size = size
        for key, _ in SIZES + MARGINS:
            setattr(settings.layout, key, getattr(fresh, key))
        self.state.issue.save(settings)
        self.show_settings(settings.layout)
        self.state.data_changed.emit()
        info(self, "Defaults restored", f"Default type sizes and margins for {size} have been restored and saved.")
