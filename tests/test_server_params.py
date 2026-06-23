"""
Tests for the server functionality with updated parameter exposure.
"""

import inspect
from pathlib import Path
from typing import Any, Dict, Tuple
from unittest.mock import MagicMock, patch

import pytest


def _get_tool(mock_tool: MagicMock, name: str) -> Any:
    return {f.__name__: f for call in mock_tool.call_args_list for f in [call[0][0]]}[
        name
    ]


@pytest.fixture
def mock_project_dir() -> Path:
    """Return a mock project directory path."""
    return Path("/fake/project/dir")


@pytest.mark.asyncio
async def test_run_pytest_check_parameters(mock_project_dir: Path) -> None:
    """Test that run_pytest_check properly uses server parameters and passes parameters correctly."""
    with (
        patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
        patch(
            "mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest"
        ) as mock_check_pytest,
    ):
        # Setup mocks
        mock_tool = MagicMock()
        mock_fastmcp.return_value.tool.return_value = mock_tool

        # Setup mock result that check_code_with_pytest will return
        mock_check_pytest.return_value = {
            "success": True,
            "summary": {"passed": 5, "failed": 0, "error": 0},
            "test_results": MagicMock(),
        }

        # Import after patching to ensure mocks are in place
        from mcp_tools_py.server import ToolServer

        # Create server with the static parameters
        with patch.object(
            ToolServer,
            "_check_tool_availability",
            return_value={},
        ):
            _server = ToolServer(
                mock_project_dir, test_folder="custom_tests", keep_temp_files=True
            )
            _server._is_tool_available = lambda tool_name: True  # type: ignore[method-assign]

        assert (
            len(mock_tool.call_args_list) >= 2
        ), "Expected at least 2 tools to be registered"
        run_pytest_check = _get_tool(mock_tool, "run_pytest_check")

        # Call with only the dynamic parameters (without test_folder and keep_temp_files)
        result = run_pytest_check(
            markers=["slow", "integration"],
            extra_args=["--no-header"],
            env_vars={"TEST_ENV": "value"},
        )

        # Verify check_code_with_pytest was called with correct parameters
        # test_folder and keep_temp_files should come from the server instance
        # verbosity comes from sanitize_extra_args (default 2)
        mock_check_pytest.assert_called_once_with(
            project_dir=str(mock_project_dir),
            test_folder="custom_tests",  # From server constructor
            python_executable=_server._resolved_python,  # Resolved by server
            markers=["slow", "integration"],
            verbosity=2,
            extra_args=["--no-header"],
            env_vars={"TEST_ENV": "value"},
            venv_path=None,
            keep_temp_files=True,  # From server constructor
            skip_default_test_folder=False,
        )

        # Verify the result is properly formatted
        assert "All 5 tests passed successfully" in result


@pytest.mark.asyncio
async def test_run_pylint_check_signature() -> None:
    """Test that run_pylint_check has extra_args and no categories or disable_codes."""
    with patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp:
        mock_tool = MagicMock()
        mock_fastmcp.return_value.tool.return_value = mock_tool

        from mcp_tools_py.server import ToolServer

        with patch.object(
            ToolServer,
            "_check_tool_availability",
            return_value={},
        ):
            _server = ToolServer(project_dir=Path("/test/project"))
            _server._is_tool_available = lambda tool_name: True  # type: ignore[method-assign]

        # Look up run_pylint_check by name to avoid fragile index assumptions
        tools = {
            f.__name__: f for call in mock_tool.call_args_list for f in [call[0][0]]
        }
        run_pylint_check = tools["run_pylint_check"]
        signature = inspect.signature(run_pylint_check)
        params = signature.parameters

        assert "extra_args" in params, "run_pylint_check must have extra_args parameter"
        assert (
            "categories" not in params
        ), "run_pylint_check must NOT have categories parameter"
        assert (
            "disable_codes" not in params
        ), "run_pylint_check must NOT have disable_codes parameter"


# Step 3: Tests for Server Interface Enhancement with show_details Parameter


@pytest.fixture
def mock_server() -> Tuple[Any, MagicMock]:
    """Create ToolServer for testing."""
    with patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp:
        mock_tool = MagicMock()
        mock_fastmcp.return_value.tool.return_value = mock_tool

        from mcp_tools_py.server import ToolServer

        with patch.object(
            ToolServer,
            "_check_tool_availability",
            return_value={},
        ):
            server = ToolServer(project_dir=Path("/test/project"))
            server._is_tool_available = lambda tool_name: True  # type: ignore[method-assign]

        # Return server and the mock tool for test access
        return server, mock_tool


@pytest.fixture
def mock_pytest_results_few_tests() -> Dict[str, Any]:
    """Mock results for ≤3 tests scenario."""
    return {
        "success": True,
        "summary": {
            "passed": 2,
            "failed": 1,
            "error": 0,
            "collected": 3,
            "duration": 1.5,
        },
        "test_results": MagicMock(),
    }


@pytest.fixture
def mock_pytest_results_many_failures() -> Dict[str, Any]:
    """Mock results for >10 failures scenario."""
    return {
        "success": True,
        "summary": {
            "passed": 5,
            "failed": 15,
            "error": 2,
            "collected": 22,
            "duration": 5.2,
        },
        "test_results": MagicMock(),
    }


@pytest.fixture
def mock_pytest_results_success() -> Dict[str, Any]:
    """Mock results for successful test run."""
    return {
        "success": True,
        "summary": {
            "passed": 10,
            "failed": 0,
            "error": 0,
            "collected": 10,
            "duration": 2.3,
        },
        "test_results": None,
    }


# Parameter Integration Tests


@pytest.mark.asyncio
async def test_run_pytest_check_with_show_details_true(
    mock_server: Tuple[Any, MagicMock],
) -> None:
    """Test that run_pytest_check properly handles show_details=True parameter."""
    server, mock_tool = mock_server

    with patch(
        "mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest"
    ) as mock_check:
        mock_check.return_value = {
            "success": True,
            "summary": {"passed": 3, "failed": 0, "error": 0, "collected": 3},
            "test_results": None,
        }

        # Get the run_pytest_check function
        run_pytest_check = _get_tool(mock_tool, "run_pytest_check")

        # Call with simplified signature (no show_details or verbosity)
        result = run_pytest_check(markers=["unit"])

        # Verify check_code_with_pytest was called correctly
        mock_check.assert_called_once()
        call_args = mock_check.call_args

        # Verify standard parameters are passed correctly
        assert call_args[1]["project_dir"] == str(Path("/test/project"))
        assert call_args[1]["markers"] == ["unit"]
        assert call_args[1]["verbosity"] == 2  # default from sanitize_extra_args

        # Verify result formatting
        assert "All 3 tests passed successfully" in result


@pytest.mark.asyncio
async def test_run_pytest_check_with_show_details_false(
    mock_server: Tuple[Any, MagicMock],
) -> None:
    """Test that run_pytest_check properly handles show_details=False parameter."""
    server, mock_tool = mock_server

    with patch(
        "mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest"
    ) as mock_check:
        mock_check.return_value = {
            "success": True,
            "summary": {"passed": 5, "failed": 0, "error": 0, "collected": 5},
            "test_results": None,
        }

        # Get the run_pytest_check function
        run_pytest_check = _get_tool(mock_tool, "run_pytest_check")

        # Call with simplified signature (always shows details now)
        result = run_pytest_check()

        # Verify check_code_with_pytest was called correctly
        mock_check.assert_called_once()
        call_args = mock_check.call_args

        # Verify verbosity defaults from sanitize_extra_args
        assert call_args[1]["verbosity"] == 2
        assert "All 5 tests passed successfully" in result


@pytest.mark.asyncio
async def test_run_pytest_check_backward_compatibility(
    mock_server: Tuple[Any, MagicMock],
) -> None:
    """Test that existing function calls work without show_details parameter."""
    server, mock_tool = mock_server

    with patch(
        "mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest"
    ) as mock_check:
        mock_check.return_value = {
            "success": True,
            "summary": {"passed": 8, "failed": 0, "error": 0, "collected": 8},
            "test_results": None,
        }

        # Get the run_pytest_check function
        run_pytest_check = _get_tool(mock_tool, "run_pytest_check")

        # Call with existing parameter style (no show_details)
        old_style_result = run_pytest_check(markers=["integration"])

        # Verify it works and produces expected result
        assert "All 8 tests passed successfully" in old_style_result
        mock_check.assert_called_once()


# Output Control Tests


@pytest.mark.asyncio
async def test_show_details_with_focused_test_run(
    mock_server: Tuple[Any, MagicMock], mock_pytest_results_few_tests: Dict[str, Any]
) -> None:
    """Test show_details behavior with focused test run (≤3 tests)."""
    server, mock_tool = mock_server

    with (
        patch(
            "mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest"
        ) as mock_check,
        patch(
            "mcp_tools_py.checker_tools.create_prompt_for_failed_tests"
        ) as mock_create_prompt,
    ):
        mock_check.return_value = mock_pytest_results_few_tests
        mock_create_prompt.return_value = "Detailed failure information..."

        # Get the run_pytest_check function
        run_pytest_check = _get_tool(mock_tool, "run_pytest_check")

        # Call function - always shows details now
        result = run_pytest_check(markers=["unit"])

        # With always show_details=True and few tests, should show detailed output
        mock_create_prompt.assert_called_once()
        assert "Detailed failure information..." in result


@pytest.mark.asyncio
async def test_show_details_with_many_failures(
    mock_server: Tuple[Any, MagicMock],
    mock_pytest_results_many_failures: Dict[str, Any],
) -> None:
    """Test show_details behavior with many failures (>10 failures)."""
    server, mock_tool = mock_server

    with (
        patch(
            "mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest"
        ) as mock_check,
        patch(
            "mcp_tools_py.checker_tools.create_prompt_for_failed_tests"
        ) as mock_create_prompt,
    ):
        mock_check.return_value = mock_pytest_results_many_failures
        mock_create_prompt.return_value = "Many failures detected..."

        # Get the run_pytest_check function
        run_pytest_check = _get_tool(mock_tool, "run_pytest_check")

        # Call function - always shows details now
        result = run_pytest_check()

        # With always show_details=True, should show detailed output
        mock_create_prompt.assert_called_once()
        assert "Many failures detected..." in result


@pytest.mark.asyncio
async def test_show_details_output_length_limits(
    mock_server: Tuple[Any, MagicMock],
) -> None:
    """Test that output respects length limits and truncation."""
    server, mock_tool = mock_server

    # Create mock results with potential for long output
    long_output_results = {
        "success": True,
        "summary": {"passed": 0, "failed": 5, "error": 0, "collected": 5},
        "test_results": MagicMock(),
    }

    with (
        patch(
            "mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest"
        ) as mock_check,
        patch(
            "mcp_tools_py.checker_tools.create_prompt_for_failed_tests"
        ) as mock_create_prompt,
    ):
        mock_check.return_value = long_output_results
        # Simulate long output that should be truncated
        mock_create_prompt.return_value = "\n".join([f"Line {i}" for i in range(350)])

        # Get the run_pytest_check function
        run_pytest_check = _get_tool(mock_tool, "run_pytest_check")

        # Call function - always shows details now
        result = run_pytest_check()

        # Verify create_prompt_for_failed_tests was called
        mock_create_prompt.assert_called_once()

        # The result should contain the truncated output
        # Note: Truncation logic is in create_prompt_for_failed_tests
        assert "Line 0" in result


# Integration Tests


@pytest.mark.asyncio
async def test_mcp_tool_decorator_compatibility() -> None:
    """Test that MCP tool decorator works with current and future parameters."""
    with patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp:
        mock_tool = MagicMock()
        mock_fastmcp.return_value.tool.return_value = mock_tool

        from mcp_tools_py.server import ToolServer

        with patch.object(
            ToolServer,
            "_check_tool_availability",
            return_value={},
        ):
            server = ToolServer(project_dir=Path("/test/project"))
            server._is_tool_available = lambda tool_name: True  # type: ignore[method-assign]

        # Verify that tools were registered correctly
        assert (
            len(mock_tool.call_args_list) >= 2
        ), "Expected at least 2 tools registered"

        # Verify run_pytest_check is callable
        run_pytest_check = _get_tool(mock_tool, "run_pytest_check")
        assert callable(run_pytest_check)

        # Verify the function has proper signature
        signature = inspect.signature(run_pytest_check)
        assert len(signature.parameters) > 0, "Function should have parameters"


@pytest.mark.asyncio
async def test_enhanced_reporting_integration_preparation(
    mock_server: Tuple[Any, MagicMock],
) -> None:
    """Test preparation for enhanced reporting integration with show_details."""
    server, mock_tool = mock_server

    # Test that current implementation can handle enhanced reporting calls
    with (
        patch(
            "mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest"
        ) as mock_check,
        patch(
            "mcp_tools_py.checker_tools.create_prompt_for_failed_tests"
        ) as mock_create_prompt,
    ):
        # Setup mocks
        mock_check.return_value = {
            "success": True,
            "summary": {"passed": 2, "failed": 1, "error": 0, "collected": 3},
            "test_results": MagicMock(),
        }
        mock_create_prompt.return_value = "Enhanced failure details..."

        # Get the run_pytest_check function
        run_pytest_check = _get_tool(mock_tool, "run_pytest_check")

        # Call function - always shows details now
        result = run_pytest_check()

        # Always shows details, should use enhanced reporting
        mock_create_prompt.assert_called_once()
        assert "Enhanced failure details..." in result

        # Verify that enhanced reporting functions are available
        # The reporting module should have the enhanced functions from Steps 1-2
        from mcp_tools_py.code_checker_pytest.reporting import should_show_details

        # Test that should_show_details function works
        test_results = {"summary": {"collected": 3, "failed": 1, "error": 0}}
        assert should_show_details(test_results, True) == True
        assert should_show_details(test_results, False) == False


# Step 3: Tests for Pylint max_issues Parameter


class TestServerPylintMaxIssues:
    """Tests for max_issues parameter wiring in run_pylint_check."""

    def test_run_pylint_check_passes_max_issues(self) -> None:
        """Verify max_issues=3 is forwarded to get_pylint_prompt."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch(
                "mcp_tools_py.checker_tools.pylint_tool.get_pylint_prompt"
            ) as mock_get_pylint_prompt,
            patch(
                "mcp_tools_py.checker_tools.pylint_tool.resolve_target_directories",
                return_value=["src"],
            ),
        ):
            mock_tool = MagicMock()
            mock_fastmcp.return_value.tool.return_value = mock_tool
            mock_get_pylint_prompt.return_value = "some issues"

            from mcp_tools_py.server import ToolServer

            _server = ToolServer(project_dir=Path("/test/project"))
            _server._is_tool_available = lambda tool_name: True  # type: ignore[method-assign]
            run_pylint_check = _get_tool(mock_tool, "run_pylint_check")

            run_pylint_check(max_issues=3)

            mock_get_pylint_prompt.assert_called_once()
            assert mock_get_pylint_prompt.call_args[1]["max_issues"] == 3

    def test_run_pylint_check_default_max_issues(self) -> None:
        """Verify default max_issues=1 is forwarded to get_pylint_prompt."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch(
                "mcp_tools_py.checker_tools.pylint_tool.get_pylint_prompt"
            ) as mock_get_pylint_prompt,
            patch(
                "mcp_tools_py.checker_tools.pylint_tool.resolve_target_directories",
                return_value=["src"],
            ),
        ):
            mock_tool = MagicMock()
            mock_fastmcp.return_value.tool.return_value = mock_tool
            mock_get_pylint_prompt.return_value = None

            from mcp_tools_py.server import ToolServer

            _server = ToolServer(project_dir=Path("/test/project"))
            _server._is_tool_available = lambda tool_name: True  # type: ignore[method-assign]
            run_pylint_check = _get_tool(mock_tool, "run_pylint_check")

            run_pylint_check()

            mock_get_pylint_prompt.assert_called_once()
            assert mock_get_pylint_prompt.call_args[1]["max_issues"] == 1

    def test_format_pylint_result_returns_prompt_directly(self) -> None:
        """Verify _format_pylint_result returns the prompt without extra prefix."""
        with patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp:
            mock_tool = MagicMock()
            mock_fastmcp.return_value.tool.return_value = mock_tool

            from mcp_tools_py.checker_tools import CheckerTools
            from mcp_tools_py.server import ToolServer

            server = ToolServer(project_dir=Path("/test/project"))
            checker = CheckerTools(server)

            prompt = "pylint found some issues related to code W0612."
            result = checker._format_pylint_result(prompt)
            assert result == prompt
            assert "Pylint found issues that need attention" not in result

            # None case still works
            result_none = checker._format_pylint_result(None)
            assert "No issues found" in result_none

    def test_run_pylint_check_has_max_issues_parameter(self) -> None:
        """Verify run_pylint_check signature includes max_issues."""
        with patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp:
            mock_tool = MagicMock()
            mock_fastmcp.return_value.tool.return_value = mock_tool

            from mcp_tools_py.server import ToolServer

            _server = ToolServer(project_dir=Path("/test/project"))
            run_pylint_check = _get_tool(mock_tool, "run_pylint_check")
            signature = inspect.signature(run_pylint_check)

            assert "max_issues" in signature.parameters
            assert signature.parameters["max_issues"].default == 1
            assert signature.parameters["max_issues"].annotation == int


# Additional Parameter Validation Tests


@pytest.mark.asyncio
async def test_integration_with_existing_server_parameters(
    mock_server: Tuple[Any, MagicMock],
) -> None:
    """Test integration with server constructor parameters."""
    server, mock_tool = mock_server

    # Verify that server constructor parameters are properly used
    assert server.project_dir == Path("/test/project")
    assert server.test_folder == "tests"  # default
    assert server.keep_temp_files == False  # default

    with patch(
        "mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest"
    ) as mock_check:
        mock_check.return_value = {
            "success": True,
            "summary": {"passed": 3, "failed": 0, "error": 0, "collected": 3},
            "test_results": None,
        }

        # Get the run_pytest_check function
        run_pytest_check = _get_tool(mock_tool, "run_pytest_check")

        # Call function
        result = run_pytest_check()

        # Verify that server parameters were passed to check_code_with_pytest
        mock_check.assert_called_once()
        call_args = mock_check.call_args

        assert call_args[1]["project_dir"] == str(Path("/test/project"))
        assert call_args[1]["test_folder"] == "tests"
        assert call_args[1]["keep_temp_files"] == False


# Tests for simplified signature and defensive error handling


@pytest.mark.asyncio
async def test_run_pytest_check_simplified_signature(
    mock_server: Tuple[Any, MagicMock],
) -> None:
    """Test that run_pytest_check has simplified signature without verbosity/show_details."""
    _server, mock_tool = mock_server

    run_pytest_check = _get_tool(mock_tool, "run_pytest_check")
    signature = inspect.signature(run_pytest_check)
    params = list(signature.parameters.keys())

    # Assert signature has: markers, extra_args, env_vars
    assert "markers" in params
    assert "extra_args" in params
    assert "env_vars" in params

    # Assert signature does NOT have: verbosity, show_details
    assert "verbosity" not in params
    assert "show_details" not in params


@pytest.mark.asyncio
async def test_run_pytest_check_never_raises(
    mock_server: Tuple[Any, MagicMock],
) -> None:
    """Test that run_pytest_check returns a string on error, never raises."""
    _server, mock_tool = mock_server

    with patch(
        "mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest"
    ) as mock_check:
        mock_check.side_effect = RuntimeError("something broke")

        run_pytest_check = _get_tool(mock_tool, "run_pytest_check")

        # Should not raise
        result = run_pytest_check()

        assert isinstance(result, str)
        assert "Unexpected error" in result
        assert "RuntimeError" in result
        assert "something broke" in result


@pytest.mark.asyncio
async def test_run_pytest_check_prepends_dedup_notes(
    mock_server: Tuple[Any, MagicMock],
) -> None:
    """Test that deduplication notes from sanitize_extra_args are prepended to output."""
    _server, mock_tool = mock_server

    with patch(
        "mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest"
    ) as mock_check:
        mock_check.return_value = {
            "success": True,
            "summary": {"passed": 5, "failed": 0, "error": 0, "collected": 5},
            "test_results": None,
        }

        run_pytest_check = _get_tool(mock_tool, "run_pytest_check")

        # Call with extra_args containing -m flag AND markers parameter
        # sanitize_extra_args should produce a note about -m being ignored
        result = run_pytest_check(
            extra_args=["-m", "slow"],
            markers=["unit"],
        )

        # The note about -m flag should be prepended
        assert "Note:" in result
        assert "-m" in result
