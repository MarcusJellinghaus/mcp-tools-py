"""Tests for failing-test blocks: stage loop, xdist header, logs and --show-capture."""

import pytest

from mcp_tools_py.code_checker_pytest.models import (
    Crash,
    Log,
    LogRecord,
    PytestReport,
    StageInfo,
    Summary,
    Test,
)
from mcp_tools_py.code_checker_pytest.reporting import (
    ALL_CAPTURE,
    NO_CAPTURED_OUTPUT_NOTE,
    Sections,
    capture_kinds,
    create_prompt_for_failed_tests,
    create_prompt_for_passing_output,
)
from mcp_tools_py.code_checker_pytest.utils import SHOW_OUTPUT_NOTE
from mcp_tools_py.utils.report_budget import TOOL_LINES

BIG = "\n".join(f"print line {i}" for i in range(2000))


def _record(msg: str, levelname: str = "WARNING") -> LogRecord:
    """Build a record from logger "app" at mod.py:12."""
    return LogRecord(
        name="app",
        msg=msg,
        args=None,
        levelname=levelname,
        levelno=30,
        pathname="/src/mod.py",
        filename="mod.py",
        module="mod",
        exc_info=None,
        exc_text=None,
        stack_info=None,
        lineno=12,
        funcName="check",
        created=0.0,
        msecs=0.0,
        relativeCreated=0.0,
        thread=1,
        threadName="MainThread",
        processName="MainProcess",
        process=1,
    )


def _stage(outcome: str = "passed", **kwargs: object) -> StageInfo:
    return StageInfo(duration=0.1, outcome=outcome, **kwargs)  # type: ignore[arg-type]


def _failed_call(**kwargs: object) -> StageInfo:
    return _stage(
        "failed",
        crash=Crash(path="tests/t.py", lineno=3, message="AssertionError: boom"),
        longrepr="E   assert 1 == 2",
        **kwargs,
    )


def _test(
    outcome: str = "failed",
    setup: StageInfo | None = None,
    call: StageInfo | None = None,
    teardown: StageInfo | None = None,
) -> Test:
    return Test(
        nodeid="tests/t.py::test_x",
        lineno=1,
        keywords=[],
        outcome=outcome,
        setup=setup if setup is not None else _stage(),
        call=call,
        teardown=teardown if teardown is not None else _stage(),
    )


def _report(tests: list[Test]) -> PytestReport:
    return PytestReport(
        created=0.0,
        duration=1.0,
        exitcode=1,
        root="/tmp",
        environment={},
        summary=Summary(collected=len(tests), total=len(tests), failed=len(tests)),
        tests=tests,
    )


def _prompt(test: Test, capture: frozenset[str] = ALL_CAPTURE) -> str:
    prompt = create_prompt_for_failed_tests(_report([test]), capture=capture)
    assert prompt is not None
    return prompt


class TestStageOrder:
    """Failure info of every stage comes before any captured output."""

    def test_large_setup_stdout_does_not_hide_call_longrepr(self) -> None:
        test = _test(setup=_stage(stdout=BIG), call=_failed_call())

        prompt = _prompt(test)

        assert "  Longrepr:\n```\nE   assert 1 == 2\n```" in prompt
        assert "print line 0\n" not in prompt
        assert "Test Setup Stdout" in prompt
        assert len(prompt.splitlines()) <= TOOL_LINES

    def test_large_call_stdout_does_not_hide_teardown_longrepr(self) -> None:
        test = _test(
            outcome="error",
            call=_stage(stdout=BIG),
            teardown=_stage("failed", longrepr="E   teardown broke"),
        )

        prompt = _prompt(test)

        assert "  Test Teardown Longrepr:\n```\nE   teardown broke\n```" in prompt
        assert prompt.index("Test Teardown Longrepr") < prompt.index("Stdout")
        assert len(prompt.splitlines()) <= TOOL_LINES


class TestTeardown:
    """Teardown failures render under the Test Teardown prefix."""

    def test_teardown_failure_is_shown(self) -> None:
        teardown = _stage(
            "failed",
            crash=Crash(path="tests/t.py", lineno=9, message="RuntimeError: td"),
            longrepr="E   RuntimeError: td",
        )
        test = _test(outcome="error", call=_stage(), teardown=teardown)

        prompt = _prompt(test)

        assert "  Test Teardown Outcome: failed" in prompt
        assert "Test Teardown Crash Error Message: RuntimeError: td" in prompt
        assert "  Test Teardown Longrepr:\n```\nE   RuntimeError: td\n```" in prompt

    def test_setup_failure_keeps_its_labels(self) -> None:
        setup = _stage(
            "failed",
            crash=Crash(path="tests/t.py", lineno=5, message="fixture broke"),
            longrepr="E   fixture broke",
            stdout="setup print",
        )
        test = _test(outcome="error", setup=setup)

        prompt = _prompt(test)

        assert "  Test Setup Outcome: failed" in prompt
        assert "  Test Setup Longrepr:\n```\nE   fixture broke\n```" in prompt
        assert "  Test Setup Stdout:\n```\nsetup print\n```" in prompt


class TestXdistHeader:
    """The [gwN] header of a stage longrepr is stripped."""

    def test_passed_stage_with_header_only_has_no_section(self) -> None:
        test = _test(
            setup=_stage(longrepr="[gw0] win32 -- Python 3.11"),
            call=_failed_call(),
            teardown=_stage(longrepr="[gw0] win32 -- Python 3.11"),
        )

        prompt = _prompt(test)

        assert "[gw0]" not in prompt
        assert "Test Setup Longrepr" not in prompt
        assert "Test Teardown Longrepr" not in prompt

    def test_failed_stage_header_is_removed(self) -> None:
        call = _failed_call()
        call.longrepr = "[gw3] linux -- Python 3.12\nE   assert 1 == 2"

        prompt = _prompt(_test(call=call))

        assert "[gw3]" not in prompt
        assert "  Longrepr:\n```\nE   assert 1 == 2\n```" in prompt

    def test_passed_call_with_header_has_no_longrepr(self) -> None:
        teardown = _stage("failed", longrepr="E   td")
        call = _stage(longrepr="[gw1] linux -- Python 3.12")

        prompt = _prompt(_test(outcome="error", call=call, teardown=teardown))

        assert "  Longrepr:" not in prompt
        assert "Test Teardown Longrepr" in prompt


class TestLogs:
    """Log records appear per stage."""

    def test_call_logs_shown_as_log(self) -> None:
        call = _failed_call(log=Log(logs=[_record("disk low")]))

        prompt = _prompt(_test(call=call))

        assert "  Log:\n```\nWARNING  app:mod.py:12 disk low\n```" in prompt

    def test_setup_and_teardown_logs_use_prefix(self) -> None:
        test = _test(
            setup=_stage(log=Log(logs=[_record("in setup", "INFO")])),
            call=_failed_call(),
            teardown=_stage(log=Log(logs=[_record("in teardown")])),
        )

        prompt = _prompt(test)

        assert "  Test Setup Log:\n```\nINFO     app:mod.py:12 in setup\n```" in prompt
        assert "  Test Teardown Log:\n```\nWARNING  app:mod.py:12 in teardown\n```" in (
            prompt
        )


class TestShowCapture:
    """The capture kinds select stdout, stderr and logs."""

    @staticmethod
    def _captured_test() -> Test:
        return _test(
            call=_failed_call(
                stdout="OUT_TEXT",
                stderr="ERR_TEXT",
                log=Log(logs=[_record("LOG_TEXT")]),
            )
        )

    def test_empty_capture_hides_everything(self) -> None:
        prompt = _prompt(self._captured_test(), capture=frozenset())

        assert "OUT_TEXT" not in prompt
        assert "ERR_TEXT" not in prompt
        assert "LOG_TEXT" not in prompt
        assert "E   assert 1 == 2" in prompt

    def test_log_only(self) -> None:
        prompt = _prompt(self._captured_test(), capture=frozenset({"log"}))

        assert "LOG_TEXT" in prompt
        assert "OUT_TEXT" not in prompt
        assert "ERR_TEXT" not in prompt

    def test_stdout_only(self) -> None:
        prompt = _prompt(self._captured_test(), capture=frozenset({"stdout"}))

        assert "OUT_TEXT" in prompt
        assert "LOG_TEXT" not in prompt
        assert "ERR_TEXT" not in prompt

    def test_default_shows_all(self) -> None:
        prompt = _prompt(self._captured_test())

        assert "OUT_TEXT" in prompt
        assert "ERR_TEXT" in prompt
        assert "LOG_TEXT" in prompt


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("no", frozenset()),
        ("stdout", frozenset({"stdout"})),
        ("stderr", frozenset({"stderr"})),
        ("log", frozenset({"log"})),
        ("all", ALL_CAPTURE),
        (None, ALL_CAPTURE),
    ],
)
def test_capture_kinds(value: str | None, expected: frozenset[str]) -> None:
    assert capture_kinds(value) == expected


class TestSectionsNamed:
    """Sections.named adds text that fits and names text that does not."""

    def test_fitting_text_is_added(self) -> None:
        out = Sections(10, 1000)

        out.named("Slowest", "row 1\nrow 2")

        assert out.text() == "row 1\nrow 2"

    def test_text_that_does_not_fit_is_named(self) -> None:
        out = Sections(3, 1000)

        out.named("Slowest", "\n".join(f"row {i}" for i in range(10)))

        assert "row 0" not in out.text()
        assert out.text().endswith("Not shown, budget used up: Slowest")


class TestPassingOutput:
    """Passing output includes log records."""

    def test_log_records_are_listed(self) -> None:
        test = _test(
            outcome="passed",
            call=_stage(stdout="CALL_OUT", log=Log(logs=[_record("call log")])),
            teardown=_stage(log=Log(logs=[_record("td log")])),
        )

        result = create_prompt_for_passing_output(_report([test]))

        assert "  Call stdout:\n```\nCALL_OUT\n```" in result
        assert "  Call log:\n```\nWARNING  app:mod.py:12 call log\n```" in result
        assert "  Teardown log:\n```\nWARNING  app:mod.py:12 td log\n```" in result

    def test_logs_alone_make_a_block(self) -> None:
        test = _test(outcome="passed", call=_stage(log=Log(logs=[_record("only")])))

        result = create_prompt_for_passing_output(_report([test]))

        assert result != NO_CAPTURED_OUTPUT_NOTE
        assert "only" in result

    def test_notes_mention_log_records(self) -> None:
        assert "log records" in NO_CAPTURED_OUTPUT_NOTE
        assert SHOW_OUTPUT_NOTE.endswith(
            "which shows the output and log records of passing tests."
        )
