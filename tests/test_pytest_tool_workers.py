"""Tests for the workers note and serial sizing in run_pytest_check."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.checker_tools import CheckerTools
from mcp_tools_py.code_checker_pytest.marker_hint import RERUN_TIP
from mcp_tools_py.code_checker_pytest.verdict import RunStatus
from tests._pytest_results import make_pytest_results
from tests.conftest import make_environment_info

_PYTEST_TOOL = "mcp_tools_py.checker_tools.pytest_tool"
_GET_ENVIRONMENT_INFO = "mcp_tools_py.utils.tool_context.get_environment_info"
_NOTE = "workers: 4 (config.toml)"


@pytest.fixture
def run_pytest_check(tmp_path: Path, all_modules_importable: Any) -> Iterator[Any]:
    """run_pytest_check over tmp_path, with pytest-json-report reported installed."""
    with patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp:
        mock_tool = MagicMock()
        mock_fastmcp.return_value.tool.return_value = mock_tool

        from mcp_tools_py.server import (  # pylint: disable=import-outside-toplevel
            ToolServer,
        )

        with patch.object(
            ToolServer, "_warn_missing_console_scripts", return_value=None
        ):
            ToolServer(project_dir=tmp_path)

    tools = {f.__name__: f for call in mock_tool.call_args_list for f in [call[0][0]]}
    info = make_environment_info(distributions={"pytest-json-report": "1.5.0"})
    with patch(_GET_ENVIRONMENT_INFO, return_value=info):
        yield tools["run_pytest_check"]


def _pyproject(project_dir: Path, *lines: str) -> None:
    body = "\n".join(lines)
    (project_dir / "pyproject.toml").write_text(
        f"[tool.pytest.ini_options]\n{body}\n", encoding="utf-8"
    )


def _passed(**fields: Any) -> dict[str, Any]:
    return make_pytest_results(
        exit_code=0, summary={"passed": 2, "collected": 2}, **fields
    )


def _call(run_pytest_check: Any, results: dict[str, Any], **kwargs: Any) -> str:
    with patch(f"{_PYTEST_TOOL}.check_code_with_pytest", return_value=results):
        reply: str = run_pytest_check(**kwargs)
    return reply


def _addopts_lines(reply: str) -> list[str]:
    return [line for line in reply.splitlines() if line.startswith("addopts (")]


def test_workers_note_is_the_first_line(run_pytest_check: Any) -> None:
    reply = _call(run_pytest_check, _passed(workers_note=_NOTE))

    assert reply.splitlines()[0] == _NOTE


def test_workers_note_comes_before_the_other_notes(run_pytest_check: Any) -> None:
    paths_note = "testpaths: tests"
    results = _passed(workers_note=_NOTE, test_paths_note=paths_note)

    lines = _call(run_pytest_check, results).splitlines()

    assert lines[0] == _NOTE
    assert lines[1] == paths_note


def test_no_workers_note_leaves_the_reply_unchanged(run_pytest_check: Any) -> None:
    without_key = _call(run_pytest_check, _passed())
    with_none = _call(run_pytest_check, _passed(workers_note=None))

    assert with_none == without_key
    assert not with_none.startswith("workers:")


@pytest.mark.parametrize(
    ("serial", "shown"), [(False, True), (True, False)], ids=["xdist", "serial"]
)
def test_serial_run_drops_the_xdist_addopts_line(
    run_pytest_check: Any, tmp_path: Path, serial: bool, shown: bool
) -> None:
    """A run sized to serial reports deselection, so the xdist case is gone."""
    _pyproject(tmp_path, "addopts = \"-n auto -m 'not slow'\"")

    reply = _call(run_pytest_check, _passed(workers_serial=serial))

    assert bool(_addopts_lines(reply)) is shown


@pytest.mark.parametrize(
    ("serial", "shown"), [(False, True), (True, False)], ids=["xdist", "serial"]
)
def test_serial_run_drops_the_rerun_tip(
    run_pytest_check: Any, tmp_path: Path, serial: bool, shown: bool
) -> None:
    _pyproject(tmp_path, 'addopts = "-n auto"', 'markers = ["fast"]')
    results = make_pytest_results(
        RunStatus.ERROR, ["internal error"], exit_code=3, workers_serial=serial
    )

    reply = _call(run_pytest_check, results, markers=["fast"])

    assert (RERUN_TIP in reply) is shown


def test_unexpected_error_keeps_the_workers_note(run_pytest_check: Any) -> None:
    with patch.object(
        CheckerTools,
        "_format_pytest_result_with_details",
        side_effect=RuntimeError("boom"),
    ):
        reply = _call(run_pytest_check, _passed(workers_note=_NOTE))

    assert reply.startswith(f"{_NOTE}\n\n")
    assert "Unexpected error running pytest" in reply


def test_unexpected_error_without_note_is_the_error_alone(
    run_pytest_check: Any,
) -> None:
    with patch.object(
        CheckerTools,
        "_format_pytest_result_with_details",
        side_effect=RuntimeError("boom"),
    ):
        reply = _call(run_pytest_check, _passed())

    assert reply.startswith("Unexpected error running pytest")


def test_effective_config_is_passed_to_the_runner(run_pytest_check: Any) -> None:
    with patch(
        f"{_PYTEST_TOOL}.check_code_with_pytest", return_value=_passed()
    ) as mock_run:
        run_pytest_check()

    assert mock_run.call_args.kwargs["effective"] is not None


def test_docstring_points_to_pytest_workers(run_pytest_check: Any) -> None:
    doc = run_pytest_check.__doc__

    assert "pytest_workers" in doc
    assert "docs/user-config.md" in doc
