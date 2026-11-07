"""Tests for how PythonToolkit's `check` action maps a mypy result."""

from pathlib import Path

import pytest
from mcp_coder_utils.toolkit import ActionRequest, ActionResult

from mcp_tools_py.code_checker_mypy.models import MypyMessage, MypyResult
from mcp_tools_py.toolkit import PythonToolkit

_NO_ISSUES = "mypy found no issues."
_EARLY_STOP = "mypy exited with code 2, more errors may appear after these are fixed"

_ERROR = MypyMessage(
    file="src/mod.py",
    line=3,
    column=1,
    severity="error",
    message="Bad return type",
    code="return-value",
)
_NOTE = MypyMessage(
    file="src/mod.py",
    line=5,
    column=1,
    severity="note",
    message='Revealed type is "int"',
)
_WARNING = MypyMessage(
    file="src/mod.py",
    line=7,
    column=1,
    severity="warning",
    message="Unused section",
)
_RAW = "mypy raw text"
_NOTE_RAW = 'src/mod.py:5:1: note: Revealed type is "int"'
_STDERR = "first warning line\nsecond warning line"
_STDERR_ONE_LINE = "Warning from mypy: first warning line second warning line"


def _run_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mypy_result: MypyResult
) -> ActionResult:
    """Run the quick `check` action with mypy returning `mypy_result`.

    Returns:
        The ActionResult after going through `_merge`.
    """
    monkeypatch.setattr(
        "mcp_tools_py.toolkit_checks.run_mypy_check",
        lambda *args, **kwargs: mypy_result,
    )
    (tmp_path / "src").mkdir()
    request = ActionRequest(
        action="check", depth="quick", project_dir=tmp_path, params={}
    )
    return PythonToolkit().run(request)


class TestStatusSummaryRaw:
    """Status, summary and raw for each kind of mypy run."""

    @pytest.mark.parametrize(
        ("mypy_result", "status", "summary", "raw"),
        [
            pytest.param(
                MypyResult(return_code=0, messages=[]),
                "ok",
                _NO_ISSUES,
                "",
                id="clean",
            ),
            pytest.param(
                MypyResult(return_code=0, messages=[], raw_output=_RAW, stderr=_STDERR),
                "ok",
                f"{_NO_ISSUES} {_STDERR_ONE_LINE}",
                _RAW,
                id="rc0-stderr",
            ),
            pytest.param(
                MypyResult(return_code=1, messages=[_NOTE], raw_output=_NOTE_RAW),
                "ok",
                _NO_ISSUES,
                _NOTE_RAW,
                id="rc1-notes-only",
            ),
            pytest.param(
                MypyResult(
                    return_code=1,
                    messages=[_NOTE],
                    raw_output=_NOTE_RAW,
                    stderr=_STDERR,
                ),
                "ok",
                f"{_NO_ISSUES} {_STDERR_ONE_LINE}",
                _NOTE_RAW,
                id="rc1-notes-only-stderr",
            ),
            pytest.param(
                MypyResult(return_code=1, messages=[_ERROR], raw_output=_RAW),
                "findings",
                "mypy found 1 issue(s).",
                _RAW,
                id="rc1-errors",
            ),
            pytest.param(
                MypyResult(
                    return_code=1, messages=[_ERROR], raw_output=_RAW, stderr=_STDERR
                ),
                "findings",
                f"mypy found 1 issue(s). {_STDERR_ONE_LINE}",
                _RAW,
                id="rc1-errors-stderr",
            ),
            pytest.param(
                MypyResult(return_code=2, messages=[_ERROR], raw_output=_RAW),
                "findings",
                f"mypy found 1 issue(s). {_EARLY_STOP}",
                _RAW,
                id="rc2-errors",
            ),
            pytest.param(
                MypyResult(
                    return_code=2, messages=[_ERROR], raw_output=_RAW, stderr=_STDERR
                ),
                "findings",
                f"mypy found 1 issue(s). {_EARLY_STOP} {_STDERR_ONE_LINE}",
                _RAW,
                id="rc2-errors-stderr",
            ),
            pytest.param(
                MypyResult(
                    return_code=2,
                    messages=[_ERROR],
                    raw_output=_RAW,
                    stderr="plugin.py: INTERNAL ERROR\nTraceback",
                ),
                "findings",
                f"mypy found 1 issue(s). {_EARLY_STOP} "
                "Warning from mypy: plugin.py: INTERNAL ERROR Traceback",
                _RAW,
                id="rc2-plugin-crash",
            ),
            pytest.param(
                MypyResult(
                    return_code=3,
                    messages=[],
                    error="mypy exited with code 3: first line\nsecond line",
                    raw_output=_RAW,
                ),
                "error",
                "mypy exited with code 3: first line second line",
                _RAW,
                id="new-failure",
            ),
        ],
    )
    def test_run_kinds(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mypy_result: MypyResult,
        status: str,
        summary: str,
        raw: str,
    ) -> None:
        result = _run_check(tmp_path, monkeypatch, mypy_result)

        assert result.status == status
        assert result.summary == summary
        assert result.raw == raw
        assert "\n" not in result.summary

    def test_timeout_keeps_newlines_and_advice(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        error = (
            "mypy timed out after 5 seconds\n"
            "Retry with a larger timeout_seconds (this run used 5)."
        )

        result = _run_check(
            tmp_path,
            monkeypatch,
            MypyResult(return_code=1, messages=[], error=error),
        )

        assert result.status == "error"
        assert result.summary == error
        assert result.raw == ""


class TestFindings:
    """Which messages become findings, and what the findings hold."""

    def test_notes_are_excluded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result = _run_check(
            tmp_path,
            monkeypatch,
            MypyResult(return_code=1, messages=[_ERROR, _NOTE]),
        )

        assert [finding.message for finding in result.findings] == ["Bad return type"]
        assert "1 issue(s)" in result.summary
        assert "Revealed type" not in result.fix_text

    def test_warning_severity_is_not_a_finding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result = _run_check(
            tmp_path,
            monkeypatch,
            MypyResult(return_code=1, messages=[_ERROR, _WARNING]),
        )

        assert [finding.message for finding in result.findings] == ["Bad return type"]
        assert "1 issue(s)" in result.summary
        assert "Unused section" not in result.fix_text

    def test_finding_message_and_key_are_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hinted = _ERROR._replace(hint="See the docs")

        result = _run_check(
            tmp_path, monkeypatch, MypyResult(return_code=1, messages=[hinted])
        )

        finding = result.findings[0]
        assert finding.message == "Bad return type"
        assert finding.key == "src/mod.py|return-value|Bad return type"


class TestHints:
    """Hint lines in fix_text, after the result has gone through `_merge`."""

    def test_hints_sit_under_their_own_bullet(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hinted = _ERROR._replace(hint="First hint\nSecond hint")
        plain = _ERROR._replace(message="Other error", code="arg-type")

        result = _run_check(
            tmp_path, monkeypatch, MypyResult(return_code=1, messages=[hinted, plain])
        )

        assert result.fix_text.splitlines() == [
            "- src/mod.py:3: return-value: Bad return type",
            "    First hint",
            "    Second hint",
            "- src/mod.py:3: arg-type: Other error",
        ]

    def test_negative_line_has_no_line_number(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        unlocated = _ERROR._replace(line=-1)

        result = _run_check(
            tmp_path, monkeypatch, MypyResult(return_code=1, messages=[unlocated])
        )

        assert result.fix_text.splitlines() == [
            "- src/mod.py: return-value: Bad return type",
        ]

    def test_hint_keeps_its_own_indentation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hinted = _ERROR._replace(
            hint="Source file found twice:\n  pkg.mod: first\n  mod: second"
        )

        result = _run_check(
            tmp_path, monkeypatch, MypyResult(return_code=2, messages=[hinted])
        )

        assert result.fix_text.splitlines()[1:] == [
            "    Source file found twice:",
            "      pkg.mod: first",
            "      mod: second",
        ]
