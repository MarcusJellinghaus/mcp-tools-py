"""Tests for report_extras: report flags, report-level sections, empty-result lines."""

from dataclasses import replace
from pathlib import Path

import pytest

from mcp_tools_py.code_checker_pytest.models import (
    Collector,
    PytestReport,
    StageInfo,
    Summary,
    Test,
)
from mcp_tools_py.code_checker_pytest.models import Warning as ReportWarning
from mcp_tools_py.code_checker_pytest.pytest_config import (
    EffectiveConfig,
    OptionValue,
)
from mcp_tools_py.code_checker_pytest.report_extras import (
    DEFAULT_DURATIONS_MIN,
    DURATIONS_MIN_NOTE,
    SNAPSHOT_NOTE,
    ReportFlags,
    flag_notes,
    hint_line,
    report_flags,
    report_sections,
    resolve_report_chars,
    skipped_block,
)
from mcp_tools_py.code_checker_pytest.reporting import DROPPED_NOTICE

BIG_LINES = 500
BIG_CHARS = 50_000


def _effective(options: dict[str, OptionValue]) -> EffectiveConfig:
    """An EffectiveConfig holding only the given options."""
    return EffectiveConfig(
        config=None,
        not_read=None,
        ini_source="pyproject.toml",
        ini_tokens=[],
        env_tokens=[],
        m=None,
        k=None,
        numprocesses=False,
        n=None,
        strict_markers=False,
        project_strict_markers=False,
        options=options,
    )


def _flags(**changes: object) -> ReportFlags:
    """ReportFlags with nothing in effect, then the given fields."""
    flags = ReportFlags(
        letters=frozenset(),
        r_label=None,
        no_effect="",
        durations=None,
        durations_min=DEFAULT_DURATIONS_MIN,
        durations_min_in_call=False,
        show_capture=None,
        snapshot_update=False,
        disable_warnings=False,
    )
    return replace(flags, **changes)  # type: ignore[arg-type]


def _test(
    nodeid: str,
    setup: float = 0.0,
    call: float = 0.0,
    teardown: float = 0.0,
    outcome: str = "passed",
) -> Test:
    """A test with the given stage durations."""
    return Test(
        nodeid=nodeid,
        lineno=1,
        keywords=[],
        outcome=outcome,
        setup=StageInfo(duration=setup, outcome="passed"),
        call=StageInfo(duration=call, outcome="passed"),
        teardown=StageInfo(duration=teardown, outcome="passed"),
    )


def _skipped(root: Path, nodeid: str, lineno: int, reason: str = "r") -> Test:
    """A test skipped in its call stage at tests/test_a.py:lineno."""
    longrepr = str((str(root / "tests" / "test_a.py"), lineno, f"Skipped: {reason}"))
    return Test(
        nodeid=nodeid,
        lineno=1,
        keywords=[],
        outcome="skipped",
        setup=StageInfo(duration=0.0, outcome="passed"),
        call=StageInfo(duration=0.0, outcome="skipped", longrepr=longrepr),
    )


def _warning(root: Path, message: str, lineno: int = 3) -> ReportWarning:
    """A DeprecationWarning at tests/test_a.py:lineno."""
    return ReportWarning(
        message=message,
        category="DeprecationWarning",
        when="runtest",
        filename=str(root / "tests" / "test_a.py"),
        lineno=lineno,
    )


def _report(
    root: Path,
    tests: list[Test] | None = None,
    warnings: list[ReportWarning] | None = None,
) -> PytestReport:
    """A report rooted at `root`."""
    tests = tests if tests is not None else [_test("tests/test_a.py::test_ok")]
    return PytestReport(
        created=0.0,
        duration=0.5,
        exitcode=0,
        root=str(root),
        environment={},
        summary=Summary(collected=len(tests), total=len(tests)),
        tests=tests,
        warnings=warnings,
    )


class TestResolveReportChars:
    """resolve_report_chars follows pytest's getreportopt with this tool's deviations."""

    @pytest.mark.parametrize(
        ("value", "letters", "no_effect"),
        [
            ("a", {"s", "w"}, ""),
            ("A", {"s", "w"}, ""),
            ("ax", {"s", "w"}, "x"),
            ("xa", {"s", "w"}, ""),
            ("xN", set(), ""),
            ("z", set(), "z"),
            ("S", {"s"}, ""),
            ("s", {"s"}, ""),
            ("w", {"w"}, ""),
            ("sw", {"s", "w"}, ""),
            ("N", set(), ""),
            ("fE", set(), ""),
            ("F", set(), ""),
            ("sxp", {"s"}, "xp"),
            ("sxX", {"s"}, "xX"),
            ("xpxP", set(), "xpP"),
            ("sNw", {"w"}, ""),
            ("s w", {"s", "w"}, ""),
        ],
    )
    def test_cases(self, value: str, letters: set[str], no_effect: str) -> None:
        """Section letters after resolution and the letters without effect."""
        assert resolve_report_chars(value) == (frozenset(letters), no_effect)


class TestReportFlags:
    """report_flags reads the effective options."""

    def test_nothing_in_effect(self) -> None:
        """No tracked options → nothing in effect."""
        assert report_flags(_effective({})) == _flags()

    def test_call_r(self) -> None:
        """A call -r keeps its label and the no-effect letters."""
        flags = report_flags(
            _effective({"-r": OptionValue("sx", "extra_args", "-r sx")})
        )
        assert flags.letters == {"s"}
        assert flags.r_label == "-r sx"
        assert flags.no_effect == "x"

    @pytest.mark.parametrize("source", ["pyproject.toml", "PYTEST_ADDOPTS", "-o"])
    def test_config_r(self, source: str) -> None:
        """A config -r turns on letters, but has no label and no note."""
        flags = report_flags(_effective({"-r": OptionValue("ax", source, "-rax")}))
        assert flags.letters == {"s", "w"}
        assert flags.r_label is None
        assert flags.no_effect == ""

    def test_durations(self) -> None:
        """--durations and --durations-min are read; in_call from the source."""
        flags = report_flags(
            _effective(
                {
                    "--durations": OptionValue("3", "pyproject.toml", "--durations=3"),
                    "--durations-min": OptionValue(
                        "0.5", "extra_args", "--durations-min=0.5"
                    ),
                }
            )
        )
        assert flags.durations == 3
        assert flags.durations_min == 0.5
        assert flags.durations_min_in_call

    def test_durations_min_from_config_not_in_call(self) -> None:
        """A config --durations-min is honoured but not in the call."""
        flags = report_flags(
            _effective({"--durations-min": OptionValue("0", "PYTEST_ADDOPTS")})
        )
        assert flags.durations_min == 0.0
        assert not flags.durations_min_in_call

    @pytest.mark.parametrize("value", ["abc", "", "-1"])
    def test_durations_not_an_int(self, value: str) -> None:
        """A --durations value that is not a count is not in effect."""
        flags = report_flags(
            _effective({"--durations": OptionValue(value, "extra_args")})
        )
        assert flags.durations is None

    def test_durations_min_not_a_number(self) -> None:
        """An unreadable --durations-min falls back to the default."""
        flags = report_flags(
            _effective({"--durations-min": OptionValue("x", "extra_args")})
        )
        assert flags.durations_min == DEFAULT_DURATIONS_MIN

    def test_other_flags(self) -> None:
        """--show-capture, --snapshot-update, --disable-warnings."""
        flags = report_flags(
            _effective(
                {
                    "--show-capture": OptionValue("log", "extra_args"),
                    "--snapshot-update": OptionValue("", "pyproject.toml"),
                    "--disable-warnings": OptionValue("", "extra_args"),
                }
            )
        )
        assert flags.show_capture == "log"
        assert flags.snapshot_update
        assert flags.disable_warnings


class TestSkipSection:
    """-rs lists folded skip reasons."""

    def test_skip_reasons(self, tmp_path: Path) -> None:
        """Folded entries under a header."""
        tests = [
            _skipped(tmp_path, f"tests/test_a.py::test_{i}", 12, "slow")
            for i in range(3)
        ]
        text = report_sections(
            _report(tmp_path, tests),
            _flags(letters=frozenset({"s"}), r_label="-rs"),
            BIG_LINES,
            BIG_CHARS,
        )
        assert text == "Skip reasons:\nSKIPPED [3] tests/test_a.py:12: slow"

    def test_config_s_with_skips(self, tmp_path: Path) -> None:
        """A config -rs shows its section when there is something to show."""
        tests = [_skipped(tmp_path, "tests/test_a.py::test_x", 4)]
        text = report_sections(
            _report(tmp_path, tests),
            _flags(letters=frozenset({"s"})),
            BIG_LINES,
            BIG_CHARS,
        )
        assert text == "Skip reasons:\nSKIPPED [1] tests/test_a.py:4: r"


class TestWarningSection:
    """-rw lists warning groups."""

    def test_warnings(self, tmp_path: Path) -> None:
        """Groups by category and message, most frequent first."""
        warnings = [_warning(tmp_path, "old api")] + [
            _warning(tmp_path, "older api", lineno=i) for i in range(5, 7)
        ]
        text = report_sections(
            _report(tmp_path, warnings=warnings),
            _flags(letters=frozenset({"w"}), r_label="-rw"),
            BIG_LINES,
            BIG_CHARS,
        )
        assert text == (
            "Warnings:\n"
            "DeprecationWarning: older api — 2× (first: tests/test_a.py:5)\n"
            "DeprecationWarning: old api — 1× (first: tests/test_a.py:3)"
        )

    def test_disable_warnings_suppresses(self, tmp_path: Path) -> None:
        """--disable-warnings: no section and no empty line for w."""
        text = report_sections(
            _report(tmp_path, warnings=[_warning(tmp_path, "old api")]),
            _flags(letters=frozenset({"w"}), r_label="-rw", disable_warnings=True),
            BIG_LINES,
            BIG_CHARS,
        )
        assert text == ""


class TestDurationsSection:
    """--durations lists the slowest stages."""

    def _tests(self) -> list[Test]:
        return [
            _test("t.py::a", setup=0.30, call=0.10, teardown=0.0),
            _test("t.py::b", setup=0.0, call=0.50, teardown=0.20),
            _test("t.py::c", setup=0.0, call=0.001, teardown=0.0),
        ]

    def test_three_slowest_across_stages(self, tmp_path: Path) -> None:
        """--durations=3 lists the 3 slowest entries, stages mixed."""
        text = report_sections(
            _report(tmp_path, self._tests()),
            _flags(durations=3),
            BIG_LINES,
            BIG_CHARS,
        )
        assert text == (
            "Slowest 3 durations:\n"
            "0.50s call t.py::b\n"
            "0.30s setup t.py::a\n"
            "0.20s teardown t.py::b"
        )

    def test_zero_lists_all_with_hidden_line(self, tmp_path: Path) -> None:
        """--durations=0 lists all; entries below the default minimum are counted."""
        text = report_sections(
            _report(tmp_path, self._tests()),
            _flags(durations=0),
            BIG_LINES,
            BIG_CHARS,
        )
        assert text == (
            "Slowest durations:\n"
            "0.50s call t.py::b\n"
            "0.30s setup t.py::a\n"
            "0.20s teardown t.py::b\n"
            "0.10s call t.py::a\n"
            "(5 durations < 0.005s hidden; pass --durations-min=0 to show them.)"
        )

    def test_user_minimum(self, tmp_path: Path) -> None:
        """A user --durations-min is the cut-off in rows and hidden line."""
        text = report_sections(
            _report(tmp_path, self._tests()),
            _flags(durations=0, durations_min=0.25),
            BIG_LINES,
            BIG_CHARS,
        )
        assert text == (
            "Slowest durations:\n"
            "0.50s call t.py::b\n"
            "0.30s setup t.py::a\n"
            "(7 durations < 0.25s hidden; pass --durations-min=0 to show them.)"
        )

    def test_hidden_count_only_within_cut(self, tmp_path: Path) -> None:
        """Entries below the minimum outside the first N are not counted."""
        text = report_sections(
            _report(tmp_path, self._tests()),
            _flags(durations=5),
            BIG_LINES,
            BIG_CHARS,
        )
        assert text.endswith(
            "(1 durations < 0.005s hidden; pass --durations-min=0 to show them.)"
        )

    def test_minimum_zero_shows_all(self, tmp_path: Path) -> None:
        """--durations-min=0 hides nothing."""
        text = report_sections(
            _report(tmp_path, self._tests()),
            _flags(durations=0, durations_min=0.0),
            BIG_LINES,
            BIG_CHARS,
        )
        assert "hidden" not in text
        assert len(text.splitlines()) == 10

    def test_config_durations_on_clean_run(self, tmp_path: Path) -> None:
        """A config --durations shows on a clean run too."""
        text = report_sections(
            _report(tmp_path, [_test("t.py::a", call=0.02)]),
            _flags(durations=10),
            BIG_LINES,
            BIG_CHARS,
        )
        assert text.startswith("Slowest 10 durations:\n0.02s call t.py::a")


class TestEmptyResults:
    """Call -r flags with nothing to show print one line; config ones nothing."""

    @pytest.mark.parametrize(
        ("label", "letters", "expected"),
        [
            ("-rs", {"s"}, "-rs: no skipped tests."),
            ("-r s", {"s"}, "-r s: no skipped tests."),
            ("--report-chars=s", {"s"}, "--report-chars=s: no skipped tests."),
            ("-rsw", {"s", "w"}, "-rsw: no skipped tests, no warnings."),
            ("-ra", {"s", "w"}, "-ra: no skipped tests, no warnings."),
            ("-rw", {"w"}, "-rw: no warnings."),
        ],
    )
    def test_call_empty_lines(
        self, tmp_path: Path, label: str, letters: set[str], expected: str
    ) -> None:
        """The line uses the label as passed and lists the empty parts."""
        text = report_sections(
            _report(tmp_path),
            _flags(letters=frozenset(letters), r_label=label),
            BIG_LINES,
            BIG_CHARS,
        )
        assert text == expected

    def test_ra_with_disable_warnings(self, tmp_path: Path) -> None:
        """--disable-warnings drops the warnings part."""
        text = report_sections(
            _report(tmp_path),
            _flags(letters=frozenset({"s", "w"}), r_label="-ra", disable_warnings=True),
            BIG_LINES,
            BIG_CHARS,
        )
        assert text == "-ra: no skipped tests."

    def test_ra_with_skips_no_warnings(self, tmp_path: Path) -> None:
        """Skip section, then the empty line for warnings."""
        tests = [_skipped(tmp_path, "tests/test_a.py::test_x", 4)]
        text = report_sections(
            _report(tmp_path, tests),
            _flags(letters=frozenset({"s", "w"}), r_label="-ra"),
            BIG_LINES,
            BIG_CHARS,
        )
        assert text == (
            "Skip reasons:\nSKIPPED [1] tests/test_a.py:4: r\n-ra: no warnings."
        )

    def test_config_ra_clean_prints_nothing(self, tmp_path: Path) -> None:
        """Config-sourced -ra on a clean report → nothing."""
        text = report_sections(
            _report(tmp_path),
            _flags(letters=frozenset({"s", "w"})),
            BIG_LINES,
            BIG_CHARS,
        )
        assert text == ""

    def test_no_supported_letters_prints_nothing(self, tmp_path: Path) -> None:
        """-rx in the call has no section letters → no empty line."""
        text = report_sections(
            _report(tmp_path),
            _flags(r_label="-rx", no_effect="x"),
            BIG_LINES,
            BIG_CHARS,
        )
        assert text == ""

    def test_svrw_label(self, tmp_path: Path) -> None:
        """-svrw is sanitized to -rw; its label is -rw."""
        flags = report_flags(_effective({"-r": OptionValue("w", "extra_args", "-rw")}))
        assert report_sections(_report(tmp_path), flags, BIG_LINES, BIG_CHARS) == (
            "-rw: no warnings."
        )


class TestBudget:
    """Sections are cut to the budget left, first rows kept."""

    def test_durations_cut_to_first_rows(self, tmp_path: Path) -> None:
        """--durations=0 with more rows than fit: the slowest rows, then the count."""
        tests = [_test(f"t.py::t{i:02}", call=1.0 + i / 100) for i in range(40)]
        text = report_sections(
            _report(tmp_path, tests), _flags(durations=0), 12, BIG_CHARS
        )
        lines = text.splitlines()
        assert lines[0] == "Slowest durations:"
        assert lines[1] == "1.39s call t.py::t39"
        assert lines[2] == "1.38s call t.py::t38"
        assert lines[-1].endswith("more rows not shown, budget used up.)")
        shown = len(lines) - 2
        assert lines[-1] == f"({41 - shown} more rows not shown, budget used up.)"
        assert len(lines) <= 11
        assert DROPPED_NOTICE not in text

    def test_long_skip_list_cut(self, tmp_path: Path) -> None:
        """A long -rs list shows its first rows, then the omitted count."""
        tests = [
            _skipped(tmp_path, f"tests/test_a.py::test_{i}", i + 1) for i in range(30)
        ]
        text = report_sections(
            _report(tmp_path, tests),
            _flags(letters=frozenset({"s"}), r_label="-rs"),
            8,
            BIG_CHARS,
        )
        lines = text.splitlines()
        assert lines[0] == "Skip reasons:"
        assert lines[1] == "SKIPPED [1] tests/test_a.py:1: r"
        shown = len(lines) - 2
        assert lines[-1] == f"({30 - shown} more rows not shown, budget used up.)"

    def test_chars_budget_cuts(self, tmp_path: Path) -> None:
        """The character budget cuts rows as well."""
        tests = [_test(f"t.py::t{i:02}", call=1.0 + i / 100) for i in range(40)]
        text = report_sections(_report(tmp_path, tests), _flags(durations=0), 500, 400)
        assert len(text) <= 400
        assert text.splitlines()[-1].endswith("more rows not shown, budget used up.)")

    def test_all_three_over_budget_share_evenly(self, tmp_path: Path) -> None:
        """-rs, -rw and --durations all over budget: each shows its first rows."""
        tests = [
            _skipped(tmp_path, f"tests/test_a.py::test_{i}", i + 1) for i in range(30)
        ] + [_test(f"t.py::t{i:02}", call=1.0 + i / 100) for i in range(30)]
        warnings = [_warning(tmp_path, f"msg {i}") for i in range(30)]
        text = report_sections(
            _report(tmp_path, tests, warnings),
            _flags(letters=frozenset({"s", "w"}), r_label="-rsw", durations=0),
            31,
            BIG_CHARS,
        )
        assert "Skip reasons:\nSKIPPED [1] tests/test_a.py:1: r" in text
        assert "Warnings:\nDeprecationWarning: msg 0" in text
        assert "Slowest durations:\n1.29s call t.py::t29" in text
        assert text.count("more rows not shown, budget used up.)") == 3
        assert DROPPED_NOTICE not in text
        assert len(text.splitlines()) <= 30

    def test_section_without_room_is_named(self, tmp_path: Path) -> None:
        """A section whose first row does not fit is named in the dropped notice."""
        tests = [_test(f"t.py::t{i:02}", call=1.0) for i in range(5)]
        text = report_sections(
            _report(tmp_path, tests), _flags(durations=0), 3, BIG_CHARS
        )
        assert text == f"{DROPPED_NOTICE} durations"


class TestHintLine:
    """hint_line offers one combined -r value and --durations=5 when they add something."""

    def _skips(self, root: Path) -> list[Test]:
        return [_skipped(root, "tests/test_a.py::test_x", 4)]

    def test_skips_and_warnings_no_flags(self, tmp_path: Path) -> None:
        """Skips + warnings, nothing in effect → -rsw and --durations=5."""
        report = _report(
            tmp_path, self._skips(tmp_path), [_warning(tmp_path, "old api")]
        )
        assert hint_line(report, _flags()) == (
            'For details: extra_args=["-rsw", "--durations=5"]'
            " (skip reasons, warnings — counted only by default, slowest tests)"
        )

    def test_only_skips(self, tmp_path: Path) -> None:
        """Skips only → -rs."""
        report = _report(tmp_path, self._skips(tmp_path))
        assert hint_line(report, _flags()) == (
            'For details: extra_args=["-rs", "--durations=5"]'
            " (skip reasons, slowest tests)"
        )

    def test_only_warnings(self, tmp_path: Path) -> None:
        """Warnings only → -rw with the counted-only part."""
        report = _report(tmp_path, warnings=[_warning(tmp_path, "old api")])
        assert hint_line(report, _flags()) == (
            'For details: extra_args=["-rw", "--durations=5"]'
            " (warnings — counted only by default, slowest tests)"
        )

    def test_config_rs_with_warnings_offers_rsw(self, tmp_path: Path) -> None:
        """addopts -rs + warnings → -rsw, so following the hint keeps skip reasons."""
        report = _report(tmp_path, warnings=[_warning(tmp_path, "old api")])
        hint = hint_line(report, _flags(letters=frozenset({"s"})))
        assert hint is not None
        assert hint.startswith('For details: extra_args=["-rsw", "--durations=5"]')
        assert "(skip reasons, warnings — counted only by default, slowest tests)" in (
            hint
        )

    def test_all_in_effect_fast_run(self, tmp_path: Path) -> None:
        """-rsw in effect + fast run → no hint."""
        report = _report(
            tmp_path, self._skips(tmp_path), [_warning(tmp_path, "old api")]
        )
        assert hint_line(report, _flags(letters=frozenset({"s", "w"}))) is None

    def test_ra_counts_as_s_and_w(self, tmp_path: Path) -> None:
        """-ra in addopts resolves to s+w → no -r part, no hint."""
        flags = report_flags(
            _effective({"-r": OptionValue("a", "pyproject.toml", "-ra")})
        )
        report = _report(
            tmp_path, self._skips(tmp_path), [_warning(tmp_path, "old api")]
        )
        assert hint_line(report, flags) is None

    def test_rx_never_carried(self, tmp_path: Path) -> None:
        """-rx in effect is not carried into the hint's -r value."""
        flags = report_flags(_effective({"-r": OptionValue("x", "extra_args", "-rx")}))
        report = _report(tmp_path, self._skips(tmp_path))
        assert hint_line(report, flags) == (
            'For details: extra_args=["-rs", "--durations=5"]'
            " (skip reasons, slowest tests)"
        )

    def test_clean_fast_run(self, tmp_path: Path) -> None:
        """Clean fast run → no hint."""
        assert hint_line(_report(tmp_path), _flags()) is None

    def test_clean_slow_run(self, tmp_path: Path) -> None:
        """Clean run whose stages sum to 11 s → --durations=5 only."""
        tests = [
            _test("t.py::a", setup=1.0, call=5.0, teardown=0.0),
            _test("t.py::b", setup=0.0, call=4.0, teardown=1.0),
        ]
        assert hint_line(_report(tmp_path, tests), _flags()) == (
            'For details: extra_args=["--durations=5"] (slowest tests)'
        )

    def test_slow_run_with_durations_in_effect(self, tmp_path: Path) -> None:
        """--durations already in effect → no durations part."""
        tests = [_test("t.py::a", call=11.0)]
        assert hint_line(_report(tmp_path, tests), _flags(durations=3)) is None

    def test_durations_in_effect_keeps_r_part(self, tmp_path: Path) -> None:
        """--durations in effect drops only its own part."""
        report = _report(tmp_path, self._skips(tmp_path))
        assert hint_line(report, _flags(durations=0)) == (
            'For details: extra_args=["-rs"] (skip reasons)'
        )

    def test_disable_warnings_only_warnings(self, tmp_path: Path) -> None:
        """--disable-warnings + only warnings → no -r part, no hint on a fast run."""
        report = _report(tmp_path, warnings=[_warning(tmp_path, "old api")])
        assert hint_line(report, _flags(disable_warnings=True)) is None

    def test_disable_warnings_with_skips(self, tmp_path: Path) -> None:
        """--disable-warnings + skips + warnings → -rs only."""
        report = _report(
            tmp_path, self._skips(tmp_path), [_warning(tmp_path, "old api")]
        )
        assert hint_line(report, _flags(disable_warnings=True)) == (
            'For details: extra_args=["-rs", "--durations=5"]'
            " (skip reasons, slowest tests)"
        )


class TestFlagNotes:
    """flag_notes: no-effect letters, --durations-min without --durations, snapshots."""

    def test_none(self) -> None:
        """Nothing in effect → no notes."""
        assert not flag_notes(_flags())

    @pytest.mark.parametrize("letters", ["xp", "z"])
    def test_no_effect(self, letters: str) -> None:
        """One note listing all no-effect letters."""
        assert flag_notes(_flags(no_effect=letters)) == [
            f"-r{letters} has no effect here; supported: -rs, -rw"
            " (failures are always shown; -s shows passing-test output)"
        ]

    def test_no_effect_from_report_flags(self) -> None:
        """-rxp in the call → note for xp."""
        flags = report_flags(
            _effective({"-r": OptionValue("xp", "extra_args", "-rxp")})
        )
        assert flag_notes(flags) == [
            "-rxp has no effect here; supported: -rs, -rw"
            " (failures are always shown; -s shows passing-test output)"
        ]

    def test_durations_min_without_durations(self) -> None:
        """--durations-min in the call without --durations → note."""
        assert flag_notes(_flags(durations_min_in_call=True)) == [DURATIONS_MIN_NOTE]

    def test_durations_min_with_durations(self) -> None:
        """--durations-min with --durations → no note."""
        assert not flag_notes(_flags(durations_min_in_call=True, durations=5))

    def test_durations_min_from_config(self) -> None:
        """A config --durations-min without --durations → no note."""
        flags = report_flags(
            _effective({"--durations-min": OptionValue("0", "pyproject.toml")})
        )
        assert not flag_notes(flags)

    @pytest.mark.parametrize(
        "source", ["extra_args", "PYTEST_ADDOPTS", "pyproject.toml"]
    )
    def test_snapshot_update_any_source(self, source: str) -> None:
        """--snapshot-update from any source → the snapshot note."""
        flags = report_flags(_effective({"--snapshot-update": OptionValue("", source)}))
        assert flag_notes(flags) == [SNAPSHOT_NOTE]

    def test_all_notes_in_order(self) -> None:
        """No-effect, then --durations-min, then snapshot."""
        notes = flag_notes(
            _flags(no_effect="x", durations_min_in_call=True, snapshot_update=True)
        )
        assert notes[1:] == [DURATIONS_MIN_NOTE, SNAPSHOT_NOTE]
        assert notes[0].startswith("-rx has no effect here")


def _module_skip(root: Path, name: str, reason: str = "no db") -> Collector:
    """A collector skipped at module level in tests/<name>:3."""
    longrepr = str((str(root / "tests" / name), 3, f"Skipped: {reason}"))
    return Collector(
        nodeid=f"tests/{name}", outcome="skipped", result=[], longrepr=longrepr
    )


def _exit5_report(root: Path, collectors: list[Collector]) -> PytestReport:
    """An exit-5 report: no tests, the given collectors."""
    return replace(
        _report(root, tests=[]), exitcode=5, collectors=collectors, tests=None
    )


class TestSkippedBlock:
    """skipped_block: the count and folded skip lines of an exit-5 run."""

    def test_two_module_skips(self, tmp_path: Path) -> None:
        """The count, then one skip line per collector."""
        report = _exit5_report(
            tmp_path,
            [_module_skip(tmp_path, "test_a.py"), _module_skip(tmp_path, "test_b.py")],
        )
        assert skipped_block(report, BIG_LINES, BIG_CHARS) == (
            "⏭️ Skipped: 2\n"
            "SKIPPED [1] tests/test_a.py:3: no db\n"
            "SKIPPED [1] tests/test_b.py:3: no db"
        )

    def test_nothing_skipped(self, tmp_path: Path) -> None:
        """No skipped collector or test gives an empty block."""
        collector = Collector(nodeid="tests/test_a.py", outcome="passed", result=[])
        report = _exit5_report(tmp_path, [collector])
        assert skipped_block(report, BIG_LINES, BIG_CHARS) == ""

    def test_reasons_over_budget(self, tmp_path: Path) -> None:
        """Reasons that do not fit are named in the dropped notice; the count stays."""
        collectors = [
            _module_skip(tmp_path, f"test_{i}.py", f"reason {i}") for i in range(50)
        ]
        block = skipped_block(_exit5_report(tmp_path, collectors), 10, 2000)
        lines = block.splitlines()
        assert lines[0] == "⏭️ Skipped: 50"
        assert lines[-1] == f"{DROPPED_NOTICE} skip reasons"
        assert len(lines) <= 10
        assert len(block) <= 2000

    def test_unparsable_reasons(self, tmp_path: Path) -> None:
        """A skip without a readable reason still gives the count, no notice."""
        collector = Collector(
            nodeid="tests/test_a.py", outcome="skipped", result=[], longrepr=None
        )
        report = _exit5_report(tmp_path, [collector])
        assert skipped_block(report, BIG_LINES, BIG_CHARS) == "⏭️ Skipped: 1"
