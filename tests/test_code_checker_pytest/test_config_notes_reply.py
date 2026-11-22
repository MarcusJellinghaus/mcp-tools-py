"""Reply-level tests for the addopts line and the marker hint of run_pytest_check."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.code_checker_pytest.marker_hint import STRICT_SUGGESTION
from mcp_tools_py.code_checker_pytest.verdict import RunStatus
from mcp_tools_py.toolkit import UNATTENDED_EXCLUDED_MARKERS
from tests._pytest_results import make_pytest_results
from tests.conftest import make_command_result, make_environment_info

_PYTEST_TOOL = "mcp_tools_py.checker_tools.pytest_tool"
_RUNNERS = "mcp_tools_py.code_checker_pytest.runners"
_GET_ENVIRONMENT_INFO = "mcp_tools_py.utils.tool_context.get_environment_info"
_INI_WAY_OUT = ' — to run without: extra_args=["-o", "addopts="]'
_NO_TESTS = "No Tests Found: Pytest did not find any tests to run."
_UNKNOWN_UNIT = (
    "ERROR: Unknown marker(s) in '-m' expression: unit. "
    "Use 'pytest --markers' to see available markers."
)
_UNIT_HINT = "`unit` is not registered in the project config."


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


def _results(
    status: RunStatus = RunStatus.PASSED,
    problems: list[str] | None = None,
    exit_code: int | None = 0,
    marker_error: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    return make_pytest_results(
        status, problems, exit_code=exit_code, marker_error=marker_error, **fields
    )


def _passed(**summary: Any) -> dict[str, Any]:
    return _results(summary={"passed": 2, "collected": 2, **summary})


def _failed() -> dict[str, Any]:
    return _results(RunStatus.FAILED, summary={"failed": 1, "collected": 1})


def _no_tests() -> dict[str, Any]:
    return _results(RunStatus.ERROR, [_NO_TESTS], exit_code=5)


def _call(run_pytest_check: Any, results: dict[str, Any], **kwargs: Any) -> str:
    with patch(f"{_PYTEST_TOOL}.check_code_with_pytest", return_value=results):
        reply: str = run_pytest_check(**kwargs)
    return reply


def _addopts_lines(reply: str) -> list[str]:
    return [line for line in reply.splitlines() if line.startswith("addopts (")]


def test_clean_full_pass_shows_no_addopts_line(
    run_pytest_check: Any, tmp_path: Path
) -> None:
    _pyproject(tmp_path, 'addopts = "-n auto"')

    reply = _call(run_pytest_check, _passed())

    assert _addopts_lines(reply) == []


def test_xdist_pass_with_default_m_shows_the_line(
    run_pytest_check: Any, tmp_path: Path
) -> None:
    """Under xdist the report has no deselected count; a default -m may deselect."""
    _pyproject(tmp_path, "addopts = \"-n auto -m 'not slow'\"")

    reply = _call(run_pytest_check, _passed())

    assert _addopts_lines(reply) == [
        f"addopts (pyproject.toml): -n auto -m 'not slow'{_INI_WAY_OUT}"
    ]


def test_pass_with_default_m_without_n_shows_no_line(
    run_pytest_check: Any, tmp_path: Path
) -> None:
    _pyproject(tmp_path, "addopts = \"-m 'not slow'\"")

    reply = _call(run_pytest_check, _passed())

    assert _addopts_lines(reply) == []


def test_deselected_tests_show_the_line(run_pytest_check: Any, tmp_path: Path) -> None:
    _pyproject(tmp_path, "addopts = \"-m 'not slow'\"")

    reply = _call(run_pytest_check, _passed(deselected=1, collected=3))

    assert _addopts_lines(reply) == [
        f"addopts (pyproject.toml): -m 'not slow'{_INI_WAY_OUT}"
    ]


@pytest.mark.parametrize(
    "results",
    [
        _failed(),
        _results(RunStatus.ERROR, ["Usage Error: bad flag"], exit_code=4),
        _results(RunStatus.SUSPICIOUS, summary={"collected": 2}),
    ],
    ids=["failed", "error", "suspicious"],
)
def test_unclean_runs_show_the_line(
    run_pytest_check: Any, tmp_path: Path, results: dict[str, Any]
) -> None:
    _pyproject(tmp_path, 'addopts = "-n auto"')

    reply = _call(run_pytest_check, results)

    assert _addopts_lines(reply) == [f"addopts (pyproject.toml): -n auto{_INI_WAY_OUT}"]


def test_collect_only_without_deselection_shows_no_line(
    run_pytest_check: Any, tmp_path: Path
) -> None:
    _pyproject(tmp_path, 'addopts = "-n auto"')
    results = _results(RunStatus.SUSPICIOUS, summary={"collected": 2})

    reply = _call(run_pytest_check, results, extra_args=["--collect-only"])

    assert _addopts_lines(reply) == []


def test_collect_only_with_deselection_shows_the_line(
    run_pytest_check: Any, tmp_path: Path
) -> None:
    _pyproject(tmp_path, 'addopts = "-n auto"')
    results = _results(RunStatus.SUSPICIOUS, summary={"collected": 3, "deselected": 1})

    reply = _call(run_pytest_check, results, extra_args=["--collect-only"])

    assert _addopts_lines(reply) == [f"addopts (pyproject.toml): -n auto{_INI_WAY_OUT}"]


@pytest.mark.parametrize(
    ("kwargs", "source"),
    [
        ({"markers": ["fast"]}, "markers"),
        ({"extra_args": ["-m", ""]}, "extra_args"),
    ],
    ids=["markers", "empty-extra-args-m"],
)
def test_replaced_m_on_a_pass_shows_the_line(
    run_pytest_check: Any, tmp_path: Path, kwargs: dict[str, Any], source: str
) -> None:
    _pyproject(tmp_path, "addopts = \"-m 'not slow'\"")

    reply = _call(run_pytest_check, _passed(), **kwargs)

    assert _addopts_lines(reply) == [
        f"addopts (pyproject.toml): -m 'not slow' was replaced by {source}"
        f"{_INI_WAY_OUT}"
    ]


def test_pytest_addopts_on_a_failure_gets_its_own_line(
    run_pytest_check: Any, tmp_path: Path
) -> None:
    _pyproject(tmp_path, 'markers = ["slow"]')

    reply = _call(run_pytest_check, _failed(), env_vars={"PYTEST_ADDOPTS": "-x"})

    assert (
        'PYTEST_ADDOPTS: -x — to run without: env_vars={"PYTEST_ADDOPTS": ""}'
        in reply.splitlines()
    )


def test_empty_pytest_addopts_shows_no_line(
    run_pytest_check: Any, tmp_path: Path
) -> None:
    _pyproject(tmp_path, 'markers = ["slow"]')

    reply = _call(run_pytest_check, _failed(), env_vars={"PYTEST_ADDOPTS": ""})

    assert "PYTEST_ADDOPTS:" not in reply


def test_pytest_ini_on_a_failure_shows_the_not_read_note(
    run_pytest_check: Any, tmp_path: Path
) -> None:
    _pyproject(tmp_path, 'addopts = "-n auto"')
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

    reply = _call(run_pytest_check, _failed())

    assert "pytest config is in pytest.ini, not read" in reply.splitlines()
    assert _addopts_lines(reply) == []


def test_unregistered_marker_on_exit_5_gets_hint_before_problems(
    run_pytest_check: Any, tmp_path: Path
) -> None:
    _pyproject(tmp_path, 'markers = ["integration: slow ones", "slow"]')

    reply = _call(run_pytest_check, _no_tests(), markers=["unit"])

    hint = f"{_UNIT_HINT} Registered: integration, slow"
    assert "No Tests Found" in reply
    assert hint in reply.splitlines()
    assert STRICT_SUGGESTION in reply.splitlines()
    assert reply.index(hint) < reply.index(STRICT_SUGGESTION) < reply.index("Problems:")


def test_addopts_m_unit_on_exit_5_gets_line_and_hint(
    run_pytest_check: Any, tmp_path: Path
) -> None:
    _pyproject(tmp_path, 'addopts = "-m unit"')

    reply = _call(run_pytest_check, _no_tests())

    lines = reply.splitlines()
    assert _addopts_lines(reply) == [f"addopts (pyproject.toml): -m unit{_INI_WAY_OUT}"]
    assert f"{_UNIT_HINT} The project config registers none." in lines
    assert lines.index(_addopts_lines(reply)[0]) < lines.index(STRICT_SUGGESTION)


def test_toolkit_unattended_contract_gets_no_marker_hint(
    run_pytest_check: Any, tmp_path: Path
) -> None:
    _pyproject(tmp_path, 'addopts = "--strict-markers"')

    reply = _call(
        run_pytest_check,
        _no_tests(),
        markers=list(UNATTENDED_EXCLUDED_MARKERS),
        extra_args=["-o", "strict_markers=false"],
    )

    assert "No Tests Found" in reply
    assert "not registered in the project config" not in reply
    assert STRICT_SUGGESTION not in reply


def test_exit_4_error_line_after_long_stderr_reaches_the_reply(
    run_pytest_check: Any, tmp_path: Path
) -> None:
    """The real run_tests finds pytest's ERROR: line beyond the 500-char cut."""
    _pyproject(tmp_path, 'markers = ["slow"]')
    warnings = "\n".join(f"PytestWarning: plugin warning {i:03}" for i in range(20))
    assert len(warnings) > 600
    command_result = make_command_result(4, stderr=f"{warnings}\n{_UNKNOWN_UNIT}")

    with patch(f"{_RUNNERS}.execute_command", return_value=command_result):
        reply = run_pytest_check(extra_args=["-m", "unit"])

    lines = reply.splitlines()
    assert _UNKNOWN_UNIT in lines
    assert f"{_UNIT_HINT} Registered: slow" in lines
    assert lines.index(_UNKNOWN_UNIT) < lines.index(f"{_UNIT_HINT} Registered: slow")
