"""Functions for running import-linter contract checks with structured output."""

import logging
import re

from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT
from mcp_tools_py.utils.subprocess_runner import execute_command

logger = logging.getLogger(__name__)

_VERBOSE_FLAGS: tuple[str, ...] = ("-v", "--verbose")
MAX_OUTPUT_LINES: int = 300
_TRUNCATION_MARKER: str = (
    "[output truncated — run with --contract <name> for individual results]"
)

_SUMMARY_RE = re.compile(r"Contracts:\s+(\d+)\s+kept,\s+(\d+)\s+broken")
_BROKEN_LINE_RE = re.compile(r"^(?P<name>.+?)\s+BROKEN\s+\[", re.MULTILINE)
_WARNING_RE = re.compile(
    r"^No matches for ignored import\s+(?P<src>\S[^\n]*?)\s*->\s*"
    r"(?P<dst>\S[^\n]*?\.)\s*$",
    re.MULTILINE,
)


def _strip_verbose_flags(
    extra_args: list[str] | None,
) -> tuple[list[str], bool]:
    """Return (cleaned_args, was_stripped)."""
    if not extra_args:
        return [], False
    cleaned = [arg for arg in extra_args if arg not in _VERBOSE_FLAGS]
    return cleaned, len(cleaned) != len(extra_args)


def _parse_summary(combined: str) -> tuple[int, int] | None:
    """Return (kept, broken) or None if summary line not found."""
    match = _SUMMARY_RE.search(combined)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def _parse_broken_contracts(combined: str) -> list[str]:
    """Return ordered, de-duplicated list of broken contract names."""
    seen: set[str] = set()
    result: list[str] = []
    for match in _BROKEN_LINE_RE.finditer(combined):
        name = match.group("name").strip()
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return result


def _join_wrapped_warning_lines(combined: str) -> str:
    """Join wrapped 'No matches for ignored import ...' lines into one each.

    lint-imports may wrap long warning lines even without --verbose.
    Walk lines in order; whenever a line starts with the warning prefix
    and does not yet end with '.', glue it to subsequent non-blank lines
    until a '.' terminator is reached or no further continuation exists.

    Returns:
        The input text with wrapped warning lines re-joined.
    """
    lines = combined.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(
            "No matches for ignored import"
        ) and not line.rstrip().endswith("."):
            joined = line.rstrip()
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if nxt.strip():
                    joined = joined + " " + nxt.strip()
                    j += 1
                    if joined.rstrip().endswith("."):
                        break
                else:
                    j += 1
            out.append(joined)
            i = j
        else:
            out.append(line)
            i += 1
    return "\n".join(out)


def _parse_warnings(combined: str) -> list[str]:
    """Return list of warning sentences (whitespace-collapsed)."""
    joined_text = _join_wrapped_warning_lines(combined)
    warnings: list[str] = []
    for match in _WARNING_RE.finditer(joined_text):
        sentence = " ".join(match.group(0).split())
        warnings.append(sentence)
    return warnings


def _classify_state(return_code: int, summary: tuple[int, int] | None) -> str:
    """Return 'PASSED', 'BROKEN', or 'ERROR'."""
    if summary is None:
        return "ERROR"
    _kept, broken = summary
    if return_code == 0 and broken == 0:
        return "PASSED"
    if return_code != 0 and broken > 0:
        return "BROKEN"
    return "ERROR"


def _format_state_header(state: str, summary: tuple[int, int] | None) -> str:
    """Return the bare state header text (without the surrounding ===)."""
    if state == "PASSED":
        return "PASSED"
    if state == "BROKEN" and summary is not None:
        kept, broken = summary
        return f"BROKEN: {broken} of {kept + broken} contracts failed"
    return "ERROR: lint-imports output could not be parsed"


def _format_report(
    state: str,
    summary: tuple[int, int] | None,
    broken_contracts: list[str],
    warnings: list[str],
    raw_body: str,
    info_line: str | None,
) -> str:
    """Assemble the final string and apply the line cap.

    Returns:
        Multi-line report text, truncated to `MAX_OUTPUT_LINES`.
    """
    lines: list[str] = []

    if info_line:
        lines.append(info_line)

    header = _format_state_header(state, summary)
    lines.append(f"=== {header} ===")

    if summary is not None:
        kept, broken = summary
        lines.append(f"Contracts: {kept} kept, {broken} broken")

    if state == "BROKEN" and broken_contracts:
        lines.append("Broken contracts:")
        for name in broken_contracts:
            lines.append(f"  - {name}")

    if warnings:
        lines.append("Warnings:")
        for warning in warnings:
            lines.append(f"  - {warning}")

    lines.append("")

    body = raw_body if raw_body.strip() else "(no output)"
    lines.extend(body.splitlines())

    if len(lines) > MAX_OUTPUT_LINES:
        lines = lines[:MAX_OUTPUT_LINES] + [_TRUNCATION_MARKER]

    return "\n".join(lines)


@log_function_call
def run_lint_imports_check_impl(
    lint_imports_binary: str,
    project_dir: str,
    extra_args: list[str] | None = None,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
) -> str:
    """Run lint-imports and return an LLM-optimised structured report.

    The first non-empty line is always either an info line (when flags
    were stripped) or the state header. Truncation cannot hide it.

    Args:
        lint_imports_binary: Path to the lint-imports executable.
        project_dir: Directory to run lint-imports in.
        extra_args: Additional lint-imports arguments.
        timeout_seconds: Maximum seconds to wait for lint-imports.

    Returns:
        Structured report (state header + summary + raw output, capped).
    """
    cleaned_args, stripped = _strip_verbose_flags(extra_args)
    info_line = "[Info: stripped --verbose/-v from extra_args]" if stripped else None

    command = [lint_imports_binary] + cleaned_args
    result = execute_command(command, cwd=project_dir, timeout_seconds=timeout_seconds)

    if result.timed_out:
        return f"=== ERROR: lint-imports timed out after {timeout_seconds} seconds ==="
    if result.execution_error:
        return f"=== ERROR: lint-imports failed to run: {result.execution_error} ==="

    combined = "\n".join(s for s in (result.stdout, result.stderr) if s)

    summary = _parse_summary(combined)
    broken_contracts = _parse_broken_contracts(combined)
    warnings = _parse_warnings(combined)
    state = _classify_state(result.return_code, summary)

    return _format_report(
        state, summary, broken_contracts, warnings, combined, info_line
    )
