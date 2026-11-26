"""The program window (blueprint M14)."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QPlainTextEdit, QPushButton, QTabWidget, QToolBar, QVBoxLayout,
                               QWidget, QDialog)

from .. import __version__
from ..tools.libreoffice import LIBREOFFICE
from .common import AppState, error, open_folder
from .screens.cover_print import CoverPrintScreen
from .screens.export import ExportScreen
from .screens.issue import IssueScreen, NewIssueDialog
from .screens.journal import JournalScreen
from .screens.layout import LayoutScreen
from .screens.offprints import OffprintsScreen
from .screens.review import ReviewScreen

APP_NAME = "Journal Issue Builder"


def default_journal_folder() -> Path:
    documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    base = Path(documents) if documents else Path.home()
    return base / APP_NAME / "Sample Journal"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1200, 820)
        self.settings = QSettings("JournalIssueBuilder", "JournalIssueBuilder")
        self.state = AppState()

        # Top bar: journal folder and issue choice
        toolbar = QToolBar("Issue")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        self.journal_label = QLabel()
        self.issue_box = QComboBox()
        self.issue_box.setMinimumWidth(320)
        self.issue_box.activated.connect(self.issue_chosen)
        new_issue = QPushButton("New issue…")
        new_issue.clicked.connect(self.new_issue)
        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(6, 2, 6, 2)
        bar_layout.addWidget(self.journal_label, 1)
        bar_layout.addWidget(QLabel("Issue:"))
        bar_layout.addWidget(self.issue_box)
        bar_layout.addWidget(new_issue)
        toolbar.addWidget(bar)

        self.tabs = QTabWidget()
        self.screens = [
            ("Journal", JournalScreen(self.state)),
            ("Issue", IssueScreen(self.state)),
            ("Review", ReviewScreen(self.state)),
            ("Layout", LayoutScreen(self.state)),
            ("Cover and print", CoverPrintScreen(self.state)),
            ("Export", ExportScreen(self.state)),
            ("Offprints", OffprintsScreen(self.state)),
        ]
        for title, screen in self.screens:
            self.tabs.addTab(screen, title)
        self.setCentralWidget(self.tabs)
        self.statusBar().showMessage("Ready")

        self.build_menus()
        self.state.journal_changed.connect(self.refresh_issue_list)
        self.state.issue_changed.connect(self.refresh_issue_list)

    # ------------------------------------------------------------------ menus

    def build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        for text, slot in (("New journal folder…", self.new_journal), ("Open journal folder…", self.open_journal),
                           ("Show journal folder", lambda: self.state.journal and open_folder(self.state.journal.root)),
                           ("Show issue folder", lambda: self.state.issue and open_folder(self.state.issue.path))):
            action = QAction(text, self)
            action.triggered.connect(slot)
            file_menu.addAction(action)
        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        help_menu = self.menuBar().addMenu("&Help")
        check = QAction("System check…", self)
        check.triggered.connect(self.system_check)
        help_menu.addAction(check)
        about = QAction("About", self)
        about.triggered.connect(lambda: QMessageBox.about(
            self, APP_NAME, f"<b>{APP_NAME}</b> {__version__}<br>Assembles journal issues from Word, ODT and "
                            "PDF articles: electronic and print files, covers and offprints.<br><br>"
                            "Licence: GNU AGPL-3.0. Uses LibreOffice, pikepdf, ReportLab, pdfplumber, "
                            "pypdfium2, python-docx and Qt (PySide6)."))
        help_menu.addAction(about)

    # ------------------------------------------------------------------ journal and issue

    def start(self) -> None:
        last = self.settings.value("journal_folder", "")
        folder = Path(last) if last else default_journal_folder()
        first_run = not (folder / "journal.json").is_file()
        try:
            self.state.open_journal(folder)
        except OSError as problem:
            error(self, "Journal folder", f"Could not open {folder}:\n{problem}")
            return
        self.settings.setValue("journal_folder", str(folder))
        if first_run and not self.state.journal.list_issues():
            # Start with an issue so every screen can be explored at once.
            from datetime import date

            issue = self.state.journal.create_issue(1, 1, "January", date.today().year + 1)
            self.state.open_issue(issue)
            QMessageBox.information(
                self, "Welcome",
                f"A sample journal was created in:\n{folder}\n\nReplace the sample details on the Journal screen, "
                "then add articles on the Issue screen.")
        if LIBREOFFICE.find() is None:
            QMessageBox.warning(self, "LibreOffice not found", LIBREOFFICE.install_hint +
                                "\n\nWithout LibreOffice, Word and ODT articles cannot be laid out.")

    def refresh_issue_list(self) -> None:
        journal = self.state.journal
        self.issue_box.clear()
        if journal is None:
            return
        self.journal_label.setText(f"<b>{journal.load_journal().title}</b>")
        current = self.state.issue.path if self.state.issue else None
        for issue in journal.list_issues():
            self.issue_box.addItem(issue.load().label, str(issue.path))
            if current is not None and issue.path == current:
                self.issue_box.setCurrentIndex(self.issue_box.count() - 1)

    def issue_chosen(self) -> None:
        path = self.issue_box.currentData()
        if path and self.state.journal and (self.state.issue is None or str(self.state.issue.path) != path):
            match = [i for i in self.state.journal.list_issues() if str(i.path) == path]
            if match:
                self.state.open_issue(match[0])

    def new_issue(self) -> None:
        journal = self.state.journal
        if journal is None:
            return
        issues = [i.load() for i in journal.list_issues()]
        last = issues[-1] if issues else None
        dialog = NewIssueDialog(self, last.volume if last else 1, (last.number + 1) if last else 1,
                                last.year if last else 2027)
        if dialog.exec():
            try:
                issue = journal.create_issue(dialog.volume.value(), dialog.number.value(),
                                             dialog.month.currentData(), dialog.year.value(),
                                             dialog.title.text().strip())
            except FileExistsError as problem:
                error(self, "New issue", str(problem))
                return
            self.state.open_issue(issue)
            self.tabs.setCurrentIndex(1)

    def new_journal(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose an empty folder for the new journal")
        if folder:
            self.switch_journal(Path(folder))

    def open_journal(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open a journal folder (it contains journal.json)")
        if folder:
            if not (Path(folder) / "journal.json").is_file():
                error(self, "Open journal", "That folder has no journal.json. Use 'New journal folder' instead.")
                return
            self.switch_journal(Path(folder))

    def switch_journal(self, folder: Path) -> None:
        self.state.open_journal(folder)
        self.settings.setValue("journal_folder", str(folder))
        self.tabs.setCurrentIndex(0)

    def system_check(self) -> None:
        import contextlib
        import io

        from ..doctor import run_doctor

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            run_doctor()
        dialog = QDialog(self)
        dialog.setWindowTitle("System check")
        dialog.resize(760, 420)
        text = QPlainTextEdit(buffer.getvalue())
        text.setReadOnly(True)
        layout = QVBoxLayout(dialog)
        layout.addWidget(text)
        dialog.exec()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = MainWindow()
    window.show()
    window.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
