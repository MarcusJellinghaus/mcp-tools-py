"""Rope-based refactoring operations (move, rename)."""

from __future__ import annotations

import ast
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Set

import rope.base.project  # pylint: disable=import-error
import rope.refactor.move  # pylint: disable=import-error
import rope.refactor.rename  # pylint: disable=import-error
from rope.base.change import ChangeSet  # pylint: disable=import-error
from rope.base.project import Project  # pylint: disable=import-error


@contextmanager
def _with_rope_project(project_dir: Path) -> Iterator[Project]:
    """Context manager: open fresh rope Project, yield, close."""
    project = Project(str(project_dir))
    try:
        yield project
    finally:
        project.close()


def _get_top_level_symbols(source: str) -> List[str]:
    """Parse source and return top-level symbol names."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    symbols: List[str] = []
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


def _format_changes(changes: ChangeSet, dry_run: bool) -> str:
    """Format a rope ChangeSet into a human-readable report."""
    prefix = "[DRY RUN] Would modify" if dry_run else "Modified"
    create_prefix = "[DRY RUN] Would create" if dry_run else "Created"
    lines: List[str] = []
    seen: Set[str] = set()

    for change in changes.changes:
        rel_path = change.resource.path
        if rel_path in seen:
            continue
        seen.add(rel_path)
        if hasattr(change, "new_contents") and change.resource.exists():
            lines.append(f"  {prefix}: {rel_path}")
        elif not change.resource.exists():
            lines.append(f"  {create_prefix}: {rel_path}")
        else:
            lines.append(f"  {prefix}: {rel_path}")

    return "\n".join(lines)


def _ensure_parents(dest_path: Path) -> None:
    """Create parent directories and __init__.py files for a destination."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    # Walk up from the dest parent to find package dirs that need __init__.py
    current = dest_path.parent
    while current != current.parent:
        init_file = current / "__init__.py"
        if not init_file.exists() and (current / "__init__.py").parent.exists():
            # Only create __init__.py if there are .py files or it's needed
            init_file.write_text("")
        # Check if we've hit a dir that already has __init__.py
        if init_file.exists():
            break
        current = current.parent


def move_symbol(
    project_dir: Path,
    source_file: str,
    symbol_name: str,
    dest_file: str,
    dry_run: bool = False,
) -> str:
    """Move a top-level symbol to another module. Updates imports project-wide."""
    abs_source = project_dir / source_file
    abs_dest = project_dir / dest_file

    if not abs_source.exists():
        return f"Error: file not found: {source_file}"

    source_text = abs_source.read_text(encoding="utf-8")

    # Find symbol offset
    offset = _find_symbol_offset(source_text, symbol_name)
    if offset is None:
        available = _get_top_level_symbols(source_text)
        available_str = ", ".join(available) if available else "(none)"
        return (
            f"Symbol '{symbol_name}' not found in {source_file}.\n"
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
        _ensure_parents(abs_dest)
        if not abs_dest.exists():
            abs_dest.write_text("")

    try:
        with _with_rope_project(project_dir) as project:
            source_resource = project.get_resource(source_file)

            # Ensure rope can see the dest file
            if not dry_run:
                dest_resource = project.get_resource(dest_file)
            else:
                # For dry run, create temp file so rope can reference it
                if not abs_dest.exists():
                    _ensure_parents(abs_dest)
                    abs_dest.write_text("")
                    dest_resource = project.get_resource(dest_file)
                else:
                    dest_resource = project.get_resource(dest_file)

            mover = rope.refactor.move.create_move(project, source_resource, offset)
            changes = mover.get_changes(dest_resource)

            if dry_run:
                result = f"[DRY RUN] move_symbol preview:\n{_format_changes(changes, dry_run=True)}"
                # Clean up temp files created for dry run
                if abs_dest.exists() and abs_dest.read_text() == "":
                    abs_dest.unlink()
                    # Clean up empty __init__.py files created for dry run
                    _cleanup_empty_dirs(abs_dest.parent, project_dir)
                return result

            project.do(changes)
            return f"move_symbol completed successfully.\n{_format_changes(changes, dry_run=False)}"

    except Exception as exc:  # pylint: disable=broad-exception-caught
        return f"Error moving '{symbol_name}': {exc}"


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
        current = current.parent


def rename_symbol(
    project_dir: Path,
    file_path: str,
    symbol_name: str,
    new_name: str,
    dry_run: bool = False,
) -> str:
    """Rename a symbol and update all references project-wide."""
    abs_path = project_dir / file_path
    if not abs_path.exists():
        return f"Error: file not found: {file_path}"

    source_text = abs_path.read_text(encoding="utf-8")

    # Find symbol offset
    offset = _find_symbol_offset(source_text, symbol_name)
    if offset is None:
        available = _get_top_level_symbols(source_text)
        available_str = ", ".join(available) if available else "(none)"
        return (
            f"Symbol '{symbol_name}' not found in {file_path}.\n"
            f"Available top-level symbols: {available_str}"
        )

    try:
        with _with_rope_project(project_dir) as project:
            source_resource = project.get_resource(file_path)
            renamer = rope.refactor.rename.Rename(project, source_resource, offset)
            changes = renamer.get_changes(new_name)

            if dry_run:
                return f"[DRY RUN] rename_symbol preview:\n{_format_changes(changes, dry_run=True)}"

            project.do(changes)
            return f"rename_symbol completed successfully.\n{_format_changes(changes, dry_run=False)}"

    except Exception as exc:  # pylint: disable=broad-exception-caught
        return f"Error renaming '{symbol_name}': {exc}"


def move_module(
    project_dir: Path,
    source_module: str,
    dest_package: str,
    dry_run: bool = False,
) -> str:
    """Move an entire module to a new package. Updates all references."""
    abs_source = project_dir / source_module
    abs_dest_pkg = project_dir / dest_package

    if not abs_source.exists():
        return f"Error: file not found: {source_module}"

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

            project.do(changes)
            return f"move_module completed successfully.\n{_format_changes(changes, dry_run=False)}"

    except Exception as exc:  # pylint: disable=broad-exception-caught
        return f"Error moving module '{source_module}': {exc}"
