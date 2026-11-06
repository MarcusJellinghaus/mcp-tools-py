"""Integration tests for how real collection failures are classified and rendered."""

import sys
from pathlib import Path
from typing import Any

import pytest

from mcp_tools_py.code_checker_pytest.runners import check_code_with_pytest
from mcp_tools_py.code_checker_pytest.verdict import RunStatus, format_error_text


def _write_test_modules(tests_dir: Path, source: str, count: int = 2) -> None:
    tests_dir.mkdir(parents=True)
    for index in range(count):
        (tests_dir / f"test_mod{index}.py").write_text(source)


def _run(project_dir: Path, extra_args: list[str] | None = None) -> dict[str, Any]:
    return check_code_with_pytest(
        str(project_dir),
        python_executable=sys.executable,
        extra_args=extra_args,
        timeout_seconds=120,
    )


@pytest.mark.integration
def test_serial_run_with_every_module_failing_is_error(tmp_path: Path) -> None:
    """A serial run printing `collected 0 items / N errors` is not No Tests Found."""
    _write_test_modules(tmp_path / "tests", "import module_that_does_not_exist\n")

    result = _run(tmp_path)

    verdict = result["verdict"]
    assert verdict.status is RunStatus.ERROR
    assert verdict.exit_code == 2
    assert result["test_results"] is not None
    text = format_error_text(result["test_results"], verdict)
    assert "collectors failed" in text
    assert "No Tests Found" not in text


@pytest.mark.integration
def test_sibling_conftests_failing_under_xdist_show_both_causes(
    tmp_path: Path,
) -> None:
    """Two conftest.py files failing differently both reach the error text."""
    pytest.importorskip("xdist")
    for name, cause in (("alpha", "alpha_cause"), ("beta", "beta_cause")):
        directory = tmp_path / "tests" / name
        directory.mkdir(parents=True)
        (directory / "conftest.py").write_text(f"raise RuntimeError('{cause}')\n")
        (directory / f"test_{name}.py").write_text("def test_ok():\n    assert True\n")

    result = _run(tmp_path, extra_args=["-n", "2"])

    text = format_error_text(result["test_results"], result["verdict"])
    assert "alpha_cause" in text
    assert "beta_cause" in text
    assert "tests failed" not in text


@pytest.mark.integration
def test_two_syntax_errors_are_two_distinct_errors(tmp_path: Path) -> None:
    """Syntax errors in two modules name different files, so they stay separate."""
    _write_test_modules(tmp_path / "tests", "def broken(:\n")

    result = _run(tmp_path)

    verdict = result["verdict"]
    assert verdict.status is RunStatus.ERROR
    assert len(verdict.problems) == 2
    text = format_error_text(result["test_results"], verdict)
    assert "2 collectors failed (2 distinct errors)" in text


@pytest.mark.integration
def test_empty_test_directory_is_no_tests_found(tmp_path: Path) -> None:
    """Exit code 5 still reports No Tests Found."""
    (tmp_path / "tests").mkdir()

    result = _run(tmp_path)

    verdict = result["verdict"]
    assert verdict.status is RunStatus.ERROR
    assert any("No Tests Found" in problem for problem in verdict.problems)
