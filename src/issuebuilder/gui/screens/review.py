"""Review screen (blueprint M5): check and correct the label of every paragraph."""

from __future__ import annotations

import io

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QScrollArea, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ...analyzer.blocks import fill_details
from ...analyzer.rules import LABELS, LOW_CONFIDENCE
from ...builder.article import article_pdf_path, build_articles
from ...importers.convert import clean_word_path
from ..common import AppState, Worker, combo, error, info, note, set_combo
from .issue import STATUS_LABELS

LABEL_NAMES = {
    "title": "Title", "subtitle": "Subtitle", "author": "Author", "orcid": "ORCID", "email": "Email",
    "institution": "Institution", "abstract": "Abstract", "keywords": "Keywords", "heading1": "Heading 1",
    "heading2": "Heading 2", "body": "Body text", "references": "References", "other": "Other section",
    "ignore": "Ignore (leave out)",
}


def confidence_colour(confidence: float, confirmed: bool) -> QColor:
    if confirmed:
        return QColor("#e8f5e9")       # green: checked by the editor
    if confidence < LOW_CONFIDENCE:
        return QColor("#ffe0b2")       # orange: please check
    if confidence < 0.8:
        return QColor("#fff9c4")       # yellow: probably right
    return QColor("#ffffff")


class ReviewScreen(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.article = None
        self.worker: Worker | None = None
        self.loading = False

        self.picker = QComboBox()
        self.picker.currentIndexChanged.connect(self.pick)
        self.status = combo(list(STATUS_LABELS.items()))
        self.status.currentIndexChanged.connect(self.status_changed)
        top = QHBoxLayout()
        top.addWidget(QLabel("Article"))
        top.addWidget(self.picker, 1)
        top.addWidget(QLabel("Status"))
        top.addWidget(self.status)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Label", "Sure", "Text"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(1, 50)
        self.table.setWordWrap(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.quick = combo([(l, LABEL_NAMES[l]) for l in LABELS])
        set_selected = QPushButton("Set label for selected rows")
        set_selected.clicked.connect(self.set_selected)
        apply = QPushButton("Apply labels to details")
        apply.setToolTip("Fill title, authors, abstract and keywords from the labels")
        apply.clicked.connect(self.apply_labels)
        actions = QHBoxLayout()
        actions.addWidget(self.quick)
        actions.addWidget(set_selected)
        actions.addStretch()
        actions.addWidget(apply)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(note("Each paragraph has a label. Orange rows are uncertain: please check them. "
                                   "Changes are saved at once. Green rows were checked by you."))
        left_layout.addWidget(self.table, 1)
        left_layout.addLayout(actions)

        self.preview_button = QPushButton("Update preview")
        self.preview_button.clicked.connect(self.update_preview)
        self.preview_info = note("The preview shows the article as it will be laid out.")
        self.pages = QVBoxLayout()
        pages_widget = QWidget()
        pages_widget.setLayout(self.pages)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(pages_widget)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.preview_button)
        right_layout.addWidget(self.preview_info)
        right_layout.addWidget(scroll, 1)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(splitter, 1)

        state.issue_changed.connect(self.load)
        state.data_changed.connect(self.load)

    # ------------------------------------------------------------------ loading

    def load(self) -> None:
        issue = self.state.issue
        self.setEnabled(issue is not None)
        current = self.article.id if self.article else None
        self.loading = True
        self.picker.clear()
        if issue is None:
            self.loading = False
            return
        for a in issue.load_articles():
            if a.import_status == "ok":
                self.picker.addItem(f"{a.id}  {a.title[:70] or a.source_name}", a.id)
        self.loading = False
        index = self.picker.findData(current) if current else 0
        self.picker.setCurrentIndex(max(index, 0))
        self.pick()

    def pick(self) -> None:
        if self.loading:
            return
        article_id = self.picker.currentData()
        self.clear_preview()
        if article_id is None or self.state.issue is None:
            self.article = None
            self.table.setRowCount(0)
            return
        self.article = self.state.issue.load_article(article_id)
        self.loading = True
        set_combo(self.status, self.article.review_status)
        self.loading = False
        self.fill_table()
        if self.article.source_kind == "pdf":
            self.preview_info.setText("PDF article: it is inserted as sent. Check its title and authors with "
                                      "'Edit details' on the Issue screen.")

    def fill_table(self) -> None:
        self.loading = True
        self.table.setRowCount(0)
        for row, block in enumerate(self.article.blocks):
            self.table.insertRow(row)
            box = combo([(l, LABEL_NAMES[l]) for l in LABELS], block.label)
            box.currentIndexChanged.connect(lambda _=0, r=row, b=box: self.label_changed(r, b.currentData()))
            self.table.setCellWidget(row, 0, box)
            sure = QTableWidgetItem("✓" if block.confirmed else f"{int(block.confidence * 100)}%")
            text = QTableWidgetItem(block.text if len(block.text) < 600 else block.text[:600] + " …")
            colour = QBrush(confidence_colour(block.confidence, block.confirmed))
            sure.setBackground(colour)
            text.setBackground(colour)
            self.table.setItem(row, 1, sure)
            self.table.setItem(row, 2, text)
        self.table.resizeRowsToContents()
        self.loading = False

    # ------------------------------------------------------------------ editing

    def save(self) -> None:
        self.state.issue.save_article(self.article)

    def label_changed(self, row: int, label: str) -> None:
        if self.loading or self.article is None:
            return
        block = self.article.blocks[row]
        block.label = label
        block.confirmed = True
        self.save()
        colour = QBrush(confidence_colour(block.confidence, True))
        for col in (1, 2):
            self.table.item(row, col).setBackground(colour)
        self.table.item(row, 1).setText("✓")

    def set_selected(self) -> None:
        if self.article is None:
            return
        label = self.quick.currentData()
        for row in sorted({i.row() for i in self.table.selectedIndexes()}):
            box = self.table.cellWidget(row, 0)
            set_combo(box, label)  # triggers label_changed
        self.save()

    def status_changed(self) -> None:
        if self.loading or self.article is None:
            return
        self.article.review_status = self.status.currentData()
        self.save()
        self.state.data_changed.emit()

    def apply_labels(self) -> None:
        if self.article is None or self.article.source_kind != "word":
            return
        fill_details(self.article, clean_word_path(self.state.issue, self.article.id))
        self.save()
        info(self, "Details updated",
             f"Title: {self.article.title}\nAuthors: {self.article.author_names or '(none)'}\n"
             f"Keywords: {', '.join(self.article.keywords) or '(none)'}\n\n"
             "Check the details with 'Edit details' on the Issue screen.")
        self.state.data_changed.emit()

    # ------------------------------------------------------------------ preview

    def clear_preview(self) -> None:
        while self.pages.count():
            widget = self.pages.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()

    def update_preview(self) -> None:
        if self.article is None or self.state.issue is None:
            return
        if self.worker is not None and self.worker.isRunning():
            return
        issue, article_id = self.state.issue, self.article.id

        def job(progress):
            settings = issue.load()
            article = issue.load_article(article_id)
            problems = build_articles(issue, [article], settings.layout, progress)
            if problems:
                raise RuntimeError("\n".join(problems))
            return render_pages(article_pdf_path(issue, article_id))

        self.preview_button.setEnabled(False)
        self.preview_info.setText("Laying out the article…")
        self.worker = Worker(job, self)
        self.worker.finished_ok.connect(self.show_pages)
        self.worker.failed.connect(self.preview_failed)
        self.worker.start()

    def preview_failed(self, text: str) -> None:
        self.preview_button.setEnabled(True)
        self.preview_info.setText("The preview could not be made.")
        error(self, "Preview", text)

    def show_pages(self, images: list[bytes]) -> None:
        self.preview_button.setEnabled(True)
        self.clear_preview()
        self.preview_info.setText(f"{len(images)} page(s). Labels changed? Press 'Update preview' again.")
        for n, data in enumerate(images, 1):
            pixmap = QPixmap()
            pixmap.loadFromData(data, "PNG")
            label = QLabel()
            label.setPixmap(pixmap)
            label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            label.setStyleSheet("border: 1px solid #999; background: white;")
            caption = QLabel(f"Page {n}")
            caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.pages.addWidget(label)
            self.pages.addWidget(caption)
        self.pages.addStretch()


def render_pages(pdf_path, max_pages: int = 40, width_px: int = 420) -> list[bytes]:
    """Page pictures for the preview (pypdfium2, no external program needed)."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    images = []
    try:
        for index in range(min(len(pdf), max_pages)):
            page = pdf[index]
            scale = width_px / page.get_width()
            image = page.render(scale=scale).to_pil()
            buffer = io.BytesIO()
            image.save(buffer, "PNG")
            images.append(buffer.getvalue())
    finally:
        pdf.close()
    return images
