"""Tests for CheckerTools extraction from server.py."""

import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from mcp_tools_py.checker_tools import CheckerTools
from mcp_tools_py.utils.python_environment import PythonEnvironment
from mcp_tools_py.utils.tool_context import ToolContext
from tests.test_tool_availability._helpers import _dummy_python


def _remove_console_script(context: ToolContext, tool_name: str) -> None:
    """Make a console-script tool unavailable by deleting its binary."""
    binary = context.tool_environment.binary(tool_name)
    assert binary is not None
    binary.unlink()


# --- Vulture handler tests ---


def _capture_vulture(
    tool_context: ToolContext,
) -> Any:
    """Register checker tools and capture the run_vulture_check function."""
    captured_fns: dict[str, Any] = {}

    def capture(fn: Any) -> Any:
        captured_fns[fn.__name__] = fn
        return fn

    mock_mcp = MagicMock()
    mock_mcp.tool.return_value = capture
    checker = CheckerTools(tool_context)
    checker.register(mock_mcp)
    return captured_fns["run_vulture_check"]


def test_vulture_unavailable_returns_error(tool_context: ToolContext) -> None:
    """When vulture is not available, return an error message."""
    _remove_console_script(tool_context, "vulture")
    run_vulture = _capture_vulture(tool_context)
    result = run_vulture()
    assert "vulture is not available" in result


def test_vulture_success_returns_raw_output(tool_context: ToolContext) -> None:
    """When vulture succeeds, return raw stdout."""
    run_vulture = _capture_vulture(tool_context)

    with (
        patch(
            "mcp_tools_py.checker_tools.vulture_tool.run_vulture",
            return_value="No dead code found!",
        ),
        patch(
            "mcp_tools_py.checker_tools.vulture_tool.resolve_target_directories",
            return_value=["src"],
        ),
        patch.object(Path, "exists", return_value=False),
    ):
        result = run_vulture()

    assert "No dead code found!" in result


def test_vulture_failure_returns_raw_output(tool_context: ToolContext) -> None:
    """When vulture fails, return raw stdout+stderr."""
    run_vulture = _capture_vulture(tool_context)

    with (
        patch(
            "mcp_tools_py.checker_tools.vulture_tool.run_vulture",
            return_value="vulture: error: invalid config",
        ),
        patch(
            "mcp_tools_py.checker_tools.vulture_tool.resolve_target_directories",
            return_value=["src"],
        ),
        patch.object(Path, "exists", return_value=False),
    ):
        result = run_vulture()

    assert "vulture: error: invalid config" in result


def test_vulture_passes_whitelist_to_runner(tool_context: ToolContext) -> None:
    """When whitelist file exists, it is passed to run_vulture_check."""
    run_vulture = _capture_vulture(tool_context)

    with (
        patch(
            "mcp_tools_py.checker_tools.vulture_tool.run_vulture",
            return_value="ok",
        ) as mock_runner,
        patch(
            "mcp_tools_py.checker_tools.vulture_tool.resolve_target_directories",
            return_value=["src"],
        ),
        patch.object(Path, "exists", return_value=True),
    ):
        run_vulture()

    whitelist_str = str(tool_context.project_dir / "vulture_whitelist.py")
    assert mock_runner.call_args[1]["whitelist_path"] == whitelist_str


def test_vulture_passes_resolved_timeout(tool_context: ToolContext) -> None:
    """The resolved timeout is passed to run_vulture_check."""
    run_vulture = _capture_vulture(tool_context)

    with (
        patch(
            "mcp_tools_py.checker_tools.vulture_tool.run_vulture",
            return_value="ok",
        ) as mock_runner,
        patch(
            "mcp_tools_py.checker_tools.vulture_tool.resolve_target_directories",
            return_value=["src"],
        ),
        patch.object(Path, "exists", return_value=False),
    ):
        run_vulture()

    assert mock_runner.call_args[1]["timeout_seconds"] == 120


# --- Lint-imports handler tests ---


def test_lint_imports_passes_resolved_timeout(tool_context: ToolContext) -> None:
    """The resolved timeout and the project interpreter reach the runner."""
    run_lint_imports = _capture_tool(tool_context, "run_lint_imports_check")

    with patch(
        "mcp_tools_py.checker_tools.lint_imports_tool.run_lint_imports_check_impl",
        return_value="=== PASSED ===",
    ) as mock_runner:
        run_lint_imports()

    assert mock_runner.call_args.kwargs["timeout_seconds"] == 120
    assert mock_runner.call_args.kwargs["python_executable"] == str(
        tool_context.environment.interpreter
    )


def test_lint_imports_binary_comes_from_the_tool_env(tmp_path: Path) -> None:
    """The script is taken from the tool env, not from --python-executable.

    The shared fixture backs both environments with one directory, so only a
    context where they differ can tell the two lookups apart.  The project env
    holds no lint-imports, so a registrar still reading `context.environment`
    short-circuits and never calls the impl at all.
    """
    proj_base, tool_base = tmp_path / "projenv", tmp_path / "toolenv"
    proj_base.mkdir()
    tool_base.mkdir()
    project_env = PythonEnvironment(Path(_dummy_python(proj_base)))
    tool_env = PythonEnvironment(Path(_dummy_python(tool_base, "lint-imports")))
    context = ToolContext(
        project_dir=tmp_path,
        environment=project_env,
        tool_environment=tool_env,
    )
    run_lint_imports = _capture_tool(context, "run_lint_imports_check")

    with patch(
        "mcp_tools_py.checker_tools.lint_imports_tool.run_lint_imports_check_impl",
        return_value="=== PASSED ===",
    ) as mock_runner:
        run_lint_imports()

    assert mock_runner.call_args.kwargs["lint_imports_binary"] == str(
        tool_env.binary("lint-imports")
    )
    assert mock_runner.call_args.kwargs["python_executable"] == str(
        project_env.interpreter
    )


# --- Bandit handler tests ---


def test_bandit_passes_resolved_timeout(tool_context: ToolContext) -> None:
    """The resolved timeout is passed to run_bandit_check_impl."""
    run_bandit = _capture_tool(tool_context, "run_bandit_check")

    with (
        patch(
            "mcp_tools_py.checker_tools.bandit_tool.run_bandit_check_impl",
        ) as mock_runner,
        patch(
            "mcp_tools_py.checker_tools.bandit_tool.resolve_target_directories",
            return_value=["src"],
        ),
    ):
        mock_runner.return_value.error = None
        run_bandit()

    assert mock_runner.call_args[1]["timeout_seconds"] == 120


# --- Ruff handler tests ---


def test_ruff_check_passes_resolved_timeout(tool_context: ToolContext) -> None:
    """The resolved timeout is passed to run_ruff_check_impl."""
    run_ruff_check = _capture_tool(tool_context, "run_ruff_check")

    with (
        patch(
            "mcp_tools_py.checker_tools.ruff_check_tool.run_ruff_check_impl",
            return_value="ok",
        ) as mock_runner,
        patch(
            "mcp_tools_py.checker_tools.ruff_check_tool.resolve_target_directories",
            return_value=["src"],
        ),
    ):
        run_ruff_check()

    assert mock_runner.call_args[1]["timeout_seconds"] == 120


def test_ruff_fix_passes_resolved_timeout(tool_context: ToolContext) -> None:
    """The resolved timeout is passed to run_ruff_fix_impl."""
    run_ruff_fix = _capture_tool(tool_context, "run_ruff_fix")

    with (
        patch(
            "mcp_tools_py.checker_tools.ruff_fix_tool.run_ruff_fix_impl",
            return_value="ok",
        ) as mock_runner,
        patch(
            "mcp_tools_py.checker_tools.ruff_fix_tool.resolve_target_directories",
            return_value=["src"],
        ),
    ):
        run_ruff_fix()

    assert mock_runner.call_args[1]["timeout_seconds"] == 120


# --- Auto-detection tests ---


def _capture_tool(
    tool_context: ToolContext,
    tool_name: str,
) -> Any:
    """Register checker tools and capture a specific tool function."""
    captured_fns: dict[str, Any] = {}

    def capture(fn: Any) -> Any:
        captured_fns[fn.__name__] = fn
        return fn

    mock_mcp = MagicMock()
    mock_mcp.tool.return_value = capture
    checker = CheckerTools(tool_context)
    checker.register(mock_mcp)
    return captured_fns[tool_name]


def test_pylint_auto_detects_directories(tool_context: ToolContext) -> None:
    """Pylint uses resolve_target_directories when no dirs are given."""
    run_pylint = _capture_tool(tool_context, "run_pylint_check")

    with (
        patch(
            "mcp_tools_py.checker_tools.pylint_tool.resolve_target_directories",
            return_value=["src", "tests"],
        ),
        patch(
            "mcp_tools_py.checker_tools.pylint_tool.get_pylint_prompt",
            return_value=None,
        ) as mock_prompt,
    ):
        run_pylint()

    assert mock_prompt.call_args[1]["target_directories"] == ["src", "tests"]


def test_pylint_resolution_error_returns_message(tool_context: ToolContext) -> None:
    """Pylint returns error string when directory resolution fails."""
    run_pylint = _capture_tool(tool_context, "run_pylint_check")

    with patch(
        "mcp_tools_py.checker_tools.pylint_tool.resolve_target_directories",
        return_value="Error resolving target directories: No target directories found",
    ):
        result = run_pylint()

    assert "Error resolving target directories" in result


def test_pylint_passes_default_timeout(tool_context: ToolContext) -> None:
    """Without configuration the built-in default reaches get_pylint_prompt."""
    run_pylint = _capture_tool(tool_context, "run_pylint_check")

    with (
        patch(
            "mcp_tools_py.checker_tools.pylint_tool.resolve_target_directories",
            return_value=["src"],
        ),
        patch(
            "mcp_tools_py.checker_tools.pylint_tool.get_pylint_prompt",
            return_value=None,
        ) as mock_prompt,
    ):
        run_pylint()

    assert mock_prompt.call_args[1]["timeout_seconds"] == 120


def test_pylint_invalid_timeout_returns_message(tool_context: ToolContext) -> None:
    """An invalid configured timeout comes back as text, and pylint is never run."""
    (tool_context.project_dir / "pyproject.toml").write_text(textwrap.dedent("""\
            [tool.mcp-tools-py]
            pylint-timeout = 0
            """))
    run_pylint = _capture_tool(tool_context, "run_pylint_check")

    with (
        patch(
            "mcp_tools_py.checker_tools.pylint_tool.resolve_target_directories",
            return_value=["src"],
        ),
        patch(
            "mcp_tools_py.checker_tools.pylint_tool.get_pylint_prompt",
            return_value=None,
        ) as mock_prompt,
    ):
        result = run_pylint()

    assert "pylint-timeout must be a positive integer" in result
    mock_prompt.assert_not_called()


def test_mypy_auto_detects_directories(tool_context: ToolContext) -> None:
    """Mypy uses resolve_target_directories when no dirs are given."""
    run_mypy = _capture_tool(tool_context, "run_mypy_check")

    with (
        patch(
            "mcp_tools_py.checker_tools.mypy_tool.resolve_target_directories",
            return_value=["src", "tests"],
        ),
        patch(
            "mcp_tools_py.checker_tools.mypy_tool.get_mypy_prompt",
            return_value=None,
        ) as mock_prompt,
    ):
        run_mypy()

    assert mock_prompt.call_args[1]["target_directories"] == ["src", "tests"]


def test_mypy_resolution_error_returns_message(tool_context: ToolContext) -> None:
    """Mypy returns error string when directory resolution fails."""
    run_mypy = _capture_tool(tool_context, "run_mypy_check")

    with patch(
        "mcp_tools_py.checker_tools.mypy_tool.resolve_target_directories",
        return_value="Error resolving target directories: No target directories found",
    ):
        result = run_mypy()

    assert "Error resolving target directories" in result


def test_mypy_passes_explicit_timeout(tool_context: ToolContext) -> None:
    """An explicit timeout_seconds reaches get_mypy_prompt."""
    run_mypy = _capture_tool(tool_context, "run_mypy_check")

    with (
        patch(
            "mcp_tools_py.checker_tools.mypy_tool.resolve_target_directories",
            return_value=["src"],
        ),
        patch(
            "mcp_tools_py.checker_tools.mypy_tool.get_mypy_prompt",
            return_value=None,
        ) as mock_prompt,
    ):
        run_mypy(timeout_seconds=900)

    assert mock_prompt.call_args[1]["timeout_seconds"] == 900


def test_mypy_passes_default_timeout(tool_context: ToolContext) -> None:
    """Without configuration the built-in default reaches get_mypy_prompt."""
    run_mypy = _capture_tool(tool_context, "run_mypy_check")

    with (
        patch(
            "mcp_tools_py.checker_tools.mypy_tool.resolve_target_directories",
            return_value=["src"],
        ),
        patch(
            "mcp_tools_py.checker_tools.mypy_tool.get_mypy_prompt",
            return_value=None,
        ) as mock_prompt,
    ):
        run_mypy()

    assert mock_prompt.call_args[1]["timeout_seconds"] == 120


def test_mypy_invalid_timeout_returns_message(tool_context: ToolContext) -> None:
    """An invalid timeout_seconds comes back as text, and mypy is never run."""
    run_mypy = _capture_tool(tool_context, "run_mypy_check")

    with (
        patch(
            "mcp_tools_py.checker_tools.mypy_tool.resolve_target_directories",
            return_value=["src"],
        ),
        patch(
            "mcp_tools_py.checker_tools.mypy_tool.get_mypy_prompt",
            return_value=None,
        ) as mock_prompt,
    ):
        result = run_mypy(timeout_seconds=0)

    assert "timeout_seconds" in result
    mock_prompt.assert_not_called()


def test_vulture_auto_detects_directories(tool_context: ToolContext) -> None:
    """Vulture uses resolve_target_directories when no dirs are given."""
    run_vulture_fn = _capture_vulture(tool_context)

    with (
        patch(
            "mcp_tools_py.checker_tools.vulture_tool.resolve_target_directories",
            return_value=["src", "tests"],
        ),
        patch(
            "mcp_tools_py.checker_tools.vulture_tool.run_vulture",
            return_value="ok",
        ) as mock_runner,
        patch.object(Path, "exists", return_value=False),
    ):
        run_vulture_fn()

    assert mock_runner.call_args[1]["target_directories"] == ["src", "tests"]


def test_vulture_resolution_error_returns_message(tool_context: ToolContext) -> None:
    """Vulture returns error string when directory resolution fails."""
    run_vulture_fn = _capture_vulture(tool_context)

    with patch(
        "mcp_tools_py.checker_tools.vulture_tool.resolve_target_directories",
        return_value="Error resolving target directories: No target directories found",
    ):
        result = run_vulture_fn()

    assert "Error resolving target directories" in result


# --- Ruff check handler tests ---


def test_ruff_check_unavailable_returns_error(tool_context: ToolContext) -> None:
    """When ruff is not available, return an error message."""
    _remove_console_script(tool_context, "ruff")
    run_ruff_check = _capture_tool(tool_context, "run_ruff_check")
    result = run_ruff_check()
    assert "ruff is not available" in result


def test_ruff_check_success_delegates_to_impl(tool_context: ToolContext) -> None:
    """When ruff check succeeds, delegate to run_ruff_check_impl."""
    run_ruff_check = _capture_tool(tool_context, "run_ruff_check")

    with (
        patch(
            "mcp_tools_py.checker_tools.ruff_check_tool.run_ruff_check_impl",
            return_value="No ruff issues found.",
        ) as mock_impl,
        patch(
            "mcp_tools_py.checker_tools.ruff_check_tool.resolve_target_directories",
            return_value=["src"],
        ),
    ):
        result = run_ruff_check()

    assert "No ruff issues found." in result
    mock_impl.assert_called_once()


def test_ruff_check_resolution_error_returns_message(tool_context: ToolContext) -> None:
    """Ruff check returns error string when directory resolution fails."""
    run_ruff_check = _capture_tool(tool_context, "run_ruff_check")

    with patch(
        "mcp_tools_py.checker_tools.ruff_check_tool.resolve_target_directories",
        return_value="Error resolving target directories: No target directories found",
    ):
        result = run_ruff_check()

    assert "Error resolving target directories" in result


# --- Ruff fix handler tests ---


def test_ruff_fix_unavailable_returns_error(tool_context: ToolContext) -> None:
    """When ruff is not available, return an error message."""
    _remove_console_script(tool_context, "ruff")
    run_ruff_fix = _capture_tool(tool_context, "run_ruff_fix")
    result = run_ruff_fix()
    assert "ruff is not available" in result


def test_ruff_fix_success_delegates_to_impl(tool_context: ToolContext) -> None:
    """When ruff fix succeeds, delegate to run_ruff_fix_impl."""
    run_ruff_fix = _capture_tool(tool_context, "run_ruff_fix")

    with (
        patch(
            "mcp_tools_py.checker_tools.ruff_fix_tool.run_ruff_fix_impl",
            return_value="No fixable violations found — no files modified.",
        ) as mock_impl,
        patch(
            "mcp_tools_py.checker_tools.ruff_fix_tool.resolve_target_directories",
            return_value=["src"],
        ),
    ):
        result = run_ruff_fix()

    assert "No fixable violations found" in result
    mock_impl.assert_called_once()


def test_ruff_fix_resolution_error_returns_message(tool_context: ToolContext) -> None:
    """Ruff fix returns error string when directory resolution fails."""
    run_ruff_fix = _capture_tool(tool_context, "run_ruff_fix")

    with patch(
        "mcp_tools_py.checker_tools.ruff_fix_tool.resolve_target_directories",
        return_value="Error resolving target directories: No target directories found",
    ):
        result = run_ruff_fix()

    assert "Error resolving target directories" in result


# --- Tach handler tests ---


def test_tach_unavailable_returns_error(tool_context: ToolContext) -> None:
    """When tach is not available, return an error message."""
    _remove_console_script(tool_context, "tach")
    run_tach_check = _capture_tool(tool_context, "run_tach_check")
    result = run_tach_check()
    assert "tach is not available" in result


def test_tach_success_returns_raw_output(tool_context: ToolContext) -> None:
    """When tach succeeds, return the runner's output."""
    run_tach_check = _capture_tool(tool_context, "run_tach_check")

    with patch(
        "mcp_tools_py.checker_tools.tach_tool.run_tach",
        return_value="tach check passed (no output).",
    ) as mock_runner:
        result = run_tach_check()

    assert result == "tach check passed (no output)."
    mock_runner.assert_called_once_with(
        tach_binary=str(tool_context.tool_environment.binary("tach")),
        project_dir=str(tool_context.project_dir),
        timeout_seconds=120,
    )
