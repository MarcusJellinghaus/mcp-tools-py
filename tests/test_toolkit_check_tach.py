"""Tests for tach in PythonToolkit's `check` action at the `full` depth."""

from pathlib import Path

import pytest
from mcp_coder_utils.toolkit import ActionRequest, ActionResult

from mcp_tools_py.code_checker_tach.parsers import parse_tach_json
from mcp_tools_py.code_checker_tach.runners import TachResult
from mcp_tools_py.toolkit import PythonToolkit
from tests.test_code_checker_tach.test_parsers import (
    GLOBAL_WARNING_JSON,
    VIOLATIONS_JSON,
)
from tests.test_toolkit_check import (
    _CLEAN_SRC,
    _patch_full_depth_clean,
    _write_check_project,
)


def _run_full(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, result: TachResult
) -> ActionResult:
    _write_check_project(tmp_path, _CLEAN_SRC)
    _patch_full_depth_clean(monkeypatch)
    monkeypatch.setattr(
        "mcp_tools_py.toolkit_checks.run_tach_check",
        lambda *args, **kwargs: result,
    )
    request = ActionRequest(
        action="check", depth="full", project_dir=tmp_path, params={}
    )
    return PythonToolkit().run(request)


def _parsed(text: str, return_code: int) -> TachResult:
    diagnostics = parse_tach_json(text)
    assert diagnostics is not None
    return TachResult(None, return_code, diagnostics, None)


def test_errors_are_findings_and_warnings_are_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parsed = _parsed(VIOLATIONS_JSON, 1)
    first, second, warning = parsed.diagnostics
    diagnostics = [first, second._replace(file="a/w.py"), warning]

    result = _run_full(tmp_path, monkeypatch, parsed._replace(diagnostics=diagnostics))

    assert result.status == "findings"
    assert [finding.key for finding in result.findings] == [
        "tach|a/x.py|a|b",
        "tach|a/w.py|a|b",
    ]
    assert result.findings[0].rule == "UndeclaredDependency"
    assert "tach found 2 issue(s)." in result.summary
    assert "tach: 1 warning(s): DeprecatedDependency: c -> b" in result.summary
    assert "- a/x.py: 1 — " in result.fix_text


def test_warnings_only_is_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run_full(tmp_path, monkeypatch, _parsed(GLOBAL_WARNING_JSON, 0))

    assert result.status == "ok"
    assert result.findings == []
    assert "tach: 1 warning(s): NoFirstPartyImportsFound" in result.summary


def test_unparsed_output_with_exit_zero_is_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _run_full(tmp_path, monkeypatch, TachResult(None, 0, [], "odd\ntext"))

    assert result.status == "ok"
    assert result.findings == []
    assert "tach check passed; unparsed output: odd text" in result.summary


@pytest.mark.parametrize(
    ("raw", "expected_message"),
    [
        ("Failed to parse", "tach check failed:\nFailed to parse"),
        (None, "tach check failed (exit code 1, no output)."),
    ],
)
def test_failed_unparsed_run_is_degraded_finding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    raw: str | None,
    expected_message: str,
) -> None:
    result = _run_full(tmp_path, monkeypatch, TachResult(None, 1, [], raw))

    assert result.status == "findings"
    assert len(result.findings) == 1
    assert result.findings[0].key == "tach|full"
    assert result.findings[0].message == expected_message


def test_timeout_is_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    timed_out = TachResult("tach check timed out after 5 seconds.", -1, [], None)

    result = _run_full(tmp_path, monkeypatch, timed_out)

    assert result.status == "error"
    assert "tach check timed out after 5 seconds." in result.summary
