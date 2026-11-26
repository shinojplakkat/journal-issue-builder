"""Cover and print screen (blueprint M9, M10)."""

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from ...cover.spine import fits_on_sheet, wrap_size
from ...cover.wrap import physical
from ...settings.models import GLUE, STAPLE
from ..common import AppState, combo, info, int_spin, note, set_combo, spin


class ImagePicker(QWidget):
    def __init__(self, title: str, on_change):
        super().__init__()
        self.on_change = on_change
        self.preview = QLabel("None: generated from the journal details")
        self.preview.setFixedSize(130, 180)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setWordWrap(True)
        self.preview.setStyleSheet("border: 1px solid #aaa;")
        choose = QPushButton(f"Choose {title}…")
        choose.clicked.connect(lambda: self.on_change(True))
        clear = QPushButton("Use generated")
        clear.clicked.connect(lambda: self.on_change(False))
        buttons = QVBoxLayout()
        buttons.addWidget(choose)
        buttons.addWidget(clear)
        buttons.addStretch()
        row = QHBoxLayout(self)
        row.addWidget(self.preview)
        row.addLayout(buttons)
        row.addStretch()

    def show_image(self, path: Path | None) -> None:
        if path is not None and path.is_file():
            self.preview.setPixmap(QPixmap(str(path)).scaled(126, 176, Qt.AspectRatioMode.KeepAspectRatio,
                                                             Qt.TransformationMode.SmoothTransformation))
        else:
            self.preview.setPixmap(QPixmap())
            self.preview.setText("None: generated from the journal details")


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
        cover_form.addRow(note("A front cover picture is usually A4 portrait; it scales exactly to A5. "
                               "Without a picture, a plain cover is made from the journal details."))
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
        self.grayscale = QCheckBox("Convert the interior to grayscale (needs Ghostscript)")
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
        form.addRow(self.grayscale)
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
        self.front.show_image(issue.assets / s.cover.front_image if s.cover.front_image else None)
        self.back.show_image(issue.assets / s.cover.back_image if s.cover.back_image else None)
        self.spine_text.setText(s.cover.spine_text)
        self.offprint_line.setChecked(s.cover.offprint_line)
        p = s.printing
        set_combo(self.binding, p.binding_mode)
        self.gutter_staple.setValue(p.gutter_staple_mm)
        self.gutter_glue.setValue(p.gutter_glue_mm)
        self.grayscale.setChecked(p.grayscale)
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
        p = s.printing
        p.binding_mode = self.binding.currentData()
        p.gutter_staple_mm = self.gutter_staple.value()
        p.gutter_glue_mm = self.gutter_glue.value()
        p.grayscale = self.grayscale.isChecked()
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
                return
            issue.assets.mkdir(parents=True, exist_ok=True)
            name = ("front" if field == "front_image" else "back") + Path(file).suffix.lower()
            shutil.copyfile(file, issue.assets / name)
            setattr(s.cover, field, name)
        else:
            setattr(s.cover, field, "")
        issue.save(s)
        self.load()
