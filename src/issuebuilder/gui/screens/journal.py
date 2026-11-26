"""Journal settings screen (blueprint M1): every publication detail, editable."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from ...settings.models import GLUE, STAPLE, BoardMember, JournalSettings
from ..common import AppState, ask, combo, heading, info, note


class JournalScreen(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.loaded_title = ""
        self.fields: dict[str, QLineEdit] = {}
        self.texts: dict[str, QPlainTextEdit] = {}

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.addRow(heading("Publication"))
        for key, label in (("title", "Journal title"), ("short_title", "Short title (headers, spine)"),
                           ("abbreviation", "Abbreviation"), ("print_issn", "Print ISSN"),
                           ("e_issn", "Online ISSN"), ("frequency", "Frequency"),
                           ("doi_prefix", "DOI prefix (optional)")):
            self.fields[key] = QLineEdit()
            form.addRow(label, self.fields[key])
        form.addRow(heading("Publisher"))
        for key, label in (("publisher", "Publisher"), ("address", "Address"), ("website", "Website"),
                           ("email", "Email")):
            self.fields[key] = QLineEdit()
            form.addRow(label, self.fields[key])

        form.addRow(heading("Logo"))
        self.logo_preview = QLabel("No logo")
        self.logo_preview.setFixedHeight(90)
        self.logo_preview.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        choose = QPushButton("Choose logo…")
        choose.clicked.connect(self.choose_logo)
        remove = QPushButton("Remove logo")
        remove.clicked.connect(self.remove_logo)
        logo_row = QHBoxLayout()
        logo_row.addWidget(self.logo_preview, 1)
        logo_row.addWidget(choose)
        logo_row.addWidget(remove)
        form.addRow("Logo image", logo_row)

        form.addRow(heading("Editors"))
        self.fields["editor_in_chief"] = QLineEdit()
        form.addRow("Editor-in-Chief", self.fields["editor_in_chief"])
        self.texts["editors"] = QPlainTextEdit()
        self.texts["editors"].setFixedHeight(70)
        form.addRow("Editors (one per line)", self.texts["editors"])

        self.board = QTableWidget(0, 3)
        self.board.setHorizontalHeaderLabels(["Name", "Role", "Institution"])
        self.board.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.board.setMinimumHeight(140)
        add_member = QPushButton("Add member")
        add_member.clicked.connect(lambda: self.board.insertRow(self.board.rowCount()))
        remove_member = QPushButton("Remove selected")
        remove_member.clicked.connect(self.remove_member)
        buttons = QHBoxLayout()
        buttons.addWidget(add_member)
        buttons.addWidget(remove_member)
        buttons.addStretch()
        board_box = QVBoxLayout()
        board_box.addWidget(self.board)
        board_box.addLayout(buttons)
        form.addRow("Editorial board", board_box)

        form.addRow(heading("Statements"))
        for key, label in (("aims_scope", "Aims and scope"), ("peer_review", "Peer-review statement"),
                           ("copyright_text", "Copyright text"), ("licence", "Licence (used everywhere)"),
                           ("notes_for_authors", "Notes for authors")):
            self.texts[key] = QPlainTextEdit()
            self.texts[key].setFixedHeight(64)
            form.addRow(label, self.texts[key])

        form.addRow(heading("Defaults for new issues"))
        self.page_size = combo([("A5", "A5 (148 × 210 mm)"), ("A4", "A4 (210 × 297 mm)")])
        self.binding = combo([(STAPLE, "Staples (saddle stitch)"), (GLUE, "Glue binding (professional)")])
        form.addRow("Page size", self.page_size)
        form.addRow("Binding", self.binding)

        save = QPushButton("Save journal details")
        save.setDefault(True)
        save.clicked.connect(self.save)
        self.folder_label = note("")

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.addWidget(note("These details appear on the title page, imprint, masthead, covers and in "
                                    "the PDF information. Replace the sample values with your journal's."))
        inner_layout.addLayout(form)
        inner_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)

        bottom = QHBoxLayout()
        bottom.addWidget(self.folder_label, 1)
        bottom.addWidget(save)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll)
        layout.addLayout(bottom)

        state.journal_changed.connect(self.load)

    # ------------------------------------------------------------------ load / save

    def load(self) -> None:
        if self.state.journal is None:
            return
        j = self.state.journal.load_journal()
        self.loaded_title = j.title
        for key, field in self.fields.items():
            field.setText(str(getattr(j, key)))
        for key, text in self.texts.items():
            value = getattr(j, key)
            text.setPlainText("\n".join(value) if isinstance(value, list) else value)
        self.board.setRowCount(0)
        for member in j.board:
            row = self.board.rowCount()
            self.board.insertRow(row)
            for col, value in enumerate((member.name, member.role, member.institution)):
                self.board.setItem(row, col, QTableWidgetItem(value))
        from ..common import set_combo

        set_combo(self.page_size, j.default_page_size)
        set_combo(self.binding, j.default_binding)
        self.show_logo(j)
        self.folder_label.setText(f"Journal folder: {self.state.journal.root}")

    def collect(self) -> JournalSettings:
        j = self.state.journal.load_journal()
        for key, field in self.fields.items():
            setattr(j, key, field.text().strip())
        for key, text in self.texts.items():
            value = text.toPlainText().strip()
            if key == "editors":
                setattr(j, key, [line.strip() for line in value.splitlines() if line.strip()])
            else:
                setattr(j, key, value)
        members = []
        for row in range(self.board.rowCount()):
            cells = [(self.board.item(row, c).text().strip() if self.board.item(row, c) else "") for c in range(3)]
            if any(cells):
                members.append(BoardMember(*cells))
        j.board = members
        j.default_page_size = self.page_size.currentData()
        j.default_binding = self.binding.currentData()
        return j

    def save(self) -> None:
        if self.state.journal is None:
            return
        j = self.collect()
        if self.loaded_title and j.title != self.loaded_title:
            if not ask(self, "Journal title changed",
                       "An ISSN is tied to the journal title. Changing the title may need a new ISSN "
                       "from the ISSN centre.\n\nSave the new title?"):
                return
        self.state.journal.save_journal(j)
        self.loaded_title = j.title
        self.state.data_changed.emit()
        info(self, "Saved", "Journal details saved.")

    # ------------------------------------------------------------------ logo / board

    def show_logo(self, j: JournalSettings) -> None:
        path = self.state.journal.logo_path(j)
        if path is None:
            self.logo_preview.setText("No logo")
            self.logo_preview.setPixmap(QPixmap())
            return
        pixmap = QPixmap(str(path))
        self.logo_preview.setPixmap(pixmap.scaledToHeight(84, Qt.TransformationMode.SmoothTransformation))

    def choose_logo(self) -> None:
        if self.state.journal is None:
            return
        file, _ = QFileDialog.getOpenFileName(self, "Choose logo", "", "Images (*.png *.jpg *.jpeg)")
        if not file:
            return
        j = self.collect()
        self.state.journal.set_logo(j, Path(file))
        self.state.journal.save_journal(j)
        self.show_logo(j)

    def remove_logo(self) -> None:
        if self.state.journal is None:
            return
        j = self.collect()
        j.logo = ""
        self.state.journal.save_journal(j)
        self.show_logo(j)

    def remove_member(self) -> None:
        rows = sorted({i.row() for i in self.board.selectedIndexes()}, reverse=True)
        for row in rows:
            self.board.removeRow(row)
