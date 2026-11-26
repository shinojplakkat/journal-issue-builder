"""LibreOffice wrapper. The user installs LibreOffice; we only find and call it."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .external import ExternalTool, windows_program_files

LIBREOFFICE = ExternalTool(
    name="LibreOffice",
    commands=["soffice", "libreoffice"],
    version_args=["--version"],
    install_hint=(
        "Please install LibreOffice from https://www.libreoffice.org/download/ "
        "(on Ubuntu: sudo apt install libreoffice), then start this program again."
    ),
    extra_places=[
        *windows_program_files("LibreOffice", "program", "soffice.exe"),
        Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
    ],
)


class ConversionError(RuntimeError):
    pass


def convert(files: list[Path], target: str, outdir: Path, timeout: float = 600) -> dict[Path, Path]:
    """Convert files with LibreOffice; target is "pdf" or "docx".

    Returns {source: converted file}. Files that failed are left out, so one
    bad file never stops the rest (blueprint M3).

    A private LibreOffice profile is used, so the conversion works even when
    the editor has LibreOffice open on the screen at the same time.
    """
    outdir.mkdir(parents=True, exist_ok=True)
    if not files:
        return {}
    filter_name = {"pdf": "pdf", "docx": "docx:MS Word 2007 XML"}[target]
    profile = Path(tempfile.mkdtemp(prefix="issuebuilder-lo-"))
    try:
        result = LIBREOFFICE.run(
            [
                f"-env:UserInstallation={profile.as_uri()}",
                "--headless", "--norestore", "--nolockcheck",
                "--convert-to", filter_name,
                "--outdir", str(outdir),
                *[str(f) for f in files],
            ],
            timeout=timeout,
        )
    finally:
        shutil.rmtree(profile, ignore_errors=True)

    done = {}
    for source in files:
        produced = outdir / (Path(source).stem + "." + target)
        if produced.is_file() and produced.stat().st_size > 0:
            done[Path(source)] = produced
    if not done and files:
        detail = (result.stderr or result.stdout or "").strip()[-400:]
        raise ConversionError(f"LibreOffice could not convert the file(s). {detail}")
    return done


def convert_one(source: Path, target: str, outdir: Path) -> Path:
    done = convert([source], target, outdir)
    if Path(source) not in done:
        raise ConversionError(f"LibreOffice could not convert {Path(source).name}.")
    return done[Path(source)]
