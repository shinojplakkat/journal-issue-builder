"""Book library storage, deliberately separate from journal/issue folders."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from ..settings.load_save import read_json, write_json, safe_name
from .models import Book, Chapter


class BookLibrary:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def list_books(self) -> list["BookFolder"]:
        return sorted((BookFolder(self, p) for p in self.root.iterdir()
                       if p.is_dir() and (p / "book.json").is_file()),
                      key=lambda f: f.load().title.casefold())

    def create_book(self, title: str, book_type: str = "edited") -> "BookFolder":
        slug = safe_name(title, 48).lower()
        target = self.root / slug
        suffix = 2
        while target.exists():
            target = self.root / f"{slug}_{suffix}"
            suffix += 1
        folder = BookFolder(self, target)
        for name in ("assets", "originals", "work", "output"):
            (target / name).mkdir(parents=True, exist_ok=True)
        folder.save(Book(title=title.strip(), book_type=book_type, id=target.name))
        return folder


class BookFolder:
    def __init__(self, library: BookLibrary, path: Path):
        self.library, self.path = library, Path(path)

    @property
    def book_file(self) -> Path:
        return self.path / "book.json"

    @property
    def originals(self) -> Path:
        return self.path / "originals"

    @property
    def work(self) -> Path:
        return self.path / "work"

    @property
    def output(self) -> Path:
        return self.path / "output"

    def load(self) -> Book:
        return Book.from_dict(read_json(self.book_file))

    def save(self, book: Book) -> None:
        book.updated_at = __import__("datetime").datetime.now().isoformat(timespec="seconds")
        if not book.created_at:
            book.created_at = book.updated_at
        write_json(self.book_file, book.to_dict())

    def add_chapter_file(self, source: Path, book: Book) -> Chapter:
        source = Path(source)
        if not source.is_file() or source.stat().st_size == 0:
            raise ValueError(f"File is empty or missing: {source}")
        suffix = source.suffix.lower()
        if suffix not in {".doc", ".docx", ".odt", ".rtf", ".pdf"}:
            raise ValueError(f"Unsupported chapter format: {suffix}")
        chapter_id = f"ch{len(book.chapters) + 1:03d}"
        while any(ch.id == chapter_id for ch in book.chapters):
            chapter_id = f"ch{int(chapter_id[2:]) + 1:03d}"
        filename = f"{chapter_id}_{safe_name(source.stem)}{suffix}"
        target = self.originals / filename
        shutil.copy2(source, target)
        chapter = Chapter(id=chapter_id, title=source.stem, source_file=f"originals/{filename}",
                          source_name=source.name)
        book.chapters.append(chapter)
        self.save(book)
        return chapter
