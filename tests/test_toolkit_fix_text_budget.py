"""Budget tests for the toolkit's `ActionResult.fix_text`."""

from pathlib import Path

import pytest
from mcp_coder_utils.toolkit import ActionResult, Finding

from mcp_tools_py.code_checker_mypy.models import MypyMessage, MypyResult
from mcp_tools_py.toolkit_checks import (
    FIX_TEXT_HINT,
    _merge,
    _result_from_findings,
    _run_mypy,
)
from mcp_tools_py.utils.report_budget import TOOL_CHARS, TOOL_LINES
from mcp_tools_py.utils.tool_context import ToolContext


def _pylint_findings(count: int) -> tuple[list[Finding], list[str | None]]:
    findings = [
        Finding(
            key=f"src/m{i}.py|W{i % 50:04d}|message {i % 50}",
            message=f"message {i % 50}",
            path=f"src/m{i}.py",
            rule=f"W{i % 50:04d}",
        )
        for i in range(count)
    ]
    locations: list[str | None] = [f"{f.path}:{i + 1}" for i, f in enumerate(findings)]
    return findings, locations


def test_many_pylint_findings_are_bounded_and_keep_every_finding() -> None:
    findings, locations = _pylint_findings(1500)

    result = _result_from_findings(
        None, findings, "ok", "1500 issue(s).", locations=locations
    )

    assert len(result.fix_text.splitlines()) <= TOOL_LINES
    assert len(result.fix_text) <= TOOL_CHARS
    assert result.fix_text.endswith(FIX_TEXT_HINT)
    assert len(result.findings) == 1500
    assert [f.key for f in result.findings] == [f.key for f in findings]


def test_findings_are_grouped_by_rule_largest_first() -> None:
    findings = [
        Finding(key="1", message="unused", path="src/a.py", rule="W1"),
        Finding(key="2", message="bad", path="tests/b.py", rule="E2"),
        Finding(key="3", message="bad", path="src/c.py", rule="E2"),
    ]

    result = _result_from_findings(
        None, findings, "ok", "3", locations=["src/a.py:4", "tests/b.py:7", None]
    )

    assert result.fix_text.splitlines() == [
        "E2 (2 findings) (src: 1, tests: 1)",
        "- tests/b.py: 7 — bad",
        "- src/c.py — bad",
        "W1 (1 finding) (src: 1)",
        "- src/a.py: 4 — unused",
    ]


def test_merge_of_eight_large_results_represents_every_tool() -> None:
    results = [
        ActionResult(
            status="findings",
            summary=f"tool{i}",
            findings=[Finding(key=f"k{i}", message="m")],
            fix_text="\n".join(
                [f"TOOL{i} header"] + [f"tool{i} line {n}" for n in range(999)]
            ),
        )
        for i in range(8)
    ]

    merged = _merge(results)

    assert len(merged.fix_text.splitlines()) <= TOOL_LINES
    assert len(merged.fix_text) <= TOOL_CHARS
    for i in range(8):
        assert f"TOOL{i} header" in merged.fix_text
    assert len(merged.findings) == 8


def test_pytest_node_ids_render_one_row_per_failing_test() -> None:
    findings = [
        Finding(
            key="tests/test_a.py::test_x",
            message="assert 1 == 2",
            path="tests/test_a.py",
        ),
        Finding(
            key="tests/test_a.py::test_y[1:2]",
            message="ValueError: boom",
            path="tests/test_a.py",
        ),
    ]

    result = _result_from_findings(
        None, findings, "ok", "2 failed", locations=[f.key for f in findings]
    )

    assert result.fix_text.splitlines() == [
        "2 findings (tests: 2)",
        "- tests/test_a.py::test_x — assert 1 == 2",
        "- tests/test_a.py::test_y[1:2] — ValueError: boom",
    ]


def test_fifteen_failing_tests_are_all_named() -> None:
    """Rule-less findings are not capped at LOCATIONS_PER_RULE rows."""
    findings = [
        Finding(
            key=f"tests/test_a.py::test_{i}",
            message="assert False",
            path="tests/test_a.py",
        )
        for i in range(15)
    ]

    result = _result_from_findings(
        None, findings, "ok", "15 failed", locations=[f.key for f in findings]
    )

    for finding in findings:
        assert f"- {finding.key} — assert False" in result.fix_text
    assert "more location" not in result.fix_text


def test_finding_without_path_shows_its_message() -> None:
    finding = Finding(key="pytest|collection|xdist", message="xdist differs")

    result = _result_from_findings(None, [finding], "ok", "1", locations=[None])

    assert result.fix_text.splitlines() == ["1 finding", "- xdist differs"]


def _mypy_errors() -> list[MypyMessage]:
    hint = "\n".join(f"hint {n} " + "x" * 300 for n in range(8))
    big = [
        MypyMessage(
            file="src/big.py",
            line=i,
            column=1,
            severity="error",
            message=f"Error of code{i % 4}",
            code=f"code{i % 4}",
            hint=hint,
        )
        for i in range(1400)
    ]
    spread = [
        MypyMessage(
            file=f"src/m{i}.py",
            line=1,
            column=1,
            severity="error",
            message="Error of code4",
            code="code4",
            hint=hint,
        )
        for i in range(100)
    ]
    return big + spread


def test_mypy_fix_text_is_bounded_and_grouped_by_code(
    tool_context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    errors = _mypy_errors()
    monkeypatch.setattr(
        "mcp_tools_py.toolkit_checks.run_mypy_check",
        lambda *args, **kwargs: MypyResult(return_code=1, messages=errors),
    )
    (Path(tool_context.project_dir) / "src").mkdir()

    result = _run_mypy(tool_context, "quick")

    lines = result.fix_text.splitlines()
    assert len(lines) <= TOOL_LINES
    assert len(result.fix_text) <= TOOL_CHARS
    for code in range(5):
        assert sum(line.startswith(f"code{code} (") for line in lines) == 1
    row = lines.index(
        "- src/big.py: 0, 4, 8, 12, 16, 20, 24, 28, 32, 36 (+340) — Error of code0"
    )
    assert lines[row + 1].startswith("        hint 0 ")
    assert result.fix_text.endswith(FIX_TEXT_HINT)
    assert len(result.findings) == 1500
