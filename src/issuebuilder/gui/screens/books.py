"""Book Publishing screen: create edited books and compile submitted chapters."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
                               QTabWidget, QTextEdit, QVBoxLayout, QWidget)

from ...books.export import export_book
from ...books.models import Book, Contributor, isbn13_valid
from ...books.storage import BookFolder, BookLibrary
from ..common import Worker, error, info, note, open_folder


class NewBookDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create a book")
        form = QFormLayout(self)
        self.title = QLineEdit()
        self.kind = QComboBox(); self.kind.addItem("Edited volume", "edited"); self.kind.addItem("Authored monograph", "monograph")
        form.addRow("Book title", self.title); form.addRow("Book type", self.kind)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)


class BooksScreen(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.library: BookLibrary | None = None
        self.folder: BookFolder | None = None
        self.worker: Worker | None = None
        root = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.location = QLabel("No book library selected")
        choose = QPushButton("Choose book library…"); choose.clicked.connect(self.choose_library)
        new = QPushButton("New book…"); new.clicked.connect(self.new_book)
        self.books = QComboBox(); self.books.currentIndexChanged.connect(self.select_book)
        bar.addWidget(self.location, 1); bar.addWidget(choose); bar.addWidget(new); root.addLayout(bar)
        root.addWidget(QLabel("Book:") ); root.addWidget(self.books)
        self.tabs = QTabWidget()
        self.details = QWidget(); self._build_details()
        self.chapters = QWidget(); self._build_chapters()
        self.matter = QWidget(); self._build_matter()
        self.tabs.addTab(self.details, "Book details"); self.tabs.addTab(self.chapters, "Chapters")
        self.tabs.addTab(self.matter, "Front and back matter")
        root.addWidget(self.tabs, 1)
        footer = QHBoxLayout()
        self.export_button = QPushButton("Build book PDF"); self.export_button.clicked.connect(self.export)
        open_output = QPushButton("Open output folder"); open_output.clicked.connect(self.open_output)
        self.status = QLabel("Create or open a book to begin.")
        footer.addWidget(self.export_button); footer.addWidget(open_output); footer.addWidget(self.status, 1)
        root.addLayout(footer)
        saved = self.settings.value("book_library", "")
        if saved and Path(saved).is_dir(): self.set_library(Path(saved))

    def _build_details(self):
        layout = QVBoxLayout(self.details); form = QFormLayout()
        self.fields = {}
        labels = [("title", "Title"), ("subtitle", "Subtitle"), ("publisher", "Publisher"),
                  ("publisher_address", "Publisher address"), ("publication_place", "Place of publication"),
                  ("isbn_print", "ISBN (print)"), ("isbn_ebook", "ISBN (digital)"),
                  ("edition", "Edition"), ("language", "Language"), ("subject", "Subject"),
                  ("series_title", "Series"), ("series_number", "Series number"), ("price", "Price"),
                  ("copyright_holder", "Copyright holder"), ("copyright_statement", "Copyright statement")]
        for key, label in labels:
            field = QLineEdit(); self.fields[key] = field; form.addRow(label, field)
        self.year = QSpinBox(); self.year.setRange(1450, 2200); form.addRow("Publication year", self.year)
        self.copyright_year = QSpinBox(); self.copyright_year.setRange(1450, 2200); form.addRow("Copyright year", self.copyright_year)
        self.trim = QComboBox(); self.trim.addItems(["A5", "A4"]); form.addRow("Trim size", self.trim)
        self.contributors = QTableWidget(0, 5); self.contributors.setHorizontalHeaderLabels(["Name", "Role", "Affiliation", "Email", "ORCID"])
        self.contributors.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        add = QPushButton("Add contributor"); add.clicked.connect(lambda: self.contributors.insertRow(self.contributors.rowCount()))
        remove = QPushButton("Remove selected"); remove.clicked.connect(lambda: self.contributors.removeRow(self.contributors.currentRow()) if self.contributors.currentRow() >= 0 else None)
        layout.addLayout(form); layout.addWidget(QLabel("Editors, authors and other contributors")); layout.addWidget(self.contributors, 1)
        row=QHBoxLayout(); row.addWidget(add); row.addWidget(remove); save=QPushButton("Save book details"); save.clicked.connect(self.save_details); row.addStretch(); row.addWidget(save); layout.addLayout(row)

    def _build_matter(self):
        layout = QVBoxLayout(self.matter)
        self.matter_fields = {}
        for key, label in (("dedication", "Dedication"), ("epigraph", "Epigraph"),
                           ("foreword", "Foreword"), ("preface", "Preface"),
                           ("acknowledgements", "Acknowledgements"), ("introduction", "Introduction"),
                           ("appendices", "Appendices"), ("glossary", "Glossary"),
                           ("bibliography", "Consolidated bibliography"), ("index_note", "Index / index material")):
            layout.addWidget(QLabel(label))
            editor = QTextEdit(); editor.setMinimumHeight(65)
            self.matter_fields[key] = editor
            layout.addWidget(editor, 1 if key in ("foreword", "preface", "introduction", "appendices", "bibliography") else 0)
        save = QPushButton("Save front and back matter")
        save.clicked.connect(self.save_matter)
        layout.addWidget(save)

    def _build_chapters(self):
        layout=QVBoxLayout(self.chapters)
        self.chapter_table=QTableWidget(0,5); self.chapter_table.setHorizontalHeaderLabels(["Include", "Chapter title", "Authors", "Source file", "Chapter ID"])
        self.chapter_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        self.chapter_table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        self.chapter_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        buttons=QHBoxLayout(); add=QPushButton("Import chapter files…"); add.clicked.connect(self.add_chapters)
        remove=QPushButton("Remove selected chapter"); remove.clicked.connect(self.remove_chapter)
        up=QPushButton("Move up"); up.clicked.connect(lambda:self.move_chapter(-1)); down=QPushButton("Move down"); down.clicked.connect(lambda:self.move_chapter(1))
        save=QPushButton("Save chapter order"); save.clicked.connect(self.save_chapters)
        for b in (add,remove,up,down,save): buttons.addWidget(b)
        layout.addWidget(note("Import DOC, DOCX, ODT, RTF or PDF files. Original submissions are copied unchanged into the book folder."))
        layout.addWidget(self.chapter_table,1); layout.addLayout(buttons)

    def choose_library(self):
        path=QFileDialog.getExistingDirectory(self,"Choose or create a book library")
        if path: self.set_library(Path(path))

    def set_library(self,path:Path):
        self.library=BookLibrary(path); self.settings.setValue("book_library",str(path)); self.location.setText(str(path)); self.refresh_books()

    def refresh_books(self, select=None):
        if not self.library: return
        self.books.blockSignals(True); self.books.clear()
        for folder in self.library.list_books(): self.books.addItem(folder.load().title or folder.path.name,str(folder.path))
        if select:
            i=self.books.findData(str(select.path)); self.books.setCurrentIndex(i)
        self.books.blockSignals(False); self.select_book(self.books.currentIndex())

    def new_book(self):
        if not self.library:
            self.choose_library()
            if not self.library:return
        dialog=NewBookDialog(self)
        if dialog.exec() and dialog.title.text().strip():
            folder=self.library.create_book(dialog.title.text().strip(),dialog.kind.currentData()); self.refresh_books(folder)

    def select_book(self,index):
        if not self.library or index<0: self.folder=None; return
        self.folder=BookFolder(self.library,Path(self.books.itemData(index))); self.load_book()

    def load_book(self):
        if not self.folder:return
        book=self.folder.load()
        for key,field in self.fields.items(): field.setText(str(getattr(book,key)))
        self.year.setValue(book.publication_year); self.copyright_year.setValue(book.copyright_year); self.trim.setCurrentText(book.trim_size)
        for key, editor in self.matter_fields.items(): editor.setPlainText(getattr(book, key))
        self.contributors.setRowCount(0)
        for c in book.contributors:
            row=self.contributors.rowCount(); self.contributors.insertRow(row)
            for col,value in enumerate((c.name,c.role,c.affiliation,c.email,c.orcid)): self.contributors.setItem(row,col,QTableWidgetItem(value))
        self.chapter_table.setRowCount(0)
        for ch in book.chapters:
            row=self.chapter_table.rowCount(); self.chapter_table.insertRow(row)
            check=QTableWidgetItem(); check.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable); check.setCheckState(Qt.CheckState.Checked if ch.include else Qt.CheckState.Unchecked)
            self.chapter_table.setItem(row,0,check)
            for col,value in enumerate((ch.title,", ".join(ch.authors),ch.source_name,ch.id),1): self.chapter_table.setItem(row,col,QTableWidgetItem(value))
        self.status.setText(f"{len(book.chapters)} chapter(s)")

    def save_details(self):
        if not self.folder:return
        book=self.folder.load()
        for key,field in self.fields.items(): setattr(book,key,field.text().strip())
        for key in ("isbn_print", "isbn_ebook"):
            value = getattr(book, key).strip()
            if value and not isbn13_valid(value):
                QMessageBox.warning(self, "Invalid ISBN", f"The {key.replace('_', ' ')} must be a valid 13-digit ISBN (check digit included).")
                return
        book.publication_year=self.year.value(); book.copyright_year=self.copyright_year.value(); book.trim_size=self.trim.currentText()
        book.contributors=[]
        for row in range(self.contributors.rowCount()):
            vals=[self.contributors.item(row,col).text() if self.contributors.item(row,col) else "" for col in range(5)]
            if vals[0].strip(): book.contributors.append(Contributor(name=vals[0],role=vals[1] or "Author",affiliation=vals[2],email=vals[3],orcid=vals[4]))
        self.folder.save(book); self.books.setItemText(self.books.currentIndex(),book.title); info(self,"Book details","Book details saved.")

    def save_matter(self):
        if not self.folder: return
        book = self.folder.load()
        for key, editor in self.matter_fields.items(): setattr(book, key, editor.toPlainText().strip())
        self.folder.save(book)
        info(self, "Book matter", "Front and back matter saved.")

    def add_chapters(self):
        if not self.folder:return
        files,_=QFileDialog.getOpenFileNames(self,"Select chapter files","","Documents (*.doc *.docx *.odt *.rtf *.pdf)")
        if not files:return
        book=self.folder.load(); failures=[]
        for file in files:
            try:self.folder.add_chapter_file(Path(file),book)
            except Exception as exc:failures.append(f"{file}: {exc}")
        self.load_book()
        if failures:error(self,"Some chapters could not be imported","\n".join(failures))

    def save_chapters(self):
        if not self.folder:return
        book=self.folder.load(); by_id={ch.id:ch for ch in book.chapters}; ordered=[]
        for row in range(self.chapter_table.rowCount()):
            ident=self.chapter_table.item(row,4).text(); ch=by_id.get(ident)
            if ch:
                ch.title=self.chapter_table.item(row,1).text(); ch.authors=[x.strip() for x in self.chapter_table.item(row,2).text().split(",") if x.strip()]
                ch.include=self.chapter_table.item(row,0).checkState()==Qt.CheckState.Checked; ordered.append(ch)
        book.chapters=ordered; self.folder.save(book); self.status.setText("Chapter order saved.")

    def remove_chapter(self):
        row=self.chapter_table.currentRow()
        if row<0 or not self.folder:return
        ident=self.chapter_table.item(row,4).text(); book=self.folder.load(); book.chapters=[ch for ch in book.chapters if ch.id!=ident]; self.folder.save(book); self.load_book()

    def move_chapter(self,step):
        row=self.chapter_table.currentRow(); target=row+step
        if row<0 or not 0<=target<self.chapter_table.rowCount():return
        items=[self.chapter_table.takeItem(row,col) for col in range(self.chapter_table.columnCount())]
        self.chapter_table.removeRow(row); self.chapter_table.insertRow(target)
        for col,item in enumerate(items):
            if item:self.chapter_table.setItem(target,col,item)
        self.chapter_table.setCurrentCell(target,1)

    def export(self):
        if not self.folder or (self.worker and self.worker.isRunning()):return
        self.save_chapters(); self.export_button.setEnabled(False); self.status.setText("Building book…")
        self.worker=Worker(lambda progress:export_book(self.folder,progress),self)
        self.worker.progress.connect(self.status.setText); self.worker.finished_ok.connect(self.export_done); self.worker.failed.connect(self.export_failed); self.worker.start()

    def export_done(self,path):
        self.export_button.setEnabled(True); self.status.setText(f"Created: {path}"); info(self,"Book exported",f"Book PDF created:\n{path}")

    def export_failed(self,message):
        self.export_button.setEnabled(True); self.status.setText("Export failed."); error(self,"Book export failed",message)

    def open_output(self):
        if self.folder:open_folder(self.folder.output)
