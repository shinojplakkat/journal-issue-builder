"""The program window (blueprint M14)."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QPlainTextEdit, QPushButton, QTabWidget, QToolBar, QVBoxLayout,
                               QWidget, QDialog)

from .. import __version__
from ..tools.libreoffice import LIBREOFFICE
from .common import AppState, error, open_folder
from .screens.books import BooksScreen
from .screens.cover_print import CoverPrintScreen
from .screens.export import ExportScreen
from .screens.issue import IssueScreen, NewIssueDialog
from .screens.journal import JournalScreen
from .screens.layout import LayoutScreen
from .screens.offprints import OffprintsScreen
from .screens.review import ReviewScreen

APP_NAME = "Journal Issue Builder"

APP_STYLESHEET = """
QWidget { color: #1f2937; font-size: 10pt; }
QMainWindow, QDialog { background: #f3f6fb; }
QToolBar { background: #ffffff; border: 0; border-bottom: 1px solid #dbe3ef; spacing: 10px; padding: 8px 12px; }
QMenuBar { background: #ffffff; border-bottom: 1px solid #e2e8f0; padding: 3px 8px; }
QMenuBar::item { padding: 6px 10px; border-radius: 6px; }
QMenuBar::item:selected, QMenu::item:selected { background: #e8efff; color: #1d4ed8; }
QMenu { background: #ffffff; border: 1px solid #dbe3ef; padding: 6px; }
QMenu::item { padding: 7px 28px 7px 12px; border-radius: 5px; }
QTabWidget::pane { background: #f3f6fb; border: 0; }
QTabBar::tab { background: #e9eef6; color: #475569; padding: 10px 14px; margin-right: 4px; border-top-left-radius: 9px; border-top-right-radius: 9px; }
QTabBar::tab:selected { background: #ffffff; color: #1d4ed8; font-weight: 600; }
QGroupBox { background: #ffffff; border: 1px solid #dce4ef; border-radius: 11px; margin-top: 14px; padding: 14px 10px 10px 10px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: #334155; }
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTableWidget, QListWidget, QTreeWidget {
  background: #ffffff; border: 1px solid #cbd5e1; border-radius: 7px; padding: 5px 7px; selection-background-color: #dbeafe; selection-color: #1e3a8a;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
  border: 1px solid #3b82f6;
}
QPushButton { background: #e9eff8; border: 1px solid #d2dce9; border-radius: 8px; padding: 8px 13px; color: #24364b; }
QPushButton:hover { background: #dce8f8; border-color: #a9c4e8; }
QPushButton:pressed { background: #cbdcf3; }
QPushButton:disabled { color: #94a3b8; background: #eef2f7; }
QCheckBox { spacing: 7px; }
QHeaderView::section { background: #eef3f9; color: #334155; border: 0; border-bottom: 1px solid #dbe3ef; padding: 8px; font-weight: 600; }
QScrollArea { background: transparent; border: 0; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 3px; }
QScrollBar::handle:vertical { background: #c2ccda; border-radius: 5px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #94a3b8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QStatusBar { background: #ffffff; border-top: 1px solid #dbe3ef; color: #64748b; }
"""


def default_journal_folder() -> Path:
    documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    base = Path(documents) if documents else Path.home()
    return base / APP_NAME / "Sample Journal"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        app = QApplication.instance()
        if app is not None:
            app.setStyle("Fusion")
            app.setStyleSheet(APP_STYLESHEET)
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.settings = QSettings("JournalIssueBuilder", "JournalIssueBuilder")
        self._fit_to_available_screen()
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinimizeButtonHint |
                            Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowCloseButtonHint)
        self.state = AppState()

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
            ("Book Publishing", BooksScreen(self.settings)),
        ]
        for title, screen in self.screens:
            self.tabs.addTab(screen, title)
        self.setCentralWidget(self.tabs)
        self.statusBar().showMessage("Ready")
        self.build_menus()
        self.state.journal_changed.connect(self.refresh_issue_list)
        self.state.issue_changed.connect(self.refresh_issue_list)

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
        window_menu = self.menuBar().addMenu("&Window")
        minimize = QAction("Minimize window", self)
        minimize.setShortcut("Ctrl+Shift+I")
        minimize.triggered.connect(self.showMinimized)
        window_menu.addAction(minimize)
        maximize = QAction("Maximize window", self)
        maximize.setShortcut("Ctrl+Shift+M")
        maximize.triggered.connect(self.showMaximized)
        window_menu.addAction(maximize)
        restore = QAction("Restore window size", self)
        restore.setShortcut("Ctrl+Shift+N")
        restore.triggered.connect(self.showNormal)
        window_menu.addAction(restore)
        help_menu = self.menuBar().addMenu("&Help")
        check = QAction("System check…", self)
        check.triggered.connect(self.system_check)
        help_menu.addAction(check)
        about = QAction("About", self)
        about.triggered.connect(lambda: QMessageBox.about(
            self, APP_NAME, f"<b>{APP_NAME}</b> {__version__}<br>Creates journal issues and edited books from Word, ODT and PDF submissions.<br><br>"
                            "Licence: GNU AGPL-3.0. Uses LibreOffice, pikepdf, ReportLab, pdfplumber, pypdfium2, python-docx and Qt (PySide6)."))
        help_menu.addAction(about)

    def _fit_to_available_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(1100, 700)
            self.setMinimumSize(680, 480)
            return
        area = screen.availableGeometry()
        width = min(1200, max(600, area.width() - 48))
        height = min(740, max(480, area.height() - 72))
        self.setMinimumSize(min(760, width), min(540, height))
        self.resize(width, height)
        self.move(area.x() + (area.width() - width) // 2,
                  area.y() + (area.height() - height) // 2)

    def start(self) -> None:
        last = self.settings.value("journal_folder", "")
        folder = Path(last) if last else default_journal_folder()
        first_run = not (folder / "journal.json").is_file()
        try:
            self.state.open_journal(folder)
        except OSError as problem:
            error(self, "Journal folder", f"Could not open {folder}:\\n{problem}")
            return
        self.settings.setValue("journal_folder", str(folder))
        if first_run and not self.state.journal.list_issues():
            from datetime import date
            issue = self.state.journal.create_issue(1, 1, "January", date.today().year + 1)
            self.state.open_issue(issue)
            QMessageBox.information(self, "Welcome", f"A sample journal was created in:\\n{folder}\\n\\nReplace the sample details on the Journal screen, then add articles on the Issue screen.")
        if LIBREOFFICE.find() is None:
            QMessageBox.warning(self, "LibreOffice not found", LIBREOFFICE.install_hint + "\\n\\nWithout LibreOffice, Word and ODT articles cannot be laid out.")

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
