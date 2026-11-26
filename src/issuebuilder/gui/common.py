"""Shared pieces for the program window: app state, background jobs, small helpers."""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFrame, QLabel, QMessageBox, QSpinBox,
                               QWidget)

from ..settings.load_save import IssueFolder, JournalFolder


class AppState(QObject):
    """The journal and issue currently open. Screens listen to its signals."""

    journal_changed = Signal()
    issue_changed = Signal()
    data_changed = Signal()   # articles or settings changed somewhere

    def __init__(self):
        super().__init__()
        self.journal: JournalFolder | None = None
        self.issue: IssueFolder | None = None

    def open_journal(self, folder: Path) -> None:
        self.journal = JournalFolder.create(folder)
        issues = self.journal.list_issues()
        self.issue = issues[-1] if issues else None
        self.journal_changed.emit()
        self.issue_changed.emit()

    def open_issue(self, issue: IssueFolder | None) -> None:
        self.issue = issue
        self.issue_changed.emit()


class Worker(QThread):
    """Runs a slow job (LibreOffice, PDF building) without freezing the window."""

    progress = Signal(str)
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, job: Callable[[Callable[[str], None]], object], parent=None):
        super().__init__(parent)
        self._job = job

    def run(self) -> None:
        try:
            result = self._job(self.progress.emit)
        except Exception as error:
            self.failed.emit(f"{error}\n\n{traceback.format_exc()}")
            return
        self.finished_ok.emit(result)


def open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def open_file(path: Path) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def info(parent: QWidget, title: str, text: str) -> None:
    QMessageBox.information(parent, title, text)


def error(parent: QWidget, title: str, text: str) -> None:
    QMessageBox.critical(parent, title, text)


def ask(parent: QWidget, title: str, text: str) -> bool:
    return QMessageBox.question(parent, title, text) == QMessageBox.StandardButton.Yes


def combo(items: list[tuple[str, str]], current: str = "") -> QComboBox:
    """A drop-down showing labels and storing values: items = [(value, label), ...]."""
    box = QComboBox()
    for value, label in items:
        box.addItem(label, value)
    set_combo(box, current)
    return box


def set_combo(box: QComboBox, value: str) -> None:
    index = box.findData(value)
    if index >= 0:
        box.setCurrentIndex(index)


def spin(value: float, low: float, high: float, step: float = 0.5, decimals: int = 1, suffix: str = "") -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(low, high)
    box.setDecimals(decimals)
    box.setSingleStep(step)
    box.setValue(value)
    if suffix:
        box.setSuffix(suffix)
    return box


def int_spin(value: int, low: int, high: int) -> QSpinBox:
    box = QSpinBox()
    box.setRange(low, high)
    box.setValue(value)
    return box


def heading(text: str) -> QLabel:
    label = QLabel(f"<b>{text}</b>")
    label.setContentsMargins(0, 8, 0, 2)
    return label


def note(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: #555;")
    return label


def line() -> QFrame:
    frame = QFrame()
    frame.setFrameShape(QFrame.Shape.HLine)
    frame.setFrameShadow(QFrame.Shadow.Sunken)
    return frame


class NeedsIssue(QLabel):
    """Shown on screens that need an open issue."""

    def __init__(self):
        super().__init__("Create or open an issue first (Issue screen, 'New issue').")
        self.setWordWrap(True)
