"""Tests for report_data: pure extraction from the parsed pytest report."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_tools_py.code_checker_pytest.models import (
    Collector,
    LogRecord,
    PytestReport,
    StageInfo,
    Summary,
    Test,
)
from mcp_tools_py.code_checker_pytest.parsers import parse_pytest_report
from mcp_tools_py.code_checker_pytest.report_data import (
    SkipKey,
    folded_skips,
    format_log_record,
    module_skip_count,
    relative_path,
    skip_lines,
    skipped_count,
    strip_xdist_header,
)
from mcp_tools_py.code_checker_pytest.reporting import get_test_summary


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


def _skip_repr(path: Path, lineno: int, reason: str = "r") -> str:
    """A skip longrepr as pytest-json-report writes it: str of the tuple."""
    return str((str(path), lineno, f"Skipped: {reason}"))


def _skipped_test(
    nodeid: str,
    longrepr: str | None,
    keywords: list[str],
    when: str = "setup",
    outcome: str = "skipped",
) -> Test:
    """A test whose `when` stage has stage outcome "skipped"."""
    stage = StageInfo(duration=0.0, outcome="skipped", longrepr=longrepr)
    passed_setup = StageInfo(duration=0.0, outcome="passed")
    return Test(
        nodeid=nodeid,
        lineno=1,
        keywords=keywords,
        outcome=outcome,
        setup=stage if when == "setup" else passed_setup,
        call=stage if when == "call" else None,
    )


def _skipped_collector(nodeid: str, longrepr: str | None) -> Collector:
    """A collector with outcome "skipped"."""
    return Collector(nodeid=nodeid, outcome="skipped", result=[], longrepr=longrepr)


def _report(
    root: Path,
    tests: list[Test] | None = None,
    collectors: list[Collector] | None = None,
    skipped: int | None = None,
) -> PytestReport:
    """A report rooted at `root` with the given tests and collectors."""
    return PytestReport(
        created=0.0,
        duration=0.5,
        exitcode=0,
        root=str(root),
        environment={},
        summary=Summary(
            collected=len(tests or []), total=len(tests or []), skipped=skipped
        ),
        collectors=collectors,
        tests=tests,
    )


class TestFoldedSkips:
    """folded_skips folds skip entries like pytest's _folded_skips."""

    def test_module_pytestmark_folds_without_lineno(self, tmp_path: Path) -> None:
        """Module-level pytestmark skip: keywords have skip, not pytestmark."""
        path = tmp_path / "tests" / "test_a.py"
        tests = [
            _skipped_test(
                f"tests/test_a.py::test_{i}", _skip_repr(path, 3 + i), ["skip"]
            )
            for i in range(2)
        ]
        folded = folded_skips(_report(tmp_path, tests))
        assert folded == [(2, SkipKey("tests/test_a.py", None, "r"))]
        assert skip_lines(folded) == ["SKIPPED [2] tests/test_a.py: r"]

    def test_decorated_skips_keep_lineno(self, tmp_path: Path) -> None:
        """Decorated @pytest.mark.skip tests carry skip and pytestmark."""
        path = tmp_path / "tests" / "test_a.py"
        keywords = ["skip", "pytestmark", "test_a.py"]
        tests = [
            _skipped_test("tests/test_a.py::test_x", _skip_repr(path, 4), keywords),
            _skipped_test("tests/test_a.py::test_y", _skip_repr(path, 8), keywords),
        ]
        folded = folded_skips(_report(tmp_path, tests))
        assert folded == [
            (1, SkipKey("tests/test_a.py", 4, "r")),
            (1, SkipKey("tests/test_a.py", 8, "r")),
        ]

    def test_same_location_and_reason_folds(self, tmp_path: Path) -> None:
        """Call-stage skips at one location with one reason fold, with lineno."""
        path = tmp_path / "tests" / "test_b.py"
        tests = [
            _skipped_test(
                f"tests/test_b.py::test_p[{i}]", _skip_repr(path, 12), [], "call"
            )
            for i in range(3)
        ]
        folded = folded_skips(_report(tmp_path, tests))
        assert skip_lines(folded) == ["SKIPPED [3] tests/test_b.py:12: r"]

    def test_xdist_header_stripped(self, tmp_path: Path) -> None:
        """A [gwN] first line is dropped before the tuple is read."""
        path = tmp_path / "tests" / "test_a.py"
        longrepr = "[gw0] win32 -- Python 3.12 C:\\py.exe\n" + _skip_repr(path, 4)
        tests = [_skipped_test("tests/test_a.py::test_x", longrepr, [], "call")]
        assert folded_skips(_report(tmp_path, tests)) == [
            (1, SkipKey("tests/test_a.py", 4, "r"))
        ]

    def test_windows_shaped_longrepr(self, tmp_path: Path) -> None:
        """Doubled backslashes in the repr are read by ast.literal_eval."""
        longrepr = "('C:\\\\proj\\\\tests\\\\test_a.py', 4, 'Skipped: r')"
        tests = [_skipped_test("tests/test_a.py::test_x", longrepr, [], "call")]
        with patch(
            "mcp_tools_py.code_checker_pytest.report_data.relative_path",
            side_effect=lambda path, root: path,
        ) as rel:
            folded = folded_skips(_report(tmp_path, tests))
        rel.assert_called_once_with("C:\\proj\\tests\\test_a.py", str(tmp_path))
        assert folded == [(1, SkipKey("C:\\proj\\tests\\test_a.py", 4, "r"))]

    def test_collectors_first_then_tests(self, tmp_path: Path) -> None:
        """Collector skips come first and keep their line number."""
        test_path = tmp_path / "tests" / "test_a.py"
        mod_path = tmp_path / "tests" / "test_mod.py"
        tests = [
            _skipped_test(
                "tests/test_a.py::test_x", _skip_repr(test_path, 4), [], "call"
            )
        ]
        collectors = [
            _skipped_collector("tests/test_mod.py", _skip_repr(mod_path, 2, "no db"))
        ]
        folded = folded_skips(_report(tmp_path, tests, collectors))
        assert skip_lines(folded) == [
            "SKIPPED [1] tests/test_mod.py:2: no db",
            "SKIPPED [1] tests/test_a.py:4: r",
        ]

    def test_xfailed_not_listed(self, tmp_path: Path) -> None:
        """An xfailed test's skipped call stage is not a skip entry."""
        tests = [
            _skipped_test(
                "tests/test_a.py::test_x",
                "def test_x():\n>   assert False\nE   assert False",
                [],
                "call",
                outcome="xfailed",
            )
        ]
        assert not folded_skips(_report(tmp_path, tests))

    @pytest.mark.parametrize(
        "longrepr",
        [None, "not a tuple", "('a', 1)", "(1, 2, 3)", "('a', 'x', 'Skipped: r')"],
    )
    def test_unparseable_longrepr_ignored(
        self, tmp_path: Path, longrepr: str | None
    ) -> None:
        """Longreprs that are not a (path, lineno, reason) tuple are skipped over."""
        tests = [_skipped_test("tests/test_a.py::test_x", longrepr, [], "call")]
        collectors = [_skipped_collector("tests/test_mod.py", longrepr)]
        assert not folded_skips(_report(tmp_path, tests, collectors))

    def test_non_skipped_collector_ignored(self, tmp_path: Path) -> None:
        """Only collectors with outcome skipped are read."""
        path = tmp_path / "tests" / "test_mod.py"
        collector = Collector(
            nodeid="tests/test_mod.py",
            outcome="passed",
            result=[],
            longrepr=_skip_repr(path, 2),
        )
        assert not folded_skips(_report(tmp_path, collectors=[collector]))

    def test_reason_without_prefix_kept(self, tmp_path: Path) -> None:
        """A reason without the "Skipped: " prefix is kept as given."""
        longrepr = str((str(tmp_path / "t.py"), 1, "plain reason"))
        tests = [_skipped_test("t.py::test_x", longrepr, [], "call")]
        assert skip_lines(folded_skips(_report(tmp_path, tests))) == [
            "SKIPPED [1] t.py:1: plain reason"
        ]

    def test_no_tests_no_collectors(self, tmp_path: Path) -> None:
        """A report without tests or collectors gives no entries."""
        assert not folded_skips(_report(tmp_path))


class TestSkipCounts:
    """module_skip_count and skipped_count."""

    def test_module_skip_count_distinct_nodeids(self, tmp_path: Path) -> None:
        """Each skipped collector node ID counts once."""
        longrepr = _skip_repr(tmp_path / "tests" / "test_mod.py", 2)
        collectors = [
            _skipped_collector("tests/test_mod.py", longrepr),
            _skipped_collector("tests/test_mod.py", longrepr),
            _skipped_collector("tests/test_other.py", longrepr),
            Collector(nodeid="tests/test_ok.py", outcome="passed", result=[]),
        ]
        assert module_skip_count(_report(tmp_path, collectors=collectors)) == 2

    def test_module_skip_count_without_collectors(self, tmp_path: Path) -> None:
        """No collectors gives zero."""
        assert module_skip_count(_report(tmp_path)) == 0

    def test_skipped_count_adds_module_skips(self, tmp_path: Path) -> None:
        """Summary skips plus skipped collectors."""
        collectors = [_skipped_collector("tests/test_mod.py", None)]
        assert skipped_count(_report(tmp_path, collectors=collectors, skipped=2)) == 3

    def test_skipped_count_summary_none(self, tmp_path: Path) -> None:
        """A missing summary skip count reads as zero."""
        assert skipped_count(_report(tmp_path)) == 0


def test_get_test_summary_counts_module_skips(tmp_path: Path) -> None:
    """⏭️ Skipped includes skipped collectors; Summary.skipped is unchanged."""
    path = tmp_path / "tests" / "test_a.py"
    tests = [
        _skipped_test(f"tests/test_a.py::test_{i}", _skip_repr(path, 3), [], "call")
        for i in range(2)
    ]
    collectors = [
        _skipped_collector(
            "tests/test_mod.py", _skip_repr(tmp_path / "tests" / "test_mod.py", 2)
        )
    ]
    report = _report(tmp_path, tests, collectors, skipped=2)
    assert "⏭️ Skipped: 3" in get_test_summary(report)
    assert report.summary.skipped == 2


def test_get_test_summary_module_skips_only(tmp_path: Path) -> None:
    """Skipped collectors alone produce the skipped part."""
    collectors = [_skipped_collector("tests/test_mod.py", None)]
    assert "⏭️ Skipped: 1" in get_test_summary(_report(tmp_path, collectors=collectors))
