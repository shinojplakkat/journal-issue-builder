import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication
from docx import Document
from docx.oxml.ns import qn

from issuebuilder.builder.word_layout import restyle
from issuebuilder.settings.models import Article, Block, LayoutSettings
from issuebuilder.settings.script_fonts import import_user_font, script_font


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_script_specific_font_overrides_fallbacks():
    layout = LayoutSettings.from_dict({
        "indic_font": "Noto Serif Malayalam",
        "script_fonts": {"Malayalam": "Manjari", "Devanagari": "Mukta"},
    })

    assert script_font("Malayalam", layout.indic_font, layout.script_fonts) == "Manjari"
    assert script_font("Devanagari", layout.indic_font, layout.script_fonts) == "Mukta"
    assert script_font("Tamil", layout.indic_font, layout.script_fonts) == "Noto Serif Tamil"


def test_legacy_malayalam_font_setting_remains_supported():
    layout = LayoutSettings.from_dict({"indic_font": "Rachana"})

    assert script_font("Malayalam", layout.indic_font, layout.script_fonts) == "Rachana"


def test_mapped_font_is_written_to_article_text_runs():
    document = Document()
    document.add_paragraph("മലയാളം പരീക്ഷണം")
    article = Article(id="a01", blocks=[Block(i=0, text="മലയാളം പരീക്ഷണം", label="body")])
    layout = LayoutSettings.for_page_size("A5")
    layout.script_fonts["Malayalam"] = "Local Malayalam Family"

    restyle(document, article, layout)

    assert document.paragraphs[0].runs[0]._element.rPr.rFonts.get(qn("w:cs")) == "Local Malayalam Family"


def test_import_font_copies_and_registers_a_local_font(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    source = Path(__file__).parents[1] / "fonts" / "Manjari-Regular.otf"
    family, installed = import_user_font(source)

    assert family == "Manjari"
    assert installed.is_file()
    assert "manjari" in installed.name.casefold()
    if sys.platform == "win32":
        assert installed.parent == tmp_path / "local" / "Microsoft/Windows/Fonts"
    elif sys.platform == "darwin":
        assert installed.parent == tmp_path / "home" / "Library/Fonts"
    else:
        assert installed.parent == tmp_path / "home" / ".local/share/fonts/journal-issue-builder"

    if sys.platform == "win32":
        import ctypes
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows NT\CurrentVersion\Fonts", 0,
                                winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, f"{family} (TrueType)")
        except OSError:
            pass
        ctypes.windll.gdi32.RemoveFontResourceW(str(installed))
        ctypes.windll.user32.SendMessageW(0xFFFF, 0x001D, 0, 0)
