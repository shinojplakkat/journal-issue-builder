"""Ghostscript wrapper. Optional: used only for grayscale print files and PDF/A."""

from .external import ExternalTool

GHOSTSCRIPT = ExternalTool(
    name="Ghostscript",
    # gswin64c / gswin32c are the console versions installed on Windows.
    commands=["gs", "gswin64c", "gswin32c"],
    version_args=["--version"],
    install_hint=(
        "Optional. Without it, grayscale print files and PDF/A export are switched off. "
        "Install from https://www.ghostscript.com/releases/ (on Ubuntu: sudo apt install ghostscript)."
    ),
    required=False,
)
