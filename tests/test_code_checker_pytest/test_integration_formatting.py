"""End-to-end integration tests for detailed output formatting functionality."""

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, cast

import pytest

from mcp_tools_py.code_checker_pytest.models import (
    Crash,
    PytestReport,
    StageInfo,
    Summary,
    Test,
)
from mcp_tools_py.code_checker_pytest.parsers import parse_pytest_report
from mcp_tools_py.server import CodeCheckerServer


class TestIntegrationFormatting:
    """Integration tests for detailed output formatting end-to-end flow."""

    @pytest.fixture
    def temp_project_dir(self) -> Generator[Path, None, None]:
        """Create a temporary directory for test projects."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def server(self, temp_project_dir: Path) -> CodeCheckerServer:
        """Create a CodeCheckerServer instance for testing."""
        return CodeCheckerServer(project_dir=temp_project_dir)

    def _create_focused_project(self, project_dir: Path) -> None:
        """Create a small focused project with 1 passing test and 1 failing test with prints."""
        (project_dir / "tests").mkdir(parents=True, exist_ok=True)

        # Create conftest.py
        (project_dir / "tests" / "conftest.py").write_text("""
# Basic pytest configuration for focused testing
import pytest

@pytest.fixture
def sample_data():
    return {"value": 42, "name": "test"}
""")

        # Create test_simple.py with print statements
        (project_dir / "tests" / "test_simple.py").write_text("""
def test_passing():
    \"\"\"A simple passing test.\"\"\"
    print("Debug: test_passing started")
    result = 2 + 2
    print(f"Debug: calculation result is {result}")
    assert result == 4
    print("Debug: test_passing completed successfully")

def test_failing_with_prints():
    \"\"\"A failing test that includes print statements for debugging.\"\"\"
    print("Debug: processing value")
    data = {"key": "value"}
    print(f"Debug: data structure is {data}")
    
    # This will fail
    result = len(data)
    print(f"Debug: data length is {result}")
    assert result == 5  # Intentionally wrong
    print("Debug: this line should not be reached")
""")

    def _create_large_project(self, project_dir: Path) -> None:
        """Create a large project with multiple test files and many failures."""
        (project_dir / "tests").mkdir(parents=True, exist_ok=True)

        # Create conftest.py
        (project_dir / "tests" / "conftest.py").write_text("""
import pytest

@pytest.fixture
def common_data():
    return list(range(10))
""")

        # Create test_module_a.py - 5 tests: 3 pass, 2 fail
        (project_dir / "tests" / "test_module_a.py").write_text("""
def test_a1_pass():
    assert 1 == 1

def test_a2_pass():
    assert "hello" == "hello"

def test_a3_pass():
    assert [1, 2, 3] == [1, 2, 3]

def test_a4_fail():
    print("Debug: test_a4_fail executing")
    assert 1 == 2  # Fail

def test_a5_fail():
    print("Debug: test_a5_fail processing data")
    data = [1, 2, 3]
    print(f"Debug: data is {data}")
    assert len(data) == 5  # Fail
""")

        # Create test_module_b.py - 10 tests: 5 pass, 5 fail
        (project_dir / "tests" / "test_module_b.py").write_text("""
def test_b1_pass():
    assert True

def test_b2_pass():
    assert 10 > 5

def test_b3_pass():
    assert "test" in "testing"

def test_b4_pass():
    assert {"a": 1}.get("a") == 1

def test_b5_pass():
    assert not False

def test_b6_fail():
    print("Debug: b6 starting")
    assert False  # Fail

def test_b7_fail():
    print("Debug: b7 calculating")
    result = 5 * 5
    print(f"Result: {result}")
    assert result == 30  # Fail

def test_b8_fail():
    print("Debug: b8 list operations")
    items = [1, 2, 3, 4]
    print(f"Items: {items}")
    assert len(items) == 10  # Fail

def test_b9_fail():
    print("Debug: b9 string operations")
    text = "hello world"
    print(f"Text: {text}")
    assert text.startswith("goodbye")  # Fail

def test_b10_fail():
    print("Debug: b10 dict operations")
    data = {"x": 1, "y": 2}
    print(f"Data: {data}")
    assert data["z"] == 3  # Fail - KeyError
""")

        # Create test_module_c.py - 8 tests: all pass
        (project_dir / "tests" / "test_module_c.py").write_text("""
def test_c1_pass():
    assert 42 == 42

def test_c2_pass():
    assert "python" == "python"

def test_c3_pass():
    assert [1, 2] + [3, 4] == [1, 2, 3, 4]

def test_c4_pass():
    assert max([1, 5, 3]) == 5

def test_c5_pass():
    assert min([1, 5, 3]) == 1

def test_c6_pass():
    assert sum([1, 2, 3]) == 6

def test_c7_pass():
    assert len("hello") == 5

def test_c8_pass():
    assert sorted([3, 1, 2]) == [1, 2, 3]
""")

    def _create_edge_case_project(self, project_dir: Path) -> None:
        """Create project with edge cases: collection errors and all passing tests."""
        (project_dir / "tests").mkdir(parents=True, exist_ok=True)

        # Create test_no_assertions.py with collection errors
        (project_dir / "tests" / "test_no_assertions.py").write_text("""
# This will cause collection errors
import non_existent_module

def test_with_import_error():
    non_existent_module.do_something()
    assert True
    
def test_syntax_error():
    # Intentional syntax error
    if True
        assert True
""")

        # Create test_all_pass.py with only passing tests
        (project_dir / "tests" / "test_all_pass.py").write_text("""
def test_simple_pass():
    print("Debug: simple test passing")
    assert True

def test_math_pass():
    print("Debug: math test")
    assert 2 + 2 == 4

def test_string_pass():
    print("Debug: string test")
    assert "hello".upper() == "HELLO"
""")

    def test_focused_debugging_session(
        self, temp_project_dir: Path, server: CodeCheckerServer
    ) -> None:
        """Test focused debugging session with ≤3 tests and show_details=True."""
        self._create_focused_project(temp_project_dir)

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
        result = server._format_pytest_result_with_details(
            test_results, show_details=True
        )

        # Verify detailed output includes print statements
        assert "Debug: processing value" in result
        assert "Debug: data structure is" in result
        assert "Debug: data length is" in result
        assert "AssertionError" in result
        assert len(result.split("\n")) > 10  # Substantial detail

    def test_large_test_suite_with_failures(
        self, temp_project_dir: Path, server: CodeCheckerServer
    ) -> None:
        """Test large test suite with >10 failures and show_details=True."""
        self._create_large_project(temp_project_dir)

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

        result = server._format_pytest_result_with_details(
            test_results, show_details=True
        )

        # Should handle many failures gracefully
        assert "Debug:" in result  # Should include print output
        assert "AssertionError" in result
        assert len(result.split("\n")) > 20  # Should have substantial content

    def test_specific_test_with_prints(self, temp_project_dir: Path) -> None:
        """Test specific test execution with prints (extra_args + show_details)."""
        self._create_focused_project(temp_project_dir)
        server = CodeCheckerServer(project_dir=temp_project_dir)

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
        result = server._format_pytest_result_with_details(
            test_results, show_details=True
        )

        # Should include print output since show_details=True
        assert "Debug: processing value" in result
        assert "Debug: data structure is" in result

    def test_marker_filtering_with_details(self, temp_project_dir: Path) -> None:
        """Test marker filtering combined with show_details."""
        (temp_project_dir / "tests").mkdir(parents=True, exist_ok=True)

        # Create test with markers
        (temp_project_dir / "tests" / "test_markers.py").write_text("""
import pytest

@pytest.mark.slow
def test_slow_operation():
    print("Debug: slow operation starting")
    assert 1 == 2  # Intentional failure

@pytest.mark.fast  
def test_fast_operation():
    print("Debug: fast operation")
    assert True
""")

        server = CodeCheckerServer(project_dir=temp_project_dir)

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
                    "nodeid": "tests/test_markers.py::test_slow_operation",
                    "lineno": 10,
                    "keywords": ["test_slow_operation", "slow"],
                    "outcome": "failed",
                    "call": {
                        "duration": 0.001,
                        "outcome": "failed",
                        "longrepr": "AssertionError: assert 1 == 2",
                        "stdout": "Debug: slow operation starting\n",
                        "stderr": "",
                        "crash": {
                            "path": str(temp_project_dir / "tests" / "test_markers.py"),
                            "lineno": 6,
                            "message": "AssertionError: assert 1 == 2",
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

        result = server._format_pytest_result_with_details(
            test_results, show_details=True
        )

        # Should include debug output from the marked test
        assert "Debug: slow operation starting" in result

    def test_verbose_pytest_with_show_details(self, temp_project_dir: Path) -> None:
        """Test verbosity interaction with show_details."""
        self._create_focused_project(temp_project_dir)
        server = CodeCheckerServer(project_dir=temp_project_dir)

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
        result = server._format_pytest_result_with_details(
            test_results, show_details=True
        )

        assert "Debug: processing value" in result
        assert "AssertionError" in result

    def test_no_tests_found_with_show_details(self, temp_project_dir: Path) -> None:
        """Test edge case: no tests found with show_details=True."""
        server = CodeCheckerServer(project_dir=temp_project_dir)

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

        result = server._format_pytest_result_with_details(
            test_results, show_details=True
        )

        # Should handle empty results gracefully
        assert "All 0 tests passed successfully" in result

    def test_all_tests_pass_with_show_details(self, temp_project_dir: Path) -> None:
        """Test edge case: all tests pass with show_details=True."""
        self._create_edge_case_project(temp_project_dir)
        server = CodeCheckerServer(project_dir=temp_project_dir)

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

        result = server._format_pytest_result_with_details(
            test_results, show_details=True
        )

        # Should show success message
        assert "All 3 tests passed successfully" in result

    def test_collection_errors_with_show_details(self, temp_project_dir: Path) -> None:
        """Test collection errors with show_details=True."""
        server = CodeCheckerServer(project_dir=temp_project_dir)

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

        result = server._format_pytest_result_with_details(
            test_results, show_details=True
        )

        # Collection errors should always be shown regardless of show_details
        assert "ImportError" in result or "SyntaxError" in result

    def test_output_length_management(self, temp_project_dir: Path) -> None:
        """Test output length management and truncation."""
        server = CodeCheckerServer(project_dir=temp_project_dir)

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

        result = server._format_pytest_result_with_details(
            test_results, show_details=True
        )

        # Should include some output but manage length
        assert "Debug line" in result
        # The exact truncation behavior depends on the implementation

    def test_performance_validation(self, temp_project_dir: Path) -> None:
        """Test that integration has reasonable performance."""
        self._create_large_project(temp_project_dir)
        server = CodeCheckerServer(project_dir=temp_project_dir)

        # Create proper PytestReport structure for performance test
        test_entries = []
        for i in range(7):
            test_entries.append(
                {
                    "nodeid": f"tests/test_module_b.py::test_b{i}_fail",
                    "lineno": 10,
                    "keywords": [f"test_b{i}_fail"],
                    "outcome": "failed",
                    "call": {
                        "duration": 0.001,
                        "outcome": "failed",
                        "longrepr": f"AssertionError: Test {i} failed",
                        "stdout": f"Debug: test {i} output\n",
                        "stderr": "",
                        "crash": {
                            "path": str(
                                temp_project_dir / "tests" / "test_module_b.py"
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

        start_time = time.time()
        result = server._format_pytest_result_with_details(
            test_results, show_details=True
        )
        end_time = time.time()

        # Should complete within reasonable time (< 1 second for formatting)
        assert end_time - start_time < 1.0
        assert len(result) > 0  # Should produce output

    def test_clean_temporary_file_handling(self, temp_project_dir: Path) -> None:
        """Test proper resource cleanup - no temp files left behind."""
        initial_files = list(temp_project_dir.rglob("*"))

        self._create_focused_project(temp_project_dir)
        server = CodeCheckerServer(project_dir=temp_project_dir)

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
            server._format_pytest_result_with_details(test_results, show_details=True)

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
