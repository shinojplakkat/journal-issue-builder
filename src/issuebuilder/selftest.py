"""`issuebuilder selftest`: build a tiny issue from scratch to prove the installation works.

Used by the build on the finished package (Windows and Ubuntu), and useful on a
new computer. Writes a report to the given file (the Windows program has no console).
"""

from __future__ import annotations

import tempfile
import traceback
from pathlib import Path


def _sample_word(path: Path) -> Path:
    from docx import Document

    doc = Document()
    doc.add_heading("A Self-Test Article on Performance", level=0)
    doc.add_paragraph("Test Author")
    doc.add_paragraph("Department of Testing, Sample University")
    doc.add_paragraph("Abstract: This article checks that the program can lay out a Word file. " * 3)
    doc.add_paragraph("Keywords: test, layout, issue")
    doc.add_heading("Introduction", level=1)
    for _ in range(6):
        doc.add_paragraph("The program restyles this paragraph into the journal template. " * 6)
    doc.add_paragraph("കേരളകലാമണ്ഡലം — മലയാളം പരിശോധന.")
    doc.add_heading("References", level=1)
    doc.add_paragraph("Author, A. (2026). A book. Sample Press.")
    doc.save(str(path))
    return path


class _Report(list):
    """Lines of the report, also written to the file at once, so a hang shows where it stopped."""

    def __init__(self, path: Path | None):
        super().__init__()
        self.path = Path(path) if path else None
        if self.path:
            self.path.write_text("", encoding="utf-8")

    def append(self, line: str) -> None:
        super().append(line)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def __iadd__(self, more):
        for line in more:
            self.append(line)
        return self


def run_selftest(report_file: Path | None = None) -> int:
    lines = _Report(report_file)
    ok = False
    try:
        from .doctor import TOOLS, check_tool
        from .importers.convert import import_files
        from .outputs.export import run_export
        from .settings.load_save import JournalFolder

        lines.append("Started")
        for tool in TOOLS:
            lines.append(f"Checking {tool.name}")
            found, message = check_tool(tool)
            lines.append(f"{tool.name}: {'OK' if found else 'not available'} - {message}")
        with tempfile.TemporaryDirectory(prefix="issuebuilder-selftest-") as tmp:
            root = Path(tmp)
            journal = JournalFolder.create(root / "journal")
            issue = journal.create_issue(1, 1, "January", 2027)
            settings = issue.load()
            settings.export.print_cover = True
            issue.save(settings)
            lines.append("Importing a Word article")
            articles = import_files(issue, settings, [_sample_word(root / "article.docx")])
            lines.append(f"Import: {articles[0].import_status} {articles[0].import_message}".strip())
            lines.append(f"Title found: {articles[0].title}")
            result = run_export(journal, issue, lines.append, force=True, offprints=True)
            lines += [f"Note: {n}" for n in result.notes]
            lines += [f"File: {f.name}" for f in result.files]
            electronic = issue.output / f"{settings.slug}_electronic_issue.pdf"
            ok = result.ok and articles[0].import_status == "ok" and electronic.is_file() \
                and electronic.stat().st_size > 1000
    except Exception:
        lines.append(traceback.format_exc())
    lines.append("SELFTEST " + ("PASSED" if ok else "FAILED"))
    print("\n".join(lines))
    return 0 if ok else 1
