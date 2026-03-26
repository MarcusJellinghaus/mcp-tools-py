"""Rope-based refactoring operations (move, rename).

Public functions (rename_symbol, move_symbol, move_module) run rope in
an isolated subprocess via rope_cli.py to avoid blocking MCP server
stdio pipes.  The _*_impl helpers contain the actual rope logic and
are called directly only from the CLI entry point or tests.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import subprocess as _subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import rope.refactor.move  # pylint: disable=import-error
import rope.refactor.rename  # pylint: disable=import-error
from igittigitt import IgnoreParser  # pylint: disable=import-error
from rope.base.change import ChangeSet  # pylint: disable=import-error
from rope.base.project import Project  # pylint: disable=import-error

from mcp_tools_py.utils.subprocess_runner import execute_command

logger = logging.getLogger(__name__)

_DEFAULT_IGNORED = [
    ".ropeproject",
    "__pycache__",
    "*.pyc",
    ".git",
    "node_modules",
    ".venv",
    "venv",
    ".tox",
    "build",
    "dist",
    ".mypy_cache",
    ".pytest_cache",
    ".eggs",
    "*.egg-info",
]


# Gitignore utilities copied from p_workspace (directory_utils.py).
# TODO: Refactor into shared mcp_utils package later.


def read_gitignore_rules(
    gitignore_path: Path,
) -> Callable[[str], bool] | None:
    """Read and parse a .gitignore file to create a matcher function.

    Args:
        gitignore_path: Path to the .gitignore file

    Returns:
        A matcher function, or None if file doesn't exist.
    """
    if not gitignore_path.is_file():
        logger.debug("No .gitignore file found at %s", gitignore_path)
        return None

    try:
        logger.debug("Parsing gitignore file at %s", gitignore_path)
        parser = IgnoreParser()
        parser.parse_rule_file(gitignore_path)

        def matcher(path: str) -> bool:
            return bool(parser.match(path))

        return matcher

    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Error reading/parsing gitignore: %s", str(exc))
        return None


def _build_ignored_resources(project_dir: Path) -> list[str]:
    """Build rope ignored_resources from .gitignore + hardcoded defaults."""
    patterns = list(_DEFAULT_IGNORED)

    gitignore_path = project_dir / ".gitignore"
    matcher = read_gitignore_rules(gitignore_path)

    if matcher is not None:
        try:
            for root, dirs, _files in os.walk(project_dir):
                root_path = Path(root)
                surviving: list[str] = []
                for d in dirs:
                    if d in patterns:
                        continue  # already ignored by defaults
                    abs_dir = str(root_path / d)
                    if matcher(abs_dir):
                        try:
                            rel_path = str((root_path / d).relative_to(project_dir))
                        except ValueError:
                            continue
                        if rel_path not in patterns:
                            patterns.append(rel_path)
                    else:
                        surviving.append(d)
                dirs[:] = surviving  # only descend into non-ignored dirs
        except OSError as exc:
            logger.warning("Error scanning project dir for gitignore: %s", exc)

    # Rope compiles patterns as regex — backslashes cause invalid escapes on Windows.
    return [p.replace("\\", "/") for p in patterns]


@contextmanager
def _with_rope_project(project_dir: Path) -> Iterator[Project]:
    """Context manager: open fresh rope Project, yield, close."""
    ignored = _build_ignored_resources(project_dir)
    project = Project(str(project_dir), ropefolder=None, ignored_resources=ignored)
    try:
        yield project
    finally:
        project.close()


def _get_top_level_symbols(source: str) -> list[str]:
    """Parse source and return top-level symbol names."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    symbols: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(node.name)
        elif isinstance(node, ast.ClassDef):
            symbols.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    symbols.append(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            symbols.append(node.target.id)
    return symbols


def _find_symbol_offset(source: str, symbol_name: str) -> int | None:
    """Find the byte offset of a top-level symbol in source code."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    for node in ast.iter_child_nodes(tree):
        name: str | None = None
        col: int = 0
        line: int = 0
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
            line = node.lineno
            # col_offset points to the keyword (def/class/async), not the name.
            # Advance past the keyword to point at the identifier.
            if isinstance(node, ast.AsyncFunctionDef):
                col = node.col_offset + len("async def ")
            elif isinstance(node, ast.FunctionDef):
                col = node.col_offset + len("def ")
            else:
                col = node.col_offset + len("class ")
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == symbol_name:
                    name = target.id
                    line = target.lineno
                    col = target.col_offset
                    break
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == symbol_name:
                name = node.target.id
                line = node.target.lineno
                col = node.target.col_offset

        if name == symbol_name:
            # Convert line/col to offset
            lines = source.splitlines(keepends=True)
            offset = sum(len(lines[i]) for i in range(line - 1)) + col
            return offset

    return None


def _format_changes(
    changes: ChangeSet, dry_run: bool, pre_existing: set[str] | None = None
) -> str:
    """Format a rope ChangeSet into a human-readable report.

    Args:
        changes: The rope ChangeSet to format.
        dry_run: Whether this is a dry-run preview.
        pre_existing: Paths that existed before the operation. Used in
            non-dry-run mode to distinguish created vs modified files.
    """
    prefix = "[DRY RUN] Would modify" if dry_run else "Modified"
    create_prefix = "[DRY RUN] Would create" if dry_run else "Created"
    lines: list[str] = []
    seen: set[str] = set()

    for change in changes.changes:
        rel_path = change.resource.path
        if rel_path in seen:
            continue
        seen.add(rel_path)
        if dry_run:
            # Before project.do(), exists() is accurate.
            if change.resource.exists():
                lines.append(f"  {prefix}: {rel_path}")
            else:
                lines.append(f"  {create_prefix}: {rel_path}")
        else:
            # After project.do(), everything exists; use pre_existing set.
            if pre_existing is not None and rel_path not in pre_existing:
                lines.append(f"  {create_prefix}: {rel_path}")
            else:
                lines.append(f"  {prefix}: {rel_path}")

    return "\n".join(lines)


def _ensure_parents(dest_path: Path, project_dir: Path) -> None:
    """Create parent directories and __init__.py files for a destination."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    # Walk up from the dest parent to find package dirs that need __init__.py
    current = dest_path.parent
    while current != current.parent and current != project_dir:
        init_file = current / "__init__.py"
        if init_file.exists():
            break  # reached an existing package boundary
        init_file.write_text("", encoding="utf-8")
        current = current.parent


def _move_symbol_impl(
    project_dir: Path,
    source_file: str,
    symbol_name: str,
    dest_file: str,
    dry_run: bool,
) -> str:
    """Inner implementation of move_symbol — runs inside a subprocess."""
    abs_source = project_dir / source_file
    abs_dest = project_dir / dest_file

    source_text = abs_source.read_text(encoding="utf-8")
    offset = _find_symbol_offset(source_text, symbol_name)
    if offset is None:
        available = _get_top_level_symbols(source_text)
        available_str = ", ".join(available) if available else "(none)"
        return (
            f"Symbol '{symbol_name}' not found in {source_file}.\n"
            f"Only top-level symbols (functions, classes, variables) are supported.\n"
            f"Available top-level symbols: {available_str}"
        )

    # Check for name collision in destination
    if abs_dest.exists():
        dest_text = abs_dest.read_text(encoding="utf-8")
        dest_symbols = _get_top_level_symbols(dest_text)
        if symbol_name in dest_symbols:
            return (
                f"Name collision: '{symbol_name}' already exists in {dest_file}. "
                f"Rename the symbol in the destination first."
            )

    # Create destination file and parent dirs if needed
    created_dest = False
    if not dry_run:
        _ensure_parents(abs_dest, project_dir)
        if not abs_dest.exists():
            abs_dest.write_text("", encoding="utf-8")
            created_dest = True

    created_for_dry_run = False

    try:
        with _with_rope_project(project_dir) as project:
            source_resource = project.get_resource(source_file)

            if not dry_run:
                dest_resource = project.get_resource(dest_file)
            else:
                if not abs_dest.exists():
                    _ensure_parents(abs_dest, project_dir)
                    abs_dest.write_text("", encoding="utf-8")
                    created_for_dry_run = True
                dest_resource = project.get_resource(dest_file)

            mover = rope.refactor.move.create_move(project, source_resource, offset)
            changes = mover.get_changes(dest_resource)

            if dry_run:
                try:
                    return f"[DRY RUN] move_symbol preview:\n{_format_changes(changes, dry_run=True)}"
                finally:
                    _cleanup_created_files(abs_dest, created_for_dry_run, project_dir)

            pre_existing = _collect_existing_paths(changes)
            project.do(changes)
            return f"move_symbol completed successfully.\n{_format_changes(changes, dry_run=False, pre_existing=pre_existing)}"

    except Exception as exc:  # pylint: disable=broad-exception-caught
        _cleanup_created_files(abs_dest, created_dest, project_dir)
        return f"Error moving '{symbol_name}': {exc}"


def _run_rope_subprocess(
    operation: str,
    args_dict: dict[str, object],
    timeout: int = 120,
) -> str:
    """Run a rope operation in an isolated subprocess.

    Why subprocess isolation is required:
    The MCP server communicates via stdin/stdout JSON-RPC pipes. On Windows,
    child processes inherit these handles, and rope's full-project scan
    blocks the event loop — preventing the server from sending responses.
    Neither multiprocessing.Process nor anyio.to_thread.run_sync() solved
    this because the MCP SDK calls sync tools directly without threadpool
    offloading (mcp.server.fastmcp.utilities.func_metadata lines 92-95).

    The fix: run rope in a completely separate process with stdin=DEVNULL
    and file-based stdout, using the same execute_command pattern that
    already works for pytest/pylint/mypy in this project.
    """
    command = [
        sys.executable,
        "-m",
        "mcp_tools_py.refactoring.rope_cli",
        operation,
        json.dumps(args_dict),
    ]
    result = execute_command(
        command=command,
        cwd=str(args_dict["project_dir"]),
        timeout_seconds=timeout,
    )

    if result.timed_out:
        return f"Error: {operation} timed out after {timeout}s"

    if result.execution_error:
        return f"Error running {operation}: {result.execution_error}"

    if result.return_code != 0:
        # rope_cli outputs structured JSON errors to stdout
        try:
            output = json.loads(result.stdout)
            if "error" in output:
                return f"Error in {operation}: {output['error']}"
        except (json.JSONDecodeError, ValueError):
            pass
        stderr = result.stderr.strip()
        return f"Error running {operation} (exit {result.return_code}): {stderr}"

    # Log stderr warnings/logs for debugging (rope emits to stderr)
    if result.stderr and result.stderr.strip():
        stderr_preview = result.stderr.strip()[:200]
        logger.debug("rope subprocess stderr: %s", stderr_preview)

    # Parse JSON output from rope_cli
    try:
        output = json.loads(result.stdout)
        if "error" in output:
            return f"Error in {operation}: {output['error']}"
        return str(output["result"])
    except (json.JSONDecodeError, KeyError):
        # Fall back to raw stdout if JSON parsing fails
        return result.stdout.strip() if result.stdout.strip() else "No output from rope"


def move_symbol(
    project_dir: Path,
    source_file: str,
    symbol_name: str,
    dest_file: str,
    dry_run: bool = False,
    timeout: int = 120,
) -> str:
    """Move a top-level symbol to another module. Updates imports project-wide."""
    abs_source = project_dir / source_file
    if not abs_source.exists():
        return f"Error: file not found: {source_file}"

    return _run_rope_subprocess(
        "move_symbol",
        {
            "project_dir": str(project_dir),
            "source_file": source_file,
            "symbol_name": symbol_name,
            "dest_file": dest_file,
            "dry_run": dry_run,
        },
        timeout=timeout,
    )


def _collect_existing_paths(changes: ChangeSet) -> set[str]:
    """Return the set of resource paths that exist before project.do()."""
    return {
        change.resource.path for change in changes.changes if change.resource.exists()
    }


def _cleanup_created_files(
    abs_dest: Path, created_for_dry_run: bool, project_dir: Path
) -> None:
    """Remove temporary files created during a dry-run move_symbol."""
    if (
        created_for_dry_run
        and abs_dest.exists()
        and abs_dest.read_text(encoding="utf-8") == ""
    ):
        abs_dest.unlink()
        _cleanup_empty_dirs(abs_dest.parent, project_dir)


def _cleanup_empty_dirs(directory: Path, stop_at: Path) -> None:
    """Remove empty __init__.py files and directories created during dry run."""
    current = directory
    while current != stop_at and current.is_relative_to(stop_at):
        init_file = current / "__init__.py"
        if init_file.exists() and init_file.read_text(encoding="utf-8") == "":
            # Only remove if the directory has no other content
            contents = list(current.iterdir())
            if contents == [init_file]:
                init_file.unlink()
                current.rmdir()
            else:
                break
        current = current.parent


def _rename_symbol_impl(
    project_dir: Path,
    file_path: str,
    symbol_name: str,
    new_name: str,
    dry_run: bool,
) -> str:
    """Inner implementation of rename_symbol — runs inside a subprocess."""
    abs_path = project_dir / file_path
    source_text = abs_path.read_text(encoding="utf-8")

    offset = _find_symbol_offset(source_text, symbol_name)
    if offset is None:
        available = _get_top_level_symbols(source_text)
        available_str = ", ".join(available) if available else "(none)"
        return (
            f"Symbol '{symbol_name}' not found in {file_path}.\n"
            f"Only top-level symbols (functions, classes, variables) are supported.\n"
            f"Available top-level symbols: {available_str}"
        )

    try:
        with _with_rope_project(project_dir) as project:
            source_resource = project.get_resource(file_path)
            renamer = rope.refactor.rename.Rename(project, source_resource, offset)
            changes = renamer.get_changes(new_name)

            if dry_run:
                return f"[DRY RUN] rename_symbol preview:\n{_format_changes(changes, dry_run=True)}"

            pre_existing = _collect_existing_paths(changes)
            project.do(changes)
            return f"rename_symbol completed successfully.\n{_format_changes(changes, dry_run=False, pre_existing=pre_existing)}"

    except Exception as exc:  # pylint: disable=broad-exception-caught
        return f"Error renaming '{symbol_name}': {exc}"


def rename_symbol(
    project_dir: Path,
    file_path: str,
    symbol_name: str,
    new_name: str,
    dry_run: bool = False,
    timeout: int = 120,
) -> str:
    """Rename a symbol and update all references project-wide."""
    abs_path = project_dir / file_path
    if not abs_path.exists():
        return f"Error: file not found: {file_path}"

    return _run_rope_subprocess(
        "rename_symbol",
        {
            "project_dir": str(project_dir),
            "file_path": file_path,
            "symbol_name": symbol_name,
            "new_name": new_name,
            "dry_run": dry_run,
        },
        timeout=timeout,
    )


def _cleanup_package(abs_pkg: Path, project_dir: Path) -> None:
    """Remove a package directory created temporarily for dry-run preview."""
    init_file = abs_pkg / "__init__.py"
    if init_file.exists() and init_file.read_text(encoding="utf-8") == "":
        contents = list(abs_pkg.iterdir())
        if contents == [init_file]:
            init_file.unlink()
            abs_pkg.rmdir()
            _cleanup_empty_dirs(abs_pkg.parent, project_dir)


def _is_git_repo(project_dir: Path) -> bool:
    """Check if project_dir is inside a git repository."""
    try:
        result = _subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=str(project_dir),
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (OSError, _subprocess.TimeoutExpired):
        return False


def _is_git_tracked(project_dir: Path, file_path: str) -> bool:
    """Check if a file is tracked by git (staged or committed)."""
    try:
        result = _subprocess.run(
            ["git", "ls-files", "--error-unmatch", file_path],
            cwd=str(project_dir),
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (OSError, _subprocess.TimeoutExpired):
        return True  # assume tracked if we can't check


def _move_module_impl(
    project_dir: Path,
    source_module: str,
    dest_package: str,
    dry_run: bool,
) -> str:
    """Inner implementation of move_module — runs inside a subprocess."""
    abs_dest_pkg = project_dir / dest_package
    abs_source = project_dir / source_module
    created_pkg_for_dry_run = False

    # Rope assumes all files are under version control when a VCS is detected.
    # Inside git repos it delegates file moves to 'git mv', which fails
    # silently on untracked files (rope.base.fscommands._execute ignores
    # the return code). The result: imports are rewritten but the file
    # stays in place. Pre-check here to give an actionable error.
    # See: https://github.com/python-rope/rope/blob/master/docs/library.rst
    #      ("File System Commands" section)
    if (
        not dry_run
        and _is_git_repo(project_dir)
        and not _is_git_tracked(project_dir, source_module)
    ):
        return (
            f"Error: {source_module} is not tracked by git. "
            f"Rope uses 'git mv' to move files in git repositories and "
            f"cannot move untracked files. "
            f"Run 'git add {source_module}' first, then retry move_module."
        )

    if not abs_dest_pkg.exists():
        abs_dest_pkg.mkdir(parents=True, exist_ok=True)
        (abs_dest_pkg / "__init__.py").write_text("", encoding="utf-8")
        if dry_run:
            created_pkg_for_dry_run = True

    try:
        with _with_rope_project(project_dir) as project:
            source_resource = project.get_resource(source_module)
            dest_resource = project.get_resource(dest_package)

            mover = rope.refactor.move.create_move(project, source_resource)
            changes = mover.get_changes(dest_resource)

            if dry_run:
                try:
                    return (
                        "[DRY RUN] move_module preview:\n"
                        f"{_format_changes(changes, dry_run=True)}"
                    )
                finally:
                    if created_pkg_for_dry_run:
                        _cleanup_package(abs_dest_pkg, project_dir)

            pre_existing = _collect_existing_paths(changes)
            project.do(changes)

            # Verify the file was actually moved
            source_name = Path(source_module).name
            expected_dest = abs_dest_pkg / source_name
            warnings = ""
            if abs_source.exists() and not expected_dest.exists():
                logger.warning(
                    "move_module: rope rewrote imports but did not move " "%s to %s",
                    source_module,
                    dest_package,
                )
                warnings = (
                    f"\n  WARNING: Imports were rewritten but {source_module} "
                    f"was not moved to {dest_package}/{source_name}. "
                    f"Move the file manually and verify imports."
                )

            return (
                f"move_module completed successfully.\n"
                f"{_format_changes(changes, dry_run=False, pre_existing=pre_existing)}"
                f"{warnings}"
            )

    except Exception as exc:  # pylint: disable=broad-exception-caught
        if created_pkg_for_dry_run:
            _cleanup_package(abs_dest_pkg, project_dir)
        return f"Error moving module '{source_module}': {exc}"


def move_module(
    project_dir: Path,
    source_module: str,
    dest_package: str,
    dry_run: bool = False,
    timeout: int = 120,
) -> str:
    """Move an entire module to a new package. Updates all references."""
    abs_source = project_dir / source_module
    if not abs_source.exists():
        return f"Error: file not found: {source_module}"

    return _run_rope_subprocess(
        "move_module",
        {
            "project_dir": str(project_dir),
            "source_module": source_module,
            "dest_package": dest_package,
            "dry_run": dry_run,
        },
        timeout=timeout,
    )
