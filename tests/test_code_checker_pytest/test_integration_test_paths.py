"""Integration tests for which tests run_pytest_check runs without a path (#58)."""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from mcp_coder_utils.toolkit import ActionRequest

from mcp_tools_py.toolkit import PythonToolkit
from tests._coverage_project import _run_pytest_check, _write_project

NOTE = "testpaths entries not found"

# Each folder holds a different number of tests, so the pass count shows
# exactly which folders ran.  Module names are unique: same-named modules
# without __init__.py clash on import.
FOLDERS = {
    "tests": (1, "test_in_tests.py"),
    "checks": (2, "test_in_checks.py"),
    "integration": (4, "test_in_integration.py"),
    "pkgs/a/tests": (8, "test_in_pkg.py"),
}


@dataclass(frozen=True)
class Row:
    """One scenario: project layout, call, and expected outcome."""

    testpaths: Optional[str]
    folders: List[str]
    passed: Optional[int]  # None: usage error, nothing passed
    note: bool
    extra_args: List[str] = field(default_factory=list)
    test_folder: Optional[str] = None


ROWS = {
    "tests": Row('["tests"]', ["tests"], 1, False),
    "not-set": Row(None, ["tests"], 1, False),
    "checks": Row('["checks"]', ["checks"], 2, False),
    "checks-with-tests": Row('["checks"]', ["checks", "tests"], 2, False),
    "two-entries": Row('["tests", "integration"]', ["tests", "integration"], 5, False),
    "glob": Row('["pkgs/*/tests"]', ["pkgs/a/tests", "tests"], 8, False),
    "one-missing": Row('["nope", "checks"]', ["checks"], 2, False),
    "all-missing": Row('["nope"]', ["tests"], 1, True),
    "all-missing-no-tests": Row('["nope"]', [], None, True),
    "empty": Row("[]", ["tests"], 1, False),
    "path-arg": Row('["checks"]', ["checks", "tests"], 1, False, ["tests"]),
    "missing-path-arg": Row('["checks"]', ["checks"], None, False, ["tests"]),
    "other-path-arg": Row('["tests"]', ["tests", "checks"], 2, False, ["checks"]),
    "test-folder": Row('["tests"]', ["tests", "checks"], 2, False, [], "checks"),
}


def _write_tests(project: Path, folders: List[str]) -> None:
    """Write each folder's test module with its number of passing tests."""
    for folder in folders:
        count, module = FOLDERS[folder]
        (project / folder).mkdir(parents=True)
        body = "".join(f"def test_{i}():\n    pass\n\n\n" for i in range(count))
        (project / folder / module).write_text(body)


def _write_pyproject(project: Path, testpaths: Optional[str]) -> None:
    """Write the pytest table, with testpaths when given."""
    line = f"testpaths = {testpaths}\n" if testpaths is not None else ""
    (project / "pyproject.toml").write_text(f"[tool.pytest.ini_options]\n{line}")


def _tool(project: Path, test_folder: Optional[str]) -> Any:
    """Register the tools for project under this interpreter.

    Returns:
        The registered run_pytest_check function.
    """
    with patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp:
        mock_tool = MagicMock()
        mock_fastmcp.return_value.tool.return_value = mock_tool

        from mcp_tools_py.server import ToolServer

        with patch.object(
            ToolServer, "_warn_missing_console_scripts", return_value=None
        ):
            ToolServer(
                project_dir=project,
                python_executable=sys.executable,
                test_folder=test_folder,
            )

    tools = {f.__name__: f for call in mock_tool.call_args_list for f in [call[0][0]]}
    return tools["run_pytest_check"]


@pytest.mark.integration
@pytest.mark.parametrize("row", list(ROWS.values()), ids=list(ROWS))
def test_run_pytest_check_selects_tests(tmp_path: Path, row: Row) -> None:
    """The pass count shows which folders ran; the note shows when expected."""
    _write_pyproject(tmp_path, row.testpaths)
    _write_tests(tmp_path, row.folders)

    reply = _tool(tmp_path, row.test_folder)(extra_args=row.extra_args or None)

    match = re.search(r"Passed: (\d+)", reply)
    passed = int(match.group(1)) if match else None
    assert passed == row.passed, reply
    assert (NOTE in reply) == row.note, reply


@pytest.mark.integration
def test_toolkit_uses_testpaths(tmp_path: Path) -> None:
    """The toolkit's context has no explicit folder, so testpaths applies."""
    _write_pyproject(tmp_path, '["checks"]')
    _write_tests(tmp_path, ["checks"])

    result = PythonToolkit().run(
        ActionRequest(action="test", depth="quick", project_dir=tmp_path, params={})
    )

    assert result.status == "ok", result.summary


@pytest.mark.integration
def test_coverage_with_missing_testpaths(tmp_path: Path) -> None:
    """Coverage handles the unresolved folder and the reply carries the note."""
    _write_project(tmp_path)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text().replace('testpaths = ["tests"]', 'testpaths = ["nope"]')
    )

    reply = _run_pytest_check(tmp_path)(coverage=True)

    assert NOTE in reply
    assert "Unexpected error" not in reply
    assert "Passed: 1" in reply
