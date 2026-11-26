"""`python -m issuebuilder doctor`: reports which tools and libraries are available."""

import importlib.util
import platform
import sys

from .tools.external import ExternalTool
from .tools.ghostscript import GHOSTSCRIPT
from .tools.libreoffice import LIBREOFFICE

TOOLS: list[ExternalTool] = [LIBREOFFICE, GHOSTSCRIPT]

# (import names to try, name shown to the user, what it is needed for)
LIBRARIES = [
    (["docx"], "python-docx", "reading and restyling Word files"),
    (["pikepdf"], "pikepdf", "joining, numbering and imposing PDFs"),
    (["reportlab"], "ReportLab", "page numbers, covers and calibration sheets"),
    (["pdfplumber"], "pdfplumber", "reading text from PDF articles"),
    (["pypdfium2"], "pypdfium2", "page previews"),
    (["PIL"], "Pillow", "pictures"),
    (["PySide6"], "PySide6", "the program window (GUI)"),
]


def check_tool(tool: ExternalTool) -> tuple[bool, str]:
    """Return (found, message) for one external program."""
    path = tool.find()
    if path is None:
        return False, f"NOT FOUND. {tool.install_hint}"
    try:
        return True, f"{tool.version()}  ({path})"
    except Exception as error:  # a broken install should be reported, not crash doctor
        return False, f"found at {path} but it did not start: {error}"


def check_library(modules: list[str]) -> bool:
    return any(importlib.util.find_spec(module) is not None for module in modules)


def run_doctor() -> int:
    """Print a status report. Returns 0 if everything required is present, else 1."""
    print("Journal Issue Builder - system check")
    print(f"Python {platform.python_version()} on {platform.system()} {platform.release()}")
    print()

    all_ok = sys.version_info >= (3, 11)
    if not all_ok:
        print("[MISSING ] Python 3.11 or newer is required.")

    print("External programs:")
    for tool in TOOLS:
        found, message = check_tool(tool)
        if found:
            label = "OK"
        elif tool.required:
            label = "MISSING"
            all_ok = False
        else:
            label = "OPTIONAL"
        print(f"  [{label:8}] {tool.name}: {message}")

    print()
    print("Python libraries:")
    for modules, name, purpose in LIBRARIES:
        if check_library(modules):
            print(f"  [OK      ] {name}")
        else:
            all_ok = False
            print(f"  [MISSING ] {name} (needed for {purpose})")

    print()
    print("Result: ready." if all_ok else "Result: some required parts are missing (see above).")
    return 0 if all_ok else 1
