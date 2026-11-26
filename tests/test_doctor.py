from pathlib import Path

import pytest

from issuebuilder.__main__ import main
from issuebuilder.tools.external import ExternalTool, ToolMissingError

MISSING = ExternalTool(
    name="Imaginary",
    commands=["no-such-program-xyz"],
    version_args=["--version"],
    install_hint="Install it.",
)


def test_missing_tool_gives_clear_error():
    assert MISSING.find() is None
    with pytest.raises(ToolMissingError, match="Imaginary was not found. Install it."):
        MISSING.require()


def test_extra_place_is_used(tmp_path: Path):
    program = tmp_path / "tool.exe"
    program.write_text("")
    tool = ExternalTool("T", ["no-such-program-xyz"], [], "", extra_places=[program])
    assert tool.find() == program


def test_doctor_runs_and_prints_report(capsys):
    code = main(["doctor"])
    output = capsys.readouterr().out
    assert code in (0, 1)
    for name in ("LibreOffice", "Pandoc", "Typst", "Ghostscript", "PyMuPDF"):
        assert name in output
