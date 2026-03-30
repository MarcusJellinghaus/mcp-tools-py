"""Reporting utilities for mypy results."""

import logging

from mcp_tools_py.code_checker_mypy.models import MypyMessage, MypyResult

logger = logging.getLogger(__name__)


def create_mypy_prompt(result: MypyResult) -> str | None:
    """
    Generate LLM-friendly prompt from mypy results.

    Args:
        result: MypyResult from type checking

    Returns:
        Formatted prompt string or None if no issues
    """
    if not result.messages:
        return None

    # Calculate summary statistics
    total_errors = len([m for m in result.messages if m.severity == "error"])
    total_warnings = len([m for m in result.messages if m.severity == "warning"])
    total_notes = len([m for m in result.messages if m.severity == "note"])

    # Get unique files with issues
    files_with_issues = len(set(msg.file for msg in result.messages))

    # Group messages by error code
    by_code: dict[str, list[MypyMessage]] = {}
    for msg in result.messages:
        code = msg.code or "other"
        if code not in by_code:
            by_code[code] = []
        by_code[code].append(msg)

    # Build prompt with summary
    lines = [f"Mypy found {len(result.messages)} type issues that need attention:"]

    # Add summary statistics
    lines.append("\n**Summary:**")
    lines.append(f"- Total issues: {len(result.messages)}")
    lines.append(f"- Errors: {total_errors}")
    if total_warnings > 0:
        lines.append(f"- Warnings: {total_warnings}")
    if total_notes > 0:
        lines.append(f"- Notes: {total_notes}")
    lines.append(f"- Files affected: {files_with_issues}")
    lines.append(f"- Error categories: {len(by_code)}")
    lines.append("")

    # Sort by error code for consistent output
    for code in sorted(by_code.keys()):
        messages = by_code[code]
        lines.append(f"**{code} ({len(messages)} issues)**")

        for msg in messages[:5]:  # Limit to first 5 per category
            location = f"{msg.file}:{msg.line}:{msg.column}"
            lines.append(f"- {location} - {msg.message}")

        if len(messages) > 5:
            lines.append(f"  ... and {len(messages) - 5} more")
        lines.append("")

    # Add fix suggestions
    lines.append("\nTo fix these issues:")
    lines.append("1. Add missing type annotations where indicated")
    lines.append("2. Ensure all function arguments and return types are properly typed")
    lines.append("3. Fix any import errors or undefined attributes")
    lines.append(
        "4. Review the specific error messages and adjust your code accordingly"
    )

    return "\n".join(lines)


def get_mypy_prompt(
    project_dir: str,
    python_executable: str,
    strict: bool = True,
    disable_error_codes: list[str] | None = None,
    target_directories: list[str] | None = None,
    follow_imports: str | None = None,
    cache_dir: str | None = None,
) -> str | None:
    """
    Run mypy and generate an LLM prompt if issues are found.

    This is a convenience function that combines running and reporting.

    Args:
        project_dir: Path to project directory
        python_executable: Python interpreter to use
        strict: Use strict mode (default: True)
        disable_error_codes: Error codes to ignore
        target_directories: Directories to check
        follow_imports: How to handle imports ('normal', 'silent', 'skip', 'error')
        cache_dir: Custom cache directory for incremental checking

    Returns:
        LLM prompt string or None if no issues
    """
    from mcp_tools_py.code_checker_mypy.runners import run_mypy_check

    result = run_mypy_check(
        project_dir=project_dir,
        python_executable=python_executable,
        strict=strict,
        disable_error_codes=disable_error_codes,
        target_directories=target_directories,
        follow_imports=follow_imports or "normal",
        cache_dir=cache_dir,
    )

    if result.error:
        return f"Mypy execution failed: {result.error}"

    return create_mypy_prompt(result)
