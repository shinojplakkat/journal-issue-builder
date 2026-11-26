"""The single place where external programs are found and run (blueprint rule 2).

Other modules never call subprocess directly. They ask this module for a
program, and get a clear message if it is not installed.
"""

import os
import shutil
import subprocess
import sys
import tempfile
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
        """Return the first line of the program's version output.

        Raises RuntimeError if the program starts but reports an error.
        """
        result = self.run(self.version_args, timeout=60)
        text = (result.stdout or result.stderr).strip()
        first = text.splitlines()[0] if text else "unknown version"
        if result.returncode != 0:
            raise RuntimeError(first)
        return first

    def run(self, args: list[str], timeout: float = 600, cwd: Path | None = None):
        """Run the program and return a CompletedProcess with its output.

        Output goes to temporary files, not pipes: LibreOffice on Windows starts
        a second process that can keep a pipe open and make the wait endless.
        On timeout the whole process tree is stopped.
        """
        command = [str(self.require()), *args]
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                cwd=cwd,
                env=clean_environment(),
                # Hides the black console window that would flash up on Windows.
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _stop_tree(process)
                raise
            out.seek(0)
            err.seek(0)
            return subprocess.CompletedProcess(
                command, code,
                out.read().decode("utf-8", "replace"),
                err.read().decode("utf-8", "replace"),
            )


def _stop_tree(process: subprocess.Popen) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        process.kill()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass


def clean_environment() -> dict[str, str]:
    """The environment for outside programs, without the packaged program's own libraries.

    The packaged program (PyInstaller) points the library search path at its
    own folder. LibreOffice must not load those libraries: it would fail with
    errors such as "GLIBCXX_3.4.31 not found" (Linux) or a missing DLL entry
    point (Windows).
    """
    env = dict(os.environ)
    if not getattr(sys, "frozen", False):
        return env
    for name in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        original = env.pop(name + "_ORIG", None)
        if original is not None:
            env[name] = original
        else:
            env.pop(name, None)
    if sys.platform == "win32":
        # Undo the DLL folder the packaged program set for itself, for the child process.
        try:
            import ctypes

            ctypes.windll.kernel32.SetDllDirectoryW(None)
        except Exception:
            pass
        bundle = str(Path(sys.executable).parent)
        env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep)
                                      if p and not p.startswith(bundle))
    return env


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
