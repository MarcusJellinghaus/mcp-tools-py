"""Budget tests for pytest passing output, --collect-only, problems and coverage."""

from pathlib import Path
from typing import Any, Iterator, List
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.checker_tools.pytest_tool import DIGEST_HINT
from mcp_tools_py.code_checker_pytest.models import (
    Collector,
    CollectorResult,
    Crash,
    PytestReport,
    StageInfo,
    Summary,
    Test,
)
from mcp_tools_py.code_checker_pytest.reporting import (
    SHOW_OUTPUT_HINT,
    create_prompt_for_passing_output,
)
from mcp_tools_py.code_checker_pytest.verdict import (
    COLLECT_HINT,
    PROBLEMS_HINT,
    RunStatus,
    cap_problems,
    format_collect_only_text,
)
from mcp_tools_py.utils.report_budget import (
    GUARD_CHARS,
    GUARD_HINT,
    GUARD_LINES,
    TOOL_LINES,
)
from tests._pytest_results import make_pytest_results
from tests.conftest import make_environment_info
from tests.test_code_checker_pytest._coverage_report import _file
from tests.test_code_checker_pytest._coverage_report import _report as _coverage_report

_PYTEST_TOOL = "mcp_tools_py.checker_tools.pytest_tool"
_COVERAGE_DATA: dict[str, Any] = {
    "totals": {"percent_covered": 50.0, "num_statements": 4, "missing_lines": 2},
    "files": {},
}


def _report(
    tests: List[Test], summary: Summary, collectors: List[Collector] | None = None
) -> PytestReport:
    return PytestReport(
        created=0.0,
        duration=1.0,
        exitcode=0,
        root="/tmp",
        environment={},
        summary=summary,
        tests=tests,
        collectors=collectors,
    )


def _fence_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.lstrip().startswith("```"))


def test_passing_output_stays_within_budget() -> None:
    stdout = "\n".join(f"print line {j}" for j in range(50))
    tests = [
        Test(
            nodeid=f"tests/t.py::test_{i}",
            lineno=1,
            keywords=[],
            outcome="passed",
            call=StageInfo(duration=0.1, outcome="passed", stdout=stdout),
        )
        for i in range(50)
    ]
    report = _report(tests, Summary(collected=50, total=50, passed=50))

    text = create_prompt_for_passing_output(report)

    assert len(text.splitlines()) <= TOOL_LINES
    assert _fence_count(text) % 2 == 0
    assert text.endswith(SHOW_OUTPUT_HINT)


def test_collect_only_stays_within_budget() -> None:
    ids = [f"tests/test_x.py::test_{n}" for n in range(2000)]
    collector = Collector(
        nodeid="tests/test_x.py",
        outcome="passed",
        result=[CollectorResult(nodeid=nodeid, type="Function") for nodeid in ids],
    )
    report = _report([], Summary(collected=2000, total=0), [collector])

    text = format_collect_only_text(report)

    assert len(text.splitlines()) <= TOOL_LINES
    assert text.splitlines()[0].startswith("Collected 2000 tests")
    assert text.endswith(COLLECT_HINT)


def test_cap_problems_stays_within_budget() -> None:
    problems = [f"problem {i}" for i in range(1000)]

    text = cap_problems(problems)

    assert len(text.splitlines()) <= TOOL_LINES
    assert text.endswith(PROBLEMS_HINT)


def _failed(i: int) -> Test:
    call = StageInfo(
        duration=0.1,
        outcome="failed",
        crash=Crash(path="tests/t.py", lineno=3, message=f"AssertionError {i}"),
        longrepr="\n".join(f"    frame {j}" for j in range(60)) + "\nE   assert 0",
        stdout="\n".join(f"print {j}" for j in range(60)),
    )
    return Test(
        nodeid=f"tests/t.py::test_{i}",
        lineno=1,
        keywords=[],
        outcome="failed",
        call=call,
    )


@pytest.fixture
def run_pytest_check(tmp_path: Path, all_modules_importable: Any) -> Iterator[Any]:
    """run_pytest_check over tmp_path, with pytest-cov reported installed."""
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
    info = make_environment_info(distributions={"pytest-cov": "7.1.0"})
    with (
        patch(f"{_PYTEST_TOOL}.get_environment_info", return_value=info),
        patch(f"{_PYTEST_TOOL}.read_fail_under", return_value=0.0),
    ):
        yield tools["run_pytest_check"]


def test_coverage_digest_and_failures_fit_under_the_guard(
    run_pytest_check: Any,
) -> None:
    failed = [_failed(i) for i in range(15)]
    report = _report(failed, Summary(collected=15, total=15, failed=15))
    digest = "\n".join(f"DIGEST line {i}" for i in range(120))
    with (
        patch(f"{_PYTEST_TOOL}.check_code_with_pytest") as mock_check,
        patch(f"{_PYTEST_TOOL}.read_coverage_report", return_value=_COVERAGE_DATA),
        patch(f"{_PYTEST_TOOL}.format_coverage_digest", return_value=digest),
    ):
        mock_check.return_value = make_pytest_results(
            RunStatus.FAILED,
            summary={"failed": 15, "collected": 15},
            test_results=report,
        )
        result = run_pytest_check(coverage=True, coverage_source=["src"])

    assert len(result.splitlines()) < GUARD_LINES
    assert GUARD_HINT not in result
    assert "Failed tests without details" in result
    assert "tests/t.py::test_14" in result
    assert digest in result


def _wide_failed(i: int) -> Test:
    longrepr = "\n".join(f"    frame {j} " + "x" * 200 for j in range(200))
    call = StageInfo(
        duration=0.1,
        outcome="failed",
        crash=Crash(path="tests/t.py", lineno=3, message=f"AssertionError {i}"),
        longrepr=f"{longrepr}\nE   assert {i} == -1",
    )
    return Test(
        nodeid=f"tests/t.py::test_{i}",
        lineno=1,
        keywords=[],
        outcome="failed",
        call=call,
    )


def test_large_digest_and_long_failures_are_not_cut_by_the_guard(
    run_pytest_check: Any,
) -> None:
    """A large max_modules digest is bounded itself; failures keep their details."""
    functions = {f"func_{k}": list(range(k * 20, k * 20 + 15, 2)) for k in range(6)}
    files = {
        f"src/package_{n}/very_long_module_name_{n}.py": _file(
            400, list(range(1, 300, 2)), functions
        )
        for n in range(200)
    }
    failed = [_wide_failed(i) for i in range(3)]
    report = _report(failed, Summary(collected=3, total=3, failed=3))
    with (
        patch(f"{_PYTEST_TOOL}.check_code_with_pytest") as mock_check,
        patch(
            f"{_PYTEST_TOOL}.read_coverage_report", return_value=_coverage_report(files)
        ),
    ):
        mock_check.return_value = make_pytest_results(
            RunStatus.FAILED,
            summary={"failed": 3, "collected": 3},
            test_results=report,
        )
        result = run_pytest_check(
            coverage=True, coverage_source=["src"], max_modules=200
        )

    assert GUARD_HINT not in result
    assert len(result.splitlines()) < GUARD_LINES
    assert len(result) < GUARD_CHARS
    for i in range(3):
        assert f"E   assert {i} == -1" in result
    assert DIGEST_HINT in result
