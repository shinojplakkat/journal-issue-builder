"""Script detection and Noto font fallback names used by layout and checks."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QFontDatabase

SCRIPT_RANGES = {
    "Arabic": ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF)),
    "Hebrew": ((0x0590, 0x05FF),),
    "Devanagari": ((0x0900, 0x097F),),
    "Bengali": ((0x0980, 0x09FF),),
    "Gurmukhi": ((0x0A00, 0x0A7F),),
    "Gujarati": ((0x0A80, 0x0AFF),),
    "Oriya": ((0x0B00, 0x0B7F),),
    "Tamil": ((0x0B80, 0x0BFF),),
    "Telugu": ((0x0C00, 0x0C7F),),
    "Kannada": ((0x0C80, 0x0CFF),),
    "Malayalam": ((0x0D00, 0x0D7F),),
    "Sinhala": ((0x0D80, 0x0DFF),),
    "Thai": ((0x0E00, 0x0E7F),),
}
SUPPORTED_SCRIPTS = tuple(SCRIPT_RANGES)


def scripts_in(text: str) -> set[str]:
    found = set()
    for character in text:
        codepoint = ord(character)
        for name, ranges in SCRIPT_RANGES.items():
            if any(start <= codepoint <= end for start, end in ranges):
                found.add(name)
                break
    return found


def noto_family(script: str, *, headings: bool = False) -> str:
    return f"Noto {'Sans' if headings else 'Serif'} {script}"


def script_font(script: str, indic_font: str, mappings: dict[str, str] | None = None,
                *, headings: bool = False) -> str:
    """Return a user's script mapping, then the legacy Malayalam font, then Noto."""
    if mappings and mappings.get(script, "").strip():
        return mappings[script].strip()
    if script == "Malayalam" and indic_font:
        return indic_font
    return noto_family(script, headings=headings)


def import_user_font(source: str | Path) -> tuple[str, Path]:
    """Install a local OTF/TTF font for the current user and return its family and path."""
    source_path = Path(source).expanduser().resolve()
    if source_path.suffix.casefold() not in {".otf", ".ttf", ".ttc"} or not source_path.is_file():
        raise ValueError("Choose an OTF, TTF or TTC font file.")
    source_id = QFontDatabase.addApplicationFont(str(source_path))
    families = QFontDatabase.applicationFontFamilies(source_id) if source_id >= 0 else []
    if not families:
        raise ValueError("The font file could not be read. Check that it is a valid OTF or TTF font.")
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Microsoft/Windows/Fonts"
    elif sys.platform == "darwin":
        root = Path.home() / "Library/Fonts"
    else:
        root = Path.home() / ".local/share/fonts/journal-issue-builder"
    root.mkdir(parents=True, exist_ok=True)
    # Include the font's family in the installed filename. Validation can then
    # find locally imported fonts even when their original download name is
    # unrelated to the family shown by the font (a common case for local fonts).
    safe_family = re.sub(r"[^A-Za-z0-9._-]+", "-", families[0]).strip(".-") or "font"
    target = root / f"{safe_family}-{source_path.name}"
    if source_path != target:
        shutil.copy2(source_path, target)
    QFontDatabase.addApplicationFont(str(target))
    if sys.platform.startswith("linux"):
        fc_cache = shutil.which("fc-cache")
        if fc_cache:
            subprocess.run([fc_cache, "-f", str(root)], check=False, capture_output=True)
    elif sys.platform == "win32":
        try:
            import winreg

            with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                  r"Software\Microsoft\Windows NT\CurrentVersion\Fonts") as key:
                winreg.SetValueEx(key, f"{families[0]} (TrueType)", 0, winreg.REG_SZ, str(target))
            import ctypes

            ctypes.windll.gdi32.AddFontResourceW(str(target))
            HWND_BROADCAST, WM_FONTCHANGE = 0xFFFF, 0x001D
            ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_FONTCHANGE, 0, 0)
        except OSError as exc:
            raise RuntimeError(f"The font was copied, but Windows could not register it: {exc}") from exc
    return families[0], target


@lru_cache(maxsize=64)
def font_file_present(family: str) -> bool:
    """Check common installed-font directories by their distribution filenames."""
    target = re.sub(r"[^a-z0-9]", "", family.casefold())
    roots = [Path(__file__).resolve().parents[3] / "fonts"]
    if sys.platform == "win32":
        roots += [Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
                  Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Windows/Fonts"]
    elif sys.platform == "darwin":
        roots += [Path("/System/Library/Fonts"), Path("/Library/Fonts"),
                  Path.home() / "Library/Fonts"]
    else:
        roots += [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"),
                  Path.home() / ".local/share/fonts", Path.home() / ".fonts"]
    for root in roots:
        if not root.is_dir():
            continue
        try:
            for path in root.rglob("*"):
                if path.is_file() and target in re.sub(r"[^a-z0-9]", "", path.stem.casefold()):
                    return True
        except OSError:
            continue
    return False
