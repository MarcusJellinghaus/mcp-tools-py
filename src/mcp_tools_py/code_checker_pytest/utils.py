"""
Utility functions for code checker pytest operations.
"""

from typing import Tuple

from mcp_tools_py.code_checker_pytest.models import ErrorContext, SanitizedArgs


def sanitize_extra_args(
    extra_args: list[str] | None,
    markers: list[str] | None,
) -> SanitizedArgs:
    """Sanitize and deduplicate extra_args before passing to pytest.

    Extracts verbosity flags, removes flags that are auto-added internally,
    and handles conflicts between extra_args and the markers parameter.

    Limitations:
        - Only ``-m`` as two separate args (``["-m", "slow"]``) is handled,
          not the combined ``-m=slow`` form.
        - Combined short flags like ``-xvs`` pass through as-is
          (not decomposed into individual flags).

    Args:
        extra_args: Optional list of extra arguments for pytest.
        markers: Optional list of marker expressions passed via the
            dedicated markers parameter.

    Returns:
        SanitizedArgs with cleaned_args, extracted verbosity, and notes.
    """
    if not extra_args:
        return SanitizedArgs(cleaned_args=[], verbosity=2, notes=[])

    cleaned: list[str] = []
    verbosity = 2
    notes: list[str] = []
    skip_next = False

    for arg in extra_args:
        if skip_next:
            skip_next = False
            continue

        # Verbosity flags: extract and remove
        if arg in ("-v", "-vv", "-vvv"):
            verbosity = arg.count("v")
            continue

        # -s flag: always auto-added, remove silently
        if arg == "-s":
            continue

        # Bare "tests" or "tests/" path: auto-appended, remove
        if arg in ("tests", "tests/"):
            continue

        # -m flag: remove if markers parameter is provided
        if arg == "-m" and markers is not None:
            skip_next = True
            notes.append(
                "Note: -m flag in extra_args was ignored "
                "because the markers parameter was used."
            )
            continue

        cleaned.append(arg)

    return SanitizedArgs(cleaned_args=cleaned, verbosity=verbosity, notes=notes)


def read_file(file_path: str) -> str:
    """
    Read the contents of a file.

    Args:
        file_path: Path to the file to read

    Returns:
        The contents of the file as a string

    Raises:
        FileNotFoundError: If the file does not exist
        PermissionError: If access to the file is denied
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        # Try with a different encoding if UTF-8 fails
        with open(file_path, "r", encoding="latin-1") as f:
            return f.read()


def get_pytest_exit_code_info(exit_code: int) -> Tuple[str, str]:
    """
    Get detailed information and suggestions for pytest exit codes.

    Args:
        exit_code: The pytest exit code

    Returns:
        Tuple containing (meaning, suggestion)
    """
    exit_code_map = {
        0: (
            "All tests passed successfully",
            "No action needed.",
        ),
        1: (
            "Tests were collected and run but some tests failed",
            "Review the test failures and fix the issues in your code.",
        ),
        2: (
            "Test execution was interrupted by the user",
            "Re-run tests when ready.",
        ),
        3: (
            "Internal pytest error",
            "Check for pytest version compatibility issues or look for bugs in pytest plugins.",
        ),
        4: (
            "pytest command line usage error",
            "Verify your pytest command arguments and fix any syntax errors.",
        ),
        5: (
            "No tests were collected",
            "Check your test file naming patterns, verify imports, and ensure tests are properly defined.",
        ),
        # Custom exit codes for pytest plugins
        6: (
            "Coverage threshold not met (pytest-cov plugin)",
            "Increase test coverage to meet the defined threshold.",
        ),
        7: (
            "Doctests failed (pytest-doctests plugin)",
            "Fix issues in your doctest examples.",
        ),
        8: (
            "Benchmark regression detected (pytest-benchmark plugin)",
            "Performance has degraded from baseline, check recent code changes.",
        ),
        # Default for unknown exit codes
    }

    # Return the mapping or a default message if exit code is unknown
    info = exit_code_map.get(
        exit_code,
        (
            f"Unknown exit code {exit_code}",
            "Check pytest documentation for this exit code or review the log for specific error messages.",
        ),
    )
    return info


def create_error_context(exit_code: int, error_message: str) -> ErrorContext:
    """
    Create a detailed error context object with exit code interpretation.

    Args:
        exit_code: Pytest exit code
        error_message: Error message from pytest execution

    Returns:
        ErrorContext object with detailed error information
    """
    exit_code_meaning, suggestion = get_pytest_exit_code_info(exit_code)

    # Extract traceback if available
    traceback = None
    if "Traceback" in error_message:
        traceback_parts = error_message.split("Traceback (most recent call last):")
        if len(traceback_parts) > 1:
            traceback = "Traceback (most recent call last):" + traceback_parts[1]

    # Extract collection errors if present
    collection_errors = None
    if "FAILED TO COLLECT" in error_message:
        collection_error_lines = []
        in_collection_error = False
        for line in error_message.split("\n"):
            if "FAILED TO COLLECT" in line:
                in_collection_error = True
                collection_error_lines.append(line)
            elif in_collection_error and line.strip():
                collection_error_lines.append(line)
            elif (
                in_collection_error and not line.strip()
            ):  # Empty line ends the section
                in_collection_error = False

        if collection_error_lines:
            collection_errors = collection_error_lines

    return ErrorContext(
        exit_code=exit_code,
        exit_code_meaning=exit_code_meaning,
        error_message=error_message,
        suggestion=suggestion,
        traceback=traceback,
        collection_errors=collection_errors,
    )
