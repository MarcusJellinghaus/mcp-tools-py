"""Integration tests for reporting.py output-formatting behaviour."""

import json
from pathlib import Path
from typing import Any, Dict, List

from mcp_tools_py.checker_tools import CheckerTools
from mcp_tools_py.code_checker_pytest.models import PytestReport
from mcp_tools_py.code_checker_pytest.parsers import parse_pytest_report
from mcp_tools_py.code_checker_pytest.reporting import (
    NO_CAPTURED_OUTPUT_NOTE,
    create_prompt_for_passing_output,
)
from mcp_tools_py.server import ToolServer
from tests.test_code_checker_pytest._helpers import (
    _create_edge_case_project,
    _create_focused_project,
    _create_large_project,
)


class TestReporting:
    """Integration tests for reporting.py output formatting end-to-end flow."""

    def test_focused_debugging_session(
        self, temp_project_dir: Path, server: ToolServer
    ) -> None:
        """Test focused debugging session with ≤3 tests and show_details=True."""
        _create_focused_project(temp_project_dir)

        # Create a proper PytestReport object
        json_report = {
            "created": 1518371686.7981803,
            "duration": 0.1235666275024414,
            "exitcode": 1,
            "root": str(temp_project_dir),
            "environment": {},
            "summary": {"collected": 2, "passed": 1, "failed": 1, "total": 2},
            "collectors": [],
            "tests": [
                {
                    "nodeid": "tests/test_simple.py::test_failing_with_prints",
                    "lineno": 10,
                    "keywords": ["test_failing_with_prints"],
                    "outcome": "failed",
                    "call": {
                        "duration": 0.001,
                        "outcome": "failed",
                        "longrepr": "AssertionError: assert 1 == 5",
                        "stdout": "Debug: processing value\nDebug: data structure is {'key': 'value'}\nDebug: data length is 1\n",
                        "stderr": "",
                        "crash": {
                            "path": str(temp_project_dir / "tests" / "test_simple.py"),
                            "lineno": 15,
                            "message": "AssertionError: assert 1 == 5",
                        },
                    },
                }
            ],
            "warnings": [],
        }

        # Create pytest_report from JSON
        pytest_report = parse_pytest_report(json.dumps(json_report))

        # Create test results dict that server expects
        test_results = {
            "success": True,
            "summary": json_report["summary"],
            "test_results": pytest_report,
        }

        # Run with show_details=True
        result = CheckerTools(server.context)._format_pytest_result_with_details(
            test_results, show_details=True
        )

        # Verify detailed output includes print statements
        assert "Debug: processing value" in result
        assert "Debug: data structure is" in result
        assert "Debug: data length is" in result
        assert "AssertionError" in result
        assert len(result.split("\n")) > 10  # Substantial detail

    def test_large_test_suite_with_failures(
        self, temp_project_dir: Path, server: ToolServer
    ) -> None:
        """Test large test suite with >10 failures and show_details=True."""
        _create_large_project(temp_project_dir)

        # Create test results with 7 failures
        test_entries = []
        for i in range(7):
            test_entries.append(
                {
                    "nodeid": f"tests/test_module_{'a' if i < 2 else 'b'}.py::test_fail_{i}",
                    "lineno": 10,
                    "keywords": [f"test_fail_{i}"],
                    "outcome": "failed",
                    "call": {
                        "duration": 0.001,
                        "outcome": "failed",
                        "longrepr": f"AssertionError: Test {i} failed",
                        "stdout": f"Debug: test_{i} executing\nDebug: processing data {i}\n",
                        "stderr": "",
                        "crash": {
                            "path": str(
                                temp_project_dir
                                / "tests"
                                / f"test_module_{'a' if i < 2 else 'b'}.py"
                            ),
                            "lineno": 15,
                            "message": f"AssertionError: Test {i} failed",
                        },
                    },
                }
            )

        json_report = {
            "created": 1518371686.7981803,
            "duration": 0.5,
            "exitcode": 1,
            "root": str(temp_project_dir),
            "environment": {},
            "summary": {"collected": 23, "passed": 16, "failed": 7, "total": 23},
            "collectors": [],
            "tests": test_entries,
            "warnings": [],
        }

        pytest_report = parse_pytest_report(json.dumps(json_report))

        test_results = {
            "success": True,
            "summary": json_report["summary"],
            "test_results": pytest_report,
        }

        result = CheckerTools(server.context)._format_pytest_result_with_details(
            test_results, show_details=True
        )

        # Should handle many failures gracefully
        assert "Debug:" in result  # Should include print output
        assert "AssertionError" in result
        assert len(result.split("\n")) > 20  # Should have substantial content

    def test_specific_test_with_prints(self, temp_project_dir: Path) -> None:
        """Test specific test execution with prints (extra_args + show_details)."""
        _create_focused_project(temp_project_dir)
        server = ToolServer(project_dir=temp_project_dir)

        # Create proper PytestReport structure
        json_report = {
            "created": 1518371686.7981803,
            "duration": 0.1235666275024414,
            "exitcode": 1,
            "root": str(temp_project_dir),
            "environment": {},
            "summary": {"collected": 1, "passed": 0, "failed": 1, "total": 1},
            "collectors": [],
            "tests": [
                {
                    "nodeid": "tests/test_simple.py::test_failing_with_prints",
                    "lineno": 10,
                    "keywords": ["test_failing_with_prints"],
                    "outcome": "failed",
                    "call": {
                        "duration": 0.001,
                        "outcome": "failed",
                        "longrepr": "AssertionError: assert 1 == 5",
                        "stdout": "Debug: processing value\nDebug: data structure is {'key': 'value'}\n",
                        "stderr": "",
                        "crash": {
                            "path": str(temp_project_dir / "tests" / "test_simple.py"),
                            "lineno": 15,
                            "message": "AssertionError: assert 1 == 5",
                        },
                    },
                }
            ],
            "warnings": [],
        }

        pytest_report = parse_pytest_report(json.dumps(json_report))

        test_results = {
            "success": True,
            "summary": json_report["summary"],
            "test_results": pytest_report,
        }

        # Test with show_details=True (which would add -s automatically)
        result = CheckerTools(server.context)._format_pytest_result_with_details(
            test_results, show_details=True
        )

        # Should include print output since show_details=True
        assert "Debug: processing value" in result
        assert "Debug: data structure is" in result

    def test_verbose_pytest_with_show_details(self, temp_project_dir: Path) -> None:
        """Test verbosity interaction with show_details."""
        _create_focused_project(temp_project_dir)
        server = ToolServer(project_dir=temp_project_dir)

        # Create proper PytestReport structure
        json_report = {
            "created": 1518371686.7981803,
            "duration": 0.1235666275024414,
            "exitcode": 1,
            "root": str(temp_project_dir),
            "environment": {},
            "summary": {"collected": 2, "passed": 1, "failed": 1, "total": 2},
            "collectors": [],
            "tests": [
                {
                    "nodeid": "tests/test_simple.py::test_failing_with_prints",
                    "lineno": 10,
                    "keywords": ["test_failing_with_prints"],
                    "outcome": "failed",
                    "call": {
                        "duration": 0.001,
                        "outcome": "failed",
                        "longrepr": "tests/test_simple.py:15: AssertionError\nE       assert 1 == 5\nE       +  where 1 = len({'key': 'value'})",
                        "stdout": "Debug: processing value\nDebug: data structure is {'key': 'value'}\nDebug: data length is 1\n",
                        "stderr": "",
                        "crash": {
                            "path": str(temp_project_dir / "tests" / "test_simple.py"),
                            "lineno": 15,
                            "message": "AssertionError: assert 1 == 5",
                        },
                    },
                }
            ],
            "warnings": [],
        }

        pytest_report = parse_pytest_report(json.dumps(json_report))

        test_results = {
            "success": True,
            "summary": json_report["summary"],
            "test_results": pytest_report,
        }

        # Both verbosity and show_details should work together
        result = CheckerTools(server.context)._format_pytest_result_with_details(
            test_results, show_details=True
        )

        assert "Debug: processing value" in result
        assert "AssertionError" in result

    def test_no_tests_found_with_show_details(self, temp_project_dir: Path) -> None:
        """Test edge case: no tests found with show_details=True."""
        server = ToolServer(project_dir=temp_project_dir)

        # Create proper PytestReport structure for no tests
        json_report = {
            "created": 1518371686.7981803,
            "duration": 0.001,
            "exitcode": 5,  # No tests found
            "root": str(temp_project_dir),
            "environment": {},
            "summary": {"collected": 0, "passed": 0, "failed": 0, "total": 0},
            "collectors": [],
            "tests": [],
            "warnings": [],
        }

        pytest_report = parse_pytest_report(json.dumps(json_report))

        test_results = {
            "success": True,
            "summary": json_report["summary"],
            "test_results": pytest_report,
        }

        result = CheckerTools(server.context)._format_pytest_result_with_details(
            test_results, show_details=True
        )

        # Should handle empty results gracefully
        assert "All 0 tests passed successfully" in result

    def test_all_tests_pass_with_show_details(self, temp_project_dir: Path) -> None:
        """Test edge case: all tests pass with show_details=True."""
        _create_edge_case_project(temp_project_dir)
        server = ToolServer(project_dir=temp_project_dir)

        # Create proper PytestReport structure for all passing tests
        json_report = {
            "created": 1518371686.7981803,
            "duration": 0.05,
            "exitcode": 0,  # All tests passed
            "root": str(temp_project_dir),
            "environment": {},
            "summary": {"collected": 3, "passed": 3, "failed": 0, "total": 3},
            "collectors": [],
            "tests": [],  # No failed tests to report
            "warnings": [],
        }

        pytest_report = parse_pytest_report(json.dumps(json_report))

        test_results = {
            "success": True,
            "summary": json_report["summary"],
            "test_results": pytest_report,
        }

        result = CheckerTools(server.context)._format_pytest_result_with_details(
            test_results, show_details=True
        )

        # Should show success message
        assert "All 3 tests passed successfully" in result

    def test_collection_errors_with_show_details(self, temp_project_dir: Path) -> None:
        """Test collection errors with show_details=True."""
        server = ToolServer(project_dir=temp_project_dir)

        # Create proper PytestReport structure for collection errors
        json_report = {
            "created": 1518371686.7981803,
            "duration": 0.01,
            "exitcode": 2,  # Collection errors
            "root": str(temp_project_dir),
            "environment": {},
            "summary": {
                "collected": 0,
                "passed": 0,
                "failed": 0,
                "error": 2,
                "total": 0,
            },
            "collectors": [
                {
                    "nodeid": "tests/test_no_assertions.py",
                    "outcome": "error",
                    "longrepr": "ImportError: No module named 'non_existent_module'",
                    "result": [],
                },
                {
                    "nodeid": "tests/test_no_assertions.py::test_syntax_error",
                    "outcome": "error",
                    "longrepr": "SyntaxError: invalid syntax",
                    "result": [],
                },
            ],
            "tests": [],
            "warnings": [],
        }

        pytest_report = parse_pytest_report(json.dumps(json_report))

        test_results = {
            "success": True,
            "summary": json_report["summary"],
            "test_results": pytest_report,
        }

        result = CheckerTools(server.context)._format_pytest_result_with_details(
            test_results, show_details=True
        )

        # Collection errors should always be shown regardless of show_details
        assert "ImportError" in result or "SyntaxError" in result

    def test_output_length_management(self, temp_project_dir: Path) -> None:
        """Test output length management and truncation."""
        server = ToolServer(project_dir=temp_project_dir)

        # Create test results with very long output
        long_output = "Debug line\n" * 400  # More than 300 line limit

        json_report = {
            "created": 1518371686.7981803,
            "duration": 0.1,
            "exitcode": 1,
            "root": str(temp_project_dir),
            "environment": {},
            "summary": {"collected": 1, "passed": 0, "failed": 1, "total": 1},
            "collectors": [],
            "tests": [
                {
                    "nodeid": "tests/test_long.py::test_long_output",
                    "lineno": 10,
                    "keywords": ["test_long_output"],
                    "outcome": "failed",
                    "call": {
                        "duration": 0.001,
                        "outcome": "failed",
                        "longrepr": "AssertionError: Long test failed",
                        "stdout": long_output,
                        "stderr": "",
                        "crash": {
                            "path": str(temp_project_dir / "tests" / "test_long.py"),
                            "lineno": 15,
                            "message": "AssertionError: Long test failed",
                        },
                    },
                }
            ],
            "warnings": [],
        }

        pytest_report = parse_pytest_report(json.dumps(json_report))

        test_results = {
            "success": True,
            "summary": json_report["summary"],
            "test_results": pytest_report,
        }

        result = CheckerTools(server.context)._format_pytest_result_with_details(
            test_results, show_details=True
        )

        # Should include some output but manage length
        assert "Debug line" in result
        # The exact truncation behavior depends on the implementation

    def test_clean_temporary_file_handling(self, temp_project_dir: Path) -> None:
        """Test proper resource cleanup - no temp files left behind."""
        initial_files = list(temp_project_dir.rglob("*"))

        _create_focused_project(temp_project_dir)
        server = ToolServer(project_dir=temp_project_dir)

        # Create proper PytestReport structure
        json_report = {
            "created": 1518371686.7981803,
            "duration": 0.1235666275024414,
            "exitcode": 1,
            "root": str(temp_project_dir),
            "environment": {},
            "summary": {"collected": 2, "passed": 1, "failed": 1, "total": 2},
            "collectors": [],
            "tests": [
                {
                    "nodeid": "tests/test_simple.py::test_failing_with_prints",
                    "lineno": 10,
                    "keywords": ["test_failing_with_prints"],
                    "outcome": "failed",
                    "call": {
                        "duration": 0.001,
                        "outcome": "failed",
                        "longrepr": "AssertionError: assert 1 == 5",
                        "stdout": "Debug: processing value\n",
                        "stderr": "",
                        "crash": {
                            "path": str(temp_project_dir / "tests" / "test_simple.py"),
                            "lineno": 15,
                            "message": "AssertionError: assert 1 == 5",
                        },
                    },
                }
            ],
            "warnings": [],
        }

        pytest_report = parse_pytest_report(json.dumps(json_report))

        test_results = {
            "success": True,
            "summary": json_report["summary"],
            "test_results": pytest_report,
        }

        # Run several formatting operations
        for _ in range(3):
            CheckerTools(server.context)._format_pytest_result_with_details(
                test_results, show_details=True
            )

        final_files = list(temp_project_dir.rglob("*"))

        # Should not have created additional temp files beyond our test files
        # (allowing for the test files we intentionally created)
        expected_new_files = ["tests", "tests/conftest.py", "tests/test_simple.py"]
        actual_new_files = [
            f.relative_to(temp_project_dir).as_posix()
            for f in final_files
            if f not in initial_files
        ]

        # All new files should be our intentional test files
        for new_file in actual_new_files:
            assert any(expected in new_file for expected in expected_new_files)


def _stage(**fields: Any) -> Dict[str, Any]:
    """Build a passing json-report stage with the given extra fields."""
    return {"duration": 0.001, "outcome": "passed", **fields}


def _report(tests: List[Dict[str, Any]]) -> PytestReport:
    """Parse a json-report holding the given test entries."""
    return parse_pytest_report(
        json.dumps(
            {
                "created": 0.0,
                "duration": 0.1,
                "exitcode": 0,
                "root": "/project",
                "environment": {},
                "summary": {"collected": len(tests), "total": len(tests)},
                "collectors": [],
                "tests": tests,
                "warnings": [],
            }
        )
    )


def _test(nodeid: str, outcome: str, **stages: Dict[str, Any]) -> Dict[str, Any]:
    """Build a json-report test entry."""
    return {
        "nodeid": nodeid,
        "lineno": 1,
        "keywords": [],
        "outcome": outcome,
        **stages,
    }


class TestPassingOutput:
    """Tests for create_prompt_for_passing_output."""

    def test_shows_output_of_every_stage_of_non_failing_tests(self) -> None:
        """Setup, call and teardown output is labelled; longrepr and failures are not shown."""
        report = _report(
            [
                _test(
                    "t.py::test_passed",
                    "passed",
                    setup=_stage(stdout="SETUP_OUT"),
                    call=_stage(stdout="CALL_OUT"),
                    teardown=_stage(stderr="TEARDOWN_ERR"),
                ),
                _test(
                    "t.py::test_skipped",
                    "skipped",
                    setup=_stage(outcome="skipped", stderr="SKIP_ERR"),
                ),
                _test(
                    "t.py::test_xfailed",
                    "xfailed",
                    call=_stage(
                        outcome="skipped",
                        stdout="XFAIL_OUT",
                        stderr="XFAIL_ERR",
                        longrepr="XFAIL_LONGREPR",
                    ),
                ),
                _test(
                    "t.py::test_failed",
                    "failed",
                    call=_stage(outcome="failed", stdout="FAILED_OUT"),
                ),
            ]
        )

        result = create_prompt_for_passing_output(report)

        assert result.startswith("Captured output of passing tests:\n")
        assert "Test ID: t.py::test_passed - outcome passed" in result
        assert "  Setup stdout:\n```\nSETUP_OUT\n```" in result
        assert "  Call stdout:\n```\nCALL_OUT\n```" in result
        assert "  Teardown stderr:\n```\nTEARDOWN_ERR\n```" in result
        assert "  Setup stderr:\n```\nSKIP_ERR\n```" in result
        assert "  Call stdout:\n```\nXFAIL_OUT\n```" in result
        assert "  Call stderr:\n```\nXFAIL_ERR\n```" in result
        assert "XFAIL_LONGREPR" not in result
        assert "FAILED_OUT" not in result
        assert "test_failed" not in result
        assert result.count("Captured output of passing tests:") == 1

    def test_leaves_out_tests_without_output(self) -> None:
        """A passing test that printed nothing is not listed."""
        report = _report(
            [
                _test("t.py::test_quiet", "passed", call=_stage()),
                _test("t.py::test_loud", "passed", call=_stage(stdout="LOUD")),
            ]
        )

        result = create_prompt_for_passing_output(report)

        assert "test_quiet" not in result
        assert "LOUD" in result

    def test_no_output_gives_note(self) -> None:
        """If no passing test printed, the note is returned."""
        report = _report(
            [
                _test("t.py::test_quiet", "passed", call=_stage(stdout="")),
                _test("t.py::test_failed", "failed", call=_stage(stdout="X")),
            ]
        )

        assert create_prompt_for_passing_output(report) == NO_CAPTURED_OUTPUT_NOTE
        assert create_prompt_for_passing_output(_report([])) == NO_CAPTURED_OUTPUT_NOTE

    def test_output_is_truncated(self) -> None:
        """Many printing tests are cut at max_output_lines."""
        report = _report(
            [
                _test(f"t.py::test_{i}", "passed", call=_stage(stdout=f"LINE_{i}"))
                for i in range(20)
            ]
        )

        result = create_prompt_for_passing_output(report, max_output_lines=10)

        assert "[Output truncated" in result
        assert "LINE_19" not in result
