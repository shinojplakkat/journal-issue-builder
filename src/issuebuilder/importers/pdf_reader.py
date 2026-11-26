"""Checking submitted PDFs and suggesting their details (blueprint M3 and M4b)."""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from ..pdfops import inspect as pdf_inspect


@dataclass
class PdfReport:
    ok: bool = True
    problem: str = ""                  # why the file cannot be used
    pages: int = 0
    width_mm: float = 0
    height_mm: float = 0
    body_pt: float = 0                 # most common text size
    suggestions: dict = field(default_factory=dict)  # title, authors, abstract


def check_pdf(path: Path) -> PdfReport:
    report = PdfReport()
    status = pdf_inspect.open_status(path)
    if status != "ok":
        report.ok = False
        report.problem = {
            "encrypted": "The PDF is password-protected. Ask the author for an unprotected copy.",
            "corrupt": "The PDF is damaged and cannot be opened.",
            "empty": "The PDF has no pages.",
        }.get(status, status)
        return report

    report.pages, (report.width_mm, report.height_mm) = pdf_inspect.page_count_and_size(path)
    lines = pdf_inspect.text_lines(path, max_pages=2)
    if not lines:
        report.ok = False
        report.problem = ("The PDF has no readable text (probably a scan). Ask for the Word file, "
                          "or a PDF made from it.")
        return report

    sizes = [round(line.size, 1) for line in lines for _ in range(max(1, len(line.text.split())))]
    report.body_pt = statistics.mode(sizes) if sizes else 0
    report.suggestions = suggest_details(lines, report.body_pt)
    return report


def suggest_details(lines, body_pt: float) -> dict:
    """Guess title (largest text on page 1), authors (lines just after it) and abstract."""
    first_page = [l for l in lines if l.page == 0]
    suggestions: dict = {"title": "", "authors": [], "abstract": ""}
    if not first_page:
        return suggestions
    top = first_page[: max(12, len(first_page) // 3)]
    largest = max(l.size for l in top)
    if largest <= body_pt + 0.5:
        title_lines = top[:1]
    else:
        title_lines = [l for l in top if abs(l.size - largest) < 0.6]
    suggestions["title"] = " ".join(l.text for l in title_lines).strip()

    after = first_page.index(title_lines[-1]) + 1
    for line in first_page[after: after + 6]:
        if re.match(r"^\s*(abstract|summary)\b", line.text, re.IGNORECASE):
            break
        if len(line.text.split()) <= 12 and not re.search(r"university|department|institute|college|@|orcid|e-?mail",
                                                          line.text, re.IGNORECASE):
            suggestions["authors"].append(re.sub(r"[\d*†‡§]+", "", line.text).strip(" ,"))

    texts = [l.text for l in lines]
    for k, text in enumerate(texts):
        match = re.match(r"^\s*(abstract|summary)\b\s*[:.\-–—]?\s*(.*)$", text, re.IGNORECASE)
        if match:
            parts = [match.group(2)] if match.group(2) else []
            for following in texts[k + 1: k + 25]:
                if re.match(r"^\s*(key\s*words?|introduction|1\.?\s)", following, re.IGNORECASE):
                    break
                parts.append(following)
            suggestions["abstract"] = " ".join(parts).strip()
            break
    return suggestions
