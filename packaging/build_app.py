"""Build the program folder with PyInstaller (Windows and Linux).

    python packaging/build_app.py

Result: dist/JournalIssueBuilder/ with the program and everything it needs
(Python, Qt, PDF libraries, fonts). LibreOffice is not included; the user
installs it once.
"""

import os
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "packaging" / "build"

sys.path.insert(0, str(ROOT / "packaging"))
import make_icon  # noqa: E402

make_icon.main(BUILD)
icon = BUILD / ("icon.ico" if sys.platform == "win32" else "icon.png")
sep = os.pathsep

PyInstaller.__main__.run([
    str(ROOT / "packaging" / "app_entry.py"),
    "--name", "JournalIssueBuilder",
    "--windowed",
    "--noconfirm",
    "--clean",
    "--paths", str(ROOT / "src"),
    "--icon", str(icon),
    "--distpath", str(ROOT / "dist"),
    "--workpath", str(BUILD / "work"),
    "--specpath", str(BUILD),
    "--add-data", f"{ROOT / 'fonts'}{sep}fonts",
    "--add-data", f"{ROOT / 'LICENSE'}{sep}.",
    "--add-data", f"{ROOT / 'THIRD_PARTY_NOTICES.md'}{sep}.",
    # Libraries that bring data files or native parts PyInstaller cannot see on its own.
    "--collect-data", "docx",          # the blank Word template python-docx starts from
    "--collect-data", "pdfminer",      # character maps used by pdfplumber
    "--collect-all", "pypdfium2",
    "--collect-all", "pypdfium2_raw",
    "--collect-all", "pikepdf",
    "--collect-all", "reportlab",
    "--hidden-import", "issuebuilder.gui.app",
    # Not used; leaving them out keeps the program smaller.
    "--exclude-module", "tkinter",
    "--exclude-module", "matplotlib",
    "--exclude-module", "numpy",
])
