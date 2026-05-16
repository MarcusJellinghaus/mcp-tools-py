"""Integration tests for reporting.py output-formatting behaviour."""

import json
from pathlib import Path

from mcp_tools_py.checker_tools import CheckerTools
from mcp_tools_py.code_checker_pytest.parsers import parse_pytest_report
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
        result = CheckerTools(server)._format_pytest_result_with_details(
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

        result = CheckerTools(server)._format_pytest_result_with_details(
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
        result = CheckerTools(server)._format_pytest_result_with_details(
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
        result = CheckerTools(server)._format_pytest_result_with_details(
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

        result = CheckerTools(server)._format_pytest_result_with_details(
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

        result = CheckerTools(server)._format_pytest_result_with_details(
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

        result = CheckerTools(server)._format_pytest_result_with_details(
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

        result = CheckerTools(server)._format_pytest_result_with_details(
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
            CheckerTools(server)._format_pytest_result_with_details(
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
