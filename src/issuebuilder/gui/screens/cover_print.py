"""Cover and print screen (blueprint M9, M10)."""

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from ...cover.spine import fits_on_sheet, wrap_size
from ...cover.wrap import physical
from ...settings.models import GLUE, STAPLE
from ..common import AppState, combo, info, int_spin, note, set_combo, spin


class ImagePicker(QWidget):
    def __init__(self, title: str, on_change):
        super().__init__()
        self.on_change = on_change
        self.image_path = None
        self.background = "#17324d"
        self.preview = QLabel("Create in software")
        self.preview.setFixedSize(150, 205)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setWordWrap(True)
        self.preview.setStyleSheet("border: 1px solid #aaa;")
        self.preview_text = QLabel(self.preview)
        self.preview_text.setGeometry(0, 0, 150, 205)
        self.preview_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_text.setWordWrap(True)
        self.preview_text.setStyleSheet("color: white; font-weight: bold; background: transparent;")
        self.source = combo([("generated", "Create in software"), ("image", "Use an image")])
        self.source.currentIndexChanged.connect(self._source_changed)
        choose = QPushButton(f"Choose {title}…")
        choose.clicked.connect(lambda: self.on_change(True))
        clear = QPushButton("Use generated")
        clear.clicked.connect(lambda: self.on_change(False))
        self.pattern = combo([("solid", "Solid color"), ("diagonal", "Diagonal stripes"),
                              ("dots", "Dots"), ("grid", "Grid")])
        self.pattern.currentIndexChanged.connect(lambda _: self.show_image(self.image_path))
        self.color_button = QPushButton("Choose background color…")
        self.color_button.clicked.connect(self.choose_color)
        buttons = QVBoxLayout()
        buttons.addWidget(self.source)
        buttons.addWidget(choose)
        buttons.addWidget(clear)
        buttons.addWidget(self.pattern)
        buttons.addWidget(self.color_button)
        buttons.addStretch()
        row = QHBoxLayout(self)
        row.addWidget(self.preview)
        row.addLayout(buttons)
        row.addStretch()

    def _source_changed(self, _):
        if self.source.currentData() == "generated" and self.image_path:
            self.on_change(False)
        elif self.source.currentData() == "image" and not self.image_path:
            self.on_change(True)

    def choose_color(self):
        color = QColorDialog.getColor(parent=self)
        if color.isValid():
            self.background = color.name()
            self.show_image(self.image_path)

    def set_design(self, path: Path | None, background: str, pattern: str):
        self.image_path = path
        self.background = background or "#17324d"
        self.pattern.blockSignals(True)
        set_combo(self.pattern, pattern)
        self.pattern.blockSignals(False)
        self.source.blockSignals(True)
        self.source.setCurrentIndex(1 if path else 0)
        self.source.blockSignals(False)
        self.show_image(path)

    def show_image(self, path: Path | None) -> None:
        self.image_path = path
        if path is not None and path.is_file():
            self.preview.setPixmap(QPixmap(str(path)).scaled(146, 201, Qt.AspectRatioMode.KeepAspectRatio,
                                                             Qt.TransformationMode.SmoothTransformation))
            self.preview_text.hide()
            self.pattern.setVisible(False)
            self.color_button.setVisible(False)
        else:
            label = {"solid": "Solid color", "diagonal": "Diagonal stripes", "dots": "Dot pattern",
                     "grid": "Grid pattern"}.get(self.pattern.currentData(), "Solid color")
            art = QPixmap(150, 205)
            art.fill(QColor(self.background))
            painter = QPainter(art)
            painter.setPen(QPen(QColor(255, 255, 255, 90), 2))
            pattern = self.pattern.currentData()
            if pattern == "diagonal":
                for x in range(-205, 200, 18):
                    painter.drawLine(x, 205, x + 205, 0)
            elif pattern == "dots":
                painter.setBrush(QColor(255, 255, 255, 100))
                for x in range(8, 150, 14):
                    for y in range(8, 205, 14):
                        painter.drawEllipse(x, y, 3, 3)
            elif pattern == "grid":
                for x in range(0, 150, 14):
                    painter.drawLine(x, 0, x, 205)
                for y in range(0, 205, 14):
                    painter.drawLine(0, y, 150, y)
            painter.end()
            self.preview.setPixmap(art)
            self.preview_text.setText(f"{label}\n\nJournal name\nIssue details")
            self.preview_text.show()
            self.pattern.setVisible(True)
            self.color_button.setVisible(True)


class CoverPrintScreen(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state

        cover = QGroupBox("Cover")
        cover_form = QFormLayout(cover)
        self.front = ImagePicker("front cover", lambda pick: self.pick_image("front_image", pick))
        self.back = ImagePicker("back cover", lambda pick: self.pick_image("back_image", pick))
        self.spine_text = QLineEdit()
        self.spine_text.setPlaceholderText("Automatic: short title • volume, issue • year")
        self.offprint_line = QCheckBox("Offprints: add an 'OFFPRINT' band with the author names on the cover")
        cover_form.addRow(note("Choose an image or create each cover in software with a solid color or pattern. "
                               "Journal and issue details are printed over both generated and image covers."))
        cover_form.addRow("Front cover", self.front)
        cover_form.addRow("Back cover", self.back)
        cover_form.addRow("Spine text", self.spine_text)
        cover_form.addRow(self.offprint_line)

        printing = QGroupBox("Printing")
        form = QFormLayout(printing)
        self.binding = combo([(STAPLE, "Staples (saddle stitch): booklet order, pages in fours"),
                              (GLUE, "Glue binding (professional): page order, cover with spine")])
        self.gutter_staple = spin(5, 0, 30, 0.5, 1, " mm")
        self.gutter_glue = spin(12, 0, 30, 0.5, 1, " mm")
        self.crop_marks = QCheckBox("Print crop and fold marks on covers")
        self.paper_profiles = {}
        self.thickness = spin(0.1, 0.03, 0.5, 0.005, 3, " mm")
        self.glue = spin(0.5, 0, 5, 0.1, 2, " mm")
        self.bleed = spin(3, 0, 10, 0.5, 1, " mm")
        self.stack = spin(0, 0, 100, 0.1, 2, " mm")
        self.edge = spin(5, 0, 20, 0.5, 1, " mm")
        self.min_spine = spin(5, 0, 30, 0.5, 1, " mm")
        self.staple_warning = int_spin(60, 8, 400)
        form.addRow("Binding", self.binding)
        form.addRow("Extra inner margin (gutter), staples", self.gutter_staple)
        form.addRow("Extra inner margin (gutter), glue", self.gutter_glue)
        form.addRow(self.crop_marks)
        form.addRow(note("Paper profiles control the printer instructions and whether to convert interiors to grayscale."))
        for paper in ("A5", "A4", "A3"):
            duplex = QCheckBox("Duplex")
            flip = combo([("short", "Flip short edge"), ("long", "Flip long edge")])
            colour = combo([("grayscale", "Black and white"), ("color", "Colour")])
            row = QHBoxLayout()
            row.addWidget(duplex)
            row.addWidget(flip)
            row.addWidget(colour)
            self.paper_profiles[paper] = (duplex, flip, colour)
            form.addRow(f"{paper} paper profile", row)
        form.addRow("Paper thickness per sheet", self.thickness)
        form.addRow("Measured stack thickness (0 = not measured)", self.stack)
        form.addRow("Glue allowance", self.glue)
        form.addRow("Bleed (glue cover)", self.bleed)
        form.addRow("Printer's unprintable edge", self.edge)
        form.addRow("Smallest spine for spine text", self.min_spine)
        form.addRow("Warn when a stapled issue has more pages than", self.staple_warning)

        spine = QGroupBox("Spine calculator")
        spine_form = QFormLayout(spine)
        self.pages = int_spin(80, 4, 2000)
        self.pages.valueChanged.connect(self.calculate)
        self.result = QLabel()
        self.result.setWordWrap(True)
        spine_form.addRow("Interior pages", self.pages)
        spine_form.addRow(self.result)
        for box in (self.thickness, self.glue, self.bleed, self.stack, self.min_spine):
            box.valueChanged.connect(self.calculate)

        save = QPushButton("Save cover and print settings")
        save.setDefault(True)
        save.clicked.connect(self.save)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        for box in (cover, printing, spine):
            inner_layout.addWidget(box)
        inner_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(save)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll)
        layout.addLayout(bottom)
        state.issue_changed.connect(self.load)

    def load(self) -> None:
        issue = self.state.issue
        self.setEnabled(issue is not None)
        if issue is None:
            return
        s = issue.load()
        self.front.set_design(issue.assets / s.cover.front_image if s.cover.front_image else None,
                              s.cover.front_background, s.cover.front_pattern)
        self.back.set_design(issue.assets / s.cover.back_image if s.cover.back_image else None,
                             s.cover.back_background, s.cover.back_pattern)
        self.spine_text.setText(s.cover.spine_text)
        self.offprint_line.setChecked(s.cover.offprint_line)
        p = s.printing
        set_combo(self.binding, p.binding_mode)
        self.gutter_staple.setValue(p.gutter_staple_mm)
        self.gutter_glue.setValue(p.gutter_glue_mm)
        self.crop_marks.setChecked(p.crop_marks)
        for paper, controls in self.paper_profiles.items():
            profile = p.paper_profiles.get(paper, {})
            duplex, flip, colour = controls
            duplex.setChecked(profile.get("duplex", True))
            set_combo(flip, profile.get("flip_edge", "long" if paper == "A5" else "short"))
            set_combo(colour, profile.get("color_mode", "grayscale" if p.grayscale else "color"))
        self.thickness.setValue(p.paper_thickness_mm)
        self.glue.setValue(p.glue_allowance_mm)
        self.bleed.setValue(p.bleed_mm)
        self.stack.setValue(p.measured_stack_mm)
        self.edge.setValue(p.unprintable_edge_mm)
        self.min_spine.setValue(p.min_spine_for_text_mm)
        self.staple_warning.setValue(p.stapled_page_warning)
        total = sum(a.page_count for a in issue.load_articles(s)) + 8
        self.pages.setValue(max(4, total + total % 2))
        self.calculate()

    def collect(self):
        s = self.state.issue.load()
        s.cover.spine_text = self.spine_text.text().strip()
        s.cover.offprint_line = self.offprint_line.isChecked()
        s.cover.front_background = self.front.background
        s.cover.back_background = self.back.background
        s.cover.front_pattern = self.front.pattern.currentData()
        s.cover.back_pattern = self.back.pattern.currentData()
        p = s.printing
        p.binding_mode = self.binding.currentData()
        p.gutter_staple_mm = self.gutter_staple.value()
        p.gutter_glue_mm = self.gutter_glue.value()
        p.crop_marks = self.crop_marks.isChecked()
        p.paper_profiles = {
            paper: {"duplex": duplex.isChecked(), "flip_edge": flip.currentData(),
                    "color_mode": colour.currentData()}
            for paper, (duplex, flip, colour) in self.paper_profiles.items()
        }
        p.paper_thickness_mm = self.thickness.value()
        p.glue_allowance_mm = self.glue.value()
        p.bleed_mm = self.bleed.value()
        p.measured_stack_mm = self.stack.value()
        p.unprintable_edge_mm = self.edge.value()
        p.min_spine_for_text_mm = self.min_spine.value()
        p.stapled_page_warning = self.staple_warning.value()
        return s

    def save(self) -> None:
        if self.state.issue is None:
            return
        self.state.issue.save(self.collect())
        self.state.data_changed.emit()
        info(self, "Saved", "Cover and print settings saved.")

    def calculate(self) -> None:
        if self.state.issue is None:
            return
        s = self.collect()
        wrap = wrap_size(s.layout.page_size, self.pages.value(), physical(s),
                         measured_stack_mm=s.printing.measured_stack_mm or None)
        text = (f"Spine {wrap.spine_mm:g} mm. Glue cover wrap {wrap.width_mm:g} × {wrap.height_mm:g} mm "
                f"(with {wrap.bleed_mm:g} mm bleed). ")
        text += "Fits on A3." if fits_on_sheet(wrap, "A3") else "Too wide for A3: separate cover pages will be made."
        if not wrap.spine_text_allowed:
            text += " Spine too thin for text: it will be left blank."
        self.result.setText(text)

    def pick_image(self, field: str, pick: bool) -> None:
        issue = self.state.issue
        if issue is None:
            return
        s = self.collect()
        if pick:
            file, _ = QFileDialog.getOpenFileName(self, "Choose cover picture", "", "Images (*.png *.jpg *.jpeg)")
            if not file:
                picker = self.front if field == "front_image" else self.back
                picker.source.blockSignals(True)
                picker.source.setCurrentIndex(0 if not picker.image_path else 1)
                picker.source.blockSignals(False)
                return
            issue.assets.mkdir(parents=True, exist_ok=True)
            name = ("front" if field == "front_image" else "back") + Path(file).suffix.lower()
            shutil.copyfile(file, issue.assets / name)
            setattr(s.cover, field, name)
        else:
            setattr(s.cover, field, "")
        issue.save(s)
        self.load()
