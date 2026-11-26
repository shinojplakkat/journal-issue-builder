"""Checks before export (blueprint M13). Errors block export; warnings do not."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..settings.load_save import IssueFolder, JournalFolder
from ..settings.models import Article, IssueSettings, JournalSettings

ISSN = re.compile(r"^\d{4}-\d{3}[\dXx]$")


@dataclass
class Finding:
    level: str      # "error" or "warning"
    where: str      # "Journal", "Issue" or the article
    message: str


def issn_valid(issn: str) -> bool:
    """ISSN check digit: weights 8..2, mod 11, 10 written as X."""
    if not ISSN.match(issn):
        return False
    digits = issn.replace("-", "")
    total = sum(int(d) * w for d, w in zip(digits[:7], range(8, 1, -1)))
    check = (11 - total % 11) % 11
    return digits[7].upper() == ("X" if check == 10 else str(check))


def check_issue(journal_folder: JournalFolder, issue_folder: IssueFolder) -> list[Finding]:
    journal = journal_folder.load_journal()
    settings = issue_folder.load()
    articles = issue_folder.load_articles(settings)
    found: list[Finding] = []
    found += _check_journal(journal)
    found += _check_issue(settings, articles)
    for article in articles:
        found += _check_article(article, settings)
    found += _check_duplicates(journal_folder, issue_folder, articles)
    return found


def _check_journal(j: JournalSettings) -> list[Finding]:
    out = []
    if not j.title.strip():
        out.append(Finding("error", "Journal", "The journal title is missing."))
    if not j.print_issn.strip() and not j.e_issn.strip():
        out.append(Finding("error", "Journal", "Both ISSNs are missing."))
    for label, issn in (("Print ISSN", j.print_issn), ("Online ISSN", j.e_issn)):
        if issn.strip() and not issn_valid(issn.strip()):
            out.append(Finding("warning", "Journal", f"{label} '{issn}' does not have a valid check digit."))
    if not j.licence.strip():
        out.append(Finding("error", "Journal", "The licence text is missing."))
    if not j.publisher.strip():
        out.append(Finding("warning", "Journal", "The publisher name is missing."))
    return out


def _check_issue(s: IssueSettings, articles: list[Article]) -> list[Finding]:
    out = []
    if s.volume < 1 or s.number < 1:
        out.append(Finding("error", "Issue", "Volume and issue number must be 1 or more."))
    if not s.month or not s.year:
        out.append(Finding("error", "Issue", "The issue date (month and year) is missing."))
    if not articles:
        out.append(Finding("error", "Issue", "The issue has no articles."))
    return out


def _check_article(a: Article, s: IssueSettings) -> list[Finding]:
    where = f"{a.id}: {a.title[:50] or a.source_name}"
    out = []
    if a.import_status != "ok":
        out.append(Finding("warning", where, f"Could not be imported and will be left out: {a.import_message}"))
        return out
    if not a.title.strip():
        out.append(Finding("error", where, "The article has no title."))
    if not any(x.name.strip() for x in a.authors):
        out.append(Finding("error", where, "The article has no author."))
    if not any(a.dates.values()):
        out.append(Finding("warning", where, "Received, accepted and published dates are missing."))
    if a.review_status == "needs_review":
        out.append(Finding("warning", where, "Not reviewed yet (Review screen)."))
    limit = s.export.abstract_word_limit
    if a.abstract and len(a.abstract.split()) > limit:
        out.append(Finding("warning", where, f"Abstract has {len(a.abstract.split())} words (limit {limit})."))
    if a.doi:
        suffix = a.doi.split("/", 1)[-1]
        if re.search(r"\d{4}-\d{3}[\dXx]", suffix) or re.search(r"(19|20)\d{2}", suffix) \
                or re.search(r"\b(vol|issue|pp?)\b", suffix, re.IGNORECASE):
            out.append(Finding("warning", where, f"DOI suffix '{suffix}' contains a year, ISSN, issue or page "
                                                 "information; DOIs should not carry meaning that may change."))
    for author in a.authors:
        if author.orcid:
            from ..analyzer.orcid import is_valid

            if not is_valid(author.orcid):
                out.append(Finding("warning", where, f"ORCID {author.orcid} of {author.name} is not valid."))
    for w in a.warnings:
        if "below" in w and "pt" in w:
            out.append(Finding("warning", where, w))
    return out


def _check_duplicates(journal_folder: JournalFolder, current: IssueFolder, articles: list[Article]) -> list[Finding]:
    """An article may belong to only one issue (same file in two issues is an error)."""
    out = []
    mine = {a.source_hash: a for a in articles if a.source_hash}
    seen_here: dict[str, str] = {}
    for a in articles:
        if a.source_hash and a.source_hash in seen_here:
            out.append(Finding("error", f"{a.id}", f"Same file as {seen_here[a.source_hash]} in this issue."))
        seen_here.setdefault(a.source_hash, a.id)
    for other in journal_folder.list_issues():
        if other.path.resolve() == current.path.resolve():
            continue
        try:
            other_settings = other.load()
            for a in other.load_articles(other_settings):
                if a.source_hash in mine:
                    out.append(Finding("error", mine[a.source_hash].id,
                                       f"This article is also in {other_settings.label}."))
        except Exception:
            continue
    return out
