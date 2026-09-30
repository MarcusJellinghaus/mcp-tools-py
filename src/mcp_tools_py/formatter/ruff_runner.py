"""Runners for the ruff formatter steps.

Invokes ruff as a subprocess and returns a FormatterResult.
"""

import re
import time
from pathlib import Path

from mcp_tools_py.formatter.common import (
    combine_output,
    formatter_binary,
    relative_path,
    truncate_output,
    version_line,
)
from mcp_tools_py.formatter.models import FormatterResult
from mcp_tools_py.utils.project_config import (
    DEFAULT_CHECK_TIMEOUT,
    read_pyproject_tool_tables,
)
from mcp_tools_py.utils.python_environment import PythonEnvironment
from mcp_tools_py.utils.ruff_parsing import RuffMessage, parse_ruff_json_output
from mcp_tools_py.utils.subprocess_runner import CommandResult, execute_command

# Anchored on `:<line>:<col>` so a drive-letter colon does not cut the path.
_FAILED_TO_PARSE = re.compile(r"error: Failed to parse (.+?):\d+:\d+")
# "ALL", "I" or "I<digits>" — not a bare "I" prefix, which would catch INP, ICN, ISC.
_ISORT_CODE = re.compile(r"ALL|I\d*")
_GLOB_CHAR = re.compile(r"[*?\[]")


def _is_syntax_error(m: RuffMessage) -> bool:
    """Whether a ruff diagnostic reports a file ruff could not parse.

    Returns:
        True for an ``invalid-syntax`` diagnostic, or one with no code.
    """
    return not m.code or m.code == "invalid-syntax"


def _render_diagnostics(messages: list[RuffMessage], project_dir: str) -> str:
    """One line per diagnostic: '<relative_path>: <code or invalid-syntax> <message>'.

    Returns:
        The rendered lines joined by newlines, or ``""`` when there are none.
    """
    return "\n".join(
        f"{relative_path(m.filename, project_dir)}: "
        f"{m.code or 'invalid-syntax'} {m.message}"
        for m in messages
    )


def _dedup(paths: list[str]) -> list[str]:
    """Paths in first-seen order, without duplicates.

    Returns:
        The deduplicated list.
    """
    return list(dict.fromkeys(paths))


def run_ruff_format(
    python_executable: str,
    target_dirs: list[str],
    project_dir: str,
    check_only: bool = False,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
    *,
    environment: PythonEnvironment | None = None,
) -> FormatterResult:
    """Run ``ruff format`` on target directories.

    Args:
        python_executable: Deprecated. Accepted and ignored; ruff runs from
            `environment`.
        target_dirs: List of directories to format.
        project_dir: Root project directory (cwd for subprocess).
        check_only: If True, pass ``--check --output-format json`` to only
            verify formatting.
        timeout_seconds: Maximum seconds to wait for ruff.
        environment: Environment whose ruff console script runs. None means
            mcp-tools-py's own environment.

    Returns:
        FormatterResult with project-relative, forward-slash paths.
        files_changed is empty in write mode, where ruff names no files.
        unparsable_files lists files ruff could not parse; ruff still formats
        the others.
    """
    env = environment or PythonEnvironment.resolve()
    binary = formatter_binary("ruff", env)
    if binary is None:
        return FormatterResult(
            output=f"ruff is not available: no console script found in {env.bin_dir}",
            success=False,
            files_changed=[],
        )

    command = [binary, "format"]
    if check_only:
        command.extend(["--check", "--output-format", "json"])
    command.extend(target_dirs)

    started = time.monotonic()
    result = execute_command(command, cwd=project_dir, timeout_seconds=timeout_seconds)

    if result.timed_out:
        return FormatterResult(
            output=f"ruff format timed out after {timeout_seconds} seconds.",
            success=False,
            files_changed=[],
        )

    if result.execution_error:
        return FormatterResult(
            output=f"ruff format failed to run: {result.execution_error}",
            success=False,
            files_changed=[],
        )

    remaining = int(timeout_seconds - (time.monotonic() - started))
    banner = version_line("ruff", binary, remaining)
    stderr_bad: list[str] = _FAILED_TO_PARSE.findall(result.stderr)

    if check_only:
        messages, parse_error = parse_ruff_json_output(result.stdout, project_dir)
        if parse_error:
            body = "\n".join(part for part in (parse_error, result.stderr) if part)
            return FormatterResult(
                output=truncate_output(f"{banner}\n{body}"),
                success=False,
                files_changed=[],
            )
        changed = [m.filename for m in messages if m.code == "unformatted"]
        json_bad = [m.filename for m in messages if _is_syntax_error(m)]
        rendered = _render_diagnostics(messages, project_dir)
        combined = "\n".join(part for part in (rendered, result.stderr) if part)
    else:
        changed, json_bad = [], []
        combined = combine_output(result)

    return FormatterResult(
        output=truncate_output(f"{banner}\n{combined}"),
        success=result.return_code == 0,
        files_changed=_dedup([relative_path(p, project_dir) for p in changed]),
        unparsable_files=_dedup(
            [relative_path(p, project_dir) for p in stderr_bad + json_bad]
        ),
    )


def _components(path: str) -> list[str]:
    """Path components after normalising separators and dropping empty/`.` parts.

    Returns:
        The components in order.
    """
    return [p for p in path.replace("\\", "/").split("/") if p not in ("", ".")]


def _literal_prefix(key: str) -> list[str]:
    """Complete leading path components of a glob key before any glob character.

    Returns:
        The literal components; empty when the key starts with a glob.
    """
    key = key.replace("\\", "/")
    match = _GLOB_CHAR.search(key)
    if match is None:
        return _components(key)
    head = key[: match.start()]
    # Drop a partial component such as `test_` in `src/test_*.py`.
    return _components(head.rsplit("/", 1)[0] if "/" in head else "")


def _overlaps(a: list[str], b: list[str]) -> bool:
    """Whether one component list is a leading run of the other.

    Returns:
        True when `a` and `b` agree on their common length.
    """
    common = min(len(a), len(b))
    return a[:common] == b[:common]


def per_file_ignores_notice(project_dir: str, target_dirs: list[str]) -> str:
    """One line naming target directories where an `I` per-file-ignore applies.

    Advisory only: keys are matched on their leading literal path components,
    keys that start with a glob and ``extend-per-file-ignores`` are not
    considered, and a malformed pyproject.toml yields no notice.

    Returns:
        The notice line, or ``""`` when no target directory is affected.
    """
    try:
        tables = read_pyproject_tool_tables(Path(project_dir))
    except ValueError:
        return ""
    ruff = tables.get("ruff")
    if not isinstance(ruff, dict):
        return ""
    lint = ruff.get("lint")
    sources = [ruff.get("per-file-ignores")]
    if isinstance(lint, dict):
        sources.append(lint.get("per-file-ignores"))

    keys: list[str] = []
    dirs: list[str] = []
    for ignores in sources:
        if not isinstance(ignores, dict):
            continue
        for key, codes in ignores.items():
            prefix = _literal_prefix(key)
            if not prefix or not isinstance(codes, list):
                continue
            if not any(isinstance(c, str) and _ISORT_CODE.fullmatch(c) for c in codes):
                continue
            hits = [d for d in target_dirs if _overlaps(prefix, _components(d))]
            if hits:
                keys.append(key)
                dirs.extend(hits)

    if not dirs:
        return ""
    return (
        f"Note: ruff per-file-ignores {', '.join(repr(k) for k in _dedup(keys))} "
        f"ignore import sorting (I) under {', '.join(_dedup(dirs))}; "
        "ruff_imports does not sort those files."
    )


def _run_failure(result: CommandResult, timeout_seconds: int) -> FormatterResult | None:
    """The early-return result for a ruff check run that timed out or failed to start.

    Returns:
        A failed FormatterResult without a version banner, or None when ruff ran.
    """
    if result.timed_out:
        output = f"ruff check timed out after {timeout_seconds} seconds."
    elif result.execution_error:
        output = f"ruff check failed to run: {result.execution_error}"
    else:
        return None
    return FormatterResult(output=output, success=False, files_changed=[])


def run_ruff_imports(
    python_executable: str,
    target_dirs: list[str],
    project_dir: str,
    check_only: bool = False,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
    *,
    environment: PythonEnvironment | None = None,
) -> FormatterResult:
    """Sort imports with ``ruff check --select I``.

    A ``--no-fix --output-format json`` pre-check collects the diagnostics;
    in write mode a ``--fix`` run follows, since its own output lists only
    what remains unfixed.

    Args:
        python_executable: Deprecated. Accepted and ignored; ruff runs from
            `environment`.
        target_dirs: List of directories to sort imports in.
        project_dir: Root project directory (cwd for subprocess).
        check_only: If True, run only the pre-check.
        timeout_seconds: Maximum seconds to wait for each ruff invocation.
        environment: Environment whose ruff console script runs. None means
            mcp-tools-py's own environment.

    Returns:
        FormatterResult with project-relative, forward-slash paths.
        files_changed lists the files with fixable diagnostics.
        unparsable_files lists files ruff could not parse; the fix run still
        sorts the others.
    """
    env = environment or PythonEnvironment.resolve()
    binary = formatter_binary("ruff", env)
    if binary is None:
        return FormatterResult(
            output=f"ruff is not available: no console script found in {env.bin_dir}",
            success=False,
            files_changed=[],
        )

    base = [binary, "check", "--select", "I"]
    started = time.monotonic()
    pre = execute_command(
        [*base, "--no-fix", "--output-format", "json", *target_dirs],
        cwd=project_dir,
        timeout_seconds=timeout_seconds,
    )
    failure = _run_failure(pre, timeout_seconds)
    if failure is not None:
        return failure

    def finish(
        combined: str,
        success: bool,
        changed: list[str] | None = None,
        unparsable: list[str] | None = None,
    ) -> FormatterResult:
        remaining = int(timeout_seconds - (time.monotonic() - started))
        header = [
            version_line("ruff", binary, remaining),
            per_file_ignores_notice(project_dir, target_dirs),
        ]
        output = "\n".join(part for part in (*header, combined) if part)
        return FormatterResult(
            output=truncate_output(output),
            success=success,
            files_changed=changed or [],
            unparsable_files=unparsable or [],
        )

    if pre.return_code == 2:
        return finish(pre.stderr, False)

    messages, parse_error = parse_ruff_json_output(pre.stdout, project_dir)
    if parse_error:
        return finish(parse_error, False)

    def paths(selected: list[RuffMessage]) -> list[str]:
        return sorted({relative_path(m.filename, project_dir) for m in selected})

    unparsable = paths([m for m in messages if _is_syntax_error(m)])
    violations = paths([m for m in messages if not _is_syntax_error(m)])
    changed = paths([m for m in messages if m.fixable])

    if check_only:
        return finish(
            _render_diagnostics(messages, project_dir),
            not violations and not unparsable,
            changed,
            unparsable,
        )

    # Runs even with unparsable files: ruff skips them and sorts the rest.
    started = time.monotonic()
    fix = execute_command(
        [*base, "--fix", *target_dirs],
        cwd=project_dir,
        timeout_seconds=timeout_seconds,
    )
    failure = _run_failure(fix, timeout_seconds)
    if failure is not None:
        return failure
    if fix.return_code == 2:
        return finish(fix.stderr, False)
    return finish(
        combine_output(fix),
        fix.return_code == 0 and not unparsable,
        changed,
        unparsable,
    )
