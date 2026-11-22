"""Integration tests for the marker hint and the addopts line against real pytest."""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.code_checker_pytest.marker_hint import (
    RERUN_TIP,
    STRICT_SUGGESTION,
    marker_notes,
)
from mcp_tools_py.code_checker_pytest.pytest_config import (
    addopts_notes,
    effective_config,
)
from mcp_tools_py.code_checker_pytest.runners import check_code_with_pytest
from mcp_tools_py.code_checker_pytest.utils import sanitize_extra_args
from mcp_tools_py.code_checker_pytest.verdict import RunStatus

_INI_WAY_OUT = ' — to run without: extra_args=["-o", "addopts="]'
_UNIT_HINT = "`unit` is not registered in the project config."
_SLOW_TESTS = (
    "import pytest\n\n\n"
    "def test_plain():\n    pass\n\n\n"
    "@pytest.mark.slow\n"
    "def test_slow():\n    pass\n"
)
_needs_pytest_9 = pytest.mark.skipif(
    pytest.version_tuple < (9,), reason="pytest 9 checks -m names and [tool.pytest]"
)


def _project(project: Path, table: str, tests: str = _SLOW_TESTS) -> Path:
    """Write pyproject.toml with the given pytest table and one test module."""
    (project / "pyproject.toml").write_text(table, encoding="utf-8")
    (project / "tests").mkdir()
    (project / "tests" / "test_mod.py").write_text(tests, encoding="utf-8")
    return project


def _run(
    project: Path, extra_args: list[str]
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Run pytest the way run_pytest_check does.

    Returns:
        check_code_with_pytest's result, the addopts notes and the marker notes.
    """
    sanitized = sanitize_extra_args(extra_args, None, project_dir=str(project))
    results = check_code_with_pytest(
        str(project),
        python_executable=sys.executable,
        extra_args=sanitized.cleaned_args,
        timeout_seconds=120,
    )
    effective = effective_config(str(project), None, sanitized.cleaned_args, None)
    notes = marker_notes(effective, results["exit_code"], results["marker_error"])
    return results, addopts_notes(effective), notes


def _tool(project: Path) -> Any:
    """Register the tools for project under this interpreter.

    Returns:
        The registered run_pytest_check function.
    """
    with patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp:
        mock_tool = MagicMock()
        mock_fastmcp.return_value.tool.return_value = mock_tool

        from mcp_tools_py.server import (  # pylint: disable=import-outside-toplevel
            ToolServer,
        )

        with patch.object(
            ToolServer, "_warn_missing_console_scripts", return_value=None
        ):
            ToolServer(project_dir=project, python_executable=sys.executable)

    tools = {f.__name__: f for call in mock_tool.call_args_list for f in [call[0][0]]}
    return tools["run_pytest_check"]


@pytest.mark.integration
def test_unregistered_name_without_strict_exits_5_with_hint(tmp_path: Path) -> None:
    project = _project(tmp_path, '[tool.pytest.ini_options]\nmarkers = ["slow"]\n')

    results, _, notes = _run(project, ["-m", "unit"])

    assert results["exit_code"] == 5
    assert notes == [f"{_UNIT_HINT} Registered: slow", STRICT_SUGGESTION]


@pytest.mark.integration
@_needs_pytest_9
def test_unregistered_name_with_strict_shows_pytest_line_and_hint(
    tmp_path: Path,
) -> None:
    project = _project(
        tmp_path,
        '[tool.pytest.ini_options]\naddopts = "--strict-markers"\nmarkers = ["slow"]\n',
    )

    results, _, notes = _run(project, ["-m", "unit"])

    assert results["exit_code"] == 4
    assert results["marker_error"].startswith("ERROR: Unknown marker(s)")
    assert notes == [results["marker_error"], f"{_UNIT_HINT} Registered: slow"]


@pytest.mark.integration
@_needs_pytest_9
def test_unregistered_name_with_strict_under_xdist_gets_rerun_tip(
    tmp_path: Path,
) -> None:
    pytest.importorskip("xdist")
    project = _project(
        tmp_path,
        '[tool.pytest.ini_options]\naddopts = "--strict-markers"\nmarkers = ["slow"]\n',
    )

    results, _, notes = _run(project, ["-m", "unit", "-n", "2"])

    assert results["exit_code"] == 3
    assert notes == [f"{_UNIT_HINT} Registered: slow", RERUN_TIP]


@pytest.mark.integration
@_needs_pytest_9
@pytest.mark.parametrize(
    ("numprocesses", "exit_code", "tip"),
    [(["-n", "2"], 3, True), ([], 4, False), (["-n", "0"], 4, False)],
    ids=["n2", "no-n", "n0"],
)
def test_syntax_error_gets_rerun_tip_only_under_xdist(
    tmp_path: Path, numprocesses: list[str], exit_code: int, tip: bool
) -> None:
    if numprocesses:
        pytest.importorskip("xdist")
    project = _project(tmp_path, '[tool.pytest.ini_options]\nmarkers = ["a"]\n')

    results, _, notes = _run(project, ["-m", "a and", *numprocesses])

    assert results["exit_code"] == exit_code
    assert (RERUN_TIP in notes) is tip
    if exit_code == 4:
        assert "Wrong expression passed to '-m'" in notes[0]
    assert not any(_UNIT_HINT in note for note in notes)


@pytest.mark.integration
@_needs_pytest_9
@pytest.mark.parametrize(
    "header", ["[tool.pytest.ini_options]", "[tool.pytest]"], ids=["ini", "native"]
)
def test_list_addopts_m_unit_in_either_table(tmp_path: Path, header: str) -> None:
    project = _project(tmp_path, f'{header}\naddopts = ["-m", "unit"]\n')

    results, addopts, notes = _run(project, [])

    assert results["exit_code"] == 5
    assert addopts == [f"addopts (pyproject.toml): -m unit{_INI_WAY_OUT}"]
    assert notes == [
        f"{_UNIT_HINT} The project config registers none.",
        STRICT_SUGGESTION,
    ]


@pytest.mark.integration
def test_xdist_default_m_has_no_deselected_count_and_shows_the_line(
    tmp_path: Path,
) -> None:
    """xdist does not relay deselection; the reply still shows the defaults."""
    pytest.importorskip("xdist")
    project = _project(
        tmp_path,
        "[tool.pytest.ini_options]\n"
        "addopts = \"-n 2 -m 'not slow'\"\n"
        'markers = ["slow"]\n',
    )

    results, _, _ = _run(project, [])

    assert results["verdict"].status is RunStatus.PASSED
    assert results["summary"]["passed"] == 1
    assert not results["summary"]["deselected"]

    reply = _tool(project)()

    assert f"addopts (pyproject.toml): -n 2 -m 'not slow'{_INI_WAY_OUT}" in (
        reply.splitlines()
    ), reply
