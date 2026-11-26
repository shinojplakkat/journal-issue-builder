"""Typst wrapper. Typst is bundled with the installer or found on PATH."""

from .external import ExternalTool

TYPST = ExternalTool(
    name="Typst",
    commands=["typst"],
    version_args=["--version"],
    install_hint=(
        "Typst should come with this program. For development, download it from "
        "https://github.com/typst/typst/releases and put it on PATH or in the 'bin' folder."
    ),
)
