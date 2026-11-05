"""Tests for merging saved coverage data files."""

import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from mcp_tools_py.code_checker_pytest.coverage_store import merge_coverage_data
from mcp_tools_py.utils.subprocess_runner import CommandResult, execute_command
from tests.conftest import make_command_result

_EXECUTE = "mcp_tools_py.code_checker_pytest.coverage_store.execute_command"

_LIB = """\
def first():
    return 1


def second():
    return 2
"""

_FAILURES = [
    pytest.param(
        make_command_result(
            return_code=-1, timed_out=True, execution_error="Process timed out"
        ),
        id="timeout",
    ),
    pytest.param(
        make_command_result(return_code=-1, execution_error="Could not start"),
        id="execution-error",
    ),
    pytest.param(make_command_result(return_code=1), id="non-zero"),
]


class TestMergeCommands:
    """Test the two coverage commands with execute_command patched."""

    @pytest.fixture(name="inputs")
    def _inputs(self, tmp_path: Path) -> list[str]:
        paths = [tmp_path / "one.coverage", tmp_path / "two.coverage"]
        for path in paths:
            path.write_text("")
        return [str(path) for path in paths]

    @pytest.fixture(name="temp_dir")
    def _temp_dir(self, tmp_path: Path) -> str:
        """Hold a report in merge/, so None can only come from the command checks."""
        merge_dir = tmp_path / "temp" / "merge"
        merge_dir.mkdir(parents=True)
        (merge_dir / "coverage.json").write_text(json.dumps({"files": {}}))
        return str(tmp_path / "temp")

    @staticmethod
    def _merge(inputs: list[str], temp_dir: str) -> dict[str, Any] | None:
        return merge_coverage_data(
            "/some/python", "/proj", inputs, temp_dir, {"STAGE": "one"}, 77
        )

    def test_missing_input_runs_nothing(self, inputs: list[str], temp_dir: str) -> None:
        """A missing input returns None without running coverage."""
        os.unlink(inputs[1])

        with patch(_EXECUTE) as mock_exec:
            assert self._merge(inputs, temp_dir) is None

        mock_exec.assert_not_called()

    @pytest.mark.parametrize("failure", _FAILURES)
    def test_failed_combine(
        self, inputs: list[str], temp_dir: str, failure: CommandResult
    ) -> None:
        """A failed combine returns None and skips the report."""
        with patch(_EXECUTE, return_value=failure) as mock_exec:
            assert self._merge(inputs, temp_dir) is None

        mock_exec.assert_called_once()

    @pytest.mark.parametrize("failure", _FAILURES)
    def test_failed_report(
        self, inputs: list[str], temp_dir: str, failure: CommandResult
    ) -> None:
        """A failed json command returns None, ignoring any report on disk."""
        with patch(_EXECUTE, side_effect=[make_command_result(), failure]):
            assert self._merge(inputs, temp_dir) is None

    def test_commands(self, inputs: list[str], temp_dir: str) -> None:
        """Both commands run in the project, on the inputs, without a threshold."""
        merge_dir = os.path.join(temp_dir, "merge")

        with patch(_EXECUTE, return_value=make_command_result()) as mock_exec:
            assert self._merge(inputs, temp_dir) == {"files": {}}

        combine, report = (call.args[0] for call in mock_exec.call_args_list)
        assert combine == [
            "/some/python",
            "-m",
            "coverage",
            "combine",
            "--keep",
            *inputs,
        ]
        assert report == [
            "/some/python",
            "-m",
            "coverage",
            "json",
            "-o",
            os.path.join(merge_dir, "coverage.json"),
            "--fail-under=0",
        ]
        for call in mock_exec.call_args_list:
            assert call.kwargs["cwd"] == "/proj"
            assert call.kwargs["timeout_seconds"] == 77
            assert call.kwargs["env"] == {
                "STAGE": "one",
                "COVERAGE_FILE": os.path.join(merge_dir, ".coverage"),
            }
            assert call.kwargs["env"]["COVERAGE_FILE"] not in inputs


def _measure(project: Path, data_file: Path, script: str, *flags: str) -> str:
    """Run a script of the project under coverage.

    Returns:
        The path of the data file written.
    """
    result = execute_command(
        [
            sys.executable,
            "-m",
            "coverage",
            "run",
            f"--data-file={data_file}",
            *flags,
            script,
        ],
        cwd=str(project),
    )
    assert result.return_code == 0, result.stderr
    return str(data_file)


@pytest.mark.integration
class TestMergeRealData:
    """Test merging data files written by a real coverage run."""

    @pytest.fixture(name="project")
    def _project(self, tmp_path: Path) -> Path:
        pytest.importorskip("coverage")
        project = tmp_path / "project"
        project.mkdir()
        (project / "lib.py").write_text(_LIB)
        (project / "run_first.py").write_text("import lib\n\nlib.first()\n")
        (project / "run_second.py").write_text("import lib\n\nlib.second()\n")
        return project

    @pytest.fixture(name="temp_dir")
    def _temp_dir(self, tmp_path: Path) -> str:
        """Create the run's temp directory, leaving merge/ to the merge."""
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        return str(temp_dir)

    @pytest.fixture(name="inputs")
    def _inputs(self, project: Path, temp_dir: str) -> list[str]:
        return [
            _measure(project, Path(temp_dir) / "first.coverage", "run_first.py"),
            _measure(project, Path(temp_dir) / "second.coverage", "run_second.py"),
        ]

    @staticmethod
    def _merge(
        project: Path,
        inputs: list[str],
        temp_dir: str,
        env_vars: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        return merge_coverage_data(
            sys.executable, str(project), inputs, temp_dir, env_vars, 60
        )

    def test_merges_different_functions(
        self, project: Path, inputs: list[str], temp_dir: str
    ) -> None:
        """The report covers both runs, with relative keys and function regions."""
        alone = self._merge(project, inputs[:1], os.path.join(temp_dir, "alone"))
        assert alone is not None

        merged = self._merge(project, inputs, temp_dir)

        assert merged is not None
        assert (
            merged["files"]["lib.py"]["summary"]["percent_covered"]
            > alone["files"]["lib.py"]["summary"]["percent_covered"]
        )
        assert set(merged["files"]) == {"lib.py", "run_first.py", "run_second.py"}
        functions = merged["files"]["lib.py"]["functions"]
        assert functions["first"]["missing_lines"] == []
        assert functions["second"]["missing_lines"] == []

    def test_merge_directory_is_created(
        self, project: Path, inputs: list[str], temp_dir: str
    ) -> None:
        """The merge succeeds when merge/ doesn't exist yet."""
        assert not os.path.exists(os.path.join(temp_dir, "merge"))

        assert self._merge(project, inputs, temp_dir) is not None

    def test_inputs_are_kept(
        self, project: Path, inputs: list[str], temp_dir: str
    ) -> None:
        """Combining leaves the input files in place."""
        assert self._merge(project, inputs, temp_dir) is not None

        assert all(os.path.isfile(path) for path in inputs)

    def test_configured_fail_under_is_not_applied(
        self, project: Path, inputs: list[str], temp_dir: str
    ) -> None:
        """A threshold the merged report misses doesn't fail the merge."""
        (project / ".coveragerc").write_text("[report]\nfail_under = 99\n")
        # One run leaves lib.second uncovered, so 99 is out of reach.
        assert self._merge(project, inputs[:1], temp_dir) is not None

        without_override = execute_command(
            [sys.executable, "-m", "coverage", "json", "-o", os.devnull],
            cwd=str(project),
            env={"COVERAGE_FILE": os.path.join(temp_dir, "merge", ".coverage")},
        )

        assert without_override.return_code != 0

    def test_branch_and_statement_runs_do_not_merge(
        self, project: Path, temp_dir: str
    ) -> None:
        """Coverage refuses to combine branch data with statement data."""
        inputs = [
            _measure(
                project, Path(temp_dir) / "first.coverage", "run_first.py", "--branch"
            ),
            _measure(project, Path(temp_dir) / "second.coverage", "run_second.py"),
        ]

        assert self._merge(project, inputs, temp_dir) is None

    def test_coverage_rcfile_is_honoured(
        self, project: Path, inputs: list[str], temp_dir: str, tmp_path: Path
    ) -> None:
        """The caller's COVERAGE_RCFILE reaches the coverage commands."""
        rcfile = tmp_path / "custom.rc"
        rcfile.write_text("[report]\nomit = run_*\n")

        merged = self._merge(
            project, inputs, temp_dir, {"COVERAGE_RCFILE": str(rcfile)}
        )

        assert merged is not None
        assert set(merged["files"]) == {"lib.py"}
