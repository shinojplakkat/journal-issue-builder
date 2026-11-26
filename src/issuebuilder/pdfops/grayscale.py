"""Grayscale conversion with Ghostscript (optional, blueprint 3.1)."""

from __future__ import annotations

from pathlib import Path

from ..tools.ghostscript import GHOSTSCRIPT


def available() -> bool:
    return GHOSTSCRIPT.find() is not None


def convert(source: Path, target: Path) -> tuple[bool, str]:
    """Returns (done, message). Without Ghostscript the file is left in colour."""
    if not available():
        return False, ("Ghostscript is not installed, so the interior was left in colour. "
                       "A black-and-white printer will still print it in gray.")
    result = GHOSTSCRIPT.run([
        "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER",
        "-sDEVICE=pdfwrite",
        "-sColorConversionStrategy=Gray", "-dProcessColorModel=/DeviceGray",
        "-dCompatibilityLevel=1.6", "-dAutoRotatePages=/None",
        f"-sOutputFile={target}", str(source),
    ], timeout=900)
    if result.returncode != 0 or not target.is_file():
        return False, "Ghostscript could not make the grayscale file; the interior was left in colour."
    return True, ""
