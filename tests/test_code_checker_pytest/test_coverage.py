"""Tests for the coverage run plumbing: flags, env, JSON load, fail_under read."""

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

from mcp_tools_py.code_checker_pytest.coverage import (
    _ranges,
    coverage_args,
    format_coverage_digest,
    read_coverage_report,
    read_fail_under,
    selection_line,
)
from tests.conftest import make_command_result

_EXECUTE = "mcp_tools_py.code_checker_pytest.coverage.execute_command"


class TestCoverageArgs:
    """Test the pytest flags and env vars of one coverage run."""

    def test_one_cov_flag_per_source(self, tmp_path: Path) -> None:
        """Each source directory gets its own --cov flag."""
        args, _ = coverage_args(["src", "lib"], str(tmp_path))

        assert [a for a in args if a.startswith("--cov=")] == [
            "--cov=src",
            "--cov=lib",
        ]

    def test_fail_under_zero_is_last(self, tmp_path: Path) -> None:
        """--cov-fail-under=0 comes last so it overrides earlier thresholds."""
        args, _ = coverage_args(["src"], str(tmp_path))

        assert args[-1] == "--cov-fail-under=0"

    def test_artifacts_lie_inside_temp_dir(self, tmp_path: Path) -> None:
        """The JSON report and the data file are files inside temp_dir."""
        temp_dir = str(tmp_path)
        args, env = coverage_args(["src"], temp_dir)

        report = [a for a in args if a.startswith("--cov-report=json:")]
        assert len(report) == 1
        json_path = report[0].removeprefix("--cov-report=json:")
        data_path = env["COVERAGE_FILE"]
        for path in (json_path, data_path):
            assert os.path.dirname(path) == temp_dir
            assert path != temp_dir


class TestReadCoverageReport:
    """Test loading the coverage JSON."""

    def test_valid_file(self, tmp_path: Path) -> None:
        """A valid coverage.json is returned as a dict."""
        data = {"totals": {"percent_covered": 50.0}, "files": {}}
        (tmp_path / "coverage.json").write_text(json.dumps(data), encoding="utf-8")

        assert read_coverage_report(str(tmp_path)) == data

    def test_missing_file(self, tmp_path: Path) -> None:
        """No report file yields None."""
        assert read_coverage_report(str(tmp_path)) is None

    def test_invalid_json(self, tmp_path: Path) -> None:
        """An unparsable report yields None."""
        (tmp_path / "coverage.json").write_text("{not json", encoding="utf-8")

        assert read_coverage_report(str(tmp_path)) is None

    def test_non_object_json(self, tmp_path: Path) -> None:
        """A JSON value that is not an object yields None."""
        (tmp_path / "coverage.json").write_text("[1, 2]", encoding="utf-8")

        assert read_coverage_report(str(tmp_path)) is None


class TestReadFailUnder:
    """Test reading the project's effective fail_under."""

    def test_runs_in_project_dir(self) -> None:
        """The probe runs with cwd=project_dir in the target interpreter."""
        with patch(_EXECUTE) as mock_exec:
            mock_exec.return_value = make_command_result(stdout="80.0\n")

            assert read_fail_under("/some/python", "/proj") == 80.0

            command = mock_exec.call_args.args[0]
            assert command[0] == "/some/python"
            assert mock_exec.call_args.kwargs["cwd"] == "/proj"

    def test_none_configured(self) -> None:
        """coverage reports 0.0 when no threshold is configured."""
        with patch(_EXECUTE) as mock_exec:
            mock_exec.return_value = make_command_result(stdout="0.0\n")

            assert read_fail_under("/some/python", "/proj") == 0.0

    def test_non_zero_exit(self) -> None:
        """A failing probe yields None."""
        with patch(_EXECUTE) as mock_exec:
            mock_exec.return_value = make_command_result(
                return_code=1, stderr="No module named coverage"
            )

            assert read_fail_under("/some/python", "/proj") is None

    def test_timeout(self) -> None:
        """A timed-out probe yields None."""
        with patch(_EXECUTE) as mock_exec:
            mock_exec.return_value = make_command_result(
                return_code=-1,
                timed_out=True,
                execution_error="Process timed out after 30 seconds",
            )

            assert read_fail_under("/some/python", "/proj") is None

    def test_garbage_stdout(self) -> None:
        """Output that is not a number yields None."""
        with patch(_EXECUTE) as mock_exec:
            mock_exec.return_value = make_command_result(stdout="garbage")

            assert read_fail_under("/some/python", "/proj") is None


class TestSelectionLine:
    """Test the one-line echo of what narrowed the run."""

    def test_full_suite(self) -> None:
        """Nothing narrowing yields the full-suite line."""
        assert selection_line(None, [], [], None) == (
            "selection: full suite (no markers, -k or path arguments)"
        )

    def test_markers_parameter(self) -> None:
        """The markers parameter is joined with 'and'."""
        assert selection_line(["a", "b"], [], [], None) == (
            "selection: markers 'a and b'"
        )

    def test_m_in_cleaned_args(self) -> None:
        """-m in the args is reported when markers is not given."""
        assert selection_line(None, ["-m", "slow"], [], None) == (
            "selection: markers 'slow'"
        )

    def test_m_in_addopts(self) -> None:
        """-m in addopts is reported with its source."""
        line = selection_line(None, [], [], "-n auto -m 'not integration'")

        assert line == "selection: addopts -m 'not integration'"

    def test_command_line_m_wins_over_addopts(self) -> None:
        """A command-line marker expression overrides the addopts one."""
        line = selection_line(["slow"], [], [], "-m 'not integration'")

        assert line == "selection: markers 'slow'"

    def test_extra_args_m_wins_over_markers(self) -> None:
        """extra_args follow the markers -m on the command line, so they win."""
        line = selection_line(["slow"], ["-m", "fast"], [], None)

        assert line == "selection: markers 'fast'"

    def test_k_in_args(self) -> None:
        """-k in the args is reported."""
        assert selection_line(None, ["-k", "install"], [], None) == (
            "selection: -k 'install'"
        )

    def test_k_joined_form(self) -> None:
        """The joined -kfoo form is recognised."""
        assert selection_line(None, ["-kfoo"], [], None) == "selection: -k 'foo'"

    def test_k_in_addopts(self) -> None:
        """-k in addopts is reported with its source."""
        assert selection_line(None, [], [], "-k install") == (
            "selection: addopts -k 'install'"
        )

    def test_last_value_wins(self) -> None:
        """pytest keeps the last value of a repeated option."""
        assert selection_line(None, ["-k", "a", "-k", "b"], [], None) == (
            "selection: -k 'b'"
        )

    def test_combined(self) -> None:
        """Several mechanisms are joined with '; '."""
        line = selection_line(None, ["-k", "install"], [], "-m 'not integration'")

        assert line == "selection: addopts -m 'not integration'; -k 'install'"

    def test_path_args(self) -> None:
        """Path arguments are listed."""
        line = selection_line(None, [], ["tests/a.py", "tests/b.py::test_x"], None)

        assert line == "selection: paths tests/a.py, tests/b.py::test_x"

    def test_unbalanced_quotes_in_addopts(self) -> None:
        """Unparsable addopts is treated as empty rather than raising."""
        assert selection_line(None, [], [], "-m 'not integration") == (
            "selection: full suite (no markers, -k or path arguments)"
        )


_SELECTION = "selection: full suite (no markers, -k or path arguments)"


def _file(
    stmts: int,
    missing: list[int],
    functions: dict[str, list[int]] | None = None,
) -> dict[str, Any]:
    """One file entry of the coverage JSON."""
    covered = stmts - len(missing)
    entry: dict[str, Any] = {
        "summary": {
            "num_statements": stmts,
            "covered_lines": covered,
            "missing_lines": len(missing),
            "percent_covered": 100.0 * covered / stmts if stmts else 100.0,
        },
        "missing_lines": missing,
    }
    if functions is not None:
        entry["functions"] = {
            name: {"missing_lines": lines} for name, lines in functions.items()
        }
    return entry


def _report(files: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """A coverage JSON with totals summed from files."""
    stmts = sum(f["summary"]["num_statements"] for f in files.values())
    missed = sum(f["summary"]["missing_lines"] for f in files.values())
    return {
        "totals": {
            "num_statements": stmts,
            "missing_lines": missed,
            "covered_lines": stmts - missed,
            "percent_covered": 100.0 * (stmts - missed) / stmts if stmts else 100.0,
        },
        "files": files,
    }


class TestRanges:
    """Test collapsing line numbers into ranges."""

    def test_collapse(self) -> None:
        """Consecutive runs become a-b, singletons stay single."""
        assert _ranges([1, 2, 3, 5, 7, 8]) == ["1-3", "5", "7-8"]

    def test_empty(self) -> None:
        """No lines yield no ranges."""
        assert not _ranges([])


class TestFormatCoverageDigest:
    """Test the coverage digest appended to the pytest reply."""

    def test_header_and_selection(self) -> None:
        """The header and the selection line are always the first two lines."""
        data = _report({"a.py": _file(10, [3], {"f": [3]})})

        lines = format_coverage_digest(data, _SELECTION).splitlines()

        assert lines[0] == "90.0%  10 stmts  1 missed  |  1 modules measured"
        assert lines[1] == _SELECTION

    def test_ranked_by_absolute_missing(self) -> None:
        """A big module at 90% ranks above a small one at 50%."""
        big = list(range(1, 201))
        small = list(range(1, 16))
        data = _report(
            {
                "small.py": _file(30, small, {"f": small}),
                "big.py": _file(2000, big, {"g": big}),
            }
        )

        digest = format_coverage_digest(data, _SELECTION)

        assert "big.py  200 missing  (90%)" in digest
        assert "small.py  15 missing  (50%)" in digest
        assert digest.index("big.py") < digest.index("small.py")

    def test_module_level_region(self) -> None:
        """The empty-string region is rendered as <module level>."""
        data = _report({"a.py": _file(10, [1, 2], {"": [1, 2]})})

        digest = format_coverage_digest(data, _SELECTION)

        assert "<module level>  1-2" in digest

    def test_function_cap(self) -> None:
        """Only the three functions with most missing lines are shown."""
        functions = {
            "f1": [1, 3, 5, 7],
            "f2": [11, 13, 15],
            "f3": [21, 23],
            "f4": [31],
        }
        missing = sorted(line for lines in functions.values() for line in lines)
        data = _report({"a.py": _file(50, missing, functions)})

        digest = format_coverage_digest(data, _SELECTION)

        assert "f1" in digest and "f2" in digest and "f3" in digest
        assert "f4" not in digest
        assert "    … 1 more functions" in digest

    def test_no_function_marker_under_cap(self) -> None:
        """No truncation marker when every function is shown."""
        data = _report({"a.py": _file(10, [1], {"f": [1]})})

        assert "more functions" not in format_coverage_digest(data, _SELECTION)

    def test_range_cap(self) -> None:
        """The sixth range is replaced by an ellipsis."""
        lines = [1, 3, 5, 7, 9, 11]
        data = _report({"a.py": _file(20, lines, {"f": lines})})

        digest = format_coverage_digest(data, _SELECTION)

        assert "f  1, 3, 5, 7, 9, …" in digest
        assert "11" not in digest.split("f  ", 1)[1].splitlines()[0]

    def test_zero_coverage_listed_separately(self) -> None:
        """Modules with nothing covered are not ranked but listed with counts."""
        data = _report(
            {
                "a.py": _file(10, [1], {"f": [1]}),
                "probe.py": _file(150, list(range(1, 151)), {"": [1]}),
            }
        )

        digest = format_coverage_digest(data, _SELECTION)

        assert "probe.py  150 missing" not in digest
        assert "1 modules have no covered statements in this selection:" in digest
        assert "    probe.py (150 missing statements)" in digest
        for cause in ("untested", "not selected", "never traced"):
            assert cause not in digest

    def test_max_modules_cut(self) -> None:
        """Modules beyond max_modules are summarised in a tail line."""
        files = {
            f"m{i}.py": _file(10, list(range(1, i + 2)), {"f": list(range(1, i + 2))})
            for i in range(4)
        }
        digest = format_coverage_digest(_report(files), _SELECTION, max_modules=2)

        assert "m3.py" in digest and "m2.py" in digest
        assert "m1.py" not in digest and "m0.py" not in digest
        assert "2 further modules have gaps (use max_modules to see more)." in digest

    def test_max_modules_zero(self) -> None:
        """max_modules=0 leaves only the header and the counts."""
        data = _report(
            {
                "a.py": _file(10, [1], {"f": [1]}),
                "z.py": _file(5, [1, 2, 3, 4, 5], {"": [1]}),
            }
        )

        digest = format_coverage_digest(data, _SELECTION, max_modules=0)

        assert "a.py" not in digest and "z.py" not in digest
        assert "1 modules have no covered statements in this selection:" in digest
        assert "… and 1 more" in digest
        assert "1 further modules have gaps" in digest

    def test_negative_max_modules_clamped(self) -> None:
        """A negative max_modules behaves like 0."""
        data = _report({"a.py": _file(10, [1], {"f": [1]})})

        assert format_coverage_digest(
            data, _SELECTION, max_modules=-3
        ) == format_coverage_digest(data, _SELECTION, max_modules=0)

    def test_file_level_fallback(self) -> None:
        """Without functions data, file-level ranges and one note are shown."""
        data = _report(
            {
                "a.py": _file(20, [1, 2, 4]),
                "b.py": _file(20, [5, 6]),
            }
        )

        digest = format_coverage_digest(data, _SELECTION)

        assert "    1-2, 4" in digest
        assert "    5-6" in digest
        assert digest.count("coverage >= 7.6.0") == 1

    def test_fail_under_zero(self) -> None:
        """No threshold configured yields no fail_under line."""
        data = _report({"a.py": _file(10, [1], {"f": [1]})})

        assert "fail_under" not in format_coverage_digest(data, _SELECTION)

    def test_fail_under_configured(self) -> None:
        """A configured threshold is named and said not to be applied."""
        data = _report({"a.py": _file(10, [1], {"f": [1]})})

        digest = format_coverage_digest(data, _SELECTION, fail_under=80.0)

        assert "fail_under=80 is configured; not applied to this run" in digest

    def test_fail_under_unreadable(self) -> None:
        """An unreadable threshold is reported as such."""
        data = _report({"a.py": _file(10, [1], {"f": [1]})})

        digest = format_coverage_digest(data, _SELECTION, fail_under=None)

        assert "fail_under: could not be read from the coverage config" in digest

    def test_tests_failed_warning(self) -> None:
        """A failed run carries a warning line."""
        data = _report({"a.py": _file(10, [1], {"f": [1]})})

        assert "Warning: tests failed" not in format_coverage_digest(data, _SELECTION)
        assert "Warning: tests failed" in format_coverage_digest(
            data, _SELECTION, tests_failed=True
        )

    def test_fully_covered(self) -> None:
        """No gaps at all is said explicitly."""
        data = _report({"a.py": _file(10, [], {"f": []})})

        digest = format_coverage_digest(data, _SELECTION)

        assert "No uncovered statements in the measured modules." in digest
