"""LibreOffice wrapper. The user installs LibreOffice; we only find and call it."""

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
