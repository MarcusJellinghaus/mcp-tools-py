"""Tests for report_data: pure extraction from the parsed pytest report."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_tools_py.code_checker_pytest.models import LogRecord
from mcp_tools_py.code_checker_pytest.parsers import parse_pytest_report
from mcp_tools_py.code_checker_pytest.report_data import (
    format_log_record,
    relative_path,
    strip_xdist_header,
)


def _record(exc_text: str | None = None) -> LogRecord:
    """Build a WARNING record from logger "app" at mod.py:12."""
    return LogRecord(
        name="app",
        msg="disk low",
        args=None,
        levelname="WARNING",
        levelno=30,
        pathname="/src/mod.py",
        filename="mod.py",
        module="mod",
        exc_info=None,
        exc_text=exc_text,
        stack_info=None,
        lineno=12,
        funcName="check",
        created=0.0,
        msecs=0.0,
        relativeCreated=0.0,
        thread=1,
        threadName="MainThread",
        processName="MainProcess",
        process=1,
    )


class TestStripXdistHeader:
    """strip_xdist_header drops a leading [gwN] line."""

    def test_header_only_gives_none(self) -> None:
        """A longrepr that is only the header leaves nothing."""
        assert strip_xdist_header("[gw0] win32 -- Python 3.12 C:\\py.exe") is None

    def test_header_then_body(self) -> None:
        """The body after the header is kept."""
        assert strip_xdist_header("[gw1] linux -- Python\nE  boom") == "E  boom"

    def test_without_header_unchanged(self) -> None:
        """Text without a header is returned as given."""
        text = "E  assert 1 == 2\nfoo.py:3: AssertionError"
        assert strip_xdist_header(text) == text

    def test_bracket_not_header_unchanged(self) -> None:
        """A first line starting with another bracket is kept."""
        text = "[100%] done\nmore"
        assert strip_xdist_header(text) == text

    @pytest.mark.parametrize("value", [None, ""])
    def test_empty_gives_none(self, value: str | None) -> None:
        """None and empty text give None."""
        assert strip_xdist_header(value) is None


class TestRelativePath:
    """relative_path gives a posix path relative to the root."""

    def test_inside_root(self, tmp_path: Path) -> None:
        """A path under the root becomes relative, posix form."""
        root = str(tmp_path)
        path = str(tmp_path / "pkg" / "mod.py")
        assert relative_path(path, root) == "pkg/mod.py"

    def test_outside_root(self, tmp_path: Path) -> None:
        """A path outside the root is returned as given."""
        root = str(tmp_path / "project")
        path = str(tmp_path / "elsewhere" / "mod.py")
        assert relative_path(path, root) == path

    def test_frozen_module(self, tmp_path: Path) -> None:
        """A pseudo path such as <frozen os> is returned as given."""
        assert relative_path("<frozen os>", str(tmp_path)) == "<frozen os>"

    def test_other_drive(self, tmp_path: Path) -> None:
        """relpath raising ValueError (other drive) returns the path as given."""
        with patch(
            "mcp_tools_py.code_checker_pytest.report_data.os.path.relpath",
            side_effect=ValueError("path is on mount 'D:'"),
        ):
            assert relative_path("D:\\x\\mod.py", str(tmp_path)) == "D:\\x\\mod.py"


class TestFormatLogRecord:
    """format_log_record uses pytest's default log format."""

    def test_without_exc_text(self) -> None:
        """Level padded to 8, then logger:file:line message."""
        assert format_log_record(_record()) == "WARNING  app:mod.py:12 disk low"

    def test_with_exc_text(self) -> None:
        """exc_text lines follow the record line."""
        text = "Traceback (most recent call last):\nValueError: bad"
        assert format_log_record(_record(text)) == (
            "WARNING  app:mod.py:12 disk low\n" + text
        )


def test_parse_keeps_int_warning_lineno() -> None:
    """parse_pytest_report keeps an int lineno on warnings."""
    data = {
        "created": 0.0,
        "duration": 0.1,
        "exitcode": 0,
        "root": "/project",
        "environment": {},
        "summary": {"collected": 0, "total": 0},
        "warnings": [
            {
                "message": "deprecated",
                "category": "DeprecationWarning",
                "when": "runtest",
                "filename": "/project/mod.py",
                "lineno": 7,
            }
        ],
    }
    report = parse_pytest_report(json.dumps(data))
    assert report.warnings is not None
    assert report.warnings[0].lineno == 7
    assert isinstance(report.warnings[0].lineno, int)
