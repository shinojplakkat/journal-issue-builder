"""Export screen (blueprint M13, M14): checks, outputs, progress."""

from __future__ import annotations

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QPlainTextEdit, QProgressBar, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from ...checks.validation import check_issue
from ...outputs.export import run_export
from ..common import AppState, Worker, ask, error, note, open_file, open_folder


class ExportScreen(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.worker: Worker | None = None

        outputs = QGroupBox("Outputs")
        out_layout = QVBoxLayout(outputs)
        self.options = {
            "electronic_issue": QCheckBox("Electronic issue (one PDF with bookmarks and links)"),
            "electronic_articles": QCheckBox("Electronic article PDFs (one per article, same page numbers)"),
            "include_covers_in_electronic": QCheckBox("Include the covers in the electronic issue"),
            "keep_blank_pages": QCheckBox("Keep blank pages in the electronic issue"),
            "print_interior": QCheckBox("Print interior (for the binding chosen on the Cover and print screen)"),
            "print_cover": QCheckBox("Print cover"),
            "proof_watermark": QCheckBox("Add a 'PROOF' watermark (author proofs; switch off for the final export)"),
        }
        for box in self.options.values():
            out_layout.addWidget(box)
            box.toggled.connect(self.save_options)

        checks = QGroupBox("Checks")
        checks_layout = QVBoxLayout(checks)
        self.findings = QTableWidget(0, 3)
        self.findings.setHorizontalHeaderLabels(["Level", "Where", "Message"])
        self.findings.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.findings.setColumnWidth(1, 260)
        self.findings.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        run_checks = QPushButton("Run checks")
        run_checks.clicked.connect(self.run_checks)
        checks_layout.addWidget(self.findings)
        checks_layout.addWidget(run_checks)

        self.export_button = QPushButton("Export")
        self.export_button.setDefault(True)
        self.export_button.clicked.connect(self.export)
        open_button = QPushButton("Open output folder")
        open_button.clicked.connect(lambda: self.state.issue and open_folder(self.state.issue.output))
        log_button = QPushButton("Open export log")
        log_button.clicked.connect(self.open_log)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.step = QLabel("")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        buttons = QHBoxLayout()
        buttons.addWidget(self.export_button)
        buttons.addWidget(open_button)
        buttons.addWidget(log_button)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(outputs)
        layout.addWidget(checks, 1)
        layout.addLayout(buttons)
        layout.addWidget(self.progress)
        layout.addWidget(self.step)
        layout.addWidget(note("Results and notes:"))
        layout.addWidget(self.log, 1)
        state.issue_changed.connect(self.load)

    def load(self) -> None:
        self.setEnabled(self.state.issue is not None)
        if self.state.issue is None:
            return
        export = self.state.issue.load().export
        for key, box in self.options.items():
            box.blockSignals(True)
            box.setChecked(bool(getattr(export, key)))
            box.blockSignals(False)
        self.findings.setRowCount(0)

    def save_options(self) -> None:
        if self.state.issue is None:
            return
        s = self.state.issue.load()
        for key, box in self.options.items():
            setattr(s.export, key, box.isChecked())
        self.state.issue.save(s)

    def show_findings(self, findings) -> None:
        self.findings.setRowCount(0)
        for f in findings:
            row = self.findings.rowCount()
            self.findings.insertRow(row)
            colour = QColor("#ffcdd2") if f.level == "error" else QColor("#fff9c4")
            for col, value in enumerate((f.level.capitalize(), f.where, f.message)):
                item = QTableWidgetItem(value)
                item.setBackground(QBrush(colour))
                self.findings.setItem(row, col, item)
        if not findings:
            self.findings.insertRow(0)
            self.findings.setItem(0, 0, QTableWidgetItem("OK"))
            self.findings.setItem(0, 2, QTableWidgetItem("No problems found."))

    def run_checks(self):
        if self.state.issue is None:
            return []
        findings = check_issue(self.state.journal, self.state.issue)
        self.show_findings(findings)
        return findings

    def export(self) -> None:
        if self.state.issue is None or (self.worker is not None and self.worker.isRunning()):
            return
        self.save_options()
        findings = self.run_checks()
        force = False
        if any(f.level == "error" for f in findings):
            if not ask(self, "Errors found", "The checks found errors (red rows). Export anyway, for a draft?"):
                return
            force = True
        journal, issue = self.state.journal, self.state.issue
        self.export_button.setEnabled(False)
        self.progress.setRange(0, 0)  # busy indicator
        self.log.clear()
        self.worker = Worker(lambda progress: run_export(journal, issue, progress, force=force), self)
        self.worker.progress.connect(self.step.setText)
        self.worker.finished_ok.connect(self.done)
        self.worker.failed.connect(self.failed)
        self.worker.start()

    def done(self, result) -> None:
        self.export_button.setEnabled(True)
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        lines = ["Export finished." if result.ok else "Export finished with problems."]
        lines += [f"• {n}" for n in result.notes]
        lines.append("")
        lines.append("Files:")
        lines += [f"  {f}" for f in result.files]
        self.log.setPlainText("\n".join(lines))
        self.state.data_changed.emit()
        if result.ok and result.files:
            open_folder(self.state.issue.output)

    def failed(self, text: str) -> None:
        self.export_button.setEnabled(True)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        error(self, "Export failed", text)

    def open_log(self) -> None:
        if self.state.issue is None:
            return
        log = self.state.issue.output / "export_log.txt"
        if log.is_file():
            open_file(log)
