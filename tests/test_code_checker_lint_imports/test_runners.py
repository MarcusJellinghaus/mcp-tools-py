"""Tests for code_checker_lint_imports.runners module."""

from typing import Any
from unittest.mock import patch

from mcp_tools_py.code_checker_lint_imports.runners import (
    _classify_state,
    _format_report,
    _parse_broken_contracts,
    _parse_summary,
    _parse_warnings,
    _strip_verbose_flags,
    run_lint_imports_check_impl,
)
from tests.conftest import make_command_result

MODULE_PATH = "mcp_tools_py.code_checker_lint_imports.runners"


# Captured from import-linter 2.x on 2026-05-04 (clean run, this repo).
CLEAN_OUTPUT = """\
=================
import-linter 2.0
=================

---------
Contracts
---------

Analyzed 50 files, 100 dependencies.

Layered Architecture KEPT
Forbidden imports KEPT
Independence KEPT

---
Contracts: 3 kept, 0 broken.
"""


# Captured from import-linter 2.x on 2026-05-04 (synthetic broken run).
BROKEN_OUTPUT = """\
=================
import-linter 2.0
=================

---------
Contracts
---------

Analyzed 50 files, 100 dependencies.

Layered Architecture BROKEN [12 violations]
Forbidden imports KEPT

---
Contracts: 1 kept, 1 broken.
"""


# Captured from import-linter 2.x on 2026-05-04 (synthetic warnings run).
WARNINGS_OUTPUT = """\
=================
import-linter 2.0
=================

Analyzed 50 files, 100 dependencies.

No matches for ignored import mcp_coder.mcp_workspace_git -> mcp_workspace.git_operations.

Layered Architecture KEPT

Contracts: 1 kept, 0 broken.
"""


# Verbatim wrapped form from issue #171 reproduction.
WRAPPED_WARNING_OUTPUT = """\
Analyzed 50 files, 100 dependencies.

No matches for ignored import mcp_coder.mcp_workspace_git -> 
mcp_workspace.git_operations.

Layered Architecture KEPT

Contracts: 1 kept, 0 broken.
"""


# Captured from import-linter 2.x on 2026-05-04 (malformed/error run).
MALFORMED_OUTPUT = """\
Could not read any configuration. Please check that .importlinter exists.
"""


class TestStripVerboseFlags:
    """_strip_verbose_flags removes -v / --verbose, leaves others alone."""

    def test_none_returns_empty_no_strip(self) -> None:
        cleaned, stripped = _strip_verbose_flags(None)
        assert cleaned == []
        assert stripped is False

    def test_empty_returns_empty_no_strip(self) -> None:
        cleaned, stripped = _strip_verbose_flags([])
        assert cleaned == []
        assert stripped is False

    def test_strips_verbose_long(self) -> None:
        cleaned, stripped = _strip_verbose_flags(["--verbose"])
        assert cleaned == []
        assert stripped is True

    def test_strips_verbose_short(self) -> None:
        cleaned, stripped = _strip_verbose_flags(["-v"])
        assert cleaned == []
        assert stripped is True

    def test_keeps_other_flags(self) -> None:
        cleaned, stripped = _strip_verbose_flags(["--contract", "layers", "--verbose"])
        assert cleaned == ["--contract", "layers"]
        assert stripped is True

    def test_no_verbose_no_strip(self) -> None:
        cleaned, stripped = _strip_verbose_flags(["--contract", "layers"])
        assert cleaned == ["--contract", "layers"]
        assert stripped is False


class TestParseSummary:
    """_parse_summary returns (kept, broken) or None."""

    def test_clean_output(self) -> None:
        assert _parse_summary(CLEAN_OUTPUT) == (3, 0)

    def test_broken_output(self) -> None:
        assert _parse_summary(BROKEN_OUTPUT) == (1, 1)

    def test_missing_returns_none(self) -> None:
        assert _parse_summary(MALFORMED_OUTPUT) is None

    def test_two_digit_numbers(self) -> None:
        text = "Contracts: 12 kept, 34 broken."
        assert _parse_summary(text) == (12, 34)


class TestParseBrokenContracts:
    """_parse_broken_contracts extracts ordered, deduped names."""

    def test_extracts_one(self) -> None:
        assert _parse_broken_contracts(BROKEN_OUTPUT) == ["Layered Architecture"]

    def test_extracts_multiple_in_order(self) -> None:
        text = (
            "Foo BROKEN [1]\n"
            "Bar KEPT\n"
            "Baz BROKEN [2]\n"
            "Contracts: 1 kept, 2 broken."
        )
        assert _parse_broken_contracts(text) == ["Foo", "Baz"]

    def test_returns_empty_when_none(self) -> None:
        assert _parse_broken_contracts(CLEAN_OUTPUT) == []

    def test_ignores_kept_lines(self) -> None:
        text = "Foo KEPT\nBar KEPT\nContracts: 2 kept, 0 broken."
        assert _parse_broken_contracts(text) == []

    def test_dedupes_repeats(self) -> None:
        text = "Foo BROKEN [1]\nFoo BROKEN [2]\nFoo BROKEN [3]\n"
        assert _parse_broken_contracts(text) == ["Foo"]


class TestParseWarnings:
    """_parse_warnings handles single-line and wrapped forms."""

    EXPECTED = (
        "No matches for ignored import mcp_coder.mcp_workspace_git -> "
        "mcp_workspace.git_operations."
    )

    def test_single_line(self) -> None:
        text = (
            "No matches for ignored import mcp_coder.mcp_workspace_git -> "
            "mcp_workspace.git_operations.\n"
        )
        assert _parse_warnings(text) == [self.EXPECTED]

    def test_wrapped_line(self) -> None:
        # Verbatim from issue #171 reproduction (note trailing space line 1).
        text = (
            "No matches for ignored import mcp_coder.mcp_workspace_git -> \n"
            "mcp_workspace.git_operations.\n"
        )
        assert _parse_warnings(text) == [self.EXPECTED]

    def test_in_full_output(self) -> None:
        assert _parse_warnings(WARNINGS_OUTPUT) == [self.EXPECTED]

    def test_in_wrapped_full_output(self) -> None:
        assert _parse_warnings(WRAPPED_WARNING_OUTPUT) == [self.EXPECTED]

    def test_multiple_warnings(self) -> None:
        text = (
            "No matches for ignored import a.b -> c.d.\n"
            "Some progress chatter\n"
            "No matches for ignored import e.f -> g.h.i.\n"
        )
        result = _parse_warnings(text)
        assert result == [
            "No matches for ignored import a.b -> c.d.",
            "No matches for ignored import e.f -> g.h.i.",
        ]

    def test_no_warnings(self) -> None:
        assert _parse_warnings(CLEAN_OUTPUT) == []


class TestClassifyState:
    """_classify_state full 3x3 truth table."""

    def test_rc0_clean_summary_passed(self) -> None:
        assert _classify_state(0, (3, 0)) == "PASSED"

    def test_rc0_broken_summary_error(self) -> None:
        # rc=0 with broken>0 is contradictory -> ERROR
        assert _classify_state(0, (1, 1)) == "ERROR"

    def test_rc0_no_summary_error(self) -> None:
        assert _classify_state(0, None) == "ERROR"

    def test_rc1_clean_summary_error(self) -> None:
        # rc!=0 with broken=0 is contradictory -> ERROR
        assert _classify_state(1, (3, 0)) == "ERROR"

    def test_rc1_broken_summary_broken(self) -> None:
        assert _classify_state(1, (1, 1)) == "BROKEN"

    def test_rc1_no_summary_error(self) -> None:
        assert _classify_state(1, None) == "ERROR"


class TestFormatReport:
    """_format_report assembles the structured string with line cap."""

    def test_passed_header_first_line(self) -> None:
        result = _format_report(
            state="PASSED",
            summary=(3, 0),
            broken_contracts=[],
            warnings=[],
            raw_body="some body",
            info_line=None,
        )
        first_line = result.splitlines()[0]
        assert first_line == "=== PASSED ==="

    def test_info_line_appears_above_header(self) -> None:
        result = _format_report(
            state="PASSED",
            summary=(3, 0),
            broken_contracts=[],
            warnings=[],
            raw_body="body",
            info_line="[Info: stripped --verbose/-v from extra_args]",
        )
        lines = result.splitlines()
        assert lines[0] == "[Info: stripped --verbose/-v from extra_args]"
        assert lines[1] == "=== PASSED ==="

    def test_summary_line_when_present(self) -> None:
        result = _format_report(
            state="PASSED",
            summary=(3, 0),
            broken_contracts=[],
            warnings=[],
            raw_body="body",
            info_line=None,
        )
        assert "Contracts: 3 kept, 0 broken" in result

    def test_broken_state_lists_contracts(self) -> None:
        result = _format_report(
            state="BROKEN",
            summary=(1, 2),
            broken_contracts=["Foo", "Bar"],
            warnings=[],
            raw_body="body",
            info_line=None,
        )
        assert "=== BROKEN: 2 of 3 contracts failed ===" in result
        assert "Broken contracts:" in result
        assert "  - Foo" in result
        assert "  - Bar" in result

    def test_warnings_listed(self) -> None:
        result = _format_report(
            state="PASSED",
            summary=(1, 0),
            broken_contracts=[],
            warnings=["No matches for ignored import a -> b."],
            raw_body="body",
            info_line=None,
        )
        assert "Warnings:" in result
        assert "  - No matches for ignored import a -> b." in result

    def test_error_state_no_summary_no_broken_list(self) -> None:
        result = _format_report(
            state="ERROR",
            summary=None,
            broken_contracts=[],
            warnings=[],
            raw_body="raw error text",
            info_line=None,
        )
        assert result.splitlines()[0] == (
            "=== ERROR: lint-imports output could not be parsed ==="
        )
        assert "Contracts:" not in result
        assert "Broken contracts:" not in result
        assert "raw error text" in result

    def test_line_cap_appends_truncation_marker(self) -> None:
        large_body = "\n".join(f"line {i}" for i in range(1000))
        result = _format_report(
            state="PASSED",
            summary=(3, 0),
            broken_contracts=[],
            warnings=[],
            raw_body=large_body,
            info_line=None,
        )
        last_line = result.splitlines()[-1]
        assert "[output truncated" in last_line
        assert "--contract <name>" in last_line

    def test_empty_body_substituted(self) -> None:
        result = _format_report(
            state="PASSED",
            summary=(3, 0),
            broken_contracts=[],
            warnings=[],
            raw_body="   \n  \n",
            info_line=None,
        )
        assert "(no output)" in result
        # First non-empty line is still the header.
        non_empty = [l for l in result.splitlines() if l.strip()]
        assert non_empty[0] == "=== PASSED ==="


class TestRunLintImportsCheckImpl:
    """Orchestrator integration tests with mocked execute_command."""

    @patch(f"{MODULE_PATH}.execute_command")
    def test_clean_run_starts_with_passed_header(self, mock_exec: Any) -> None:
        mock_exec.return_value = make_command_result(return_code=0, stdout=CLEAN_OUTPUT)
        result = run_lint_imports_check_impl(
            lint_imports_binary="/usr/bin/lint-imports",
            project_dir="/project",
        )
        first = result.splitlines()[0]
        assert first == "=== PASSED ==="
        assert "Contracts: 3 kept, 0 broken" in result

    @patch(f"{MODULE_PATH}.execute_command")
    def test_broken_run_lists_contract(self, mock_exec: Any) -> None:
        mock_exec.return_value = make_command_result(
            return_code=1, stdout=BROKEN_OUTPUT
        )
        result = run_lint_imports_check_impl(
            lint_imports_binary="/usr/bin/lint-imports",
            project_dir="/project",
        )
        first = result.splitlines()[0]
        assert first == "=== BROKEN: 1 of 2 contracts failed ==="
        assert "Layered Architecture" in result

    @patch(f"{MODULE_PATH}.execute_command")
    def test_error_when_no_summary(self, mock_exec: Any) -> None:
        mock_exec.return_value = make_command_result(
            return_code=2, stdout="", stderr=MALFORMED_OUTPUT
        )
        result = run_lint_imports_check_impl(
            lint_imports_binary="/usr/bin/lint-imports",
            project_dir="/project",
        )
        first = result.splitlines()[0]
        assert first == ("=== ERROR: lint-imports output could not be parsed ===")
        assert "Could not read any configuration" in result

    @patch(f"{MODULE_PATH}.execute_command")
    def test_verbose_stripped_with_info_line(self, mock_exec: Any) -> None:
        mock_exec.return_value = make_command_result(return_code=0, stdout=CLEAN_OUTPUT)
        result = run_lint_imports_check_impl(
            lint_imports_binary="/usr/bin/lint-imports",
            project_dir="/project",
            extra_args=["--verbose"],
        )
        lines = result.splitlines()
        assert lines[0] == "[Info: stripped --verbose/-v from extra_args]"
        assert lines[1] == "=== PASSED ==="
        cmd = mock_exec.call_args[0][0]
        assert "--verbose" not in cmd
        assert "-v" not in cmd

    @patch(f"{MODULE_PATH}.execute_command")
    def test_short_verbose_stripped(self, mock_exec: Any) -> None:
        mock_exec.return_value = make_command_result(return_code=0, stdout=CLEAN_OUTPUT)
        result = run_lint_imports_check_impl(
            lint_imports_binary="/usr/bin/lint-imports",
            project_dir="/project",
            extra_args=["-v"],
        )
        lines = result.splitlines()
        assert lines[0] == "[Info: stripped --verbose/-v from extra_args]"
        cmd = mock_exec.call_args[0][0]
        assert "-v" not in cmd

    @patch(f"{MODULE_PATH}.execute_command")
    def test_long_output_truncates(self, mock_exec: Any) -> None:
        big_stdout = (
            CLEAN_OUTPUT + "\n" + "\n".join(f"detail line {i}" for i in range(1000))
        )
        mock_exec.return_value = make_command_result(return_code=0, stdout=big_stdout)
        result = run_lint_imports_check_impl(
            lint_imports_binary="/usr/bin/lint-imports",
            project_dir="/project",
        )
        last = result.splitlines()[-1]
        assert "[output truncated" in last

    @patch(f"{MODULE_PATH}.execute_command")
    def test_empty_output_does_not_crash(self, mock_exec: Any) -> None:
        mock_exec.return_value = make_command_result(
            return_code=0, stdout="", stderr=""
        )
        result = run_lint_imports_check_impl(
            lint_imports_binary="/usr/bin/lint-imports",
            project_dir="/project",
        )
        assert "(no output)" in result
        assert result.splitlines()[0].startswith("===")

    @patch(f"{MODULE_PATH}.execute_command")
    def test_command_construction_uses_cleaned_args(self, mock_exec: Any) -> None:
        mock_exec.return_value = make_command_result(return_code=0, stdout=CLEAN_OUTPUT)
        run_lint_imports_check_impl(
            lint_imports_binary="/usr/bin/lint-imports",
            project_dir="/project",
            extra_args=["--contract", "layers", "--verbose"],
        )
        cmd = mock_exec.call_args[0][0]
        assert cmd == [
            "/usr/bin/lint-imports",
            "--contract",
            "layers",
        ]
        assert mock_exec.call_args.kwargs["cwd"] == "/project"


class TestRunLintImportsTimeout:
    """Timeout and execution-error reporting."""

    @patch(f"{MODULE_PATH}.execute_command")
    def test_timeout_reports_timeout(self, mock_exec: Any) -> None:
        """A killed run reports the timeout, not a parse failure."""
        mock_exec.return_value = make_command_result(
            timed_out=True,
            execution_error="Process timed out after 45 seconds",
        )

        result = run_lint_imports_check_impl(
            lint_imports_binary="/usr/bin/lint-imports",
            project_dir="/project",
            timeout_seconds=45,
        )

        first = next(line for line in result.splitlines() if line.strip())
        assert "ERROR" in first
        assert "timed out" in first
        assert "45" in first
        assert "could not be parsed" not in result

    @patch(f"{MODULE_PATH}.execute_command")
    def test_timeout_with_stripped_flags_has_no_info_line(self, mock_exec: Any) -> None:
        """The state header stays the first non-empty line on a timeout."""
        mock_exec.return_value = make_command_result(
            timed_out=True,
            execution_error="Process timed out after 45 seconds",
        )

        result = run_lint_imports_check_impl(
            lint_imports_binary="/usr/bin/lint-imports",
            project_dir="/project",
            extra_args=["--verbose"],
            timeout_seconds=45,
        )

        assert result.splitlines() == [
            "=== ERROR: lint-imports timed out after 45 seconds ==="
        ]

    @patch(f"{MODULE_PATH}.execute_command")
    def test_execution_error_reports_cause(self, mock_exec: Any) -> None:
        """An execution error is reported instead of a parse failure."""
        mock_exec.return_value = make_command_result(
            timed_out=False,
            execution_error="FileNotFoundError: lint-imports",
        )

        result = run_lint_imports_check_impl(
            lint_imports_binary="/usr/bin/lint-imports",
            project_dir="/project",
        )

        first = next(line for line in result.splitlines() if line.strip())
        assert "ERROR" in first
        assert "FileNotFoundError: lint-imports" in first
        assert "could not be parsed" not in result

    @patch(f"{MODULE_PATH}.execute_command")
    def test_forwards_timeout_seconds(self, mock_exec: Any) -> None:
        """The configured timeout reaches execute_command."""
        mock_exec.return_value = make_command_result(return_code=0, stdout=CLEAN_OUTPUT)

        run_lint_imports_check_impl(
            lint_imports_binary="/usr/bin/lint-imports",
            project_dir="/project",
            timeout_seconds=45,
        )

        assert mock_exec.call_args.kwargs["timeout_seconds"] == 45

    @patch(f"{MODULE_PATH}.execute_command")
    def test_default_timeout_seconds(self, mock_exec: Any) -> None:
        """Without an explicit value the shared default is used."""
        mock_exec.return_value = make_command_result(return_code=0, stdout=CLEAN_OUTPUT)

        run_lint_imports_check_impl(
            lint_imports_binary="/usr/bin/lint-imports",
            project_dir="/project",
        )

        assert mock_exec.call_args.kwargs["timeout_seconds"] == 120
