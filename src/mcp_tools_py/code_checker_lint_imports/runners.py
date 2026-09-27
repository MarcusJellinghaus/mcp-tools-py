"""Functions for running import-linter contract checks with structured output."""

import configparser
import importlib.metadata
import logging
import os
import re
import sys
import tomllib
from pathlib import Path

from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.environment_info import locate_packages
from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT
from mcp_tools_py.utils.subprocess_runner import execute_command

logger = logging.getLogger(__name__)

_VERBOSE_FLAGS: tuple[str, ...] = ("-v", "--verbose")
_CONFIG_CANDIDATES: tuple[str, ...] = ("setup.cfg", ".importlinter", "pyproject.toml")
_CACHE_FLAGS: tuple[str, ...] = ("--no-cache", "--cache-dir")
# import-linter's own default cache directory. Our per-version directories go
# inside it so that a project already ignoring this path ignores them too.
_CACHE_ROOT: str = ".import_linter_cache"
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


def _cache_scope() -> str | None:
    """Name a cache directory that only this grimp build can read.

    The name carries the tool env's grimp version and Python version, the two
    things that decide whether a cache entry written earlier still means what
    it says.  Both are read in-process: `lint_imports_binary` comes from the
    environment `mcp_tools_py` itself runs in, so this interpreter's metadata
    describes the grimp the subprocess will import — and reading the version
    from metadata does not import grimp's compiled extension.

    Returns:
        A directory relative to the project directory, or None when grimp's
        version cannot be read and so no safe scope can be named.
    """
    try:
        version = importlib.metadata.version("grimp")
    except importlib.metadata.PackageNotFoundError:
        return None
    token = re.sub(r"[^A-Za-z0-9._-]", "_", version)
    python = f"{sys.version_info.major}.{sys.version_info.minor}"
    return f"{_CACHE_ROOT}/grimp-{token}-py{python}"


def _scope_cache(extra_args: list[str]) -> list[str]:
    """Point grimp's cache at a directory no other grimp version can read.

    Running lint-imports from the tool env means its grimp version can differ
    from whatever else runs lint-imports against this project (CI, pre-commit,
    a terminal) — and grimp validates its cache by file mtime only, with no
    version guard, so two grimp versions sharing one `.import_linter_cache`
    would each trust the other's stale entries.  Giving each build its own
    directory keeps that apart without giving up the cache: it lives in the
    project directory and is reused by every later call, so disabling it would
    make every run rebuild the whole import graph.  A different build simply
    misses and writes its own entries.

    When grimp's version cannot be read there is no scope to name, and
    `--no-cache` is the safe answer: correctness over the speedup.

    A caller-supplied `--cache-dir` or `--no-cache` is left alone rather than
    fought.

    Args:
        extra_args: Cleaned lint-imports arguments.

    Returns:
        `extra_args`, with the caching flags appended unless caching is
        already addressed.
    """
    if any(arg in _CACHE_FLAGS or arg.startswith("--cache-dir=") for arg in extra_args):
        return extra_args
    scope = _cache_scope()
    if scope is None:
        return [*extra_args, "--no-cache"]
    return [*extra_args, "--cache-dir", scope]


def _read_ini(path: Path) -> list[str] | None:
    """Read root package names from an INI-style import-linter config.

    Args:
        path: Path to a `setup.cfg`/`.importlinter`-style file.

    Returns:
        The root package names, `[]` when the `[importlinter]` section
        names none, or `None` when there is no such section to read.
    """
    try:
        parser = configparser.ConfigParser(interpolation=None)
        if not parser.read(path, encoding="utf-8"):
            return None
        if not parser.has_section("importlinter"):
            return None
        section = parser["importlinter"]
        raw_list = section.get("root_packages")
        if raw_list is not None:
            return [line.strip() for line in raw_list.splitlines() if line.strip()]
        scalar = section.get("root_package")
        if scalar and scalar.strip():
            return [scalar.strip()]
        return []
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.debug("Could not read import-linter config %s: %s", path, exc)
        return None


def _read_toml(path: Path) -> list[str] | None:
    """Read root package names from a TOML import-linter config.

    Args:
        path: Path to a `pyproject.toml`-style file.

    Returns:
        The root package names, `[]` when the `[tool.importlinter]`
        section names none, or `None` when there is no such section.
    """
    try:
        with open(path, "rb") as handle:
            data = tomllib.load(handle)
        tool = data.get("tool")
        section = tool.get("importlinter") if isinstance(tool, dict) else None
        if not isinstance(section, dict):
            return None
        raw_list = section.get("root_packages")
        if isinstance(raw_list, list):
            return [str(name).strip() for name in raw_list if str(name).strip()]
        scalar = section.get("root_package")
        if isinstance(scalar, str) and scalar.strip():
            return [scalar.strip()]
        return []
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.debug("Could not read import-linter config %s: %s", path, exc)
        return None


def _root_packages(project_dir: str, extra_args: list[str]) -> list[str]:
    """Return the root package names lint-imports will check.

    Mirrors the CLI's discovery: an explicit `--config` wins, otherwise the
    first of `setup.cfg`, `.importlinter`, `pyproject.toml` that *has* an
    import-linter section is the config — even when it names no package.

    Args:
        project_dir: Directory lint-imports runs in.
        extra_args: lint-imports arguments, scanned for `--config`.

    Returns:
        The root package names, empty when nothing could be read.
    """
    override: str | None = None
    for index, arg in enumerate(extra_args):
        if arg.startswith("--config="):
            override = arg[len("--config=") :]
            break
        if arg == "--config" and index + 1 < len(extra_args):
            override = extra_args[index + 1]
            break

    candidates = (override,) if override else _CONFIG_CANDIDATES
    for candidate in candidates:
        path = Path(project_dir) / candidate
        reader = _read_toml if path.suffix == ".toml" else _read_ini
        names = reader(path)
        if names is not None:
            return names
    return []


def _pythonpath_env(directories: list[str]) -> dict[str, str]:
    """Build a `PYTHONPATH` override that prepends `directories`.

    Args:
        directories: Directories to place ahead of any inherited entries.

    Returns:
        A single-key env dict suitable for `execute_command(env=...)`,
        which merges it over `os.environ` key by key.
    """
    existing = os.environ.get("PYTHONPATH")
    parts = [*directories, existing] if existing else list(directories)
    return {"PYTHONPATH": os.pathsep.join(parts)}


def _without_cwd(
    directories: list[str], project_dir: str
) -> tuple[list[str], list[str]]:
    """Split off the located directories lint-imports already resolves itself.

    The CLI does `sys.path.insert(0, os.getcwd())` before it builds the graph
    and the subprocess runs with `cwd=project_dir`, so a located directory that
    *is* that working directory needs no `PYTHONPATH` entry.  Leaving it out
    matters rather than merely tidying: `PYTHONPATH` is read at interpreter
    startup, ahead of the tool env's own `site-packages`, so putting a
    flat-layout repository root there lets a stray top-level module shadow one
    of lint-imports' own dependencies.

    Args:
        directories: The usable located directories.
        project_dir: Directory lint-imports runs in.

    Returns:
        `(bridged, in_cwd)` — the directories still to prepend, and those that
        are the working directory itself.
    """
    root = Path(project_dir).resolve()
    bridged: list[str] = []
    in_cwd: list[str] = []
    for directory in directories:
        if Path(directory).resolve() == root:
            in_cwd.append(directory)
        else:
            bridged.append(directory)
    return bridged, in_cwd


def _cwd_info_line(directories: list[str]) -> str:
    """Report the located directories that are lint-imports' working directory.

    Args:
        directories: Located directories equal to the project directory.

    Returns:
        An info line saying the package is found without the bridge, so a
        reader is not left wondering why nothing was prepended.
    """
    return (
        f"[Info: not added to PYTHONPATH, already lint-imports' working "
        f"directory: {', '.join(directories)} — the package is importable "
        f"from there without it]"
    )


def _skipped_info_line(skipped: dict[str, list[str]]) -> str:
    """Report the root packages that resolved into the project's site-packages.

    Args:
        skipped: Site directories keyed by the root package found in them.

    Returns:
        An info line naming each such package, so a multi-package config
        makes clear which package went unbridged and which did not.
    """
    located_in = ", ".join(
        f"{name} in {', '.join(directories)}" for name, directories in skipped.items()
    )
    return (
        f"[Info: not added to PYTHONPATH, site-packages of the project "
        f"interpreter: {located_in} — lint-imports may be reading an "
        f"installed copy of {', '.join(skipped)}]"
    )


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
    info_lines: list[str],
) -> str:
    """Assemble the final string and apply the line cap.

    Returns:
        Multi-line report text, truncated to `MAX_OUTPUT_LINES`.
    """
    lines: list[str] = list(info_lines)

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
    *,
    python_executable: str,
) -> str:
    """Run lint-imports and return an LLM-optimised structured report.

    The first non-empty line is always either an info line or the state
    header. Truncation cannot hide it.

    Unless `extra_args` already names `--cache-dir` or `--no-cache`, a
    `--cache-dir` of its own is appended: `lint_imports_binary` runs from the
    tool env, so its grimp version can differ from whatever else runs
    lint-imports against this project, and grimp's on-disk cache is validated
    by file mtime only — sharing it across grimp versions risks a stale, wrong
    verdict, while turning it off would rebuild the whole graph every call.

    Args:
        lint_imports_binary: Path to the lint-imports executable, which
            comes from mcp-tools-py's own environment.
        project_dir: Directory to run lint-imports in.
        extra_args: Additional lint-imports arguments.
        timeout_seconds: Maximum seconds to wait for lint-imports.
        python_executable: Interpreter of the project's environment, asked
            where the root package lives.  Without that answer the script
            would check whatever copy of the project happens to be installed
            next to itself.

    Returns:
        Structured report (info lines + state header + summary + raw output,
        capped), or a single `=== ERROR: ... ===` line.
    """
    cleaned_args, stripped = _strip_verbose_flags(extra_args)
    info_lines = ["[Info: stripped --verbose/-v from extra_args]"] if stripped else []

    names = _root_packages(project_dir, cleaned_args)
    env: dict[str, str] | None = None
    if names:
        located = locate_packages(python_executable, names)
        if isinstance(located, str):
            return f"=== ERROR: could not locate {', '.join(names)}: {located} ==="
        usable, skipped = located
        usable, in_cwd = _without_cwd(usable, project_dir)
        if skipped:
            info_lines.append(_skipped_info_line(skipped))
        elif not usable and not in_cwd:
            info_lines.append(
                f"[Info: nothing added to PYTHONPATH, the project interpreter "
                f"cannot import {', '.join(names)} — lint-imports may be reading "
                f"an installed copy]"
            )
        if in_cwd:
            info_lines.append(_cwd_info_line(in_cwd))
        env = _pythonpath_env(usable) if usable else None

    command = [lint_imports_binary] + _scope_cache(cleaned_args)
    result = execute_command(
        command, cwd=project_dir, timeout_seconds=timeout_seconds, env=env
    )

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
        state, summary, broken_contracts, warnings, combined, info_lines
    )
