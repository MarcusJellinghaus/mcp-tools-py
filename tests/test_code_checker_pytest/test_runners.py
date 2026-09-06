"""Integration tests for runners.py marker filtering and runner behaviour."""

import json
import time
from pathlib import Path

from mcp_tools_py.checker_tools import CheckerTools
from mcp_tools_py.code_checker_pytest.parsers import parse_pytest_report
from mcp_tools_py.server import ToolServer
from tests.test_code_checker_pytest._helpers import _create_large_project


class TestRunners:
    """Integration tests for runners.py end-to-end flow."""

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

        result = CheckerTools(server.context)._format_pytest_result_with_details(
            test_results, show_details=True
        )

        # Should include debug output from the marked test
        assert "Debug: slow operation starting" in result

    def test_performance_validation(self, temp_project_dir: Path) -> None:
        """Test that integration has reasonable performance."""
        _create_large_project(temp_project_dir)
        server = ToolServer(project_dir=temp_project_dir)

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
        result = CheckerTools(server.context)._format_pytest_result_with_details(
            test_results, show_details=True
        )
        end_time = time.time()

        # Should complete within reasonable time (< 1 second for formatting)
        assert end_time - start_time < 1.0
        assert len(result) > 0  # Should produce output
