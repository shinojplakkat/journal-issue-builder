from pathlib import Path

from issuebuilder.books.models import Book, Chapter, Contributor, isbn13_valid
from issuebuilder.books.storage import BookLibrary


def test_isbn13_check_digit():
    assert isbn13_valid("978-0-306-40615-7")
    assert not isbn13_valid("978-0-306-40615-8")
    assert not isbn13_valid("978030640615")


def test_book_json_round_trip(tmp_path):
    library = BookLibrary(tmp_path / "books")
    folder = library.create_book("Arts and Performance", "edited")
    book = folder.load()
    book.contributors.append(Contributor(name="Editor One", role="Editor"))
    book.chapters.append(Chapter(id="ch001", title="A Chapter", authors=["Author One"]))
    folder.save(book)
    loaded = folder.load()
    assert loaded.title == "Arts and Performance"
    assert loaded.contributors[0].name == "Editor One"
    assert loaded.chapters[0].authors == ["Author One"]


def test_import_copies_source_without_modifying_it(tmp_path):
    source = tmp_path / "chapter.docx"
    source.write_bytes(b"test document bytes")
    folder = BookLibrary(tmp_path / "library").create_book("My Book")
    book = folder.load()
    chapter = folder.add_chapter_file(source, book)
    assert (folder.path / chapter.source_file).read_bytes() == source.read_bytes()
    assert source.read_bytes() == b"test document bytes"
    assert folder.load().chapters[0].id == "ch001"
