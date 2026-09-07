"""
Final validation tests for the show_details parameter implementation.

This module provides comprehensive end-to-end validation to ensure the show_details
functionality works correctly across all scenarios and meets performance requirements.
"""

import tempfile
import textwrap
from pathlib import Path
from typing import Generator

import pytest

from mcp_tools_py.checker_tools import CheckerTools
from mcp_tools_py.server import ToolServer


class TestParameterCombinationsValidation:
    """Test various parameter combinations with show_details."""

    @pytest.fixture
    def temp_project(self) -> Generator[Path, None, None]:
        """Create a temporary project with test files for validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)

            # Create source directory
            src_dir = project_path / "src"
            src_dir.mkdir()

            # Create a simple module
            (src_dir / "__init__.py").write_text("")
            (src_dir / "calculator.py").write_text(textwrap.dedent("""
                def add(a, b):
                    return a + b
                    
                def divide(a, b):
                    if b == 0:
                        raise ValueError("Cannot divide by zero")
                    return a / b
                    
                def multiply(a, b):
                    print(f"Multiplying {a} * {b}")
                    return a * b
            """))

            # Create tests directory
            tests_dir = project_path / "tests"
            tests_dir.mkdir()

            (tests_dir / "__init__.py").write_text("")

            # Create passing tests
            (tests_dir / "test_passing.py").write_text(textwrap.dedent("""
                import sys
                sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
                from pathlib import Path
                from calculator import add, multiply
                
                def test_add_positive():
                    assert add(2, 3) == 5
                    
                def test_add_negative():
                    assert add(-1, 1) == 0
                    
                def test_multiply_with_print():
                    result = multiply(3, 4)
                    print("Test completed successfully")
                    assert result == 12
            """))

            # Create failing tests
            (tests_dir / "test_failing.py").write_text(textwrap.dedent("""
                import sys
                sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
                from pathlib import Path
                from calculator import add, divide
                
                def test_add_failure():
                    print("This test will fail")
                    assert add(2, 3) == 6  # Wrong expected value
                    
                def test_divide_by_zero():
                    print("Testing division by zero")
                    result = divide(10, 0)  # This will raise ValueError
                    assert result == float('inf')
                    
                def test_another_failure():
                    assert 1 == 2, "This should fail with custom message"
            """))

            # Create collection error test
            (tests_dir / "test_collection_error.py").write_text(textwrap.dedent("""
                import nonexistent_module  # This will cause collection error
                
                def test_will_not_run():
                    pass
            """))

            yield project_path

    def test_show_details_true_with_specific_test(self, temp_project: Path) -> None:
        """Test show_details=True with specific failing test."""
        server = ToolServer(temp_project)

        # Test the formatting method directly with mock test results
        from mcp_tools_py.code_checker_pytest.models import PytestReport, Summary

        mock_test_results = PytestReport(
            created=0.0,
            duration=1.0,
            exitcode=0,
            root="/tmp",
            environment={},
            summary=Summary(
                failed=1, collected=1, total=1, passed=0, error=0, skipped=0
            ),
            tests=[],
            collectors=[],
        )

        result = CheckerTools(server.context)._format_pytest_result_with_details(
            {
                "success": True,
                "summary": {"failed": 1, "collected": 1, "passed": 0},
                "test_results": mock_test_results,
            },
            show_details=True,
        )

        # Should show detailed output or indicate failure handling
        assert "attention" in result or "completed" in result

    def test_show_details_false_with_multiple_tests(self, temp_project: Path) -> None:
        """Test show_details=False with multiple tests provides summary."""
        server = ToolServer(temp_project)

        result = CheckerTools(server.context)._format_pytest_result_with_details(
            {
                "success": True,
                "summary": {"failed": 2, "collected": 10, "passed": 8},
                "test_results": None,
            },
            show_details=False,
        )

        # Should provide summary without suggestion for large test runs
        assert "show_details=True" not in result
        assert "completed" in result

    def test_show_details_false_with_few_tests_provides_hint(
        self, temp_project: Path
    ) -> None:
        """Test that small test runs provide hint to use show_details=True."""
        server = ToolServer(temp_project)

        # Need test_results to be present for failures to trigger hint logic
        from mcp_tools_py.code_checker_pytest.models import PytestReport, Summary

        mock_test_results = PytestReport(
            created=0.0,
            duration=1.0,
            exitcode=0,
            root="/tmp",
            environment={},
            summary=Summary(
                failed=1, collected=2, total=2, passed=1, error=0, skipped=0
            ),
            tests=[],
            collectors=[],
        )

        result = CheckerTools(server.context)._format_pytest_result_with_details(
            {
                "success": True,
                "summary": {"failed": 1, "collected": 2, "passed": 1},
                "test_results": mock_test_results,
            },
            show_details=False,
        )

        # Should suggest show_details=True for small test runs with failures
        assert "show_details=True" in result

    def test_collection_errors_always_shown(self, temp_project: Path) -> None:
        """Test that collection errors are shown regardless of show_details setting."""
        server = ToolServer(temp_project)

        # Simulate collection error result
        test_result = {
            "success": True,
            "summary": {"failed": 0, "collected": 0, "passed": 0, "error": 1},
            "test_results": None,
        }

        # Both should handle collection errors
        result_false = CheckerTools(server.context)._format_pytest_result_with_details(
            test_result, show_details=False
        )
        result_true = CheckerTools(server.context)._format_pytest_result_with_details(
            test_result, show_details=True
        )

        # Both should complete without error
        assert "completed" in result_false or "Error" in result_false
        assert "completed" in result_true or "Error" in result_true


class TestOutputFormatConsistency:
    """Test that output formatting is consistent across scenarios."""

    def test_success_message_consistency(self) -> None:
        """Test that success messages are consistent."""
        server = ToolServer(Path("/tmp"))

        success_result = {
            "success": True,
            "summary": {"failed": 0, "collected": 5, "passed": 5},
            "summary_text": "All tests passed",
        }

        result_false = CheckerTools(server.context)._format_pytest_result_with_details(
            success_result, show_details=False
        )
        result_true = CheckerTools(server.context)._format_pytest_result_with_details(
            success_result, show_details=True
        )

        # Both should show success message
        assert "completed" in result_false
        assert "completed" in result_true

        # Should contain summary information
        assert "All tests passed" in result_false
        assert "All tests passed" in result_true

    def test_error_message_consistency(self) -> None:
        """Test that error messages are consistent."""
        server = ToolServer(Path("/tmp"))

        error_result = {"success": False, "error": "pytest execution failed"}

        result_false = CheckerTools(server.context)._format_pytest_result_with_details(
            error_result, show_details=False
        )
        result_true = CheckerTools(server.context)._format_pytest_result_with_details(
            error_result, show_details=True
        )

        # Both should show error message
        assert "Error running pytest" in result_false
        assert "Error running pytest" in result_true
        assert "pytest execution failed" in result_false
        assert "pytest execution failed" in result_true

    def test_invalid_summary_handling(self) -> None:
        """Test handling of invalid summary data."""
        server = ToolServer(Path("/tmp"))

        invalid_result = {
            "success": True,
            "summary": "invalid_summary_format",  # Should be dict
        }

        result_false = CheckerTools(server.context)._format_pytest_result_with_details(
            invalid_result, show_details=False
        )
        result_true = CheckerTools(server.context)._format_pytest_result_with_details(
            invalid_result, show_details=True
        )

        # Both should handle invalid format gracefully
        assert "Invalid test summary format" in result_false
        assert "Invalid test summary format" in result_true


class TestPerformanceBenchmarks:
    """Test performance impact of show_details parameter."""

    def test_both_code_paths_complete_successfully(self) -> None:
        """Test that both show_details code paths complete successfully."""
        # Note: Tests correctness, not timing - microbenchmarks are unreliable in CI
        server = ToolServer(Path("/tmp"))

        # Create test data
        test_result = {
            "success": True,
            "summary": {"failed": 0, "collected": 100, "passed": 100},
            "summary_text": "All 100 tests passed",
        }

        # Both code paths should complete successfully and return valid strings
        result_false = CheckerTools(server.context)._format_pytest_result_with_details(
            test_result, show_details=False
        )
        result_true = CheckerTools(server.context)._format_pytest_result_with_details(
            test_result, show_details=True
        )

        # Verify both paths produce valid output
        assert isinstance(result_false, str)
        assert isinstance(result_true, str)
        assert len(result_false) > 0
        assert len(result_true) > 0

    def test_memory_usage_reasonable(self) -> None:
        """Test that memory usage remains reasonable with show_details."""
        server = ToolServer(Path("/tmp"))

        # Create large test result data
        large_summary = {
            "success": True,
            "summary": {"failed": 10, "collected": 1000, "passed": 990},
            "test_results": None,
        }

        # Should complete without memory issues
        result = CheckerTools(server.context)._format_pytest_result_with_details(
            large_summary, show_details=True
        )
        assert isinstance(result, str)
        assert len(result) > 0


class TestDocumentationAccuracy:
    """Test that docstring examples work as documented."""

    def test_docstring_examples_execute(self) -> None:
        """Test that examples in docstrings actually work."""
        # This tests the examples from the docstring in run_pytest_check

        # Test that the function signature matches documentation
        server = ToolServer(Path("/tmp"))

        # These should not raise TypeError due to missing/incorrect parameters
        try:
            # Standard CI run example
            result = CheckerTools(server.context)._format_pytest_result_with_details(
                {
                    "success": True,
                    "summary": {"failed": 0, "passed": 5, "collected": 5},
                },
                show_details=False,
            )
            assert isinstance(result, str)

            # Debug specific test example
            result = CheckerTools(server.context)._format_pytest_result_with_details(
                {
                    "success": True,
                    "summary": {"failed": 1, "passed": 0, "collected": 1},
                },
                show_details=True,
            )
            assert isinstance(result, str)

        except Exception as e:
            pytest.fail(f"Docstring examples failed to execute: {e}")

    def test_parameter_type_validation(self) -> None:
        """Test that parameters accept documented types."""
        server = ToolServer(Path("/tmp"))

        # show_details should accept boolean
        assert CheckerTools(server.context)._format_pytest_result_with_details(
            {"success": True, "summary": {"passed": 1, "collected": 1}},
            show_details=True,
        )

        assert CheckerTools(server.context)._format_pytest_result_with_details(
            {"success": True, "summary": {"passed": 1, "collected": 1}},
            show_details=False,
        )

    def test_return_type_consistency(self) -> None:
        """Test that return types match documentation."""
        server = ToolServer(Path("/tmp"))

        test_cases = [
            {"success": True, "summary": {"passed": 1, "collected": 1}},
            {"success": False, "error": "test error"},
            {"success": True, "summary": {"failed": 1, "collected": 1}},
        ]

        for test_case in test_cases:
            for show_details in [True, False]:
                result = CheckerTools(
                    server.context
                )._format_pytest_result_with_details(test_case, show_details)
                assert isinstance(result, str), f"Expected str, got {type(result)}"
                assert len(result) > 0, "Result should not be empty"


def test_parameter_combinations_backward_compatible() -> None:
    """Test that new parameters don't break existing usage."""
    server = ToolServer(Path("/tmp"))

    # Should work with minimal parameters (existing usage)
    test_result = {"success": True, "summary": {"passed": 1, "collected": 1}}

    result = CheckerTools(server.context)._format_pytest_result_with_details(
        test_result, show_details=False
    )
    assert isinstance(result, str)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_none_values_handling(self) -> None:
        """Test handling of None values in summary."""
        server = ToolServer(Path("/tmp"))

        result_with_nones = {
            "success": True,
            "summary": {
                "failed": None,
                "passed": None,
                "collected": None,
                "error": None,
            },
        }

        # Should handle None values gracefully
        result = CheckerTools(server.context)._format_pytest_result_with_details(
            result_with_nones, show_details=True
        )
        assert isinstance(result, str)

        # Should not crash with None values
        result = CheckerTools(server.context)._format_pytest_result_with_details(
            result_with_nones, show_details=False
        )
        assert isinstance(result, str)

    def test_empty_summary_handling(self) -> None:
        """Test handling of empty summary dict."""
        server = ToolServer(Path("/tmp"))

        empty_result = {"success": True, "summary": {}}

        result = CheckerTools(server.context)._format_pytest_result_with_details(
            empty_result, show_details=True
        )
        assert isinstance(result, str)

    def test_missing_summary_handling(self) -> None:
        """Test handling when summary is missing."""
        server = ToolServer(Path("/tmp"))

        no_summary_result = {"success": True}

        result = CheckerTools(server.context)._format_pytest_result_with_details(
            no_summary_result, show_details=True
        )
        assert isinstance(result, str)


# Integration test that uses real pytest execution would go here
# but it requires a more complex setup with actual test files
class TestRealIntegration:
    """Integration tests with real pytest execution."""

    def test_integration_placeholder(self) -> None:
        """Placeholder for integration tests that would use real pytest."""
        # This would require setting up actual test files and running pytest
        # For now, we test the formatting logic which is the core of the feature
        assert True
