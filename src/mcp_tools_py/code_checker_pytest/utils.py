"""Utility functions for code checker pytest operations."""

import os
from typing import List, Optional, Tuple

from mcp_tools_py.code_checker_pytest.models import ErrorContext, SanitizedArgs
from mcp_tools_py.utils.file_utils import read_file as read_file

# Letters of short switches that take no value and may be combined (e.g. -xvs).
_SWITCH_LETTERS = set("xvsql")

SHOW_OUTPUT_NOTE = (
    "Note: -s was not passed to pytest. It was turned into the captured-output "
    "display, which shows output printed by passing tests."
)


def sanitize_extra_args(
    extra_args: Optional[List[str]],
    markers: Optional[List[str]],
    project_dir: str = "",
) -> SanitizedArgs:
    """Sanitize and deduplicate extra_args before passing to pytest.

    Extracts verbosity flags, removes flags that are auto-added internally,
    and handles conflicts between extra_args and the markers parameter.
    ``-s``, ``--capture=no`` and ``--capture no`` are removed and set
    ``show_output`` instead, so capture stays on.

    Limitations:
        - Only ``-m`` as two separate args (``["-m", "slow"]``) is handled,
          not the combined ``-m=slow`` form.
        - Only single-dash tokens made entirely of the letters ``x v s q l``
          are split into separate flags. Others (e.g. ``-vrs``) pass through.
        - An ``-s`` in the project's ``addopts`` or in ``PYTEST_ADDOPTS``
          still disables capture.
        - Output printed at import or collection time is not shown.

    Args:
        extra_args: Optional list of extra arguments for pytest.
        markers: Optional list of marker expressions passed via the
            dedicated markers parameter.
        project_dir: Project directory for resolving relative paths.
            When provided, non-flag args are checked as paths relative
            to this directory. If any valid path is found,
            ``has_path_args`` is set to ``True``.

    Returns:
        SanitizedArgs with cleaned_args, extracted verbosity, and notes.
    """
    if not extra_args:
        return SanitizedArgs(cleaned_args=[], verbosity=2, notes=[])

    cleaned: List[str] = []
    verbosity = 2
    notes: List[str] = []
    skip_next = False
    show_output = False

    for i, arg in enumerate(extra_args):
        if skip_next:
            skip_next = False
            continue

        # Combined switch group (e.g. -xvs): extract -v and -s, keep the rest
        if (
            len(arg) > 1
            and arg[0] == "-"
            and arg[1] != "-"
            and set(arg[1:]) <= _SWITCH_LETTERS
        ):
            if "v" in arg:
                verbosity = arg.count("v")
            if "s" in arg:
                show_output = True
            cleaned += [f"-{c}" for c in arg[1:] if c in "xql"]
            continue

        # --capture=no / --capture no: same as -s
        if arg == "--capture=no":
            show_output = True
            continue
        if arg == "--capture" and i + 1 < len(extra_args) and extra_args[i + 1] == "no":
            show_output = True
            skip_next = True
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

    if show_output:
        notes.append(SHOW_OUTPUT_NOTE)

    # Path detection: shape-then-existence classification.
    # Shape match: looks like a path if it contains "/", "\", "::", or ends with ".py".
    # If shape matches, run existence check; missing → "not found" note.
    # If shape doesn't match, fall back to existence check; missing → silent passthrough.
    has_path_args = False
    if project_dir:
        for arg in cleaned:
            if arg.startswith("-"):
                continue
            if os.path.isabs(arg):
                notes.append(f"Absolute path '{arg}' ignored for path detection.")
                continue
            looks_like_path = (
                "/" in arg or "\\" in arg or "::" in arg or arg.endswith(".py")
            )
            file_part = arg.split("::", 1)[0] if "::" in arg else arg
            exists = os.path.exists(os.path.join(project_dir, file_part))
            if looks_like_path:
                if exists:
                    has_path_args = True
                    notes.append(
                        f"Path argument '{arg}' detected; "
                        f"default test folder not appended."
                    )
                else:
                    notes.append(f"Path '{arg}' not found relative to project_dir.")
            elif exists:
                has_path_args = True
                notes.append(
                    f"Path argument '{arg}' detected; "
                    f"default test folder not appended."
                )

    return SanitizedArgs(
        cleaned_args=cleaned,
        verbosity=verbosity,
        notes=notes,
        has_path_args=has_path_args,
        show_output=show_output,
    )


def get_pytest_exit_code_info(exit_code: int) -> Tuple[str, str]:
    """Get detailed information and suggestions for pytest exit codes.

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
    """Create a detailed error context object with exit code interpretation.

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
