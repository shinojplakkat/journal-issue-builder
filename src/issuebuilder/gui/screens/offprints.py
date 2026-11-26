"""Offprints screen (blueprint M12)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QGroupBox, QHBoxLayout, QListWidget, QListWidgetItem, QPlainTextEdit,
                               QPushButton, QVBoxLayout, QWidget)

from ...assembler.issue import make_plan
from ...cover.wrap import cover_pages
from ...outputs.offprint import make_offprints
from ..common import AppState, Worker, error, info, note, open_folder


class OffprintsScreen(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.worker: Worker | None = None
        self.list = QListWidget()
        all_button = QPushButton("Select all")
        all_button.clicked.connect(lambda: self.check_all(True))
        none_button = QPushButton("Select none")
        none_button.clicked.connect(lambda: self.check_all(False))
        select = QHBoxLayout()
        select.addWidget(all_button)
        select.addWidget(none_button)
        select.addStretch()

        options = QGroupBox("Options")
        opt = QVBoxLayout(options)
        self.electronic = QCheckBox("Electronic offprint PDF")
        self.electronic.setChecked(True)
        self.printed = QCheckBox("Print offprint (stapled booklet, imposed, pages in fours)")
        self.renumber = QCheckBox("Renumber pages from 1 (normally the issue page numbers are kept)")
        self.cite = QCheckBox("Add a 'How to cite' line")
        self.cite.setChecked(True)
        self.cover_line = QCheckBox("'OFFPRINT' band with author names on the cover")
        self.cover_line.setChecked(True)
        for box in (self.electronic, self.printed, self.renumber, self.cite, self.cover_line):
            opt.addWidget(box)

        self.build_button = QPushButton("Make offprints")
        self.build_button.clicked.connect(self.build)
        open_button = QPushButton("Open offprints folder")
        open_button.clicked.connect(lambda: self.state.issue and open_folder(self.state.issue.output / "offprints"))
        buttons = QHBoxLayout()
        buttons.addWidget(self.build_button)
        buttons.addWidget(open_button)
        buttons.addStretch()
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)

        layout = QVBoxLayout(self)
        layout.addWidget(note("An offprint is one article with the issue's cover, the publication details and the "
                              "back cover. Files are named volX-issueY_Surname_ShortTitle.pdf."))
        layout.addWidget(self.list, 1)
        layout.addLayout(select)
        layout.addWidget(options)
        layout.addLayout(buttons)
        layout.addWidget(self.log, 1)
        state.issue_changed.connect(self.load)
        state.data_changed.connect(self.load)

    def load(self) -> None:
        self.list.clear()
        self.setEnabled(self.state.issue is not None)
        if self.state.issue is None:
            return
        for a in self.state.issue.load_articles():
            if a.import_status != "ok":
                continue
            pages = f"  (pp. {a.start_page}–{a.end_page})" if a.start_page else ""
            item = QListWidgetItem(f"{a.author_names or 'No author'} — {a.title or a.source_name}{pages}")
            item.setData(Qt.ItemDataRole.UserRole, a.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.list.addItem(item)

    def check_all(self, on: bool) -> None:
        for n in range(self.list.count()):
            self.list.item(n).setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)

    def build(self) -> None:
        if self.state.issue is None or (self.worker is not None and self.worker.isRunning()):
            return
        chosen = [self.list.item(n).data(Qt.ItemDataRole.UserRole) for n in range(self.list.count())
                  if self.list.item(n).checkState() == Qt.CheckState.Checked]
        if not chosen:
            info(self, "Offprints", "Tick at least one article.")
            return
        if not (self.electronic.isChecked() or self.printed.isChecked()):
            info(self, "Offprints", "Choose electronic, print, or both.")
            return
        journal_folder, issue_folder = self.state.journal, self.state.issue
        options = dict(electronic=self.electronic.isChecked(), printed=self.printed.isChecked(),
                       renumber=self.renumber.isChecked(), cite=self.cite.isChecked(),
                       cover_line=self.cover_line.isChecked())

        def job(progress):
            plan = make_plan(journal_folder, issue_folder, progress)
            journal, issue = journal_folder.load_journal(), issue_folder.load()
            progress("Making covers")
            covers = cover_pages(journal_folder, issue_folder, journal, issue)
            progress("Making offprints")
            return make_offprints(plan, journal, issue, covers, issue_folder.output / "offprints", chosen, **options)

        self.build_button.setEnabled(False)
        self.log.setPlainText("Working…")
        self.worker = Worker(job, self)
        self.worker.progress.connect(self.log.setPlainText)
        self.worker.finished_ok.connect(self.done)
        self.worker.failed.connect(self.failed)
        self.worker.start()

    def done(self, result) -> None:
        files, notes = result
        self.build_button.setEnabled(True)
        self.log.setPlainText("\n".join(notes + [""] + [str(f) for f in files]))
        self.state.data_changed.emit()
        if files:
            open_folder(self.state.issue.output / "offprints")

    def failed(self, text: str) -> None:
        self.build_button.setEnabled(True)
        self.log.setPlainText("Offprints could not be made.")
        error(self, "Offprints", text)
