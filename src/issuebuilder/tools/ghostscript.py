"""Ghostscript wrapper. Optional: used for grayscale print files and PDF/A output."""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

from .external import ExternalTool

GHOSTSCRIPT = ExternalTool(
    name="Ghostscript",
    # gswin64c / gswin32c are the console versions installed on Windows.
    commands=["gs", "gswin64c", "gswin32c"],
    version_args=["--version"],
    install_hint=(
        "Optional. Without it, grayscale conversion and PDF/A output are unavailable. "
        "Install from https://www.ghostscript.com/releases/ (on Ubuntu: sudo apt install ghostscript)."
    ),
    required=False,
)


def _search_paths() -> list[Path]:
    """Read Ghostscript's own library search paths for its PDF/A definition file."""
    result = GHOSTSCRIPT.run(["-h"], timeout=60)
    text = result.stdout + "\n" + result.stderr
    match = re.search(r"Search path:\s*(.*?)(?:\n\s*(?:For more information|Ghostscript is also)|\Z)",
                      text, re.S | re.I)
    if not match:
        return []
    paths = []
    for item in re.split(r"\s+:\s*", match.group(1)):
        item = item.strip().strip(";:")
        if item:
            paths.append(Path(item))
    return paths


def _pdfa_definition() -> Path | None:
    for folder in _search_paths():
        for candidate in (folder / "PDFA_def.ps", folder.parent.parent / "lib" / "PDFA_def.ps"):
            if candidate.is_file():
                return candidate
    return None


def _srgb_profile(definition: Path) -> Path | None:
    candidates = [
        definition.parent.parent / "iccprofiles" / "srgb.icc",
        definition.parent.parent / "iccprofiles" / "default_rgb.icc",
        Path("/usr/share/color/icc/colord/sRGB.icc"),
        Path("/usr/share/color/icc/sRGB.icc"),
        Path("/usr/local/share/color/icc/sRGB.icc"),
        Path("/System/Library/ColorSync/Profiles/sRGB Profile.icc"),
        Path("C:/Windows/System32/spool/drivers/color/sRGB Color Space Profile.icm"),
    ]
    candidates.extend(definition.parent.parent.glob("iccprofiles/*srgb*.icc"))
    return next((path for path in candidates if path.is_file()), None)


def make_pdfa2b(source: Path, target: Path, title: str = "Journal issue") -> tuple[bool, str]:
    """Create a strict Ghostscript PDF/A-2b conversion when its resources exist.

    This does not replace independent conformance validation with veraPDF.
    """
    target.unlink(missing_ok=True)
    if GHOSTSCRIPT.find() is None:
        return False, "Ghostscript is not installed; PDF/A output was not made."
    try:
        definition = _pdfa_definition()
    except Exception as error:
        return False, f"Ghostscript's PDF/A support could not be checked: {error}"
    if definition is None:
        return False, "Ghostscript's PDFA_def.ps was not found; PDF/A output was not made."
    profile = _srgb_profile(definition)
    if profile is None:
        return False, "No sRGB ICC profile was found; install one before making PDF/A output."

    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="issuebuilder-pdfa-") as temporary:
            work = Path(temporary)
            script = definition.read_text(encoding="latin-1")
            profile_literal = str(profile.resolve()).replace("\\", "/")
            profile_literal = profile_literal.replace("(", "\\(").replace(")", "\\)")
            try:
                profile_literal.encode("latin-1")
            except UnicodeEncodeError:
                return False, "The sRGB profile path contains characters Ghostscript cannot read safely."
            script, substitutions = re.subn(
                r"(?m)^/ICCProfile\s+\([^\r\n]*\)",
                lambda _: f"/ICCProfile ({profile_literal})", script, count=1,
            )
            if substitutions != 1:
                return False, "Ghostscript's PDF/A definition file could not be prepared."
            def_file = work / "PDFA_def.ps"
            def_file.write_text(script, encoding="latin-1")
            plain_title = title.replace("\r", " ").replace("\n", " ")
            title_bytes = b"\xfe\xff" + plain_title.encode("utf-16-be")
            safe_title = "".join(f"\\{byte:03o}" for byte in title_bytes)
            metadata_file = work / "PDF_metadata.ps"
            metadata_file.write_text(f"[ /Title ({safe_title}) /DOCINFO pdfmark\n", encoding="latin-1")
            result = GHOSTSCRIPT.run([
                "-dPDFA=2", "-dBATCH", "-dNOPAUSE", "-dSAFER",
                "-dPDFACompatibilityPolicy=2", "-sDEVICE=pdfwrite",
                "-sColorConversionStrategy=RGB", f"-sOutputFile={target.resolve()}",
                f"--permit-file-read={profile.resolve()}", "-c", "/PreserveAnnotTypes [/Link] def",
                "-f", str(def_file), str(source.resolve()), str(metadata_file),
            ], timeout=900, cwd=work)
        transcript = result.stdout + "\n" + result.stderr
        if result.returncode != 0 or "PDF/A processing aborted" in transcript \
                or "may not be a PDF/A file" in transcript or not target.is_file() or target.stat().st_size == 0:
            target.unlink(missing_ok=True)
            # Keep the interpreter's explanation. Older Ghostscript releases
            # print the useful /invalidfileaccess or PDF/A error before the
            # generic final "Unrecoverable error" line.
            detail = [line.strip() for line in transcript.splitlines() if line.strip()]
            summary = "\n".join(detail[-8:])[-1600:] if detail else "unknown error"
            return False, "Ghostscript could not create the PDF/A-2b file:\n" + summary
        return True, "Created using Ghostscript's strict PDF/A-2b mode. Run veraPDF before relying on conformance."
    except Exception as error:
        target.unlink(missing_ok=True)
        return False, f"PDF/A-2b conversion failed: {error}"
