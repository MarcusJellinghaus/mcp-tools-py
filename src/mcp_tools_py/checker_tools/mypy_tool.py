"""Mypy MCP tool registration."""

import logging
from typing import TYPE_CHECKING

from mcp_tools_py.code_checker_mypy import get_mypy_prompt
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.project_config import resolve_target_directories

if TYPE_CHECKING:
    from mcp_tools_py.checker_tools import CheckerTools
    from mcp_tools_py.server import FastMCPProtocol

logger = logging.getLogger(__name__)


def register(mcp: "FastMCPProtocol", checker_tools: "CheckerTools") -> None:
    """Register the mypy checker tool."""
    server = checker_tools._server

    @mcp.tool()
    @log_function_call
    def run_mypy_check(
        disable_error_codes: list[str] | None = None,
        target_directories: list[str] | None = None,
        follow_imports: str | None = None,
        cache_dir: str | None = None,
        timeout_seconds: int | None = None,
    ) -> str:
        """Run mypy type checking on the project code.

        mypy reads the project's `[tool.mypy]` configuration; the server adds only
        output-formatting flags. A project with no mypy config is checked at mypy's
        defaults and will report "passed".

        Args:
            disable_error_codes: Optional list of mypy error codes to ignore.
                Common codes to disable:
                - 'import': Import-related errors
                - 'arg-type': Argument type mismatches
                - 'no-untyped-def': Missing type annotations
                - 'attr-defined': Attribute not defined errors
                - 'var-annotated': Missing variable annotations
            target_directories: Optional list of directories to check relative to project_dir.
                Auto-detected from pyproject.toml when None. For example:
                ["src"] (source only), ["src", "tests"] (both),
                ["mypackage"] (custom package), ["."] (entire project).
            follow_imports: How to handle imports during type checking. Nothing is
                sent by default and the project's `[tool.mypy]` decides; supplying a
                value overrides it for this call and splits the mypy cache.
                Options:
                - 'normal': Follow and type check imported modules
                - 'silent': Follow imports but suppress errors in imported modules
                - 'skip': Don't follow imports, only check specified files
                - 'error': Error if imports cannot be followed
            cache_dir: Optional custom cache directory for incremental checking.
                Mypy uses caching to speed up subsequent runs.
                Defaults to .mypy_cache in the project directory.
            timeout_seconds: Maximum seconds to wait for mypy. Overrides the
                configured limit for this call. Must be a positive integer.
                Defaults to `[tool.mcp-tools-py]` config, then `--check-timeout`,
                then 120.

        Returns:
            A string containing mypy results or a prompt for an LLM to interpret
        """
        if not server._is_tool_available("mypy"):
            return server.tool_unavailable_message("mypy")

        resolved = resolve_target_directories(
            str(server.project_dir), target_directories
        )
        if isinstance(resolved, str):
            return resolved

        try:
            resolved_timeout = server.resolve_timeout("mypy", timeout_seconds)
        except ValueError as exc:
            return f"Error: {exc}"

        try:
            logger.info(
                "Starting mypy check",
                extra={
                    "project_dir": str(server.project_dir),
                    "disable_error_codes": disable_error_codes,
                    "target_directories": resolved,
                },
            )

            # Run mypy check
            mypy_prompt = get_mypy_prompt(
                str(server.project_dir),
                python_executable=server._resolved_python,
                disable_error_codes=disable_error_codes,
                target_directories=resolved,
                follow_imports=follow_imports,
                cache_dir=cache_dir,
                timeout_seconds=resolved_timeout,
            )

            # Format result
            result = checker_tools._format_mypy_result(mypy_prompt)

            logger.info(
                "Mypy check completed",
                extra={
                    "issues_found": mypy_prompt is not None,
                    "result_length": len(result),
                },
            )

            return result

        except Exception as e:
            logger.error(
                "Mypy check failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "project_dir": str(server.project_dir),
                },
            )
            raise
