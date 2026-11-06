"""Integration test for run_pytest_check(coverage=True) against a real project."""

import importlib.util
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_tools_py.code_checker_pytest.coverage_store import (
    METADATA_FILE,
    STORE_DIR,
    load_saved,
)
from tests._coverage_project import _run_pytest_check, _write_project

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        importlib.util.find_spec("pytest_cov") is None,
        reason="pytest-cov is not installed",
    ),
]


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project with one tested and one untested function, fail_under = 99."""
    _write_project(tmp_path)
    return tmp_path


def test_coverage_digest_from_a_real_run(project: Path) -> None:
    """The digest is appended, fail_under is reported but not applied."""
    result = _run_pytest_check(project)(coverage=True)

    assert "Passed: 1" in result or "passed successfully" in result
    assert "stmts" in result
    assert "selection: full suite" in result
    assert "fail_under=99 is configured; not applied to this run" in result
    assert "uncovered  6-7" in result
    assert "⚠" not in result


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_coverage_leaves_the_project_clean(project: Path) -> None:
    """Saved data exists, and git sees neither it nor any coverage output."""
    git = shutil.which("git")
    assert git is not None
    subprocess.run([git, "init"], cwd=project, check=True, capture_output=True)

    _run_pytest_check(project)(coverage=True)

    assert (project / STORE_DIR / METADATA_FILE).exists()
    status = subprocess.run(
        [git, "status", "--porcelain", "--untracked-files=all"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert not [line for line in status if ".mcp-tools-py" in line]
    assert "?? .coverage" not in status
    assert "?? coverage.json" not in status


def test_coverage_run_saves_the_data_file(project: Path) -> None:
    """The saved run references a copy of the run's coverage data."""
    _run_pytest_check(project)(coverage=True)

    saved = load_saved(str(project))
    assert saved is not None
    assert saved["hashes"].keys() >= {"src/pkg/mod.py", "tests/test_mod.py"}
    assert saved["sources"] == ["src"]
    assert saved["fail_under"] == 99.0
    data_file = saved["runs"][-1]["data_file"]
    assert data_file is not None
    assert (project / STORE_DIR / data_file).is_file()


def test_run_without_coverage_leaves_saved_data_untouched(project: Path) -> None:
    """Only a coverage run updates the saved data."""
    tool = _run_pytest_check(project)
    tool(coverage=True)
    metadata = project / STORE_DIR / METADATA_FILE
    before = metadata.read_bytes()

    tool()

    assert metadata.read_bytes() == before


def test_run_with_no_report_clears_saved_data(project: Path) -> None:
    """A coverage run selecting nothing leaves no data to keep."""
    tool = _run_pytest_check(project)
    tool(coverage=True)
    assert load_saved(str(project)) is not None

    result = tool(coverage=True, extra_args=["-k", "nomatch"])

    assert "Coverage report was not produced." in result
    assert not (project / STORE_DIR).exists()


def test_failing_collector_under_xdist_qualifies_the_digest(project: Path) -> None:
    """The digest opens with the collector count and claims no failed tests."""
    (project / "tests" / "test_broken.py").write_text(
        "import module_that_does_not_exist\n"
    )

    result = _run_pytest_check(project)(coverage=True, extra_args=["-n", "2"])

    assert (
        "\n\n⚠ 1 collector failed — coverage below reflects a partial run\n" in result
    )
    assert "tests failed" not in result


def test_failed_save_is_a_note_below_the_digest(project: Path) -> None:
    """An OSError while saving doesn't cost the digest."""
    with patch(
        "mcp_tools_py.code_checker_pytest.coverage_store.write_saved",
        side_effect=OSError("disk full"),
    ):
        result = _run_pytest_check(project)(coverage=True)

    assert "stmts" in result
    assert result.endswith("\nCould not update saved coverage data: disk full")
