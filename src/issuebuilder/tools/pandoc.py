"""Pandoc wrapper. Pandoc is bundled with the installer or found on PATH."""

from .external import ExternalTool, windows_program_files

PANDOC = ExternalTool(
    name="Pandoc",
    commands=["pandoc"],
    version_args=["--version"],
    install_hint=(
        "Pandoc should come with this program. For development, install it from "
        "https://pandoc.org/installing.html (on Ubuntu: sudo apt install pandoc)."
    ),
    extra_places=windows_program_files("Pandoc", "pandoc.exe"),
)
