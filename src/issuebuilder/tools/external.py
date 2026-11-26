"""The single place where external programs are found and run (blueprint rule 2).

Other modules never call subprocess directly. They ask this module for a
program, and get a clear message if it is not installed.
"""

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


class ToolMissingError(RuntimeError):
    """Raised when a required external program cannot be found."""


@dataclass
class ExternalTool:
    name: str                       # shown to the user, e.g. "LibreOffice"
    commands: list[str]             # names to look for on PATH
    version_args: list[str]         # arguments that print the version
    install_hint: str               # what to tell the user if it is missing
    required: bool = True           # False for optional tools (Ghostscript)
    extra_places: list[Path] = field(default_factory=list)  # usual install folders

    def find(self) -> Path | None:
        """Return the program's path, or None if it is not installed."""
        # A program bundled next to our own executable wins, so the
        # installer can ship Pandoc and Typst without touching PATH.
        bundled = _bundle_dir()
        for command in self.commands:
            for candidate in (bundled / command, bundled / (command + ".exe")):
                if candidate.is_file():
                    return candidate
        for command in self.commands:
            found = shutil.which(command)
            if found:
                return Path(found)
        for place in self.extra_places:
            if place.is_file():
                return place
        return None

    def require(self) -> Path:
        """Return the program's path, or raise a clear error."""
        path = self.find()
        if path is None:
            raise ToolMissingError(f"{self.name} was not found. {self.install_hint}")
        return path

    def version(self) -> str:
        """Return the first line of the program's version output."""
        result = self.run(self.version_args, timeout=60)
        text = (result.stdout or result.stderr).strip()
        return text.splitlines()[0] if text else "unknown version"

    def run(self, args: list[str], timeout: float = 600, cwd: Path | None = None):
        """Run the program with the given arguments and return the result."""
        command = [str(self.require()), *args]
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            # Hides the black console window that would flash up on Windows.
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )


def _bundle_dir() -> Path:
    """Folder of the packaged app (PyInstaller), or a 'bin' folder in development."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "bin"
    return Path(__file__).resolve().parents[3] / "bin"


def windows_program_files(*parts: str) -> list[Path]:
    """Possible install paths under 'Program Files' on Windows (empty elsewhere)."""
    places = []
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(variable)
        if base:
            places.append(Path(base, *parts))
    return places
