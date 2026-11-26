"""The Export button: checks, then every chosen output, then a log (blueprint 8)."""

from __future__ import annotations

import copy
import json
import platform
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from .. import __version__
from ..assembler.blank_pages import required_total
from ..assembler.issue import PageSpec, Plan, make_plan
from ..checks.validation import Finding, check_issue
from ..cover import wrap
from ..settings.defaults import PAPER_SIZES_MM
from ..settings.load_save import IssueFolder, JournalFolder
from ..settings.models import GLUE
from . import calibration, electronic, offprint, printing


@dataclass
class ExportResult:
    ok: bool = True
    files: list[Path] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    log: Path | None = None


def padded_for_binding(plan: Plan, mode: str) -> Plan:
    """The print plan: same pages, plus blank pages at the end for the binding mode."""
    printed = copy.copy(plan)
    pages = list(plan.pages)
    total = required_total(len(pages), mode)
    last_number = next((p.number for p in reversed(pages) if p.number is not None), 0) or 0
    for k in range(total - len(pages)):
        pages.append(PageSpec("blank", role="blank", element="end padding", number=last_number + k + 1,
                              print_number=False))
    printed.pages = pages
    return printed


def run_export(journal_folder: JournalFolder, issue_folder: IssueFolder,
               progress: Callable[[str], None] | None = None, *, force: bool = False,
               offprints: bool = False, offprint_print: bool = False) -> ExportResult:
    say = progress or (lambda m: None)
    result = ExportResult()
    journal = journal_folder.load_journal()
    issue = issue_folder.load()
    options = issue.export
    out = issue_folder.output
    out.mkdir(parents=True, exist_ok=True)
    name = issue.slug

    say("Checking")
    result.findings = check_issue(journal_folder, issue_folder)
    errors = [f for f in result.findings if f.level == "error"]
    if errors and not force:
        result.ok = False
        result.notes.append("Export stopped: fix the errors listed under Checks first.")
        return result

    try:
        plan = make_plan(journal_folder, issue_folder, say)
        result.notes += plan.problems
        if not plan.placements:
            result.ok = False
            result.notes.append("No article could be laid out.")
            return result
        say("Making covers")
        covers = wrap.cover_pages(journal_folder, issue_folder, journal, issue)

        if options.electronic_issue:
            say("Making the electronic issue")
            target = out / f"{name}_electronic_issue.pdf"
            result.notes += electronic.electronic_issue(
                plan, journal, issue, covers if options.include_covers_in_electronic else None, target,
                keep_blanks=options.keep_blank_pages, proof=options.proof_watermark)
            result.files.append(target)
        if options.electronic_articles:
            say("Making the article PDFs")
            result.files += electronic.electronic_articles(plan, journal, issue, out / "articles",
                                                           proof=options.proof_watermark)

        if options.print_interior or options.print_cover:
            mode = issue.printing.binding_mode
            printed = padded_for_binding(plan, mode)
            print_dir = out / "print"
            if options.print_interior:
                say("Making the print interior")
                files, notes = printing.print_interior(printed, journal, issue, print_dir, name,
                                                       proof=options.proof_watermark)
                result.files += files
                result.notes += notes
            if options.print_cover:
                say("Making the print cover")
                if mode == GLUE:
                    files, notes, size = wrap.glue_cover(covers, journal, issue, len(printed.pages), print_dir, name)
                    result.notes.append(f"Spine width {size.spine_mm:g} mm for {len(printed.pages)} pages.")
                else:
                    target = print_dir / f"{name}_cover_staple_fold_sheet.pdf"
                    notes = wrap.staple_cover(covers, issue, target)
                    files = [target]
                result.files += files
                result.notes += notes
            say("Making calibration sheets")
            sheet = printing.SHEET_FOR_BOOKLET.get(issue.layout.page_size, "A4") if mode != GLUE \
                else issue.layout.page_size
            for paper, landscape in {(sheet, mode != GLUE), ("A3", True)}:
                target = print_dir / f"calibration_{paper}{'_landscape' if landscape else ''}.pdf"
                calibration.calibration_sheet(paper, target, issue.printing.unprintable_edge_mm, landscape)
                result.files.append(target)

        if offprints:
            say("Making offprints")
            files, notes = offprint.make_offprints(plan, journal, issue, covers, out / "offprints",
                                                   electronic=True, printed=offprint_print,
                                                   cover_line=issue.cover.offprint_line)
            result.files += files
            result.notes += notes
    except Exception as error:
        result.ok = False
        result.notes.append(f"Export failed: {error}")
        result.notes.append(traceback.format_exc())
    finally:
        result.log = _write_log(out, journal_folder, issue_folder, result, locals().get("plan"))
    say("Done" if result.ok else "Finished with problems")
    return result


def _write_log(out: Path, journal_folder: JournalFolder, issue_folder: IssueFolder,
               result: ExportResult, plan: Plan | None) -> Path:
    issue = issue_folder.load()
    lines = [
        f"Journal Issue Builder {__version__} — export log",
        f"Date: {datetime.now():%Y-%m-%d %H:%M}",
        f"Computer: {platform.system()} {platform.release()}",
        f"Issue: {issue.label}",
        f"Page size: {issue.layout.page_size}; binding: {issue.printing.binding_mode}",
        "",
    ]
    if plan is not None:
        lines.append(f"Issue pages (without end padding): {len(plan.pages)}")
        for p in plan.placements:
            lines.append(f"  {p.article.id}  pp. {p.pages_label}  {p.article.title}")
        lines.append("")
    if result.findings:
        lines.append("Checks:")
        lines += [f"  [{f.level.upper()}] {f.where}: {f.message}" for f in result.findings]
        lines.append("")
    if result.notes:
        lines.append("Notes:")
        lines += [f"  {n}" for n in result.notes]
        lines.append("")
    lines.append("Files:")
    lines += [f"  {f}" for f in result.files]
    lines += ["", "Settings used:", json.dumps(issue.to_dict(), indent=2, ensure_ascii=False)]
    log = out / "export_log.txt"
    log.write_text("\n".join(lines), encoding="utf-8")
    return log


__all__ = ["run_export", "ExportResult", "PAPER_SIZES_MM"]
