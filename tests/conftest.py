"""On GitHub Actions, show each test failure as an annotation on the build page."""

import os
import sys


def _annotate(title: str, text: str) -> None:
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    text = text[-6000:].replace("%", "%25").replace("\r", "").replace("\n", "%0A")
    title = title.replace(":", " ").replace(",", " ")
    sys.__stdout__.write(f"::error title={title}::{text}\n")
    sys.__stdout__.flush()


def pytest_runtest_logreport(report):
    if report.failed:
        _annotate(f"{sys.platform} {report.nodeid}", report.longreprtext)


def pytest_collectreport(report):
    if report.failed:
        _annotate(f"{sys.platform} collecting {report.nodeid}", report.longreprtext)
