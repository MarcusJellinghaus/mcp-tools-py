"""Tests for the coverage run plumbing: flags, env, JSON load, fail_under read."""

import json
import os
from pathlib import Path
from unittest.mock import patch

from mcp_tools_py.code_checker_pytest.coverage import (
    coverage_args,
    read_coverage_report,
    read_fail_under,
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
