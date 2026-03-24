"""Rope-based refactoring operations (move, rename)."""

from __future__ import annotations

import ast
import logging
import multiprocessing
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import rope.base.project  # pylint: disable=import-error
import rope.refactor.move  # pylint: disable=import-error
import rope.refactor.rename  # pylint: disable=import-error
from igittigitt import IgnoreParser  # pylint: disable=import-error
from rope.base.change import ChangeSet  # pylint: disable=import-error
from rope.base.project import Project  # pylint: disable=import-error

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
) -> tuple[Callable[[str], bool] | None, str | None]:
    """Read and parse a .gitignore file to create a matcher function.

    Args:
        gitignore_path: Path to the .gitignore file

    Returns:
        A tuple containing (matcher_function, gitignore_content), or (None, None)
        if file doesn't exist
    """
    if not gitignore_path.is_file():
        logger.info("No .gitignore file found at %s", gitignore_path)
        return None, None

    try:
        with open(gitignore_path, "r", encoding="utf-8") as f:
            gitignore_content = f.read()

        logger.info("Gitignore content: %s", gitignore_content)

        logger.info("Parsing gitignore file at %s", gitignore_path)
        parser = IgnoreParser()
        parser.parse_rule_file(gitignore_path)

        def matcher(path: str) -> bool:
            return bool(parser.match(path))

        return matcher, gitignore_content

    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Error reading/parsing gitignore: %s", str(exc))
        return None, None


def apply_gitignore_filter(
    file_paths: list[str], matcher: Callable[[str], bool] | None, project_dir: Path
) -> list[str]:
    """Filter a list of file paths using a gitignore matcher function.

    Args:
        file_paths: List of file paths to filter
        matcher: Function that takes a path and returns True if it should be ignored
        project_dir: Base directory for resolving relative paths to absolute

    Returns:
        Filtered list of file paths that are not ignored
    """
    if matcher is None:
        return file_paths

    filtered_files = []
    for file_path in file_paths:
        abs_file_path = str(project_dir / file_path)
        if not matcher(abs_file_path):
            filtered_files.append(file_path)

    logger.info(
        "Applied gitignore filtering: %s files found, %s after filtering",
        len(file_paths),
        len(filtered_files),
    )
    return filtered_files


def _build_ignored_resources(project_dir: Path) -> list[str]:
    """Build rope ignored_resources from .gitignore + hardcoded defaults."""
    patterns = list(_DEFAULT_IGNORED)

    gitignore_path = project_dir / ".gitignore"
    matcher, _ = read_gitignore_rules(gitignore_path)

    if matcher is not None:
        try:
            for entry in os.listdir(project_dir):
                abs_entry = str(project_dir / entry)
                if matcher(abs_entry) and entry not in patterns:
                    patterns.append(entry)
        except OSError as exc:
            logger.warning("Error scanning project dir for gitignore: %s", exc)

    return patterns


@contextmanager
def _with_rope_project(project_dir: Path) -> Iterator[Project]:
    """Context manager: open fresh rope Project, yield, close."""
    ignored = _build_ignored_resources(project_dir)
    project = Project(str(project_dir), ropefolder=None, ignored_resources=ignored)
    try:
        yield project
    finally:
        project.close()


def _worker(
    queue: multiprocessing.Queue,  # type: ignore[type-arg]
    func: Callable[..., str],
    args: tuple[Any, ...],
) -> None:
    """Execute *func* in a subprocess and put the result on *queue*."""
    try:
        result = func(*args)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        result = f"Error: {exc}"
    queue.put(result)


def _run_with_timeout(
    func: Callable[..., str],
    args: tuple[Any, ...],
    timeout: int,
    operation_name: str,
) -> str:
    """Run *func(*args)* in a child process with a timeout guard.

    Returns the string result on success, or an error message on timeout.
    """
    queue: multiprocessing.Queue[str] = multiprocessing.Queue()
    process = multiprocessing.Process(target=_worker, args=(queue, func, args))
    process.start()
    try:
        result: str = queue.get(timeout=timeout)
    except Exception:  # pylint: disable=broad-exception-caught  # queue.Empty
        # Timeout path
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join()
        return (
            f"Error: {operation_name} timed out after {timeout}s.\n"
            f"Timeout: {timeout}s"
        )
    else:
        process.join(timeout=10)
        if process.is_alive():
            process.kill()
            process.join()
        return result


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
        init_file.write_text("")
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
    if not dry_run:
        _ensure_parents(abs_dest, project_dir)
        if not abs_dest.exists():
            abs_dest.write_text("")

    created_for_dry_run = False

    try:
        with _with_rope_project(project_dir) as project:
            source_resource = project.get_resource(source_file)

            if not dry_run:
                dest_resource = project.get_resource(dest_file)
            else:
                if not abs_dest.exists():
                    _ensure_parents(abs_dest, project_dir)
                    abs_dest.write_text("")
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
        return f"Error moving '{symbol_name}': {exc}"


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

    return _run_with_timeout(
        _move_symbol_impl,
        (project_dir, source_file, symbol_name, dest_file, dry_run),
        timeout,
        "move_symbol",
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
    if created_for_dry_run and abs_dest.exists() and abs_dest.read_text() == "":
        abs_dest.unlink()
        _cleanup_empty_dirs(abs_dest.parent, project_dir)


def _cleanup_empty_dirs(directory: Path, stop_at: Path) -> None:
    """Remove empty __init__.py files and directories created during dry run."""
    current = directory
    while current != stop_at and current.is_relative_to(stop_at):
        init_file = current / "__init__.py"
        if init_file.exists() and init_file.read_text() == "":
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

    return _run_with_timeout(
        _rename_symbol_impl,
        (project_dir, file_path, symbol_name, new_name, dry_run),
        timeout,
        "rename_symbol",
    )


def _move_module_impl(
    project_dir: Path,
    source_module: str,
    dest_package: str,
    dry_run: bool,
) -> str:
    """Inner implementation of move_module — runs inside a subprocess."""
    abs_dest_pkg = project_dir / dest_package

    if not abs_dest_pkg.exists():
        if not dry_run:
            abs_dest_pkg.mkdir(parents=True, exist_ok=True)
            (abs_dest_pkg / "__init__.py").write_text("")
        else:
            return (
                f"Error: destination package not found: {dest_package}. "
                f"Create the package first."
            )

    try:
        with _with_rope_project(project_dir) as project:
            source_resource = project.get_resource(source_module)
            dest_resource = project.get_resource(dest_package)

            mover = rope.refactor.move.create_move(project, source_resource)
            changes = mover.get_changes(dest_resource)

            if dry_run:
                return f"[DRY RUN] move_module preview:\n{_format_changes(changes, dry_run=True)}"

            pre_existing = _collect_existing_paths(changes)
            project.do(changes)
            return f"move_module completed successfully.\n{_format_changes(changes, dry_run=False, pre_existing=pre_existing)}"

    except Exception as exc:  # pylint: disable=broad-exception-caught
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

    return _run_with_timeout(
        _move_module_impl,
        (project_dir, source_module, dest_package, dry_run),
        timeout,
        "move_module",
    )
