"""Integration tests for the saved coverage data of PythonToolkit's `test` action."""

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest
from mcp_coder_utils.toolkit import ActionRequest, ActionResult

from mcp_tools_py.code_checker_pytest.coverage_store import (
    METADATA_FILE,
    STORE_DIR,
    load_saved,
    write_saved,
)
from mcp_tools_py.code_checker_pytest.models import PytestReport, Summary
from mcp_tools_py.code_checker_pytest.verdict import RunStatus
from mcp_tools_py.toolkit import PythonToolkit
from tests._coverage_project import _write_project
from tests._pytest_results import make_pytest_results

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        importlib.util.find_spec("pytest_cov") is None,
        reason="pytest-cov is not installed",
    ),
]


def _run_test(project: Path, depth: str = "full") -> ActionResult:
    """Run the toolkit's `test` action.

    Returns:
        The action's result.
    """
    request = ActionRequest(action="test", depth=depth, project_dir=project, params={})
    return PythonToolkit().run(request)


def _seed(project: Path) -> None:
    """Save data no real run of the project would produce."""
    write_saved(
        str(project),
        {
            "report": {"files": {}},
            "hashes": {},
            "roots": [],
            "sources": [],
            "fail_under": None,
            "runs": [
                {
                    "selection": "selection: seeded",
                    "data_file": None,
                    "failed_collectors": 0,
                    "failed_tests": 0,
                    "generic_warning": False,
                }
            ],
        },
        None,
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project with one tested and one untested function, fail_under = 99."""
    _write_project(tmp_path)
    return tmp_path


def test_passing_run_saves_the_data(project: Path) -> None:
    """The normal path saves what the digest shows."""
    result = _run_test(project)

    assert result.status == "ok"
    assert result.raw and "stmts" in result.raw
    saved = load_saved(str(project))
    assert saved is not None
    assert saved["runs"][-1]["data_file"] is not None


def test_no_tests_found_clears_the_data(project: Path) -> None:
    """The skipped early return clears what an earlier run saved."""
    _seed(project)
    (project / "tests" / "test_mod.py").unlink()

    result = _run_test(project)

    assert result.status == "skipped"
    assert not (project / STORE_DIR).exists()


def test_failing_collector_under_xdist_saves_the_data(project: Path) -> None:
    """The ERROR early return with a report and JSON saves the partial run."""
    pyproject = project / "pyproject.toml"
    pyproject.write_text(pyproject.read_text() + 'addopts = "-n 2"\n')
    (project / "tests" / "test_broken.py").write_text(
        "import module_that_does_not_exist\n"
    )

    result = _run_test(project)

    assert result.status == "error"
    saved = load_saved(str(project))
    assert saved is not None
    assert saved["runs"][-1]["failed_collectors"] == 1


def test_failed_without_findings_saves_the_data(project: Path) -> None:
    """The FAILED early return with no failing test saves the data."""
    report = PytestReport(
        created=0.0,
        duration=0.0,
        exitcode=1,
        root="",
        environment={},
        summary=Summary(collected=0, total=0),
    )
    results = make_pytest_results(
        RunStatus.FAILED,
        ["some problem"],
        test_results=report,
        summary_text="Collected 0 tests in 0.0 seconds",
    )
    data = {"files": {"src/pkg/mod.py": {"summary": {"num_statements": 1}}}}

    with (
        patch("mcp_tools_py.toolkit.check_code_with_pytest", return_value=results),
        patch("mcp_tools_py.toolkit.read_coverage_report", return_value=data),
    ):
        result = _run_test(project)

    assert result.status == "error"
    saved = load_saved(str(project))
    assert saved is not None
    assert saved["report"] == data


@pytest.mark.parametrize("depth", ["quick", "standard"])
def test_other_depths_leave_the_data_alone(project: Path, depth: str) -> None:
    """Only `full` measures coverage, so nothing else touches saved data."""
    _seed(project)
    metadata = project / STORE_DIR / METADATA_FILE
    before = metadata.read_bytes()

    result = _run_test(project, depth)

    assert result.status == "ok"
    assert metadata.read_bytes() == before


def test_failed_save_is_appended_to_raw(project: Path) -> None:
    """An OSError while saving doesn't cost the digest."""
    with patch(
        "mcp_tools_py.code_checker_pytest.coverage_store.write_saved",
        side_effect=OSError("disk full"),
    ):
        result = _run_test(project)

    assert result.status == "ok"
    assert result.raw and "stmts" in result.raw
    assert result.raw.endswith("\nCould not update saved coverage data: disk full")
