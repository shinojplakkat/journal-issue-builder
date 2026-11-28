"""Opens the real program window off-screen and walks through every screen."""

import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from issuebuilder.gui import app as gui  # noqa: E402
from issuebuilder.gui.common import ClickOnlyDoubleSpinBox  # noqa: E402
from issuebuilder.gui.screens.issue import ArticleDialog  # noqa: E402
from issuebuilder.settings.models import Article, Author, Block  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_window_and_screens(qapp, tmp_path, monkeypatch):
    # Dialogs would wait for a click; answer them automatically.
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    QSettings("JournalIssueBuilder", "JournalIssueBuilder").setValue("journal_folder", str(tmp_path / "J"))

    window = gui.MainWindow()
    window.show()
    area = qapp.primaryScreen().availableGeometry()
    assert window.height() <= area.height()
    assert window.minimumHeight() <= area.height()
    assert "Window" in [action.text().replace("&", "") for action in window.menuBar().actions()]
    assert "#f3f6fb" in qapp.styleSheet()
    window.start()
    assert window.state.journal is not None
    assert window.state.issue is not None, "a first issue is created on first run"

    # Put one article in by hand (no LibreOffice needed) and visit every screen.
    issue = window.state.issue
    settings = issue.load()
    article = Article(id="a01", source_kind="word", title="A test article", authors=[Author(name="A. Author")],
                      blocks=[Block(i=0, text="A test article", label="title", confidence=0.97),
                              Block(i=1, text="Body text", label="body", confidence=0.4)])
    settings.article_order.append("a01")
    issue.save(settings)
    issue.save_article(article)
    window.state.data_changed.emit()

    for index in range(window.tabs.count()):
        window.tabs.setCurrentIndex(index)
        qapp.processEvents()

    journal_screen = window.screens[0][1]
    journal_screen.fields["title"].setText("My Test Journal")
    journal_screen.save()
    assert window.state.journal.load_journal().title == "My Test Journal"

    review = window.screens[2][1]
    review.load()
    assert review.table.rowCount() == 2
    review.label_changed(1, "heading1")
    assert issue.load_article("a01").blocks[1].label == "heading1"

    layout_screen = window.screens[3][1]
    layout_screen.load()
    layout_screen.sizes["abstract_pt"].setValue(15)
    layout_screen.sizes["footnote_pt"].setValue(5)
    monkeypatch.setattr("issuebuilder.gui.screens.layout.info", lambda *a, **k: None)
    layout_screen.restore_defaults_button.click()
    restored = issue.load().layout
    assert restored.abstract_pt == 10
    assert restored.footnote_pt == 9
    layout_screen.save()
    layout_screen.script_choice.setCurrentIndex(layout_screen.script_choice.findData("Malayalam"))
    layout_screen.script_font_choice.setCurrentText("Manjari")
    layout_screen.map_script_font()
    assert issue.load().layout.script_fonts["Malayalam"] == "Manjari"

    cover = window.screens[4][1]
    cover.load()
    cover.calculate()
    assert "Spine" in cover.result.text()

    export = window.screens[5][1]
    findings = export.run_checks()
    assert isinstance(findings, list)

    dialog = ArticleDialog(window, issue.load_article("a01"))
    dialog.title.setText("Changed title")
    issue.save_article(dialog.apply())
    assert issue.load_article("a01").title == "Changed title"

    window.close()


def test_type_size_spinbox_ignores_wheel(qapp):
    class IgnoredEvent:
        ignored = False

        def ignore(self):
            self.ignored = True

    box = ClickOnlyDoubleSpinBox()
    box.setRange(5, 40)
    box.setValue(12)
    event = IgnoredEvent()
    box.wheelEvent(event)
    assert event.ignored
    assert box.value() == 12
