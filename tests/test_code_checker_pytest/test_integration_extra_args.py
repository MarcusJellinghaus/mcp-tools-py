"""Integration tests verifying extra_args values are never read as paths."""

import sys
from pathlib import Path
from typing import List

import pytest

from mcp_tools_py.code_checker_pytest.models import PytestReport
from mcp_tools_py.code_checker_pytest.reporting import collected_test_ids
from mcp_tools_py.code_checker_pytest.runners import check_code_with_pytest, run_tests
from mcp_tools_py.code_checker_pytest.utils import sanitize_extra_args


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a project with one passing test in each of three folders.

    tests/ also holds a second test file.
    """
    for folder, name in (("tests", "in"), ("other", "out"), ("checks", "chk")):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / f"test_{name}.py").write_text(
            f"def test_{name}():\n    pass\n"
        )
    (tmp_path / "tests" / "test_second.py").write_text("def test_second():\n    pass\n")
    return tmp_path


def _run(project: Path, args: List[str], test_folder: str = "tests") -> PytestReport:
    """Sanitize args the way the server does, then run pytest."""
    sanitized = sanitize_extra_args(args, None, project_dir=str(project))
    return run_tests(
        project_dir=str(project),
        test_folder=test_folder,
        python_executable=sys.executable,
        extra_args=sanitized.cleaned_args,
        skip_default_test_folder=sanitized.has_path_args,
        timeout_seconds=60,
    )


def _nodeids(report: PytestReport) -> List[str]:
    return [test.nodeid for test in report.tests or []]


@pytest.mark.integration
class TestExtraArgsIntegration:
    """Option values stay with their option and the default folder still runs."""

    @pytest.mark.parametrize(
        "args",
        [
            ["-k", "tests"],
            ["--json-report-omit", "log"],
            ["--cov"],
            ["--debug"],
            ["--ignore", "other"],
            ["--rootdir", "."],
        ],
    )
    def test_option_value_not_a_path(self, temp_project: Path, args: List[str]) -> None:
        """Only the default folder's tests run."""
        nodeids = _nodeids(_run(temp_project, args))
        assert nodeids
        assert all(nodeid.startswith("tests/") for nodeid in nodeids)

    def test_positional_tests_is_a_path(self, temp_project: Path) -> None:
        """A positional 'tests' runs tests/, not the configured test folder."""
        nodeids = _nodeids(_run(temp_project, ["tests"], test_folder="checks"))
        assert nodeids
        assert all(nodeid.startswith("tests/") for nodeid in nodeids)


@pytest.mark.integration
class TestCollectOnlyIntegration:
    """A real --collect-only run gives the JSON shape collected_test_ids reads."""

    @pytest.mark.parametrize(
        "args",
        [
            ["--collect-only", "-k", "test_in"],
            ["--collect-only", "-k", "test_in", "-n", "2"],
        ],
        ids=["serial", "xdist"],
    )
    def test_collect_only_lists_selected_ids(
        self, temp_project: Path, args: List[str]
    ) -> None:
        """Only the selected test is listed; none ran."""
        report = _run(temp_project, args)
        assert report.summary.total == 0
        assert report.summary.deselected == 1
        assert collected_test_ids(report) == ["tests/test_in.py::test_in"]

    def test_check_code_with_pytest_reports_deselected(
        self, temp_project: Path
    ) -> None:
        """The summary dict carries the deselected count."""
        results = check_code_with_pytest(
            project_dir=str(temp_project),
            test_folder="tests",
            python_executable=sys.executable,
            extra_args=["--collect-only", "-k", "test_in"],
            timeout_seconds=60,
        )
        assert results["summary"]["deselected"] == 1
