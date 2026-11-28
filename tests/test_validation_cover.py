"""Preflight checks flag unusably small cover photographs for print."""

from PIL import Image

from issuebuilder.checks.validation import check_issue
from issuebuilder.settings.load_save import JournalFolder


def test_low_resolution_cover_image_is_reported(tmp_path):
    journal = JournalFolder.create(tmp_path / "journal")
    issue = journal.create_issue(1, 1, "January", 2027)
    settings = issue.load()
    settings.cover.front_image = "cover.png"
    Image.new("RGB", (500, 500), "#355577").save(issue.assets / "cover.png")
    issue.save(settings)

    findings = check_issue(journal, issue)

    warnings = [finding.message for finding in findings if finding.level == "warning"]
    assert any("front cover image" in message and "dpi" in message for message in warnings)


def test_missing_cover_image_is_reported_as_generated_fallback(tmp_path):
    journal = JournalFolder.create(tmp_path / "journal")
    issue = journal.create_issue(1, 1, "January", 2027)
    settings = issue.load()
    settings.cover.back_image = "missing.png"
    issue.save(settings)

    findings = check_issue(journal, issue)

    assert any("selected back cover image 'missing.png' is missing" in finding.message
               for finding in findings)
