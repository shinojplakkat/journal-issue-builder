"""Issue screen (blueprint M2): issue details and the ordered list of articles."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QFileDialog,
                               QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from ...importers.convert import SUPPORTED, import_files, reanalyse
from ...settings.models import (ANY, ARTICLE_TYPES, LEFT, MODE_JOURNAL, MODE_ORIGINAL, MODE_PDF, MONTHS,
                                RIGHT, Article, Author)
from ..common import AppState, Worker, ask, combo, error, info, int_spin, note

MODE_LABELS = {MODE_JOURNAL: "Journal style", MODE_ORIGINAL: "Author's style", MODE_PDF: "PDF as sent"}
STATUS_LABELS = {"needs_review": "Needs review", "reviewed": "Reviewed", "keep_original": "Keep original"}


class NewIssueDialog(QDialog):
    def __init__(self, parent, volume: int, number: int, year: int):
        super().__init__(parent)
        self.setWindowTitle("New issue")
        form = QFormLayout(self)
        self.volume = int_spin(volume, 1, 999)
        self.number = int_spin(number, 1, 99)
        self.month = combo([(m, m) for m in MONTHS])
        self.year = int_spin(year, 1900, 2200)
        self.title = QLineEdit()
        self.title.setPlaceholderText("Optional, e.g. Special issue on …")
        form.addRow("Volume", self.volume)
        form.addRow("Issue number", self.number)
        form.addRow("Month", self.month)
        form.addRow("Year", self.year)
        form.addRow("Issue title", self.title)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)


class ArticleDialog(QDialog):
    """Every detail of one article (blueprint M2, M4b)."""

    def __init__(self, parent, article: Article):
        super().__init__(parent)
        self.article = article
        self.setWindowTitle(f"Article {article.id}: details")
        self.resize(760, 720)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.type = combo([(t, t) for t in ARTICLE_TYPES], article.type)
        self.title = QLineEdit(article.title)
        self.subtitle = QLineEdit(article.subtitle)
        self.short_title = QLineEdit(article.short_title)
        self.short_title.setPlaceholderText("For the running header; leave empty to use the title")
        form.addRow("Type", self.type)
        form.addRow("Title", self.title)
        form.addRow("Subtitle", self.subtitle)
        form.addRow("Short title", self.short_title)

        self.authors = QTableWidget(0, 5)
        self.authors.setHorizontalHeaderLabels(["Name", "ORCID", "Affiliation", "Email", "Corresponding"])
        self.authors.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.authors.setMinimumHeight(130)
        for author in article.authors:
            self.add_author(author)
        add = QPushButton("Add author")
        add.clicked.connect(lambda: self.add_author(Author()))
        remove = QPushButton("Remove selected")
        remove.clicked.connect(self.remove_author)
        up = QPushButton("Move up")
        up.clicked.connect(lambda: self.move_author(-1))
        row = QHBoxLayout()
        for b in (add, remove, up):
            row.addWidget(b)
        row.addStretch()
        box = QVBoxLayout()
        box.addWidget(self.authors)
        box.addLayout(row)
        form.addRow("Authors (in order)", box)

        self.abstract = QPlainTextEdit(article.abstract)
        self.abstract.setFixedHeight(90)
        self.keywords = QLineEdit("; ".join(article.keywords))
        form.addRow("Abstract", self.abstract)
        form.addRow("Keywords (separate with ;)", self.keywords)
        self.dates = {k: QLineEdit(article.dates.get(k, "")) for k in ("received", "accepted", "published")}
        dates_row = QHBoxLayout()
        for k, field in self.dates.items():
            field.setPlaceholderText("YYYY-MM-DD")
            dates_row.addWidget(QLabel(k.capitalize()))
            dates_row.addWidget(field)
        form.addRow("Dates", dates_row)
        self.doi = QLineEdit(article.doi)
        self.doi.setPlaceholderText("Optional, e.g. 10.12345/abcd.2027.001 (without https://doi.org/)")
        form.addRow("DOI", self.doi)

        modes = [(MODE_JOURNAL, "Journal style (restyled in the journal template)"),
                 (MODE_ORIGINAL, "Author's style (only page size and margins changed)")]
        if article.source_kind == "pdf":
            modes = [(MODE_PDF, "PDF as sent (scaled to the page size if needed)")]
        self.mode = combo(modes, article.mode)
        self.starts_on = combo([(RIGHT, "Right-hand page"), (LEFT, "Left-hand page"), (ANY, "Any page")],
                               article.starts_on)
        self.stamp = QCheckBox("Print issue page numbers and headers on this article")
        self.stamp.setChecked(article.stamp_numbers)
        self.status = combo(list(STATUS_LABELS.items()), article.review_status)
        form.addRow("Layout", self.mode)
        form.addRow("Starts on", self.starts_on)
        form.addRow("", self.stamp)
        form.addRow("Review status", self.status)
        layout.addLayout(form)
        if article.warnings:
            layout.addWidget(note("Notes: " + " • ".join(article.warnings)))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def add_author(self, author: Author) -> None:
        row = self.authors.rowCount()
        self.authors.insertRow(row)
        for col, value in enumerate((author.name, author.orcid, author.affiliation, author.email)):
            self.authors.setItem(row, col, QTableWidgetItem(value))
        check = QTableWidgetItem()
        check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        check.setCheckState(Qt.CheckState.Checked if author.corresponding else Qt.CheckState.Unchecked)
        self.authors.setItem(row, 4, check)

    def remove_author(self) -> None:
        for row in sorted({i.row() for i in self.authors.selectedIndexes()}, reverse=True):
            self.authors.removeRow(row)

    def move_author(self, step: int) -> None:
        row = self.authors.currentRow()
        target = row + step
        if row < 0 or not 0 <= target < self.authors.rowCount():
            return
        authors = self.read_authors()
        authors[row], authors[target] = authors[target], authors[row]
        self.authors.setRowCount(0)
        for a in authors:
            self.add_author(a)
        self.authors.selectRow(target)

    def read_authors(self) -> list[Author]:
        out = []
        for row in range(self.authors.rowCount()):
            cell = lambda c: self.authors.item(row, c).text().strip() if self.authors.item(row, c) else ""
            corresponding = self.authors.item(row, 4) is not None and \
                self.authors.item(row, 4).checkState() == Qt.CheckState.Checked
            if cell(0):
                out.append(Author(cell(0), cell(1), cell(2), cell(3), corresponding))
        return out

    def apply(self) -> Article:
        a = self.article
        a.type = self.type.currentData()
        a.title = self.title.text().strip()
        a.subtitle = self.subtitle.text().strip()
        a.short_title = self.short_title.text().strip()
        a.authors = self.read_authors()
        a.abstract = self.abstract.toPlainText().strip()
        a.keywords = [k.strip() for k in self.keywords.text().replace(",", ";").split(";") if k.strip()]
        a.dates = {k: f.text().strip() for k, f in self.dates.items()}
        a.doi = self.doi.text().strip().removeprefix("https://doi.org/")
        a.mode = self.mode.currentData()
        a.starts_on = self.starts_on.currentData()
        a.stamp_numbers = self.stamp.isChecked()
        a.review_status = self.status.currentData()
        return a


class ArticleTable(QTableWidget):
    """The article list; files can be dropped onto it."""

    def __init__(self, on_drop):
        super().__init__(0, 7)
        self.on_drop = on_drop
        self.setHorizontalHeaderLabels(["#", "Title", "Authors", "Type", "Layout", "Pages", "Status"])
        header = self.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(0, 40)
        self.setColumnWidth(2, 200)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
            files = []
            for p in paths:
                files += sorted(f for f in p.iterdir() if f.suffix.lower() in SUPPORTED) if p.is_dir() else [p]
            event.acceptProposedAction()
            self.on_drop(files)
        else:
            super().dropEvent(event)


class IssueScreen(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.worker: Worker | None = None
        self.articles: list[Article] = []

        details = QGroupBox("Issue")
        row = QHBoxLayout(details)
        self.volume = int_spin(1, 1, 999)
        self.number = int_spin(1, 1, 99)
        self.month = combo([(m, m) for m in MONTHS])
        self.year = int_spin(2027, 1900, 2200)
        self.title = QLineEdit()
        self.title.setPlaceholderText("Optional issue title")
        for label, widget in (("Volume", self.volume), ("Issue", self.number), ("Month", self.month),
                              ("Year", self.year), ("Title", self.title)):
            row.addWidget(QLabel(label))
            row.addWidget(widget, 2 if widget is self.title else 0)
        save = QPushButton("Save")
        save.clicked.connect(self.save_issue)
        row.addWidget(save)

        self.table = ArticleTable(self.import_paths)
        self.table.doubleClicked.connect(lambda _: self.edit_article())

        buttons = QHBoxLayout()
        for text, slot in (("Add files…", self.add_files), ("Edit details…", self.edit_article),
                           ("Move up", lambda: self.move(-1)), ("Move down", lambda: self.move(1)),
                           ("Remove", self.remove), ("Re-analyse", self.reanalyse)):
            button = QPushButton(text)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        buttons.addStretch()
        self.status = QLabel("")
        self.problems = note("")

        layout = QVBoxLayout(self)
        layout.addWidget(details)
        layout.addWidget(note("Add DOC, DOCX, ODT or PDF files with 'Add files…' or by dragging them onto the list. "
                              "The order here is the order in the issue. Double-click an article to edit its details. "
                              "The authors' files are copied; the originals are never changed."))
        layout.addWidget(self.table, 1)
        layout.addLayout(buttons)
        layout.addWidget(self.status)
        layout.addWidget(self.problems)

        state.issue_changed.connect(self.load)
        state.data_changed.connect(self.load)

    # ------------------------------------------------------------------ loading

    def load(self) -> None:
        enabled = self.state.issue is not None
        self.setEnabled(enabled)
        self.table.setRowCount(0)
        if not enabled:
            self.status.setText("No issue open. Use 'New issue' at the top.")
            return
        s = self.state.issue.load()
        self.volume.setValue(s.volume)
        self.number.setValue(s.number)
        from ..common import set_combo

        set_combo(self.month, s.month)
        self.year.setValue(s.year)
        self.title.setText(s.title)
        self.articles = self.state.issue.load_articles(s)
        problems = []
        for n, a in enumerate(self.articles, 1):
            row = self.table.rowCount()
            self.table.insertRow(row)
            pages = f"{a.start_page}–{a.end_page}" if a.start_page else (str(a.page_count) if a.page_count else "")
            values = [str(n), a.title or a.source_name, a.author_names, a.type, MODE_LABELS.get(a.mode, a.mode),
                      pages, STATUS_LABELS.get(a.review_status, a.review_status)]
            if a.import_status != "ok":
                values[6] = "Import failed"
                problems.append(f"{a.source_name}: {a.import_message}")
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if a.import_status != "ok":
                    item.setForeground(QBrush(QColor("#b00020")))
                elif a.review_status == "needs_review" and col == 6:
                    item.setForeground(QBrush(QColor("#a65e00")))
                self.table.setItem(row, col, item)
        self.status.setText(f"{len(self.articles)} article(s). Pages show the issue page range after an export.")
        self.problems.setText("Problems: " + " | ".join(problems) if problems else "")

    def save_issue(self) -> None:
        issue = self.state.issue
        if issue is None:
            return
        s = issue.load()
        s.month = self.month.currentData()
        s.year = self.year.value()
        s.title = self.title.text().strip()
        if (self.volume.value(), self.number.value()) != (s.volume, s.number):
            # Volume and number are part of the folder name; they are shown but kept.
            info(self, "Volume and issue number",
                 "Volume and issue number cannot be changed for an existing issue. "
                 "Create a new issue instead. The other details were saved.")
            self.volume.setValue(s.volume)
            self.number.setValue(s.number)
        issue.save(s)
        self.state.data_changed.emit()

    # ------------------------------------------------------------------ actions

    def selected(self) -> Article | None:
        row = self.table.currentRow()
        return self.articles[row] if 0 <= row < len(self.articles) else None

    def add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Add articles", "",
                                                "Articles (*.doc *.docx *.odt *.rtf *.pdf)")
        if files:
            self.import_paths([Path(f) for f in files])

    def import_paths(self, paths: list[Path]) -> None:
        issue = self.state.issue
        if issue is None or not paths:
            return
        if self.worker is not None and self.worker.isRunning():
            info(self, "Please wait", "Files are still being imported.")
            return

        def job(progress):
            settings = issue.load()
            return import_files(issue, settings, paths,
                                lambda n, total, name: progress(f"Importing {n} of {total}: {name}"))

        self.worker = Worker(job, self)
        self.worker.progress.connect(self.status.setText)
        self.worker.finished_ok.connect(self.imported)
        self.worker.failed.connect(lambda text: error(self, "Import failed", text))
        self.status.setText("Importing…")
        self.worker.start()

    def imported(self, articles: list[Article]) -> None:
        failed = [a for a in articles if a.import_status != "ok"]
        self.state.data_changed.emit()
        if failed:
            error(self, "Some files could not be imported",
                  "\n".join(f"{a.source_name}: {a.import_message}" for a in failed))

    def edit_article(self) -> None:
        article = self.selected()
        if article is None:
            return
        dialog = ArticleDialog(self, article)
        if dialog.exec():
            self.state.issue.save_article(dialog.apply())
            self.state.data_changed.emit()

    def move(self, step: int) -> None:
        row = self.table.currentRow()
        issue = self.state.issue
        if issue is None or row < 0:
            return
        s = issue.load()
        target = row + step
        order = [a.id for a in self.articles]
        if not 0 <= target < len(order):
            return
        order[row], order[target] = order[target], order[row]
        # Keep any article ids that failed to load at the end of the list.
        s.article_order = order + [i for i in s.article_order if i not in order]
        issue.save(s)
        self.state.data_changed.emit()
        self.table.selectRow(target)

    def remove(self) -> None:
        article = self.selected()
        if article is None or self.state.issue is None:
            return
        if ask(self, "Remove article", f"Remove '{article.title or article.source_name}' from this issue?\n\n"
                                       "Its files are moved to the issue's 'removed' folder, not deleted."):
            s = self.state.issue.load()
            self.state.issue.remove_article(s, article.id)
            self.state.data_changed.emit()

    def reanalyse(self) -> None:
        article = self.selected()
        if article is None or article.source_kind != "word" or article.import_status != "ok":
            info(self, "Re-analyse", "Choose a Word article that imported correctly.")
            return
        if ask(self, "Re-analyse", "Label this article again from scratch? Your corrections on the Review "
                                   "screen and the details will be replaced."):
            reanalyse(self.state.issue, article)
            self.state.issue.save_article(article)
            self.state.data_changed.emit()


__all__ = ["IssueScreen", "NewIssueDialog", "ArticleDialog", "QSpinBox"]
