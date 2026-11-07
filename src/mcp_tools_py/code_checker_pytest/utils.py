"""Utility functions for code checker pytest operations."""

import os
import sys
from typing import List, Optional, Tuple

from mcp_tools_py.code_checker_pytest.models import ErrorContext, SanitizedArgs
from mcp_tools_py.utils.file_utils import read_file as read_file

# Letters of short switches that take no value and may be combined (e.g. -xvs).
_SWITCH_LETTERS = set("xvsql")

# Hard-coded from pytest's parser with this repo's plugins. An option missing
# from it takes no value, so a following token is read as a positional, as before.
_ONE_VALUE_OPTIONS = """
-W -c -k -m -n -o -p -r
--anyio-mode --assert --asyncio-mode --basetemp --cache-show --capture
--code-highlight --color --confcutdir --config-file --cov --cov-config
--cov-context --cov-fail-under --cov-precision --cov-report --debug --deselect
--dist --doctest-glob --doctest-report --durations --durations-min --ignore
--ignore-glob --import-mode --json-report-file --json-report-indent
--json-report-verbosity --junit-prefix --junit-xml --junitprefix --junitxml
--last-failed-no-failures --lfnf --log-auto-indent --log-cli-date-format
--log-cli-format --log-cli-level --log-date-format --log-disable --log-file
--log-file-date-format --log-file-format --log-file-level --log-file-mode
--log-format --log-level --max-warnings --max-worker-restart --maxfail
--maxprocesses --maxschedchunk --metadata-from-json --metadata-from-json-file
--numprocesses --override-ini --pastebin --pdbcls --px --pythonwarnings
--report-chars --rootdir --rsyncdir --rsyncignore --show-capture --tach-base
--tach-head --tb --testrunuid --tx --verbosity
""".split()

# Option spelling -> most values it can take.
_OPTION_VALUES: dict[str, int] = {
    **dict.fromkeys(_ONE_VALUE_OPTIONS, 1),
    "--metadata": 2,
    "--json-report-omit": sys.maxsize,
}


def _values_taken(arg: str) -> int:
    """Return how many following tokens the option ``arg`` can take."""
    if arg.startswith("--"):
        return 0 if "=" in arg else _OPTION_VALUES.get(arg, 0)
    for pos, letter in enumerate(arg[1:], start=2):
        if f"-{letter}" in _OPTION_VALUES:
            return 0 if arg[pos:] else 1  # -ktests vs -xk tests
    return 0


def _positional_args(args: List[str]) -> List[str]:
    """Return the tokens of ``args`` that are neither options nor their values.

    An option takes up to its table count of following tokens that don't
    start with ``-``. Everything after ``--`` is positional.
    """
    positionals: List[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        i += 1
        if arg == "--":
            positionals += args[i:]
            break
        if not arg.startswith("-"):
            positionals.append(arg)
            continue
        for _ in range(_values_taken(arg)):
            if i == len(args) or args[i].startswith("-"):
                break
            i += 1
    return positionals


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
        - Path detection reads option values from a hard-coded table. A value
          after an option missing from the table is read as a positional.
        - Tokens after ``--`` are positional for path detection.

    Args:
        extra_args: Optional list of extra arguments for pytest.
        markers: Optional list of marker expressions passed via the
            dedicated markers parameter.
        project_dir: Project directory for resolving relative paths.
            When provided, non-flag args are checked as paths relative
            to this directory. If any valid path is found,
            ``has_path_args`` is set to ``True``.

    Returns:
        SanitizedArgs with cleaned_args, extracted verbosity, notes, and
        the detected path_args.
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
    path_args: List[str] = []
    if project_dir:
        for arg in _positional_args(cleaned):
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
                    path_args.append(arg)
                    notes.append(
                        f"Path argument '{arg}' detected; "
                        f"default test folder not appended."
                    )
                else:
                    notes.append(f"Path '{arg}' not found relative to project_dir.")
            elif exists:
                has_path_args = True
                path_args.append(arg)
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
        path_args=path_args,
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

    return ErrorContext(
        exit_code=exit_code,
        exit_code_meaning=exit_code_meaning,
        error_message=error_message,
        suggestion=suggestion,
        traceback=traceback,
    )
