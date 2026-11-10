"""Tests for vulture in PythonToolkit's `check` action at the `full` depth."""

from pathlib import Path

import pytest
from mcp_coder_utils.toolkit import ActionRequest, ActionResult

from mcp_tools_py.code_checker_vulture.parsers import parse_vulture_output
from mcp_tools_py.code_checker_vulture.runners import VultureResult
from mcp_tools_py.toolkit import PythonToolkit
from tests.test_toolkit_check import (
    _CLEAN_SRC,
    _patch_full_depth_clean,
    _write_check_project,
)

_OUTPUT = """\
src/mod.py:5: unused function '_x' (60% confidence)
src/mod.py:9: unused function '_y' (60% confidence)
src/mod.py:12: unreachable code after 'return' (100% confidence)
"""


def _run_full(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, result: VultureResult
) -> ActionResult:
    _write_check_project(tmp_path, _CLEAN_SRC)
    _patch_full_depth_clean(monkeypatch)
    monkeypatch.setattr(
        "mcp_tools_py.toolkit_checks.run_vulture_check",
        lambda *args, **kwargs: result,
    )
    request = ActionRequest(
        action="check", depth="full", project_dir=tmp_path, params={}
    )
    return PythonToolkit().run(request)


def _parsed(text: str) -> VultureResult:
    messages, unparsed = parse_vulture_output(text)
    return VultureResult(error=None, messages=messages, unparsed=unparsed)


def test_one_finding_per_message_with_unique_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _run_full(tmp_path, monkeypatch, _parsed(_OUTPUT))

    assert result.status == "findings"
    keys = [finding.key for finding in result.findings]
    assert keys == [
        "vulture|src/mod.py|unused function|_x",
        "vulture|src/mod.py|unused function|_y",
        "vulture|src/mod.py|unreachable code after 'return'|"
        "unreachable code after 'return'",
    ]
    assert result.findings[0].rule == "unused function"
    assert result.findings[0].path == "src/mod.py"
    assert "vulture found 3 issue(s)." in result.summary
    assert "src/mod.py:5" in result.fix_text


def test_keys_do_not_change_when_lines_shift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shifted = _OUTPUT.replace(":5:", ":25:").replace(":9:", ":29:")
    shifted = shifted.replace(":12:", ":32:")
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()

    before = _run_full(tmp_path / "a", monkeypatch, _parsed(_OUTPUT))
    after = _run_full(tmp_path / "b", monkeypatch, _parsed(shifted))

    assert [f.key for f in before.findings] == [f.key for f in after.findings]


def test_timeout_is_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    timed_out = VultureResult("vulture timed out after 5 seconds.", [], [])

    result = _run_full(tmp_path, monkeypatch, timed_out)

    assert result.status == "error"
    assert "vulture timed out after 5 seconds." in result.summary


def test_unparsed_only_output_is_one_line_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unparsed = VultureResult(None, [], ["vulture: error:", "  invalid config"])

    result = _run_full(tmp_path, monkeypatch, unparsed)

    assert result.status == "error"
    assert "vulture: error: invalid config" in result.summary
    assert "\n" not in result.summary
