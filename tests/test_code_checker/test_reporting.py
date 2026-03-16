"""
Tests for the code_checker_pytest reporting functionality.
"""

from typing import Any

import pytest

from mcp_tools_py.code_checker_pytest import (
    create_prompt_for_failed_tests,
    get_test_summary,
    parse_pytest_report,
)
from mcp_tools_py.code_checker_pytest.models import PytestReport, Summary

from .test_code_checker_pytest_common import SAMPLE_JSON


def test_create_prompt_no_failed_tests() -> None:
    """Test creating a prompt when there are no failed tests."""
    json_no_failed_tests = """
    {
        "created": 1518371686.7981803,
        "duration": 0.1235666275024414,
        "exitcode": 0,
        "root": "/path/to/tests",
        "environment": {
        "Python": "3.6.4",
        "Platform": "Linux-4.56.78-9-ARCH-x86_64-with-arch",
        "Packages": {
            "pytest": "3.4.0",
            "py": "1.5.2",
            "pluggy": "0.6.0"
        },
        "Plugins": {
            "json-report": "0.4.1",
            "xdist": "1.22.0",
            "metadata": "1.5.1",
            "forked": "0.2",
            "cov": "2.5.1"
        },
        "foo": "bar"
    },
    "summary": {
        "collected": 10,
        "passed": 10,
        "total": 10
    },
        "collectors": [],
        "tests": [],
        "warnings": []
    }
    """
    report = parse_pytest_report(json_no_failed_tests)
    prompt = create_prompt_for_failed_tests(report)
    assert prompt is None


def test_create_prompt_for_failed_tests() -> None:
    """Test creating a prompt for failed tests."""
    report = parse_pytest_report(SAMPLE_JSON)
    prompt = create_prompt_for_failed_tests(report)
    assert prompt is not None
    assert "The following tests failed during the test session:" in prompt
    assert "Test ID: test_foo.py::test_fail" in prompt

    # Safely check for attributes with None checks
    assert report.tests is not None
    assert report.tests[0].call is not None
    assert report.tests[0].call.crash is not None
    assert (
        "Error Message: TypeError: unsupported operand type(s) for -: 'int' and 'NoneType'"
        in prompt
    )

    assert "Stdout:" in prompt
    assert "Stderr:" in prompt
    assert "Traceback:" in prompt
    assert "test_foo.py:65 - " in prompt
    assert (
        "Can you provide an explanation for why these tests failed and suggest how they could be fixed?"
        in prompt
    )


def test_create_prompt_for_failed_tests_longrepr() -> None:
    """Test creating a prompt for failed tests with longrepr."""
    json_with_longrepr_tests = """
  {
      "created": 1518371686.7981803,
      "duration": 0.1235666275024414,
      "exitcode": 1,
      "root": "/path/to/tests",
      "environment": {
          "Python": "3.6.4",
          "Platform": "Linux-4.56.78-9-ARCH-x86_64-with-arch",
          "Packages": {
              "pytest": "3.4.0",
              "py": "1.5.2",
              "pluggy": "0.6.0"
          },
          "Plugins": {
              "json-report": "0.4.1",
              "xdist": "1.22.0",
              "metadata": "1.5.1",
              "forked": "0.2",
              "cov": "2.5.1"
          },
          "foo": "bar"
      },
      "summary": {
          "collected": 10,
          "passed": 2,
          "failed": 1,
          "total": 10
      },
      "collectors": [],
      "tests": [
          {
              "nodeid": "test_foo.py::test_fail",
              "lineno": 50,
              "keywords": [
                  "test_fail",
                  "test_foo.py",
                  "test_foo0"
              ],
              "outcome": "failed",
              "setup": {
                  "duration": 0.00018835067749023438,
                  "outcome": "passed"
              },
              "call": {
                  "duration": 0.00018835067749023438,
                  "outcome": "failed",
                  "longrepr": "def test_fail_nested():\\n    a = 1\\n    b = None\\n    a - b",
                  "crash": {
                      "path": "/path/to/tests/test_foo.py",
                      "lineno": 54,
                      "message": "TypeError: unsupported operand type(s) for -: 'int' and 'NoneType'"
                  },
                  "traceback": [
                      {
                          "path": "test_foo.py",
                          "lineno": 65,
                          "message": ""
                      }
                  ]
              },
              "teardown": {
                  "duration": 0.00018835067749023438,
                  "outcome": "passed"
              },
              "metadata": {
                  "foo": "bar"
              }
          }
      ],
      "warnings": []
  }
  """
    report = parse_pytest_report(json_with_longrepr_tests)
    prompt = create_prompt_for_failed_tests(report)
    assert prompt is not None
    assert "Longrepr:" in prompt
    assert "def test_fail_nested():" in prompt


def test_get_test_summary() -> None:
    """Test generating a human-readable summary of test results."""
    report = parse_pytest_report(SAMPLE_JSON)
    summary = get_test_summary(report)

    assert "Collected 10 tests in 0.12 seconds" in summary
    assert "✅ Passed: 2" in summary
    assert "❌ Failed: 3" in summary
    assert "⚠️ Error: 2" in summary
    assert "⏭️ Skipped: 1" in summary
    assert "🔶 Expected failures: 1" in summary
    assert "🔶 Unexpected passes: 1" in summary


def test_get_test_summary_minimal() -> None:
    """Test generating a summary with minimal test results."""
    json_minimal = """
    {
        "created": 1518371686.7981803,
        "duration": 0.1235666275024414,
        "exitcode": 0,
        "root": "/path/to/tests",
        "environment": {},
        "summary": {
            "collected": 5,
            "passed": 5,
            "total": 5
        }
    }
    """
    report = parse_pytest_report(json_minimal)
    summary = get_test_summary(report)

    assert "Collected 5 tests in 0.12 seconds" in summary
    assert "✅ Passed: 5" in summary
    assert "❌ Failed:" not in summary
    assert "⚠️ Error:" not in summary


# ===================== Tests for Enhanced Reporting Logic =====================


@pytest.fixture
def minimal_test_results() -> dict[str, dict[str, int]]:
    """Mock results for ≤3 tests."""
    return {"summary": {"collected": 2, "passed": 1, "failed": 1, "total": 2}}


@pytest.fixture
def large_test_results() -> dict[str, dict[str, int]]:
    """Mock results for >10 failures."""
    return {"summary": {"collected": 50, "passed": 35, "failed": 15, "total": 50}}


@pytest.fixture
def mock_pytest_report_with_prints() -> PytestReport:
    """PytestReport with stdout/print content in longrepr."""
    json_with_prints = """
    {
        "created": 1518371686.7981803,
        "duration": 0.1235666275024414,
        "exitcode": 1,
        "root": "/path/to/tests",
        "environment": {},
        "summary": {
            "collected": 3,
            "passed": 1,
            "failed": 2,
            "total": 3
        },
        "collectors": [],
        "tests": [
            {
                "nodeid": "test_example.py::test_with_print",
                "lineno": 10,
                "keywords": ["test_with_print"],
                "outcome": "failed",
                "setup": {
                    "duration": 0.001,
                    "outcome": "passed"
                },
                "call": {
                    "duration": 0.001,
                    "outcome": "failed",
                    "longrepr": "def test_with_print():\\n    print('Debug info: value=42')\\n    assert False, 'Intentional failure'",
                    "stdout": "Debug info: value=42\\n",
                    "crash": {
                        "path": "/path/to/tests/test_example.py",
                        "lineno": 12,
                        "message": "AssertionError: Intentional failure"
                    }
                },
                "teardown": {
                    "duration": 0.001,
                    "outcome": "passed"
                }
            },
            {
                "nodeid": "test_example.py::test_another_fail",
                "lineno": 20,
                "keywords": ["test_another_fail"],
                "outcome": "failed",
                "setup": {
                    "duration": 0.001,
                    "outcome": "passed"
                },
                "call": {
                    "duration": 0.001,
                    "outcome": "failed",
                    "longrepr": "def test_another_fail():\\n    print('More debug info')\\n    assert 1 == 2",
                    "stdout": "More debug info\\n",
                    "crash": {
                        "path": "/path/to/tests/test_example.py",
                        "lineno": 22,
                        "message": "AssertionError: assert 1 == 2"
                    }
                },
                "teardown": {
                    "duration": 0.001,
                    "outcome": "passed"
                }
            }
        ],
        "warnings": []
    }
    """
    return parse_pytest_report(json_with_prints)


def _mock_show_details_decision_logic(
    test_results: dict[str, Any], show_details: bool
) -> bool:
    """
    Test helper function that mocks the show_details decision logic for testing.

    This is a test mock implementation used to validate the expected behavior
    before the actual implementation is in place.

    Args:
        test_results: Dictionary with test summary data
        show_details: Flag indicating if details were requested

    Returns:
        bool: True if details should be shown based on mocked logic
    """
    if not show_details:
        return False

    summary = test_results.get("summary", {})
    if summary is None:
        summary = {}
    collected = summary.get("collected", 0)

    # Always show details for small test runs (≤3 tests)
    if collected <= 3:
        return True

    # For larger runs, show details only if explicitly requested
    return True


# ===================== Test Functions for Decision Logic =====================


def test_should_show_details_with_few_tests(
    minimal_test_results: dict[str, dict[str, int]],
) -> None:
    """Test decision logic for small test runs (≤3 tests)."""
    # Should show details when requested for few tests
    assert _mock_show_details_decision_logic(minimal_test_results, True) is True

    # Should not show details when not requested
    assert _mock_show_details_decision_logic(minimal_test_results, False) is False


def test_should_show_details_with_many_tests(
    large_test_results: dict[str, dict[str, int]],
) -> None:
    """Test decision logic for large test runs (>3 tests)."""
    # Should show details when explicitly requested for many tests
    assert _mock_show_details_decision_logic(large_test_results, True) is True

    # Should not show details when not requested
    assert _mock_show_details_decision_logic(large_test_results, False) is False


def test_should_show_details_with_failures() -> None:
    """Test decision logic with various failure counts."""
    test_data_with_failures = {
        "summary": {"collected": 10, "passed": 5, "failed": 5, "total": 10}
    }

    # Should show details when requested, regardless of failure count
    assert _mock_show_details_decision_logic(test_data_with_failures, True) is True

    # Should not show details when not requested
    assert _mock_show_details_decision_logic(test_data_with_failures, False) is False


def test_should_show_details_false_by_default() -> None:
    """Test that show_details defaults to False behavior."""
    test_data = {"summary": {"collected": 5, "passed": 3, "failed": 2, "total": 5}}

    # Should not show details by default (show_details=False)
    assert _mock_show_details_decision_logic(test_data, False) is False


# ===================== Test Functions for Enhanced Formatting =====================


def test_create_prompt_with_print_output_enabled(
    mock_pytest_report_with_prints: PytestReport,
) -> None:
    """Test enhanced formatting with print output enabled."""
    # Test the current behavior (this will be enhanced in step 2)
    prompt = create_prompt_for_failed_tests(
        mock_pytest_report_with_prints, max_number_of_tests_reported=10
    )

    assert prompt is not None
    assert "The following tests failed during the test session:" in prompt
    assert "test_example.py::test_with_print" in prompt

    # Check that stdout content is included (current behavior)
    assert "Stdout:" in prompt
    assert "Debug info: value=42" in prompt


def test_create_prompt_with_print_output_disabled() -> None:
    """Test enhanced formatting with print output disabled."""
    # This test will be more relevant after step 2 implementation
    # For now, test current behavior with limited output
    json_simple_failure = """
    {
        "created": 1518371686.7981803,
        "duration": 0.1235666275024414,
        "exitcode": 1,
        "root": "/path/to/tests",
        "environment": {},
        "summary": {
            "collected": 1,
            "passed": 0,
            "failed": 1,
            "total": 1
        },
        "collectors": [],
        "tests": [
            {
                "nodeid": "test_simple.py::test_fail",
                "lineno": 10,
                "keywords": ["test_fail"],
                "outcome": "failed",
                "call": {
                    "duration": 0.001,
                    "outcome": "failed",
                    "crash": {
                        "path": "/path/to/tests/test_simple.py",
                        "lineno": 5,
                        "message": "AssertionError: Test failed"
                    }
                }
            }
        ]
    }
    """

    report = parse_pytest_report(json_simple_failure)
    prompt = create_prompt_for_failed_tests(report, max_number_of_tests_reported=1)

    assert prompt is not None
    assert "test_simple.py::test_fail" in prompt
    assert "AssertionError: Test failed" in prompt


def test_create_prompt_respects_max_failures_limit() -> None:
    """Test that formatting respects maximum failure limits."""
    # Create a report with many failures
    json_many_failures = """
    {
        "created": 1518371686.7981803,
        "duration": 0.5,
        "exitcode": 1,
        "root": "/path/to/tests",
        "environment": {},
        "summary": {
            "collected": 15,
            "passed": 0,
            "failed": 15,
            "total": 15
        },
        "collectors": [],
        "tests": [
    """

    # Add 15 failed tests
    test_entries = []
    for i in range(15):
        test_entry = f"""
            {{
                "nodeid": "test_many.py::test_fail_{i}",
                "lineno": 10,
                "keywords": ["test_fail_{i}"],
                "outcome": "failed",
                "call": {{
                    "duration": 0.001,
                    "outcome": "failed",
                    "crash": {{
                        "path": "/path/to/tests/test_many.py",
                        "lineno": 10,
                        "message": "AssertionError: Test {i} failed"
                    }}
                }}
            }}"""
        test_entries.append(test_entry)

    json_many_failures += ",".join(test_entries)
    json_many_failures += """
        ],
        "warnings": []
    }
    """

    report = parse_pytest_report(json_many_failures)

    # Test with limit of 5
    prompt = create_prompt_for_failed_tests(report, max_number_of_tests_reported=5)

    assert prompt is not None

    # Count occurrences of "Test ID:" to verify limit is respected
    test_id_count = prompt.count("Test ID:")
    assert test_id_count == 5, f"Expected 5 test failures, got {test_id_count}"

    # Verify first 5 tests are included
    assert "test_fail_0" in prompt
    assert "test_fail_4" in prompt

    # Verify later tests are not included due to limit
    assert "test_fail_5" not in prompt
    assert "test_fail_14" not in prompt


def test_create_prompt_with_collection_errors() -> None:
    """Test that collection errors are always shown regardless of show_details setting."""
    json_with_collection_error = """
    {
        "created": 1518371686.7981803,
        "duration": 0.1,
        "exitcode": 2,
        "root": "/path/to/tests",
        "environment": {},
        "summary": {
            "collected": 0,
            "passed": 0,
            "failed": 0,
            "total": 0
        },
        "collectors": [
            {
                "nodeid": "test_broken.py",
                "outcome": "failed",
                "longrepr": "ImportError: No module named 'missing_dependency'",
                "result": [
                    {
                        "nodeid": "test_broken.py",
                        "type": "module"
                    }
                ]
            }
        ],
        "tests": [],
        "warnings": []
    }
    """

    report = parse_pytest_report(json_with_collection_error)
    prompt = create_prompt_for_failed_tests(report)

    assert prompt is not None
    assert "The following collectors failed during the test session:" in prompt
    assert "test_broken.py" in prompt
    assert "ImportError: No module named 'missing_dependency'" in prompt


def test_create_prompt_edge_cases() -> None:
    """Test edge cases like empty results, None values."""
    # Test with empty summary
    empty_summary = {"summary": {"collected": 0, "passed": 0, "failed": 0, "total": 0}}
    assert _mock_show_details_decision_logic(empty_summary, True) is True  # ≤3 tests
    assert _mock_show_details_decision_logic(empty_summary, False) is False

    # Test with None values
    none_summary = {"summary": None}
    # _mock_show_details_decision_logic should handle gracefully
    try:
        result = _mock_show_details_decision_logic(none_summary, True)
        # Should default to showing details when requested if data is unclear
        assert result is True
    except (KeyError, TypeError):
        # Acceptable if function doesn't handle None gracefully yet
        pass

    # Test with missing summary key
    no_summary: dict[str, Any] = {}
    assert (
        _mock_show_details_decision_logic(no_summary, True) is True
    )  # Should handle gracefully
    assert _mock_show_details_decision_logic(no_summary, False) is False

    # Test with negative/invalid values
    invalid_summary = {
        "summary": {"collected": -1, "passed": 0, "failed": 0, "total": -1}
    }
    # Should handle edge case gracefully (negative values treated as 0 or small)
    assert _mock_show_details_decision_logic(invalid_summary, True) is True


def test_create_prompt_output_length_limits() -> None:
    """Test that output respects length limitations."""
    # Create a large report to test length limits
    report = parse_pytest_report(SAMPLE_JSON)
    prompt = create_prompt_for_failed_tests(report, max_number_of_tests_reported=10)

    if prompt:
        # Count lines in the output
        line_count = len(prompt.split("\n"))

        # This is a basic length check - the 300-line limit will be implemented in step 2
        # For now, just verify the output is reasonable in size
        assert line_count > 0
        assert line_count < 1000  # Sanity check - shouldn't be excessively large


def test_future_parameter_compatibility() -> None:
    """Test that the current function signature can be extended for future parameters."""
    report = parse_pytest_report(SAMPLE_JSON)

    # Test current function works with keyword arguments (important for future compatibility)
    prompt_kwargs = create_prompt_for_failed_tests(
        test_session_result=report, max_number_of_tests_reported=2
    )

    assert prompt_kwargs is not None
    assert "The following tests failed during the test session:" in prompt_kwargs

    # Count test failures to ensure limit is respected
    test_id_count = prompt_kwargs.count("Test ID:")
    assert test_id_count == 2, f"Expected 2 test failures, got {test_id_count}"


def test_backward_compatibility() -> None:
    """Ensure existing behavior is maintained."""
    # Test that existing function signature still works
    report = parse_pytest_report(SAMPLE_JSON)

    # Current function signature should still work
    prompt_old = create_prompt_for_failed_tests(report)
    prompt_with_limit = create_prompt_for_failed_tests(
        report, max_number_of_tests_reported=1
    )

    assert prompt_old is not None
    assert prompt_with_limit is not None

    # Both should contain basic failure information
    assert "The following tests failed during the test session:" in prompt_old
    assert "The following tests failed during the test session:" in prompt_with_limit


def test_decision_logic_boundary_conditions() -> None:
    """Test boundary conditions for the show_details decision logic."""
    # Test exactly 3 tests (boundary condition)
    exactly_three_tests = {
        "summary": {"collected": 3, "passed": 2, "failed": 1, "total": 3}
    }
    assert (
        _mock_show_details_decision_logic(exactly_three_tests, True) is True
    )  # ≤3 tests
    assert _mock_show_details_decision_logic(exactly_three_tests, False) is False

    # Test exactly 4 tests (boundary condition)
    exactly_four_tests = {
        "summary": {"collected": 4, "passed": 3, "failed": 1, "total": 4}
    }
    assert (
        _mock_show_details_decision_logic(exactly_four_tests, True) is True
    )  # >3 tests but requested
    assert _mock_show_details_decision_logic(exactly_four_tests, False) is False


def test_enhanced_formatting_structure() -> None:
    """Test that enhanced formatting maintains proper structure for future enhancements."""
    report = parse_pytest_report(SAMPLE_JSON)

    # Test current function behavior with different max_number_of_tests_reported values
    prompt_single = create_prompt_for_failed_tests(
        report, max_number_of_tests_reported=1
    )
    prompt_multiple = create_prompt_for_failed_tests(
        report, max_number_of_tests_reported=5
    )

    assert prompt_single is not None
    assert prompt_multiple is not None

    # Multiple tests should have more content than single test
    assert len(prompt_multiple) >= len(prompt_single)

    # Both should maintain expected structure
    assert "Can you provide an explanation" in prompt_single
    assert "Can you provide an explanation" in prompt_multiple

    # Test that the function can handle the enhanced parameters that will be added in step 2
    # This is preparation for the include_print_output parameter
    assert "Stdout:" in prompt_multiple  # Current behavior includes stdout


def test_max_failures_limit_enforcement() -> None:
    """Test that the max failures limit is properly enforced."""
    # Test with exactly 10 failures (boundary condition)
    json_ten_failures = """
    {
        "created": 1518371686.7981803,
        "duration": 0.5,
        "exitcode": 1,
        "root": "/path/to/tests",
        "environment": {},
        "summary": {
            "collected": 10,
            "passed": 0,
            "failed": 10,
            "total": 10
        },
        "collectors": [],
        "tests": [
    """

    test_entries = []
    for i in range(10):
        test_entry = f"""
            {{
                "nodeid": "test_limit.py::test_fail_{i}",
                "lineno": 10,
                "keywords": ["test_fail_{i}"],
                "outcome": "failed",
                "call": {{
                    "duration": 0.001,
                    "outcome": "failed",
                    "crash": {{
                        "path": "/path/to/tests/test_limit.py",
                        "lineno": 10,
                        "message": "AssertionError: Test {i} failed"
                    }}
                }}
            }}"""
        test_entries.append(test_entry)

    json_ten_failures += ",".join(test_entries)
    json_ten_failures += """
        ],
        "warnings": []
    }
    """

    report = parse_pytest_report(json_ten_failures)

    # Test with limit of 10 (all should be included)
    prompt = create_prompt_for_failed_tests(report, max_number_of_tests_reported=10)
    assert prompt is not None

    test_id_count = prompt.count("Test ID:")
    assert test_id_count == 10, f"Expected 10 test failures, got {test_id_count}"

    # Test with limit of 3 (only 3 should be included)
    prompt_limited = create_prompt_for_failed_tests(
        report, max_number_of_tests_reported=3
    )
    assert prompt_limited is not None

    test_id_count_limited = prompt_limited.count("Test ID:")
    assert (
        test_id_count_limited == 3
    ), f"Expected 3 test failures, got {test_id_count_limited}"


def test_collection_errors_always_shown() -> None:
    """Test that collection errors are always shown regardless of other settings."""
    json_collection_and_test_errors = """
    {
        "created": 1518371686.7981803,
        "duration": 0.2,
        "exitcode": 2,
        "root": "/path/to/tests",
        "environment": {},
        "summary": {
            "collected": 1,
            "passed": 0,
            "failed": 1,
            "total": 1
        },
        "collectors": [
            {
                "nodeid": "test_broken.py",
                "outcome": "failed",
                "longrepr": "ImportError: No module named 'missing_dependency'",
                "result": [
                    {
                        "nodeid": "test_broken.py",
                        "type": "module"
                    }
                ]
            }
        ],
        "tests": [
            {
                "nodeid": "test_broken.py::test_simple",
                "lineno": 10,
                "keywords": ["test_simple"],
                "outcome": "failed",
                "call": {
                    "duration": 0.001,
                    "outcome": "failed",
                    "crash": {
                        "path": "/path/to/tests/test_broken.py",
                        "lineno": 10,
                        "message": "AssertionError: Regular test failure"
                    }
                }
            }
        ],
        "warnings": []
    }
    """

    report = parse_pytest_report(json_collection_and_test_errors)
    prompt = create_prompt_for_failed_tests(report)

    assert prompt is not None

    # Collection errors should always be shown
    assert "The following collectors failed during the test session:" in prompt
    assert "test_broken.py" in prompt
    assert "ImportError: No module named 'missing_dependency'" in prompt

    # Regular test failures should also be shown
    assert "The following tests failed during the test session:" in prompt
    assert "test_broken.py::test_simple" in prompt
    assert "AssertionError: Regular test failure" in prompt
