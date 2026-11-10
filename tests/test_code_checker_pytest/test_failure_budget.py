"""Tests for the per-test budget of the pytest failure prompt."""

from typing import List, Optional

from mcp_tools_py.code_checker_pytest.models import (
    Crash,
    PytestReport,
    StageInfo,
    Summary,
    Test,
    TracebackEntry,
)
from mcp_tools_py.code_checker_pytest.reporting import (
    PYTEST_HINT,
    create_prompt_for_failed_tests,
)
from mcp_tools_py.utils.report_budget import TOOL_LINES

UNDETAILED = "Failed tests without details"


def _failed_test(
    nodeid: str,
    longrepr: Optional[str] = None,
    stdout: Optional[str] = None,
) -> Test:
    call = StageInfo(
        duration=0.1,
        outcome="failed",
        crash=Crash(path="tests/t.py", lineno=3, message=f"AssertionError: {nodeid}"),
        traceback=[TracebackEntry(path="tests/t.py", lineno=3, message="frame")],
        stdout=stdout,
        longrepr=longrepr,
    )
    return Test(nodeid=nodeid, lineno=1, keywords=[], outcome="failed", call=call)


def _report(tests: List[Test]) -> PytestReport:
    return PytestReport(
        created=0.0,
        duration=1.0,
        exitcode=1,
        root="/tmp",
        environment={},
        summary=Summary(collected=len(tests), total=len(tests), failed=len(tests)),
        tests=tests,
    )


def _fence_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.lstrip().startswith("```"))


def test_many_failures_stay_within_budget_and_name_every_test() -> None:
    stdout = "\n".join(f"print line {i}" for i in range(400))
    first = _failed_test(
        "tests/t.py::test_0", longrepr="E   assert 1 == 2", stdout=stdout
    )
    tests = [first] + [_failed_test(f"tests/t.py::test_{i}") for i in range(1, 15)]

    prompt = create_prompt_for_failed_tests(_report(tests))

    assert prompt is not None
    assert len(prompt.splitlines()) <= TOOL_LINES
    assert prompt.index("Longrepr:") < prompt.index("Stdout:")
    for test in tests:
        assert test.nodeid in prompt
    assert UNDETAILED in prompt
    assert _fence_count(prompt) % 2 == 0
    assert prompt.endswith(PYTEST_HINT)


def test_longrepr_replaces_traceback() -> None:
    with_longrepr = create_prompt_for_failed_tests(
        _report([_failed_test("tests/t.py::test_a", longrepr="E   assert 0")])
    )
    without_longrepr = create_prompt_for_failed_tests(
        _report([_failed_test("tests/t.py::test_b")])
    )

    assert with_longrepr is not None and without_longrepr is not None
    assert "Traceback:" not in with_longrepr
    assert "Longrepr:" in with_longrepr
    assert "Traceback:" in without_longrepr
    assert "tests/t.py:3 - frame" in without_longrepr


def test_single_failure_has_no_undetailed_list() -> None:
    prompt = create_prompt_for_failed_tests(_report([_failed_test("tests/t.py::t")]))

    assert prompt is not None
    assert UNDETAILED not in prompt
    assert prompt.endswith(PYTEST_HINT)


def test_long_longrepr_keeps_its_last_line() -> None:
    lines = [f"    frame line {i}" for i in range(999)] + ["E   assert 41 == 42"]
    prompt = create_prompt_for_failed_tests(
        _report([_failed_test("tests/t.py::t", longrepr="\n".join(lines))])
    )

    assert prompt is not None
    assert "E   assert 41 == 42" in prompt
    assert "omitted" in prompt
    assert len(prompt.splitlines()) <= TOOL_LINES
    assert _fence_count(prompt) % 2 == 0


def test_max_failures_limits_detailed_tests() -> None:
    tests = [_failed_test(f"tests/t.py::test_{i}") for i in range(5)]

    prompt = create_prompt_for_failed_tests(_report(tests), max_failures=2)

    assert prompt is not None
    assert prompt.count("Test ID:") == 2
    assert f"{UNDETAILED} (3):" in prompt
    assert "tests/t.py::test_4" in prompt


def test_undetailed_list_is_capped() -> None:
    tests = [_failed_test(f"tests/t.py::test_{i}") for i in range(70)]

    prompt = create_prompt_for_failed_tests(_report(tests), max_failures=0)

    assert prompt is not None
    assert f"{UNDETAILED} (70):" in prompt
    assert "tests/t.py::test_49" in prompt
    assert "tests/t.py::test_50\n" not in prompt
    assert "... and 20 more" in prompt


def test_print_output_can_be_excluded() -> None:
    test = _failed_test("tests/t.py::t", stdout="hello from stdout")

    prompt = create_prompt_for_failed_tests(_report([test]), include_print_output=False)

    assert prompt is not None
    assert "hello from stdout" not in prompt


def test_sections_dropped_after_a_long_longrepr_are_named() -> None:
    longrepr = "\n".join(f"    frame {i}" for i in range(1000)) + "\nE   assert 0"
    test = _failed_test(
        "tests/t.py::test_0",
        longrepr=longrepr,
        stdout="\n".join(f"print {i}" for i in range(40)),
    )
    assert test.call is not None
    test.call.stderr = "warn 1\nwarn 2"

    prompt = create_prompt_for_failed_tests(_report([test]))

    assert prompt is not None
    assert "E   assert 0" in prompt
    assert "Not shown, budget used up: Stderr (2 lines), Stdout (40 lines)" in prompt
    assert len(prompt.splitlines()) <= TOOL_LINES
