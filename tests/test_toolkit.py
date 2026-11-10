"""Tests for PythonToolkit: describe(), prompt_fragments(), and the generic helpers.

Action-specific tests live in tests/test_toolkit_*.py, split by action:
test_toolkit_test.py, test_toolkit_format.py, test_toolkit_check.py,
test_toolkit_verify.py.
"""

import pytest
from mcp_coder_utils.toolkit import ActionResult, Finding

from mcp_tools_py.toolkit import UNATTENDED_EXCLUDED_MARKERS, PythonToolkit
from mcp_tools_py.toolkit_checks import _merge, _result_from_findings

_EXPECTED_ACTIONS = {
    "format": ["apply", "check"],
    "check": ["quick", "standard", "full"],
    "test": ["quick", "standard", "unattended", "full"],
}
_EXPECTED_PERMISSIONS = {
    "format": {
        "apply": ["mcp__mcp-tools-py__run_format_code"],
        "check": ["mcp__mcp-tools-py__run_format_code"],
    },
    "check": {
        "quick": ["mcp__mcp-tools-py__run_mypy_check"],
        "standard": [
            "mcp__mcp-tools-py__run_mypy_check",
            "mcp__mcp-tools-py__run_pylint_check",
        ],
        "full": [
            "mcp__mcp-tools-py__run_mypy_check",
            "mcp__mcp-tools-py__run_pylint_check",
            "mcp__mcp-tools-py__run_vulture_check",
            "mcp__mcp-tools-py__run_lint_imports_check",
            "mcp__mcp-tools-py__run_tach_check",
            "mcp__mcp-tools-py__run_ruff_check",
            "mcp__mcp-tools-py__run_bandit_check",
            "mcp__mcp-tools-py__run_deptry_check",
        ],
    },
    "test": {
        "quick": ["mcp__mcp-tools-py__run_pytest_check"],
        "standard": ["mcp__mcp-tools-py__run_pytest_check"],
        "unattended": ["mcp__mcp-tools-py__run_pytest_check"],
        "full": ["mcp__mcp-tools-py__run_pytest_check"],
    },
}


class TestDescribe:
    """describe() must return the final, complete ToolkitInfo."""

    def test_returns_exact_toolkit_info(self) -> None:
        info = PythonToolkit().describe()

        assert info.actions == _EXPECTED_ACTIONS
        assert info.params_schema == {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }
        assert info.llm_permissions == _EXPECTED_PERMISSIONS


class TestPromptFragments:
    """prompt_fragments() must contribute the five Python-specific slots."""

    def test_contains_required_keys(self) -> None:
        fragments = PythonToolkit().prompt_fragments()

        assert set(fragments) == {
            "language_context",
            "check_instructions",
            "check_instructions.unattended",
            "fix.check",
            "fix.test",
        }
        assert fragments["language_context"]
        assert fragments["check_instructions"]

    def test_unattended_instructions(self) -> None:
        text = PythonToolkit().prompt_fragments()["check_instructions.unattended"]

        for marker in UNATTENDED_EXCLUDED_MARKERS:
            assert marker in text
        assert 'extra_args=["-o", "strict_markers=false"]' in text
        assert "external" not in text

    def test_fix_check_has_no_mypy_output_placeholder(self) -> None:
        fragments = PythonToolkit().prompt_fragments()

        assert "[mypy_output]" not in fragments["fix.check"]
        assert "Mypy output" not in fragments["fix.check"]
        assert "findings" in fragments["fix.check"]

    def test_fix_check_is_checker_agnostic(self) -> None:
        text = PythonToolkit().prompt_fragments()["fix.check"]

        assert "mypy" not in text.lower()

    def test_fix_test_reruns_only_failing_tests(self) -> None:
        text = PythonToolkit().prompt_fragments()["fix.test"]

        assert text
        assert "[" not in text
        assert "failing tests" in text
        assert "not the whole suite" in text


class TestResultFromFindings:
    """Unit tests for the one generic helper this step needs."""

    def test_error_wins(self) -> None:
        result = _result_from_findings(
            error="boom", findings=[], ok_summary="ok", findings_summary="bad"
        )

        assert result.status == "error"
        assert result.summary == "boom"
        assert result.findings == []

    def test_findings_build_fix_text(self) -> None:
        finding = Finding(key="a", message="broke", path="a.py", rule="E1")

        result = _result_from_findings(
            error=None,
            findings=[finding],
            ok_summary="ok",
            findings_summary="1 issue",
        )

        assert result.status == "findings"
        assert result.summary == "1 issue"
        assert result.findings == [finding]
        assert "a.py" in result.fix_text
        assert "broke" in result.fix_text

    def test_locations_replace_paths_in_fix_text(self) -> None:
        located = Finding(key="a", message="broke", path="a.py", rule="E1")
        unlocated = Finding(key="b", message="also", path="b.py", rule="E2")

        result = _result_from_findings(
            error=None,
            findings=[located, unlocated],
            ok_summary="ok",
            findings_summary="2 issues",
            locations=["a.py:12", None],
        )

        assert result.fix_text.splitlines() == [
            "E1 (1 finding) ((root): 1)",
            "- a.py: 12 — broke",
            "E2 (1 finding) ((root): 1)",
            "- b.py — also",
        ]

    def test_no_error_no_findings_is_ok(self) -> None:
        result = _result_from_findings(
            error=None, findings=[], ok_summary="all good", findings_summary="bad"
        )

        assert result.status == "ok"
        assert result.summary == "all good"
        assert result.findings == []


class TestMerge:
    """Unit tests for `_merge`'s worst-status-wins semantics."""

    def test_ok_and_ok_is_ok(self) -> None:
        merged = _merge(
            [
                ActionResult(status="ok", summary="a"),
                ActionResult(status="ok", summary="b"),
            ]
        )

        assert merged.status == "ok"
        assert merged.findings == []

    def test_ok_and_findings_is_findings_with_concatenated_findings(self) -> None:
        finding = Finding(key="f1", message="broke", path="a.py")
        merged = _merge(
            [
                ActionResult(status="ok", summary="a"),
                ActionResult(status="findings", summary="b", findings=[finding]),
            ]
        )

        assert merged.status == "findings"
        assert merged.findings == [finding]
        assert merged.fix_text == "1 finding ((root): 1)\n- a.py — broke"

    def test_custom_fix_text_is_kept_exactly(self) -> None:
        finding = Finding(key="f1", message="broke", path="a.py")
        merged = _merge(
            [
                ActionResult(
                    status="findings",
                    summary="a",
                    findings=[finding],
                    fix_text="custom\n  report",
                ),
            ]
        )

        assert merged.fix_text == "custom\n  report"

    def test_findings_without_fix_text_are_rendered(self) -> None:
        first = Finding(key="f1", message="broke", path="a.py", rule="E1")
        second = Finding(key="f2", message="also broke")
        merged = _merge(
            [
                ActionResult(status="findings", summary="a", findings=[first, second]),
            ]
        )

        assert merged.fix_text.splitlines() == [
            "E1 (1 finding) ((root): 1)",
            "- a.py — broke",
            "1 finding",
            "- also broke",
        ]

    def test_ok_results_add_no_blank_lines(self) -> None:
        finding = Finding(key="f1", message="broke", path="a.py")
        merged = _merge(
            [
                ActionResult(status="ok", summary="a"),
                ActionResult(status="findings", summary="b", findings=[finding]),
                ActionResult(status="ok", summary="c"),
            ]
        )

        assert merged.fix_text == "1 finding ((root): 1)\n- a.py — broke"

    def test_custom_and_rebuilt_text_are_joined_in_result_order(self) -> None:
        finding = Finding(key="f1", message="broke", path="a.py")
        custom = Finding(key="f2", message="ignored")
        merged = _merge(
            [
                ActionResult(status="findings", summary="a", findings=[finding]),
                ActionResult(
                    status="findings",
                    summary="b",
                    findings=[custom],
                    fix_text="custom report",
                ),
            ]
        )

        assert merged.fix_text == "1 finding ((root): 1)\n- a.py — broke\ncustom report"

    def test_all_ok_has_empty_fix_text(self) -> None:
        merged = _merge(
            [
                ActionResult(status="ok", summary="a"),
                ActionResult(status="ok", summary="b"),
            ]
        )

        assert merged.fix_text == ""

    def test_findings_and_error_is_error(self) -> None:
        finding = Finding(key="f1", message="broke", path="a.py")
        merged = _merge(
            [
                ActionResult(status="findings", summary="a", findings=[finding]),
                ActionResult(status="error", summary="boom"),
            ]
        )

        assert merged.status == "error"

    def test_skipped_with_nothing_worse_stays_at_the_worse_of_the_two(self) -> None:
        merged_ok = _merge(
            [
                ActionResult(status="skipped", summary="a"),
                ActionResult(status="ok", summary="b"),
            ]
        )
        finding = Finding(key="f1", message="broke", path="a.py")
        merged_findings = _merge(
            [
                ActionResult(status="skipped", summary="a"),
                ActionResult(status="findings", summary="b", findings=[finding]),
            ]
        )

        assert merged_ok.status == "ok"
        assert merged_findings.status == "findings"


class TestActionResultValidation:
    """ActionResult's own status-validation rules, exercised directly."""

    def test_unknown_status_raises(self) -> None:
        with pytest.raises(ValueError):
            ActionResult(status="bogus", summary="x")  # type: ignore[arg-type]

    def test_findings_status_with_no_findings_raises(self) -> None:
        with pytest.raises(ValueError):
            ActionResult(status="findings", summary="x", findings=[])

    def test_ok_status_with_findings_raises(self) -> None:
        finding = Finding(key="f1", message="broke")
        with pytest.raises(ValueError):
            ActionResult(status="ok", summary="x", findings=[finding])

    def test_skipped_status_with_findings_raises(self) -> None:
        finding = Finding(key="f1", message="broke")
        with pytest.raises(ValueError):
            ActionResult(status="skipped", summary="x", findings=[finding])
