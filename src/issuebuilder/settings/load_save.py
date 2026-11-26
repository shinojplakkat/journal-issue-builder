"""Reading and writing the journal folder (blueprint 3.4).

    MyJournal/
      journal.json
      assets/                      logo and other journal images
      issues/vol1-issue2/
        issue.json
        assets/                    cover images for this issue
        originals/                 untouched submitted files
        work/                      converted and rebuilt files
        articles/<id>/article.json
        output/                    final PDFs and the export log
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from .models import Article, IssueSettings, JournalSettings, LayoutSettings


def read_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: dict) -> None:
    """Write to a temporary file first, so a power cut never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def safe_name(text: str, limit: int = 40) -> str:
    """Make text safe for a file name on Windows and Linux."""
    text = re.sub(r"[^\w\- ]+", "", text, flags=re.UNICODE).strip()
    text = re.sub(r"\s+", "_", text)
    return text[:limit] or "untitled"


def unique_name(base: str, used: set[str], suffix: str) -> str:
    """base + suffix, with _2, _3 ... added if the name is already used in this export."""
    name, n = base, 1
    while name in used:
        n += 1
        name = f"{base}_{n}"
    used.add(name)
    return name + suffix


class JournalFolder:
    """One journal on disk."""

    def __init__(self, root: Path):
        self.root = Path(root)

    @property
    def journal_file(self) -> Path:
        return self.root / "journal.json"

    @property
    def assets(self) -> Path:
        return self.root / "assets"

    @property
    def issues_dir(self) -> Path:
        return self.root / "issues"

    def exists(self) -> bool:
        return self.journal_file.is_file()

    @classmethod
    def create(cls, root: Path) -> "JournalFolder":
        """Make a new journal folder with sample details."""
        folder = cls(root)
        folder.root.mkdir(parents=True, exist_ok=True)
        folder.assets.mkdir(exist_ok=True)
        folder.issues_dir.mkdir(exist_ok=True)
        if not folder.exists():
            folder.save_journal(JournalSettings())
        return folder

    def load_journal(self) -> JournalSettings:
        return JournalSettings.from_dict(read_json(self.journal_file))

    def save_journal(self, journal: JournalSettings) -> None:
        write_json(self.journal_file, journal.to_dict())

    def logo_path(self, journal: JournalSettings) -> Path | None:
        if journal.logo and (self.assets / journal.logo).is_file():
            return self.assets / journal.logo
        return None

    def set_logo(self, journal: JournalSettings, image: Path) -> None:
        """Copy an image into the journal's assets folder and use it as the logo."""
        self.assets.mkdir(parents=True, exist_ok=True)
        target = self.assets / ("logo" + Path(image).suffix.lower())
        shutil.copyfile(image, target)
        journal.logo = target.name

    # ------------------------------------------------------------------ issues

    def list_issues(self) -> list["IssueFolder"]:
        if not self.issues_dir.is_dir():
            return []
        found = [IssueFolder(self, p) for p in self.issues_dir.iterdir() if (p / "issue.json").is_file()]

        def key(issue: IssueFolder):
            s = issue.load()
            return (s.volume, s.number)

        return sorted(found, key=key)

    def create_issue(self, volume: int, number: int, month: str, year: int,
                     title: str = "", journal: JournalSettings | None = None) -> "IssueFolder":
        journal = journal or self.load_journal()
        settings = IssueSettings(volume=volume, number=number, month=month, year=year, title=title)
        settings.layout = LayoutSettings.for_page_size(journal.default_page_size)
        settings.printing.binding_mode = journal.default_binding
        path = self.issues_dir / settings.slug
        if (path / "issue.json").exists():
            raise FileExistsError(f"Volume {volume}, Issue {number} already exists.")
        issue = IssueFolder(self, path)
        for sub in ("originals", "work", "articles", "output", "assets"):
            (path / sub).mkdir(parents=True, exist_ok=True)
        issue.save(settings)
        return issue


class IssueFolder:
    """One issue inside a journal folder."""

    def __init__(self, journal: JournalFolder, path: Path):
        self.journal = journal
        self.path = Path(path)

    issue_file = property(lambda self: self.path / "issue.json")
    originals = property(lambda self: self.path / "originals")
    work = property(lambda self: self.path / "work")
    articles_dir = property(lambda self: self.path / "articles")
    output = property(lambda self: self.path / "output")
    assets = property(lambda self: self.path / "assets")

    def load(self) -> IssueSettings:
        return IssueSettings.from_dict(read_json(self.issue_file))

    def save(self, settings: IssueSettings) -> None:
        write_json(self.issue_file, settings.to_dict())

    # ------------------------------------------------------------------ articles

    def article_file(self, article_id: str) -> Path:
        return self.articles_dir / article_id / "article.json"

    def load_article(self, article_id: str) -> Article:
        return Article.from_dict(read_json(self.article_file(article_id)))

    def save_article(self, article: Article) -> None:
        write_json(self.article_file(article.id), article.to_dict())

    def load_articles(self, settings: IssueSettings | None = None) -> list[Article]:
        """Articles in issue order. Missing article files are skipped."""
        settings = settings or self.load()
        articles = []
        for article_id in settings.article_order:
            if self.article_file(article_id).is_file():
                articles.append(self.load_article(article_id))
        return articles

    def new_article_id(self, settings: IssueSettings) -> str:
        used = set(settings.article_order)
        if self.articles_dir.is_dir():
            used |= {p.name for p in self.articles_dir.iterdir()}
        n = 1
        while f"a{n:02d}" in used:
            n += 1
        return f"a{n:02d}"

    def copy_original(self, source: Path, article_id: str) -> Path:
        """Copy the submitted file in, never touching the author's own file (rule 4)."""
        self.originals.mkdir(parents=True, exist_ok=True)
        target = self.originals / f"{article_id}_{safe_name(Path(source).stem)}{Path(source).suffix.lower()}"
        shutil.copyfile(source, target)
        return target

    def remove_article(self, settings: IssueSettings, article_id: str) -> None:
        """Take an article out of the issue. Its files are moved to a 'removed' folder, not deleted."""
        if article_id in settings.article_order:
            settings.article_order.remove(article_id)
        folder = self.articles_dir / article_id
        if folder.is_dir():
            trash = self.path / "removed"
            trash.mkdir(exist_ok=True)
            target = trash / article_id
            n = 1
            while target.exists():
                n += 1
                target = trash / f"{article_id}_{n}"
            shutil.move(str(folder), str(target))
        self.save(settings)
